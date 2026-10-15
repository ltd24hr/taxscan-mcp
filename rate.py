"""Pagina "Voglio rateizzare": come pagare a rate saldo e primo acconto (stime, con le regole generali).

Regole generali usate (fonti: Agenzia delle Entrate e guide fiscali; da ricontrollare ogni anno):
- si rateizzano saldo e PRIMO acconto delle imposte sui redditi; il secondo (o unico) acconto di novembre NO;
- fino a 6 rate (5 se si parte dal 31 luglio), l'ultima a novembre;
- dalla seconda rata si aggiunge l'interesse dello 0,33% al mese;
- pagando dal 1 al 30/31 luglio il versamento si maggiora dello 0,40%;
- per chi ha la partita IVA le rate successive alla prima cadono il 16 del mese.
Gli importi sono stime: non sostituiscono il calcolo ufficiale.
"""
import html
from datetime import date

import f24 as F
import dati_fisco as D

_CODICI_RATEIZZABILI = {"1792", "1790"}  # imposta sostitutiva: saldo e primo acconto
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
         "settembre", "ottobre", "novembre", "dicembre"]
LINK_AE = "https://www.agenziaentrate.gov.it/portale/web/guest/rateizzazione-delle-somme-dovute-in-dichiarazione"


def rateizzabile(data_iso: str) -> bool:
    """Solo le scadenze di giugno/luglio (saldo + primo acconto)."""
    try:
        return date.fromisoformat(data_iso).month in (6, 7)
    except ValueError:
        return False


def piano(importo: float, data_iso: str, n_rate: int) -> list[dict]:
    """Rate (stima): importo uguale per la quota capitale + interesse crescente, date indicative."""
    d0 = date.fromisoformat(data_iso)
    luglio = d0.month == 7
    base = importo * (1.004 if luglio else 1.0)
    max_rate = 5 if luglio else 6
    n = max(2, min(n_rate, max_rate))
    quota = base / n
    out = []
    for k in range(1, n + 1):
        if k == 1:
            d, pct = d0, 0.0
        elif luglio:
            d = date(d0.year, 7 + (k - 1), 16)
            pct = 0.33 * (k - 2)
        else:
            d = date(d0.year, 6 + (k - 1), 16)
            pct = 0.18 + 0.33 * (k - 2)
        out.append({"n": k, "data": d, "pct": round(pct, 2), "capitale": quota,
                    "interessi": quota * pct / 100, "totale": quota * (1 + pct / 100)})
    return out


