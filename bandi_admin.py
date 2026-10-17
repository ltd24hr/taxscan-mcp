"""Pagina riservata per approvare i bandi: li inserisci tu, li vedono gli utenti giusti in dashboard e,
se vuoi, partono per email (alle 8:55, a chi ha accettato le email con spunti). Chiave: ?chiave=ADMIN_TOKEN."""
import html
from datetime import date, timedelta

import agevolazioni
import db

_e = html.escape


def _destinatari(b: dict, utenti: list[dict]) -> int:
    n = 0
    for u in utenti:
        sc = u["scheda"] if isinstance(u["scheda"], dict) else {}
        if db._incentivo_pertinente(b.get("codici_ateco", ""), b.get("regioni", ""),
                                    str(sc.get("codice_ateco") or ""), str(sc.get("regione") or "")):
            n += 1
    return n


def valida(campi: dict) -> tuple[dict | None, str]:
    titolo = (campi.get("titolo") or "").strip()[:200]
    descr = (campi.get("descrizione") or "").strip()[:600]
    url = (campi.get("url_fonte") or "").strip()
    if not titolo or not descr:
        return None, "Titolo e descrizione sono obbligatori."
    if not url.startswith("https://"):
        return None, "Il link ufficiale deve cominciare con https://"
    scad = (campi.get("scadenza") or "").strip()
    if scad:
        try:
            if date.fromisoformat(scad) < date.today():
                return None, "La scadenza è già passata."
        except ValueError:
            return None, "Scadenza non valida."
    ambito = campi.get("ambito") if campi.get("ambito") in ("nazionale", "regionale", "locale") else "nazionale"
    regioni = ",".join(r for r in campi.get("regioni_lista", []) if r in agevolazioni._PROVINCE)
    if ambito != "nazionale" and not regioni:
        return None, "Per un bando regionale o locale scegli almeno una regione."
    if ambito == "nazionale":
        regioni = ""
    codici = ",".join(x.strip() for x in (campi.get("codici_ateco") or "").split(",") if x.strip())[:200]
    return {"titolo": titolo, "descrizione": descr, "requisiti": (campi.get("requisiti") or "").strip()[:400],
            "codici_ateco": codici, "url_fonte": url, "ambito": ambito, "regioni": regioni,
            "scadenza": scad or None}, ""


