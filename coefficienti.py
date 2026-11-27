"""Pagina pubblica /coefficienti: la tabella dei coefficienti di redditivita' del forfettario con ricerca per codice
ATECO o per mestiere, e il calendario generale delle scadenze. Contenuto statico, utile anche per Google."""
import html
import json

import dati_fisco as D
import privacy

# esempi in parole semplici per ogni gruppo (stesso ordine di D.GRUPPI_COEFFICIENTE, poi il residuale)
ESEMPI = {
    "Intermediari del commercio": "agente di commercio, procacciatore d'affari, rappresentante",
    "Commercio ambulante di alimentari e bevande": "ambulante di frutta e verdura, food truck che vende prodotti alimentari",
    "Commercio ambulante di altri prodotti": "ambulante di abbigliamento, bigiotteria, oggetti per la casa",
    "Industrie alimentari e delle bevande": "panificio, pasticceria di produzione, birrificio artigianale",
    "Commercio all'ingrosso e al dettaglio": "negozio, e-commerce, vendita su Amazon, Etsy o Vinted come attività",
    "Servizi di alloggio e ristorazione": "bar, ristorante, B&B, affittacamere, catering",
    "Costruzioni e attività immobiliari": "muratore, imbianchino, idraulico, elettricista, piastrellista, agente immobiliare",
    "Attività professionali, scientifiche, tecniche, sanitarie, di istruzione, servizi finanziari e assicurativi":
        "consulente, avvocato, architetto, ingegnere, grafico, fotografo, traduttore, social media manager, "
        "formatore, insegnante, psicologo, fisioterapista, infermiere, agente assicurativo",
    "residuale": "sviluppatore software, parrucchiere, estetista, tatuatore, artista, musicista, istruttore sportivo, "
                 "autotrasportatore, rider, riparazioni",
}

BOLLO = [("31-05", "Imposta di bollo sulle fatture elettroniche del 1° trimestre (se sotto 5.000 € si può rimandare)"),
         ("30-09", "Imposta di bollo sulle fatture elettroniche del 2° trimestre"),
         ("30-11", "Imposta di bollo sulle fatture elettroniche del 3° trimestre"),
         ("28-02", "Imposta di bollo sulle fatture elettroniche del 4° trimestre dell'anno prima")]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
        "novembre", "dicembre"]


def _e(x) -> str:
    return html.escape(str(x or ""), quote=True)


def _gruppi() -> list[dict]:
    out = [{"prefissi": p, "coeff": round(c * 100), "nome": g, "esempi": ESEMPI.get(g, "")}
           for p, c, g in D.GRUPPI_COEFFICIENTE]
    out.append({"prefissi": [], "coeff": round(D.COEFFICIENTE_RESIDUALE[0] * 100), "nome": D.COEFFICIENTE_RESIDUALE[1],
                "esempi": ESEMPI["residuale"]})
    return out


