"""
Bozza di F24 per una scadenza della dashboard.

NON e' un modello valido per il pagamento: e' un riepilogo, pronto da stampare o copiare, di quali righe
compilare (codice tributo, anno, periodo, importo). Il codice fiscale non viene conservato da TaxScan,
quindi resta da scrivere a mano. Il commercialista controlla prima del pagamento.
"""
import html
from datetime import date

import db
import scheda as S

_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
         "ottobre", "novembre", "dicembre"]


def _eur(x) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_it(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {_MESI[d.month - 1]} {d.year}"


def trova(id_dashboard: str, data_iso: str) -> dict | None:
    """La scadenza (con le righe) della dashboard alla data indicata, ricalcolata sui numeri di oggi."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return None
    scheda = dati.get("_scheda") or {}
    if not S.verifica_scheda(scheda)["completa"]:
        return None
    voci = S._scadenze_con_importi(S._normalizza(scheda), date.today())
    for v in voci:
        if v["data"] == data_iso and v.get("righe"):
            return v
    return None


def testo_semplice(v: dict) -> str:
    """Le righe in testo, da incollare in una mail o in un messaggio al commercialista."""
    righe = [f"Bozza F24 - scadenza {_data_it(v['data'])} (da controllare prima di pagare)"]
    for r in v["righe"]:
        if r["sezione"] == "ERARIO":
            righe.append(f"ERARIO - codice tributo {r['codice']}, rateazione {r['rateazione']}, "
                         f"anno {r['anno_riferimento']}, importo a debito {_eur(r['importo'])} EUR")
        else:
            righe.append(f"INPS - causale {r['codice']}, periodo {r['periodo_da']}-{r['periodo_a']}, "
                         f"importo a debito {_eur(r['importo'])} EUR")
    righe.append(f"Totale: {_eur(sum(r['importo'] for r in v['righe']))} EUR")
    return "\n".join(righe)


def pagina(v: dict, id_dashboard: str) -> str:
    h = html.escape
    erario = [r for r in v["righe"] if r["sezione"] == "ERARIO"]
    inps = [r for r in v["righe"] if r["sezione"] == "INPS"]
    totale = sum(r["importo"] for r in v["righe"])

    def tab_erario():
        if not erario:
            return ""
        righe = "".join(
            f"<tr><td><b>{h(r['codice'])}</b><span>{h(r['descrizione'])}</span></td><td>{h(r['rateazione'])}</td>"
            f"<td>{r['anno_riferimento']}</td><td class='n'>{_eur(r['importo'])}</td></tr>" for r in erario)
        return ("<h2>Sezione Erario</h2><table><thead><tr><th>Codice tributo</th><th>Rateazione / mese</th>"
                "<th>Anno di riferimento</th><th class='n'>Importi a debito (€)</th></tr></thead><tbody>"
                + righe + "</tbody></table>")

    def tab_inps():
        if not inps:
            return ""
        righe = "".join(
            f"<tr><td><b>{h(r['codice'])}</b><span>{h(r['descrizione'])}</span></td>"
            f"<td>{h(r['periodo_da'])} – {h(r['periodo_a'])}</td><td class='n'>{_eur(r['importo'])}</td></tr>"
            for r in inps)
        return ("<h2>Sezione INPS</h2><table><thead><tr><th>Causale contributo</th><th>Periodo di riferimento</th>"
                "<th class='n'>Importi a debito (€)</th></tr></thead><tbody>" + righe + "</tbody></table>"
                "<p class='nota'>Altri campi della sezione INPS: <b>codice sede</b> e <b>matricola INPS / codice INPS / "
                "filiale azienda</b>. Per la gestione separata la matricola è il tuo codice fiscale; per artigiani e "
                "commercianti è la tua posizione INPS. Non li conserviamo noi: li trovi sul tuo cassetto "
                "previdenziale o te li dice il commercialista.</p>")

    note_l = list(v.get("note_f24", []))
    diff = v["importo"] - totale
    if diff > 1:
        note_l.append(f"Nella tua situazione questa scadenza è di {_eur(v['importo'])} €: i restanti {_eur(diff)} € "
                      "sono la parte che non possiamo trasformare in righe di F24 e che va calcolata dal commercialista.")
    note = "".join(f"<p class='nota att'>{h(n)}</p>" for n in note_l)
    testo = testo_semplice(v)
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Bozza F24 - TaxScan</title>
<style>
@font-face{{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}}
@font-face{{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}}
@font-face{{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}}
@font-face{{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}}
:root{{--bg:#eef2f8;--card:#fff;--ink:#122452;--ink2:#3d4a73;--line:#d8e2ed;--accent:#4355cc;--warn:#efac35;
--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0a1330;--card:#122452;--ink:#fff;--ink2:#c9d3ec;--line:#25397a;--accent:#5566dd}}}}
*{{box-sizing:border-box;margin:0}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-txt);padding:16px 16px 48px;max-width:760px;margin:0 auto}}
h1,h2{{font-family:var(--f-tit)}} h1{{font-size:24px;margin:8px 0 2px}} h2{{font-size:17px;margin:22px 0 8px}}
.bozza{{display:inline-block;background:var(--warn);color:#122452;font-weight:700;font-size:12px;letter-spacing:.08em;
text-transform:uppercase;padding:4px 10px}}
.sub{{color:var(--ink2)}}
.avviso{{margin:14px 0;padding:12px 14px;border-left:4px solid var(--warn);background:var(--card)}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line)}}
th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}}
th{{font-size:12px;color:var(--ink2);font-weight:500}}
td span{{display:block;font-size:12px;color:var(--ink2)}}
.n{{text-align:right;white-space:nowrap}}
.tot{{display:flex;justify-content:space-between;margin-top:16px;padding:14px;background:var(--ink);color:var(--bg);font-weight:700}}
@media (prefers-color-scheme:dark){{.tot{{background:#05d5c8;color:#122452}}}}
.nota{{font-size:13px;color:var(--ink2);margin-top:8px}} .att{{border-left:4px solid var(--warn);padding-left:10px}}
.azioni{{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}}
button,a.b{{font:inherit;font-weight:700;border:0;padding:12px 16px;background:var(--accent);color:#fff;cursor:pointer;text-decoration:none;display:inline-block}}
button.sec,a.sec{{background:transparent;color:var(--accent);border:1px solid var(--accent)}}
ol{{padding-left:20px}} li{{margin:6px 0}}
@media print{{.azioni,.noprint{{display:none}} body{{background:#fff;color:#000}} table{{border-color:#999}} .tot{{background:#fff;color:#000;border:2px solid #000}}}}
</style></head><body>
<p class="noprint"><a href="/d/{h(id_dashboard)}" style="color:var(--accent)">← Torna alla tua situazione</a></p>
<span class="bozza">Bozza · non valida per il pagamento</span>
<h1>F24 del {h(_data_it(v['data']))}</h1>
<p class="sub">{h(v['etichetta'])} · importi stimati sui numeri che hai inserito</p>
<div class="avviso"><b>Prima di pagare, falla controllare dal tuo commercialista.</b> Questa pagina elenca le righe da
compilare; non è il modello F24 e non si può usare per pagare. Gli importi sono stime.</div>
{tab_erario()}{tab_inps()}{note}
<div class="tot"><span>Totale a debito</span><span>{_eur(totale)} €</span></div>
<div class="azioni noprint">
<button onclick="window.print()">Stampa o salva in PDF</button>
<button class="sec" id="copia">Copia il testo per il commercialista</button>
</div>
<h2>Come si paga</h2>
<ol>
<li>Mandala al tuo commercialista, che controlla gli importi e prepara l'F24 vero.</li>
<li>Oppure ricopia le righe nel servizio F24 della tua banca (home banking) o nel servizio F24 web dell'Agenzia delle Entrate, aggiungendo il tuo codice fiscale.</li>
<li>Paga entro la data indicata. Se cade di sabato, domenica o in un giorno festivo, slitta al primo giorno lavorativo.</li>
</ol>
<p class="nota">TaxScan non conserva il tuo codice fiscale né i dati di pagamento: questa pagina è ricostruita ogni volta dai numeri della tua situazione.</p>
<textarea id="t" style="position:absolute;left:-9999px">{h(testo)}</textarea>
<script>
document.getElementById('copia').onclick=async()=>{{const t=document.getElementById('t').value;
try{{await navigator.clipboard.writeText(t)}}catch(e){{const a=document.getElementById('t');a.select();document.execCommand('copy')}}
document.getElementById('copia').textContent='Copiato!'}};
</script></body></html>"""
