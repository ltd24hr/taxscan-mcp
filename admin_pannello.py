"""
TaxScan - pannello amministratore (/admin).

Una pagina privata per capire chi usa TaxScan e da dove arriva:
  - numeri chiave: iscritti, nuovi negli ultimi 7 / 30 giorni, attivi negli ultimi 7 giorni, Fatture in Cloud collegati
  - grafico giornaliero (ultimi 30 giorni): visite alla home, colloqui aperti, iscrizioni
  - imbuto: visita -> colloquio aperto -> colloquio completato -> iscritto
  - da dove arrivano (utm_source o sito di provenienza, registrati sulla home come evento 'visita')
  - dove si fermano nel colloquio (ultima domanda vista)
  - elenco iscritti con ultima attività, codice ATECO, comune/regione, FIC, email disattivate, feedback
  - esportazione CSV degli iscritti

Accesso: chiave = ADMIN_TOKEN (la stessa di /admin/feedback e /admin/bandi). Si inserisce una volta nel modulo
di accesso; il server imposta un cookie HttpOnly valido 12 ore, così la chiave non resta nell'indirizzo
(cronologia, inoltri, screenshot). Per compatibilità funziona anche ?chiave=... come le altre pagine admin.
"""
import csv
import hashlib
import hmac
import html as _html
import io
import json
import os
from datetime import date, datetime, timedelta, timezone

import db

COOKIE = "ts_admin"
DURATA_COOKIE = 12 * 3600


def _token() -> str:
    return os.environ.get("ADMIN_TOKEN", "")


def chiave_ok(chiave: str) -> bool:
    t = _token()
    return bool(t) and bool(chiave) and hmac.compare_digest(chiave, t)


def valore_cookie() -> str:
    """Il cookie non contiene la chiave: contiene una sua impronta, che cambia se cambia ADMIN_TOKEN."""
    t = _token()
    return hmac.new(t.encode(), b"taxscan-admin-v1", hashlib.sha256).hexdigest() if t else ""


def cookie_ok(valore: str) -> bool:
    atteso = valore_cookie()
    return bool(atteso) and bool(valore) and hmac.compare_digest(valore, atteso)


# --------------------------------------------------------------------- Provenienza delle visite

_BOT = ("bot", "crawl", "spider", "slurp", "preview", "monitor", "uptime", "curl", "python-requests", "headless")


def fonte_visita(query: dict, referer: str, user_agent: str) -> str | None:
    """Da dove arriva chi apre la home: utm_source se c'è, altrimenti il sito di provenienza, altrimenti 'diretto'.
    None per i bot (non vanno contati)."""
    ua = (user_agent or "").lower()
    if not ua or any(b in ua for b in _BOT):
        return None
    utm = (query.get("utm_source") or query.get("ref") or "").strip().lower()[:40]
    if utm:
        return utm
    ref = (referer or "").strip().lower()
    if ref:
        from urllib.parse import urlparse
        host = urlparse(ref).netloc.replace("www.", "")
        if host and "taxscan" not in host and "onrender.com" not in host:
            for nome in ("google", "bing", "facebook", "instagram", "linkedin", "youtube", "tiktok", "reddit", "chatgpt",
                         "claude", "perplexity", "t.co", "whatsapp", "telegram"):
                if nome in host:
                    return "x" if nome == "t.co" else nome
            return host[:40]
    return "diretto"


# --------------------------------------------------------------------- Dati

