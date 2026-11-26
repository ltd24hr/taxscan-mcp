"""
F24 per una scadenza della dashboard, per chi paga da solo (home banking).

NON e' il modello F24 ufficiale: e' l'elenco, pronto da stampare o copiare, delle righe da ricopiare nel
servizio F24 della banca (codice tributo, anno, periodo, importo). Gli importi sono stime sui numeri inseriti
dall'utente. Il codice fiscale e i dati INPS non vengono conservati da TaxScan, quindi restano da scrivere a mano.
L'utente si assume la responsabilita' del pagamento (casella "ho controllato i dati"); la verifica di un
professionista e' facoltativa. Prima di mettere questa pagina davanti a clienti paganti il motore di calcolo
va fatto rivedere una volta da un commercialista.
"""
import html
from datetime import date

import dati_fisco as D
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
    """La scadenza (con le righe) della dashboard alla data indicata, ricalcolata sui numeri di oggi.
    Una scadenza gia' passata (fino a un anno fa) si ricostruisce com'era quel giorno: serve per il ravvedimento."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return None
    scheda = dati.get("_scheda") or {}
    if not S.verifica_scheda(scheda)["completa"]:
        return None
    oggi = date.today()
    quando = date.fromisoformat(data_iso)
    rif = quando if (quando < oggi and (oggi - quando).days <= 366) else oggi
    voci = S._scadenze_con_importi(S._normalizza(scheda), rif)
    for v in voci:
        if v["data"] == data_iso and v.get("righe"):
            return v
    return None


# --------------------------------------------------------------------------- ravvedimento operoso
# Per chi paga dopo la scadenza (violazioni dal 1/9/2024, D.Lgs. 87/2024): sanzione base 25%, 12,5% se si paga entro
# 90 giorni, ridotta con il ravvedimento (art. 13 D.Lgs. 472/97): entro 14 giorni 1/15 per giorno e poi 1/10; dal 15° al
# 30° giorno 1/10; dal 31° al 90° 1/9; poi 1/8 fino al termine della dichiarazione dell'anno della violazione, 1/7 fino a
# quello dell'anno dopo, oltre 1/6. Interessi al tasso legale giorno per giorno. Codici: imposta sostitutiva 8944
# (sanzione) e 1944 (interessi); bollo sulle fatture elettroniche 2525 e 2526. I contributi INPS non si ravvedono:
# l'INPS applica le sue sanzioni civili e le calcola lui.
TASSO_LEGALE = {2023: 5.0, 2024: 2.5, 2025: 2.0, 2026: 1.6}   # % annua; dal 2027 si usa l'ultimo noto finche' non si aggiorna
CODICI_RAVVEDIMENTO = {"1790": ("8944", "1944"), "1791": ("8944", "1944"), "1792": ("8944", "1944"),
                       "2521": ("2525", "2526"), "2522": ("2525", "2526"), "2523": ("2525", "2526"),
                       "2524": ("2525", "2526")}


def _tasso(anno: int) -> float:
    if anno in TASSO_LEGALE:
        return TASSO_LEGALE[anno]
    return TASSO_LEGALE[max(TASSO_LEGALE)] if anno > max(TASSO_LEGALE) else TASSO_LEGALE[min(TASSO_LEGALE)]


def sanzione_ridotta(scadenza: date, pagamento: date) -> tuple[float, str]:
    """Percentuale di sanzione da ravvedimento (sull'imposta non versata) e la fascia in parole."""
    g = (pagamento - scadenza).days
    if g <= 0:
        return 0.0, ""
    if g <= 14:
        return 12.5 / 15 * g / 10, f"{g} {'giorno' if g == 1 else 'giorni'} di ritardo: 0,083% al giorno"
    if g <= 30:
        return 12.5 / 10, "dal 15° al 30° giorno di ritardo"
    if g <= 90:
        return 12.5 / 9, "dal 31° al 90° giorno di ritardo"
    if pagamento <= date(scadenza.year + 1, 10, 31):
        return 25 / 8, "oltre 90 giorni, entro la dichiarazione dell'anno"
    if pagamento <= date(scadenza.year + 2, 10, 31):
        return 25 / 7, "entro la dichiarazione dell'anno successivo"
    return 25 / 6, "oltre la dichiarazione dell'anno successivo"


def interessi_legali(importo: float, scadenza: date, pagamento: date) -> float:
    """Interessi al tasso legale dal giorno dopo la scadenza al giorno del pagamento, anno per anno."""
    tot, d = 0.0, scadenza
    while d < pagamento:
        fine = min(pagamento, date(d.year + 1, 1, 1))
        tot += importo * _tasso(d.year) / 100 * (fine - d).days / 365
        d = fine
    return tot


def ravvedimento(v: dict, pagamento: date) -> dict:
    """Righe in piu' per pagare in ritardo una scadenza: sanzione ridotta e interessi per ogni tributo dell'Erario."""
    scad = date.fromisoformat(v["data"])
    pct, fascia = sanzione_ridotta(scad, pagamento)
    if pct <= 0:
        return {"righe": [], "giorni": 0}
    sanz, inter = {}, {}
    for r in v.get("righe") or []:
        cod = CODICI_RAVVEDIMENTO.get(str(r.get("codice")))
        if not cod or r.get("sezione") != "ERARIO":
            continue
        chiave = (cod, r["anno_riferimento"])
        sanz[chiave] = sanz.get(chiave, 0.0) + r["importo"] * pct / 100
        inter[chiave] = inter.get(chiave, 0.0) + interessi_legali(r["importo"], scad, pagamento)
    righe = []
    for (cod, anno), x in sanz.items():
        bollo = cod[0] == "2525"
        if round(x, 2) >= 0.01:
            righe.append({"sezione": "ERARIO", "codice": cod[0], "anno_riferimento": anno, "rateazione": "", "importo": round(x, 2),
                          "descrizione": ("Bollo fatture" if bollo else "Imposta sostitutiva") + " - sanzione da ravvedimento", "ravv": True})
        y = inter[(cod, anno)]
        if round(y, 2) >= 0.01:
            righe.append({"sezione": "ERARIO", "codice": cod[1], "anno_riferimento": anno, "rateazione": "", "importo": round(y, 2),
                          "descrizione": ("Bollo fatture" if bollo else "Imposta sostitutiva") + " - interessi da ravvedimento", "ravv": True})
    inps = any(r.get("sezione") == "INPS" for r in v.get("righe") or [])
    return {"righe": righe, "giorni": (pagamento - scad).days, "percentuale": round(pct, 4), "fascia": fascia, "inps": inps}


def testo_semplice(v: dict) -> str:
    """Le righe in testo, da incollare in una mail o in un messaggio al commercialista."""
    righe = [f"Righe F24 - scadenza {_data_it(v['data'])} (stime: controlla prima di pagare)"]
    for r in v["righe"]:
        if r["sezione"] == "ERARIO":
            righe.append(f"ERARIO - codice tributo {r['codice']}, rateazione {r.get('rateazione') or '-'}, "
                         f"anno {r['anno_riferimento']}, importo a debito {_eur(r['importo'])} EUR")
        else:
            righe.append(f"INPS - causale {r['codice']}, periodo {r['periodo_da']}-{r['periodo_a']}, "
                         f"importo a debito {_eur(r['importo'])} EUR")
    righe.append(f"Totale: {_eur(sum(r['importo'] for r in v['righe']))} EUR")
    return "\n".join(righe)


def pagina(v: dict, id_dashboard: str, pagamento: date | None = None) -> str:
    h = html.escape
    oggi = date.today()
    scad = date.fromisoformat(v["data"])
    if pagamento is None and scad < oggi:
        pagamento = oggi
    rav = ravvedimento(v, pagamento) if pagamento and pagamento > scad else {"righe": [], "giorni": 0}
    if rav["righe"]:
        v = dict(v, righe=list(v["righe"]) + rav["righe"])
    erario = [r for r in v["righe"] if r["sezione"] == "ERARIO"]
    inps = [r for r in v["righe"] if r["sezione"] == "INPS"]
    totale = sum(r["importo"] for r in v["righe"])

    def tab_erario():
        if not erario:
            return ""
        righe = "".join(
            f"<tr><td><b>{h(r['codice'])}</b><span>{h(r['descrizione'])}</span></td><td>{h(r.get('rateazione') or '–')}</td>"
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

    if rav["righe"] or rav.get("giorni"):
        tot_r = sum(r["importo"] for r in rav["righe"])
        box_ravv = (f"<div class='ravv'><h2>Paghi in ritardo: ravvedimento operoso</h2>"
                    f"<p>Se paghi il <b>{h(_data_it(pagamento.isoformat()))}</b>, cioè {rav['giorni']} "
                    f"{'giorno' if rav['giorni'] == 1 else 'giorni'} dopo la scadenza, alle righe si aggiungono "
                    f"<b>{_eur(tot_r)} €</b> di sanzione ridotta ({str(rav['percentuale']).replace('.', ',')}% dell'imposta, "
                    f"{h(rav['fascia'])}) e interessi al tasso legale. Le trovi qui sotto con i loro codici tributo.</p>"
                    + ("<p class='nota att'>Per i <b>contributi INPS</b> il ravvedimento non si usa: paga le righe INPS così "
                       "come sono e l'INPS calcolerà le sanzioni civili per il ritardo; le trovi poi nel tuo cassetto previdenziale.</p>"
                       if rav.get("inps") else "")
                    + "<p class='nota'>Più presto paghi, meno spendi: la sanzione sale con i giorni di ritardo.</p></div>")
    else:
        box_ravv = ""
    box_ravv += (f"<details class='noprint ritardo'{' open' if scad < oggi else ''}><summary>"
                 f"{'Cambia la data in cui paghi' if scad < oggi else 'Pagherai dopo la scadenza? Calcola sanzione e interessi'}"
                 f"</summary><form method='get'><input type='hidden' name='data' value='{h(v['data'])}'>"
                 f"<label>Giorno in cui paghi <input type='date' name='pagamento' min='{h(v['data'])}' "
                 f"value='{h((pagamento or oggi).isoformat())}' required></label> <button>Ricalcola</button></form></details>")
    note_l = list(v.get("note_f24", []))
    diff = v["importo"] - totale
    if diff > 1:
        note_l.append(f"Nella tua situazione questa scadenza è di {_eur(v['importo'])} €: i restanti {_eur(diff)} € "
                      "sono la parte che non possiamo trasformare in righe di F24 e che va calcolata a parte (nel tuo cassetto previdenziale INPS o con un commercialista).")
    note = "".join(f"<p class='nota att'>{h(n)}</p>" for n in note_l)
    testo = testo_semplice(v)
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>F24 - TaxScan</title>
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
ul.chk{{padding-left:20px;margin:8px 0}} ul.chk li{{margin:4px 0;font-size:14px}}
label.ok{{display:flex;gap:10px;align-items:flex-start;margin:16px 0 0;padding:12px 14px;background:var(--card);border:1px solid var(--line);cursor:pointer}}
label.ok input{{flex:none;width:20px;height:20px;margin-top:2px;accent-color:var(--accent)}}
button[disabled]{{opacity:.45;cursor:not-allowed}}
.ravv{{margin:14px 0;padding:12px 14px;border-left:4px solid #c62f3a;background:var(--card)}} .ravv h2{{margin-top:0}}
details.ritardo{{margin:14px 0;padding:12px 14px;background:var(--card);border:1px solid var(--line)}}
details.ritardo summary{{cursor:pointer;font-weight:700;color:var(--accent)}}
details.ritardo form{{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin-top:10px}}
details.ritardo input{{font:inherit;padding:9px 10px;border:1px solid var(--line);margin-left:6px}}
@media print{{.azioni,.noprint,label.ok{{display:none}} body{{background:#fff;color:#000}} table{{border-color:#999}} .tot{{background:#fff;color:#000;border:2px solid #000}}}}
</style></head><body>
<p class="noprint"><a href="/d/{h(id_dashboard)}" style="color:var(--accent)">← Torna alla tua situazione</a></p>
<span class="bozza">Stime · controlla prima di pagare</span>
<h1>F24 del {h(_data_it(v['data']))}</h1>
<p class="sub">{h(v['etichetta'])} · importi stimati sui numeri che hai inserito</p>
<div class="avviso"><b>Stai preparando il pagamento da solo.</b> Questa pagina elenca le righe da ricopiare nel servizio F24
della tua banca: non è il modello ufficiale. Gli importi sono <b>stime</b> e la responsabilità di ciò che paghi è tua.
Prima di pagare controlla questi punti:
<ul class="chk">
<li>i numeri della tua situazione sono aggiornati (incassi di quest'anno e dell'anno scorso);</li>
<li>hai già pagato acconti o rate? Qui li consideriamo solo se li hai indicati; i <b>crediti da compensare</b> non sono considerati;</li>
<li>il tuo <b>codice fiscale</b> e i dati INPS (sede, matricola) li scrivi tu: non li conserviamo.</li>
</ul>
Un dubbio? Puoi far controllare queste righe a un professionista, quando vuoi: c'è la
<a href="{h(D.CONTATTI['consulenza_gratuita'])}" style="color:var(--accent)">consulenza gratuita</a> di LTD24.</div>
{box_ravv}
{tab_erario()}{tab_inps()}{note}
<div class="tot"><span>Totale a debito</span><span>{_eur(totale)} €</span></div>
<label class="ok noprint"><input type="checkbox" id="ho"><span>Ho controllato i dati e mi prendo la responsabilità del pagamento.</span></label>
<div class="azioni noprint">
<button id="copia" disabled>Copia le righe</button>
<button class="sec" id="stampa" disabled>Stampa o salva in PDF</button>
</div>
<p class="noprint"><a class="b sec" href="/d/{h(id_dashboard)}/rate?data={h(v['data'])}" style="background:#efac35;color:#122452;border:0">Voglio rateizzare: scopri come</a></p>
<h2>Come si paga, in home banking</h2>
<ol>
<li>Entra nell'area <b>pagamenti</b> della tua banca e cerca <b>F24</b>. Se ce ne sono più di uno, scegli quello che permette sia la sezione <b>Erario</b> sia la sezione <b>INPS</b> (di solito si chiama F24 ordinario).</li>
<li>Scrivi il tuo codice fiscale e ricopia le righe qui sopra, nello stesso ordine.</li>
<li>Controlla il totale e paga <b>entro la data indicata</b>. Se cade di sabato, domenica o in un giorno festivo, slitta al primo giorno lavorativo.</li>
<li>Conserva la ricevuta di pagamento (quietanza): ti servirà per la dichiarazione. Se salta la data, esiste il ravvedimento operoso (sanzione ridotta più interessi): meglio regolarizzare presto.</li>
</ol>
<p class="nota">Il pagamento F24 si può anche fare con il servizio web dell'Agenzia delle Entrate. TaxScan non conserva il tuo codice fiscale né i dati di pagamento: questa pagina è ricostruita ogni volta dai numeri della tua situazione.</p>
<textarea id="t" style="position:absolute;left:-9999px">{h(testo)}</textarea>
<script>
const ho=document.getElementById('ho'),cp=document.getElementById('copia'),st=document.getElementById('stampa');
ho.onchange=()=>{{cp.disabled=st.disabled=!ho.checked}};
st.onclick=()=>window.print();
cp.onclick=async()=>{{const t=document.getElementById('t').value;
try{{await navigator.clipboard.writeText(t)}}catch(e){{const a=document.getElementById('t');a.select();document.execCommand('copy')}}
cp.textContent='Copiato!'}};
</script></body></html>"""