def pagina(v: dict, id_dashboard: str, n_rate: int = 6) -> str:
    h = html.escape
    eur = F._eur
    riga_ok = [r for r in v["righe"] if r["sezione"] == "ERARIO" and str(r["codice"]) in _CODICI_RATEIZZABILI]
    importo = sum(r["importo"] for r in riga_ok)
    ok = rateizzabile(v["data"]) and importo > 0
    luglio = date.fromisoformat(v["data"]).month == 7
    corpo = ""
    if ok:
        max_rate = 5 if luglio else 6
        n = max(2, min(n_rate, max_rate))
        p = piano(importo, v["data"], n)
        tot = sum(x["totale"] for x in p)
        opz = "".join(f'<a class="b{"" if k == n else " sec"}" href="?data={h(v["data"])}&rate={k}">{k} rate</a>'
                      for k in range(2, max_rate + 1))
        righe = "".join(
            f"<tr><td>{x['n']}ª</td><td>{x['data'].day} {_MESI[x['data'].month - 1]}</td>"
            f"<td class='n'>{eur(x['capitale'])}</td><td class='n'>{x['pct']:.2f}%</td><td class='n'><b>{eur(x['totale'])}</b></td></tr>"
            for x in p)
        extra = f" (in più {eur(tot - importo)} € tra interessi{' e maggiorazione 0,40%' if luglio else ''})"
        corpo = f"""<h2>Quante rate?</h2><div class="azioni">{opz}</div>
<table><thead><tr><th>Rata</th><th>Data indicativa</th><th class='n'>Quota</th><th class='n'>Interessi</th><th class='n'>Da pagare (€)</th></tr></thead><tbody>{righe}</tbody></table>
<div class="tot"><span>Totale pagando a rate</span><span>{eur(tot)} €</span></div>
<p class="nota">Rispetto a pagare tutto subito ({eur(importo)} €){h(extra)}. Stima sulla sola imposta sostitutiva: i contributi INPS hanno regole proprie.
Le date indicative possono slittare al primo giorno lavorativo utile.</p>"""
    else:
        corpo = ("<p class='avviso'>Questa scadenza <b>non si può pagare a rate</b> (per esempio il secondo acconto di novembre), "
                 "oppure non ci sono righe di imposta sostitutiva rateizzabili. A rate si possono pagare il <b>saldo</b> e il "
                 "<b>primo acconto</b> di giugno/luglio.</p>")
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Pagare a rate - TaxScan</title>
<style>
@font-face{{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}}
@font-face{{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}}
@font-face{{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}}
:root{{--bg:#eef2f8;--card:#fff;--ink:#122452;--ink2:#3d4a73;--line:#d8e2ed;--accent:#4355cc;--warn:#efac35;
--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,sans-serif}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0a1330;--card:#122452;--ink:#fff;--ink2:#c9d3ec;--line:#25397a;--accent:#5566dd}}}}
*{{box-sizing:border-box;margin:0}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-txt);padding:16px 16px 48px;max-width:760px;margin:0 auto}}
h1,h2{{font-family:var(--f-tit)}} h1{{font-size:24px;margin:8px 0 2px}} h2{{font-size:17px;margin:22px 0 8px}}
.bozza{{display:inline-block;background:var(--warn);color:#122452;font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding:4px 10px}}
.sub{{color:var(--ink2)}} .avviso{{margin:14px 0;padding:12px 14px;border-left:4px solid var(--warn);background:var(--card)}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line)}}
th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}} th{{font-size:12px;color:var(--ink2);font-weight:500}}
.n{{text-align:right;white-space:nowrap}}
.tot{{display:flex;justify-content:space-between;margin-top:16px;padding:14px;background:var(--ink);color:var(--bg);font-weight:700}}
@media (prefers-color-scheme:dark){{.tot{{background:#05d5c8;color:#122452}}}}
.nota{{font-size:13px;color:var(--ink2);margin-top:8px}}
.azioni{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 16px}}
a.b{{font:inherit;font-weight:700;padding:10px 16px;background:var(--accent);color:#fff;text-decoration:none;border:1px solid var(--accent)}}
a.sec{{background:transparent;color:var(--accent)}} ol{{padding-left:20px}} li{{margin:6px 0}}
</style></head><body>
<p><a href="/d/{h(id_dashboard)}" style="color:var(--accent)">← Torna alla tua situazione</a></p>
<span class="bozza">Stime · controlla prima di scegliere</span>
<h1>Voglio pagare a rate</h1>
<p class="sub">Scadenza del {h(F._data_it(v['data']))} · {h(v['etichetta'])}</p>
{corpo}
<h2>Come si fa</h2>
<ol>
<li>Decidi <b>in quante rate</b> (sopra vedi quanto costano) e paga <b>la prima rata entro la scadenza</b> con l'F24 della banca.</li>
<li>Nella riga dell'F24, nel campo <b>«rateazione»</b>, scrivi il numero di questa rata e il totale delle rate (formato <b>NNRR</b>: per esempio la 1ª di 6 è <b>0106</b>, la 2ª di 6 è <b>0206</b>).</li>
<li>Dalla seconda rata aggiungi gli <b>interessi di rateazione</b> con il loro codice tributo (lo trovi nelle istruzioni dell'F24 sul sito dell'Agenzia delle Entrate).</li>
<li>Paga ogni rata <b>entro la sua data</b>: se salti una rata si perde il vantaggio e si applicano sanzioni.</li>
</ol>
<div class="avviso"><b>Solo il saldo e il primo acconto</b> si pagano a rate; il secondo acconto di novembre no. Questa pagina è una stima con le regole generali:
controlla sempre date e interessi sul <a href="{LINK_AE}" style="color:var(--accent)" target="_blank" rel="noopener">sito dell'Agenzia delle Entrate</a>.
Se preferisci farti guidare, c'è la <a href="{h(D.CONTATTI['consulenza_gratuita'])}" style="color:var(--accent)">consulenza gratuita</a> di LTD24.</div>
</body></html>"""