def raccogli(giorni: int = 30) -> dict:
    """Tutto quello che serve alla pagina, in poche query."""
    giorni = max(1, min(int(giorni or 30), 365))
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*),
                       count(*) FILTER (WHERE creato_il > now() - interval '7 days'),
                       count(*) FILTER (WHERE creato_il > now() - interval '30 days'),
                       count(*) FILTER (WHERE dashboard_id IS NOT NULL)
                FROM utenti""")
            tot, nuovi7, nuovi30, con_dash = cur.fetchone()
            cur.execute("SELECT count(*) FROM fic_collegamenti")
            fic_n = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM email_opt_out")
            opt_out = cur.fetchone()[0]
            # attivi = utenti con almeno un evento (per email o per id dashboard) negli ultimi 7 giorni
            cur.execute("""
                SELECT count(DISTINCT u.email) FROM utenti u
                JOIN eventi e ON e.riferimento IN (u.email, u.dashboard_id)
                WHERE e.creato_il > now() - interval '7 days'""")
            attivi7 = cur.fetchone()[0]

            cur.execute("""
                SELECT d::date,
                       (SELECT count(*) FROM eventi WHERE tipo = 'visita' AND creato_il::date = d::date),
                       (SELECT count(*) FROM eventi WHERE tipo IN ('web_aperto', 'chat_avvio') AND creato_il::date = d::date),
                       (SELECT count(*) FROM utenti WHERE creato_il::date = d::date)
                FROM generate_series(current_date - (%s - 1), current_date, interval '1 day') d
                ORDER BY d""", (giorni,))
            serie = [{"giorno": r[0].isoformat(), "visite": r[1], "colloqui": r[2], "iscritti": r[3]}
                     for r in cur.fetchall()]

            cur.execute("""
                SELECT tipo, count(DISTINCT coalesce(riferimento, id::text)) FROM eventi
                WHERE creato_il > now() - (%s || ' days')::interval
                  AND tipo IN ('visita', 'web_aperto', 'chat_avvio', 'web_completato', 'chat_quadro')
                GROUP BY tipo""", (giorni,))
            per_tipo = dict(cur.fetchall())
            cur.execute("SELECT count(*) FROM utenti WHERE creato_il > now() - (%s || ' days')::interval", (giorni,))
            iscritti_periodo = cur.fetchone()[0]

            cur.execute("""
                SELECT coalesce(dettaglio->>'fonte', 'sconosciuta'), count(*) FROM eventi
                WHERE tipo = 'visita' AND creato_il > now() - (%s || ' days')::interval
                GROUP BY 1 ORDER BY 2 DESC LIMIT 12""", (giorni,))
            fonti = [{"fonte": f, "visite": n} for f, n in cur.fetchall()]

            cur.execute("""
                SELECT u.email, u.creato_il, u.scheda, u.dashboard_id,
                       (SELECT max(e.creato_il) FROM eventi e WHERE e.riferimento IN (u.email, u.dashboard_id)),
                       (SELECT count(*) FROM eventi e WHERE e.riferimento IN (u.email, u.dashboard_id)),
                       EXISTS (SELECT 1 FROM fic_collegamenti f WHERE f.email = u.email),
                       EXISTS (SELECT 1 FROM email_opt_out o WHERE o.email = u.email),
                       (SELECT consiglia FROM feedback fb WHERE fb.email = u.email)
                FROM utenti u ORDER BY u.creato_il DESC LIMIT 500""")
            utenti = []
            for r in cur.fetchall():
                s = r[2] or {}
                utenti.append({
                    "email": r[0], "iscritto_il": r[1].isoformat() if r[1] else "",
                    "ateco": str(s.get("codice_ateco") or ""), "attivita": str(s.get("descrizione_attivita") or "")[:60],
                    "comune": str(s.get("comune") or ""), "regione": str(s.get("regione") or ""),
                    "dashboard": bool(r[3]), "ultima_attivita": r[4].isoformat() if r[4] else "",
                    "eventi": r[5] or 0, "fic": bool(r[6]), "email_off": bool(r[7]), "consiglia": r[8] or ""})
    stats = db.statistiche_eventi(giorni)
    return {
        "giorni": giorni, "generato_il": datetime.now(timezone.utc).isoformat(),
        "kpi": {"iscritti": tot, "nuovi7": nuovi7, "nuovi30": nuovi30, "attivi7": attivi7,
                "con_dashboard": con_dash, "fic": fic_n, "email_off": opt_out},
        "serie": serie,
        "imbuto": [
            {"fase": "Visite alla home", "n": per_tipo.get("visita", 0)},
            {"fase": "Colloquio aperto", "n": per_tipo.get("web_aperto", 0) + per_tipo.get("chat_avvio", 0)},
            {"fase": "Colloquio completato", "n": per_tipo.get("web_completato", 0) + per_tipo.get("chat_quadro", 0)},
            {"fase": "Iscritti", "n": iscritti_periodo},
        ],
        "fonti": fonti,
        "abbandoni": stats.get("colloqui_web_fermi_per_domanda", [])[:8],
        "utenti": utenti,
    }


def csv_utenti(dati: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["email", "iscritto_il", "ultima_attivita", "eventi", "ateco", "attivita", "comune", "regione",
                "dashboard", "fatture_in_cloud", "email_disattivate", "consiglia"])
    for u in dati["utenti"]:
        w.writerow([u["email"], u["iscritto_il"][:16], u["ultima_attivita"][:16], u["eventi"], u["ateco"], u["attivita"],
                    u["comune"], u["regione"], "si" if u["dashboard"] else "no", "si" if u["fic"] else "no",
                    "si" if u["email_off"] else "no", u["consiglia"]])
    return "﻿" + buf.getvalue()


# --------------------------------------------------------------------- Pagina

def _e(x) -> str:
    return _html.escape(str(x if x is not None else ""))


def _quando(iso: str) -> str:
    if not iso:
        return "—"
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    diff = datetime.now(timezone.utc) - t
    if diff < timedelta(hours=1):
        return f"{max(1, int(diff.total_seconds() // 60))} min fa"
    if diff < timedelta(days=1):
        return f"{int(diff.total_seconds() // 3600)} h fa"
    if diff < timedelta(days=30):
        return f"{diff.days} g fa"
    return t.strftime("%d/%m/%Y")


_CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1c19;--quiet:#6b6a64;--line:#e6e3da;--acc:#1f6f5c;--acc2:#d08a2c;--acc3:#7a5cc2}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--card:#1f1f1c;--ink:#ecebe6;--quiet:#a3a19a;--line:#33322e;--acc:#4fb79b;--acc2:#e3a54e;--acc3:#a68be6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:0 0 12px}.sub{color:var(--quiet);font-size:13px;margin:0 0 20px}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.k{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}.k b{display:block;font-size:26px;font-variant-numeric:tabular-nums}
.k span{color:var(--quiet);font-size:12.5px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px;overflow:hidden}
.due{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:760px){.due{grid-template-columns:1fr}}
.leg{display:flex;gap:16px;font-size:12.5px;color:var(--quiet);margin-bottom:8px;flex-wrap:wrap}.leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.bar{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13.5px}.bar .l{width:170px;flex:none}.bar .t{flex:1;background:var(--line);border-radius:6px;height:20px;overflow:hidden}
.bar .f{height:100%;background:var(--acc);border-radius:6px}.bar .n{width:90px;text-align:right;font-variant-numeric:tabular-nums;color:var(--quiet)}
table{width:100%;border-collapse:collapse;font-size:13.5px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--quiet);font-weight:600;font-size:12.5px;position:sticky;top:0;background:var(--card)}
.wrap{overflow-x:auto;max-height:620px}.pill{display:inline-block;font-size:11.5px;padding:1px 7px;border-radius:99px;border:1px solid var(--line);color:var(--quiet)}
.ok{color:var(--acc);border-color:var(--acc)}.ko{color:#b4483a;border-color:#b4483a}
.tool{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
input,select,button,a.btn{font:inherit;padding:7px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);text-decoration:none}
button,a.btn{cursor:pointer}a.btn:hover,button:hover{border-color:var(--acc)}
.vuoto{color:var(--quiet);font-size:13.5px}
"""