def pagina(chiave: str, messaggio: str = "") -> str:
    bandi = db.lista_incentivi_admin()
    try:
        utenti = db.utenti_per_bandi()
    except Exception:
        utenti = []
    oggi = date.today().isoformat()
    righe = ""
    for b in bandi:
        scaduto = bool(b["scadenza"] and b["scadenza"] < oggi)
        ver = (b.get("verificato_il") or "")[:10]
        non_riconfermato = bool(b["attivo"] and b.get("origine") == "auto" and ver and ver < (date.today() - timedelta(days=30)).isoformat())
        stato = ("disattivato" if not b["attivo"] else ("scaduto" if scaduto else ("non riconfermato da 30 giorni (nascosto)" if non_riconfermato
                 else (f"in arrivo dal {b['apre_il']}" if b.get("apre_il") and b["apre_il"] > oggi else "attivo"))))
        mail = (("email già richiesta" if b["notifica_il"] else "solo dashboard") + (" · trovato dalla ricerca automatica" if b.get("origine") == "auto" else "")
                + (f" · verificato il {ver}" if ver else "")
                + (f" · {len(b.get('criteri') or [])} domande requisiti" if b["attivo"] else "")
                + (" · email: parte quando si apre" if b["attivo"] and b.get("apre_il") and b["apre_il"] > oggi else ""))
        dest = _destinatari(b, utenti) if b["attivo"] and not scaduto else 0
        azioni = ""
        if b["attivo"] and not scaduto:
            if not b["notifica_il"] and not (b.get("apre_il") and b["apre_il"] > oggi):
                azioni += (f"<button name='azione' value='mail:{b['id']}'>Manda anche per email "
                           f"(a circa {dest} utenti)</button> ")
            azioni += f"<button name='azione' value='off:{b['id']}'>Disattiva</button>"
        righe += (f"<tr><td><b>{_e(b['titolo'])}</b><br>{_e(b['descrizione'])}"
                  f"<br><a href='{_e(b['url_fonte'] or '')}' target='_blank' rel='noopener'>link</a></td>"
                  f"<td>{_e(b['ambito'])}<br>{_e(b['regioni'] or 'tutta Italia')}<br>ATECO: {_e(b['codici_ateco'] or 'tutti')}</td>"
                  f"<td>{_e('a sportello (da verificare)' if b.get('sportello') else (b['scadenza'] or '—'))}</td><td>{stato}<br><small>{mail}</small></td><td>{azioni}</td></tr>")
    regioni = "".join(f"<label class='r'><input type='checkbox' name='regione' value='{_e(r)}'>{_e(r)}</label>"
                      for r in sorted(agevolazioni._PROVINCE))
    try:
        ult = db.ultima_esecuzione_bandi()
    except Exception:
        ult = None
    if ult:
        e = ult["esito"] or {}
        err = "".join(f"<li>{_e(x)}</li>" for x in (e.get("errori") or []))
        sc = "".join(f"<li>{_e(x.get('zona'))}: {_e(x.get('titolo'))} — <i>{_e(x.get('motivo'))}</i></li>"
                     for x in (e.get("scartati") or [])[:15])
        riquadro = (f"<div class='ok' style='background:#fff'><b>Ultima ricerca:</b> {_e(ult['quando'][:16].replace('T', ' '))} (ora UTC) · "
                    f"zone: {_e(', '.join(e.get('zone') or []))} · trovati {e.get('trovati', 0)} · pubblicati {len(e.get('nuovi') or [])}"
                    + (f"<br>Domande requisiti create in questa ricerca: {e['criteri_generati']}" if e.get("criteri_generati") is not None else "")
                    + (f"<br>Ricontrollati: {e['ricontrollati'].get('confermati', 0)} ancora aperti, {e['ricontrollati'].get('chiusi', 0)} chiusi (spenti), {e['ricontrollati'].get('incerti', 0)} incerti" if e.get("ricontrollati") else "")
                    + (f"<br><b>Errori:</b><ul>{err}</ul>" if err else "")
                    + (f"<br><b>Scartati:</b><ul>{sc}</ul>" if sc else "") + "</div>")
    else:
        riquadro = "<div class='ok' style='background:#fff'><b>Ultima ricerca:</b> nessuna ricerca registrata (ancora in corso, oppure mai lanciata dopo l'ultimo aggiornamento).</div>"
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Bandi - admin</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:16px;color:#122452;background:#eef2f8}}
h1{{font-size:24px}} table{{width:100%;border-collapse:collapse;background:#fff}} td,th{{padding:8px;border-bottom:1px solid #d8e2ed;text-align:left;vertical-align:top;font-size:14px}}
form.n{{background:#fff;padding:14px;margin:14px 0}} label{{display:block;font-weight:700;margin-top:10px}} input[type=text],input[type=date],textarea,select{{width:100%;padding:8px;font:inherit;border:1px solid #bcc7dc}}
.r{{display:inline-block;font-weight:400;margin:2px 10px 2px 0}} button{{font:inherit;font-weight:700;padding:8px 12px;border:0;background:#4355cc;color:#fff;cursor:pointer;margin:2px 0}}
.ok{{background:#e8f7ee;padding:10px;margin:10px 0}} small{{color:#3d4a73}}</style></head><body>
<h1>Bandi</h1>
<p><b>La ricerca è automatica</b> (una volta a settimana): i bandi trovati si pubblicano da soli dopo i controlli e, se pertinenti, partono per email. Qui puoi solo <b>spegnerne uno</b> che non ti convince. Il modulo in fondo serve solo per aggiungere un bando a mano, se vuoi.</p>
{f"<div class='ok'>{_e(messaggio)}</div>" if messaggio else ""}
{riquadro}
<p>Qui inserisci solo bandi che hai controllato sul sito ufficiale. Compaiono subito in dashboard agli utenti giusti (settore e regione);
se vuoi, partono anche per email alle 8:55 successive, solo a chi ha accettato le email con spunti.</p>
<table><thead><tr><th>Bando</th><th>Dove / settore</th><th>Scadenza</th><th>Stato</th><th></th></tr></thead><tbody>{righe or "<tr><td colspan=5>Nessun bando inserito.</td></tr>"}</tbody></table>
<form method="post" class="n"><input type="hidden" name="chiave" value="{_e(chiave)}">
<h2>Aggiungi un bando</h2>
<label>Titolo<input type="text" name="titolo" maxlength="200" required></label>
<label>Descrizione (1–2 frasi, chiara)<textarea name="descrizione" rows="3" maxlength="600" required></textarea></label>
<label>Per chi è (requisiti, breve)<input type="text" name="requisiti" maxlength="400"></label>
<label>Link al testo ufficiale (https://…)<input type="text" name="url_fonte" required></label>
<label>Ambito<select name="ambito"><option value="nazionale">Nazionale (tutta Italia)</option><option value="regionale">Regionale</option><option value="locale">Locale</option></select></label>
<label>Regioni (solo se regionale o locale)</label><div>{regioni}</div>
<label>Codici ATECO (prefissi separati da virgola, es. 43,62; vuoto = tutti i settori)<input type="text" name="codici_ateco"></label>
<label>Scadenza (facoltativa; dopo questa data il bando sparisce)<input type="date" name="scadenza"></label>
<label class="r"><input type="checkbox" name="mail" value="1"> Manda anche per email</label><br>
<button name="azione" value="nuovo">Salva il bando</button></form>
</body></html>"""