def pagina() -> str:
    base = privacy.pagina()
    head = base.split("</style>", 1)[0]
    gruppi = _gruppi()
    righe = "".join(
        f'<tr data-i="{i}"><td><b>{g["coeff"]}%</b></td><td><b>{_e(g["nome"])}</b>'
        f'<small>{_e(", ".join(g["prefissi"]) and "Codici che iniziano con " + ", ".join(g["prefissi"]))}</small>'
        f'<small>Per esempio: {_e(g["esempi"])}</small></td></tr>'
        for i, g in enumerate(gruppi))
    scad = [(d, x["descrizione"]) for x in D.SCADENZE for d in [x["data"]]] + BOLLO
    scad.sort(key=lambda t: (int(t[0][3:]), int(t[0][:2])))
    cal = "".join(f'<li><b>{int(d[:2])} {MESI[int(d[3:]) - 1]}</b><span>{_e(t)}</span></li>' for d, t in scad)
    stile = """
.cerca{display:flex;gap:8px;margin:10px 0 6px}
.cerca input{font:inherit;font-size:16px;padding:11px 13px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);flex:1;min-width:0}
#esito{min-height:24px;font-weight:600;margin:6px 0 10px}
table{width:100%;border-collapse:collapse;font-size:15px}
td{padding:12px 8px;border-top:1px solid var(--line);vertical-align:top}
td:first-child{width:64px;font-size:20px;color:var(--accent)}
td small{display:block;color:var(--mute);margin-top:3px;font-size:13.5px}
tr.on td{background:var(--bg)}
tr.via{display:none}
ul.cal{list-style:none;padding:0;margin:0}
ul.cal li{display:grid;grid-template-columns:120px 1fr;gap:10px;padding:10px 0;border-top:1px solid var(--line)}
@media(max-width:520px){ul.cal li{grid-template-columns:1fr;gap:2px}}
.cta{display:inline-block;margin-top:10px;font-weight:700;padding:12px 18px;border-radius:12px;background:var(--accent);color:#fff;text-decoration:none}
"""
    corpo = f"""</style>
<meta name="description" content="Tabella dei coefficienti di redditività del regime forfettario per codice ATECO e per mestiere, con ricerca, e calendario delle scadenze fiscali dei forfettari.">
</head><body><main>
<a href="/" style="text-decoration:none"><div class="logo">Tax<span>Scan</span></div></a>
<h1>Coefficienti del forfettario e scadenze</h1>
<p class="s">Nel regime forfettario le tasse non si pagano su tutto quello che incassi, ma su una parte: il coefficiente di redditività, che dipende da cosa fai. Cerca il tuo codice ATECO o il tuo mestiere.</p>
<div class="card">
<h2>Trova il tuo coefficiente</h2>
<div class="cerca"><input id="q" type="search" placeholder="Codice ATECO (es. 62.01) o mestiere (es. grafico)" aria-label="Codice ATECO o mestiere" autocomplete="off"></div>
<p id="esito" role="status"></p>
<table><tbody id="t">{righe}</tbody></table>
<p class="s">Esempio: con un coefficiente del 78% e 30.000 € incassati, le tasse e i contributi si calcolano su 23.400 €. Il resto (22%) è considerato spese, anche se non ne hai avute.</p>
<p class="s">Nelle divisioni 46 e 47 convivono coefficienti diversi e dal 2025 vale la nuova classificazione ATECO: in caso di dubbio conta il codice da cui la tua partita IVA è stata riclassificata. Se fai più attività di gruppi diversi, ognuna ha il suo coefficiente sui suoi incassi. Fonte: Allegato 4 della Legge 190/2014.</p>
<a class="cta" href="/#simula">Calcola quanto paghi</a>
</div>
<div class="card">
<h2>Le scadenze dell'anno</h2>
<p class="s">Le date principali per chi è nel forfettario. Quando una scadenza cade di sabato o di domenica, slitta al primo giorno lavorativo. Non tutte riguardano tutti: dipende dalla tua previdenza.</p>
<ul class="cal">{cal}</ul>
<p class="s">TaxScan ti manda un promemoria prima di ognuna, con l'importo e l'F24 già preparato. <a href="/">Scopri come</a>.</p>
</div>
<p class="s">Informazioni generali, aggiornate a novembre 2026: non sostituiscono il parere di un professionista.</p>
</main>
<script>
(function(){{var G={json.dumps(gruppi, ensure_ascii=False)},q=document.getElementById('q'),es=document.getElementById('esito'),R=document.querySelectorAll('#t tr');
function norm(s){{return s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'')}}
function gruppoCodice(c){{c=c.replace(/[^\\d.]/g,'');if(c.length<2)return -1;var best=-1,len=-1;G.forEach(function(g,i){{g.prefissi.forEach(function(p){{if(c.indexOf(p)===0&&p.length>len){{best=i;len=p.length}}}})}});return best<0?G.length-1:best}}
q.oninput=function(){{var v=q.value.trim(),hit=[];R.forEach(function(r){{r.classList.remove('on','via')}});es.textContent='';if(!v)return;
if(/^\\d/.test(v)){{var i=gruppoCodice(v);if(i<0)return;hit=[i];es.textContent='Codice '+v+': coefficiente '+G[i].coeff+'%.'}}
else{{var w=norm(v);G.forEach(function(g,i){{if(norm(g.nome+' '+g.esempi).indexOf(w)>=0)hit.push(i)}});
es.textContent=hit.length?(hit.length===1?'Coefficiente: '+G[hit[0]].coeff+'%.':'Possibili gruppi: '+hit.map(function(i){{return G[i].coeff+'%'}}).join(', ')+'.'):'Non lo trovo tra gli esempi: prova con il codice ATECO, o con un\\'altra parola.'}}
if(hit.length)R.forEach(function(r,i){{r.classList.add(hit.indexOf(i)>=0?'on':'via')}})}};}})();
</script>
</body></html>"""
    return head.replace("<title>Privacy - TaxScan</title>",
                        "<title>Coefficienti del forfettario e scadenze - TaxScan</title>") + stile + corpo