def _grafico(serie: list[dict]) -> str:
    """Barre giornaliere (colloqui) + linea (visite) + punti (iscritti), SVG senza librerie."""
    if not serie:
        return "<p class='vuoto'>Nessun dato.</p>"
    W, H, sx, sy, gb = 1040, 220, 40, 16, 28
    n = len(serie)
    massimo = max([1] + [max(p["visite"], p["colloqui"], p["iscritti"]) for p in serie])
    passo = (W - sx - 8) / n
    y = lambda v: sy + (H - sy - gb) * (1 - v / massimo)
    parti = [f"<svg viewBox='0 0 {W} {H}' width='100%' role='img' aria-label='Andamento giornaliero'>"]
    for i in range(5):
        v = massimo * i / 4
        yy = y(v)
        parti.append(f"<line x1='{sx}' x2='{W - 8}' y1='{yy:.1f}' y2='{yy:.1f}' stroke='var(--line)'/>"
                     f"<text x='{sx - 6}' y='{yy + 4:.1f}' text-anchor='end' font-size='11' fill='var(--quiet)'>{round(v)}</text>")
    linea = []
    for i, p in enumerate(serie):
        x0 = sx + i * passo
        if p["colloqui"]:
            parti.append(f"<rect x='{x0 + passo * 0.18:.1f}' y='{y(p['colloqui']):.1f}' width='{passo * 0.64:.1f}' "
                         f"height='{y(0) - y(p['colloqui']):.1f}' rx='2' fill='var(--acc)' opacity='.55'>"
                         f"<title>{p['giorno']}: {p['colloqui']} colloqui</title></rect>")
        linea.append(f"{x0 + passo / 2:.1f},{y(p['visite']):.1f}")
        if p["iscritti"]:
            parti.append(f"<circle cx='{x0 + passo / 2:.1f}' cy='{y(p['iscritti']):.1f}' r='4' fill='var(--acc3)'>"
                         f"<title>{p['giorno']}: {p['iscritti']} iscritti</title></circle>")
        if i % max(1, n // 8) == 0 or i == n - 1:
            g = p["giorno"]
            parti.append(f"<text x='{x0 + passo / 2:.1f}' y='{H - 8}' text-anchor='middle' font-size='11' fill='var(--quiet)'>"
                         f"{g[8:10]}/{g[5:7]}</text>")
    parti.append(f"<polyline points='{' '.join(linea)}' fill='none' stroke='var(--acc2)' stroke-width='2'/>")
    parti.append("</svg>")
    return "".join(parti)


def _barre(righe: list[tuple[str, int]], massimo: int | None = None, con_quota: bool = False) -> str:
    if not righe:
        return "<p class='vuoto'>Ancora nessun dato in questo periodo.</p>"
    m = massimo or max(1, max(n for _, n in righe))
    primo = righe[0][1] or 1
    out = []
    for etichetta, n in righe:
        quota = f" · {round(100 * n / primo)}%" if con_quota and primo else ""
        out.append(f"<div class='bar'><span class='l'>{_e(etichetta)}</span><span class='t'>"
                   f"<span class='f' style='width:{100 * n / m:.1f}%'></span></span><span class='n'>{n}{quota}</span></div>")
    return "".join(out)


def pagina(dati: dict) -> str:
    k = dati["kpi"]
    kpi = "".join(f"<div class='k'><b>{v}</b><span>{_e(t)}</span></div>" for t, v in (
        ("Iscritti totali", k["iscritti"]), ("Nuovi ultimi 7 giorni", k["nuovi7"]), ("Nuovi ultimi 30 giorni", k["nuovi30"]),
        ("Attivi ultimi 7 giorni", k["attivi7"]), ("Fatture in Cloud collegati", k["fic"]), ("Email disattivate", k["email_off"])))
    righe = []
    for u in dati["utenti"]:
        luogo = " · ".join(x for x in (u["comune"], u["regione"]) if x)
        badge = ""
        if u["fic"]:
            badge += "<span class='pill ok'>FIC</span> "
        if u["email_off"]:
            badge += "<span class='pill ko'>no email</span> "
        if u["consiglia"]:
            badge += f"<span class='pill'>consiglia: {_e(u['consiglia'])}</span>"
        righe.append(
            f"<tr data-q='{_e((u['email'] + ' ' + u['ateco'] + ' ' + u['attivita'] + ' ' + luogo).lower())}'>"
            f"<td><a href='mailto:{_e(u['email'])}'>{_e(u['email'])}</a></td>"
            f"<td title='{_e(u['iscritto_il'][:16])}'>{_quando(u['iscritto_il'])}</td>"
            f"<td title='{_e(u['ultima_attivita'][:16])}'>{_quando(u['ultima_attivita'])}</td>"
            f"<td>{u['eventi']}</td><td>{_e(u['ateco'])}<div class='sub' style='margin:0'>{_e(u['attivita'])}</div></td>"
            f"<td>{_e(luogo) or '—'}</td><td>{badge}</td></tr>")
    tabella = ("<div class='wrap'><table id='t'><thead><tr><th>Email</th><th>Iscritto</th><th>Ultima attività</th>"
               "<th>Azioni</th><th>ATECO / attività</th><th>Luogo</th><th></th></tr></thead><tbody>"
               + "".join(righe) + "</tbody></table></div>") if righe else "<p class='vuoto'>Nessun iscritto ancora.</p>"
    imbuto = _barre([(r["fase"], r["n"]) for r in dati["imbuto"]], con_quota=True)
    fonti = _barre([(r["fonte"], r["visite"]) for r in dati["fonti"]])
    abbandoni = _barre([(r["ultima_domanda_vista"] or "?", r["colloqui"]) for r in dati["abbandoni"]])
    g = dati["giorni"]
    scelte = "".join(f"<option value='{d}'{' selected' if d == g else ''}>Ultimi {d} giorni</option>" for d in (7, 30, 90, 365))
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>TaxScan · Pannello</title><style>{_CSS}</style></head><body><main>
<h1>TaxScan · Pannello amministratore</h1>
<p class="sub">Aggiornato {datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M')} ·
<a href="/admin/esci">Esci</a></p>
<div class="kpi">{kpi}</div>
<div class="card"><div class="tool"><h2 style="margin:0;flex:1">Andamento giornaliero</h2>
<form method="get" action="/admin"><select name="giorni" onchange="this.form.submit()">{scelte}</select></form></div>
<div class="leg"><span><i style="background:var(--acc2)"></i>Visite alla home</span><span><i style="background:var(--acc);opacity:.55"></i>Colloqui aperti</span>
<span><i style="background:var(--acc3);border-radius:50%"></i>Iscrizioni</span></div>{_grafico(dati['serie'])}</div>
<div class="due"><div class="card"><h2>Imbuto · ultimi {g} giorni</h2>{imbuto}
<p class="sub" style="margin:10px 0 0">La percentuale è rispetto alla prima fase.</p></div>
<div class="card"><h2>Da dove arrivano · ultimi {g} giorni</h2>{fonti}
<p class="sub" style="margin:10px 0 0">Usa link con <code>?utm_source=nome</code> per ogni canale.</p></div></div>
<div class="card"><h2>Dove si fermano nel colloquio</h2>{abbandoni}</div>
<div class="card"><div class="tool"><h2 style="margin:0;flex:1">Iscritti ({len(dati['utenti'])})</h2>
<input id="q" type="search" placeholder="Cerca email, ATECO, comune…" oninput="filtra()">
<a class="btn" href="/admin/utenti.csv">Scarica CSV</a></div>{tabella}</div>
</main><script>
function filtra(){{var q=document.getElementById('q').value.trim().toLowerCase();
document.querySelectorAll('#t tbody tr').forEach(function(r){{r.style.display=!q||r.dataset.q.indexOf(q)>=0?'':'none'}})}}
</script></body></html>"""


def pagina_accesso(errore: str = "") -> str:
    msg = f"<p style='color:#b4483a'>{_e(errore)}</p>" if errore else ""
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>TaxScan · Accesso</title><style>{_CSS}</style></head><body><main style="max-width:380px;padding-top:80px">
<h1>Pannello TaxScan</h1><p class="sub">Inserisci la chiave amministratore.</p>{msg}
<form method="post" action="/admin" style="display:flex;gap:8px"><input type="password" name="chiave" autocomplete="current-password"
style="flex:1" required autofocus><button>Entra</button></form></main></body></html>"""


def registra(mcp, evento) -> None:
    """Aggiunge le rotte /admin, /admin/utenti.csv, /admin/esci al server."""
    from starlette.responses import HTMLResponse, RedirectResponse, Response

    intest = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex", "X-Frame-Options": "DENY",
              "Referrer-Policy": "no-referrer"}

    def _autorizzato(request) -> bool:
        return cookie_ok(request.cookies.get(COOKIE, "")) or chiave_ok(request.query_params.get("chiave", ""))

    def _con_cookie(resp):
        resp.set_cookie(COOKIE, valore_cookie(), max_age=DURATA_COOKIE, httponly=True, secure=True,
                        samesite="strict", path="/admin")
        return resp

    @mcp.custom_route("/admin", methods=["GET", "POST"])
    async def admin_home(request):
        import asyncio
        from urllib.parse import parse_qs
        if request.method == "POST":
            corpo = parse_qs((await request.body()).decode("utf-8", "ignore"))
            if chiave_ok((corpo.get("chiave") or [""])[0]):
                return _con_cookie(RedirectResponse("/admin", status_code=303))
            await asyncio.sleep(1.5)  # rallenta i tentativi a caso
            return HTMLResponse(pagina_accesso("Chiave non valida."), status_code=403, headers=intest)
        if not _autorizzato(request):
            return HTMLResponse(pagina_accesso(), headers=intest)
        try:
            giorni = int(request.query_params.get("giorni", "30"))
        except ValueError:
            giorni = 30
        try:
            dati = await asyncio.to_thread(raccogli, giorni)
        except Exception as e:
            return HTMLResponse(f"<p>Non riesco a leggere i dati: {_e(e)}</p>", status_code=500, headers=intest)
        resp = HTMLResponse(pagina(dati), headers=intest)
        # chi entra con ?chiave= riceve il cookie e la volta dopo non serve più la chiave nell'indirizzo
        return _con_cookie(resp) if request.query_params.get("chiave") else resp

    @mcp.custom_route("/admin/utenti.csv", methods=["GET"])
    async def admin_csv(request):
        import asyncio
        if not _autorizzato(request):
            return Response("non autorizzato", status_code=403)
        dati = await asyncio.to_thread(raccogli, 30)
        nome = f"taxscan-iscritti-{date.today().isoformat()}.csv"
        return Response(csv_utenti(dati), media_type="text/csv; charset=utf-8",
                        headers={**intest, "Content-Disposition": f"attachment; filename={nome}"})

    @mcp.custom_route("/admin/esci", methods=["GET"])
    async def admin_esci(request):
        resp = RedirectResponse("/admin", status_code=303)
        resp.delete_cookie(COOKIE, path="/admin")
        return resp
