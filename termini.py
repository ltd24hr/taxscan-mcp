"""
TaxScan - termini e condizioni d'uso (pagina /termini).

I dati del titolare sono gli stessi della privacy (variabili d'ambiente su Render):
  TITOLARE_NOME, TITOLARE_INDIRIZZO, TITOLARE_NUMERO, PRIVACY_EMAIL

NOTA: testo di base scritto per il lancio; va fatto rileggere da un legale prima dell'apertura a clienti reali.
"""

import html
import os

import dati_fisco as D

AGGIORNATA = "28 ottobre 2026"


def _e(x) -> str:
    return html.escape(str(x))


def pagina() -> str:
    nome = os.environ.get("TITOLARE_NOME", "24 Tax and Consulting Ltd")
    indirizzo = os.environ.get("TITOLARE_INDIRIZZO", "").strip()
    numero = os.environ.get("TITOLARE_NUMERO", "12326663").strip()
    mail = os.environ.get("PRIVACY_EMAIL", D.CONTATTI["email"])
    chi = f"<b>{_e(nome)}</b>, società registrata nel Regno Unito"
    if numero:
        chi += f" (company number {_e(numero)})"
    if indirizzo:
        chi += f", {_e(indirizzo)}"
    chi += ", che opera con il marchio LTD24"
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Termini e condizioni - TaxScan</title>
<style>
@font-face{{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}}
@font-face{{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}}
@font-face{{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}}
@font-face{{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}}
:root{{--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--bg:#eef2f8;--card:#fff;--ink:#122452;--soft:#3d4a73;--accent:#4355cc;--accent-ink:#4355cc;--line:#d8e2ed}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0a1330;--card:#122452;--ink:#fff;--soft:#c9d3ec;--accent:#5566dd;--accent-ink:#a6b4ff;--line:#25397a}}}}
*{{box-sizing:border-box}}
h1,h2,h3,.logo{{font-family:var(--f-tit)}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--f-txt);padding:20px 16px 48px}}
main{{max-width:680px;margin:0 auto}}
.logo{{font-size:22px;font-weight:800;color:var(--ink)}} .logo span{{color:#05d5c8}}
h1{{font-size:26px;margin:14px 0 4px}} h2{{font-size:18px;margin:26px 0 6px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 18px}}
p,li{{margin:6px 0}} ul{{padding-left:20px}} .s{{color:var(--soft);font-size:14px}}
a{{color:var(--accent-ink)}}
</style></head><body><main>
<a href="/" style="text-decoration:none"><div class="logo">Tax<span>Scan</span></div></a>
<h1>Termini e condizioni</h1>
<p class="s">Condizioni d'uso di TaxScan. Aggiornate il {AGGIORNATA}.</p>
<div class="card">

<h2>In breve</h2>
<ul>
<li>TaxScan <b>prepara e spiega</b>: ti aiuta a capire tasse, scadenze e possibili risparmi con delle <b>stime</b>.</li>
<li>Non è una consulenza fiscale personalizzata e non sostituisce un commercialista. Le decisioni e le dichiarazioni restano tue.</li>
<li>L'assistente (Marcello) è un sistema di intelligenza artificiale, non una persona.</li>
</ul>

<h2>1. Chi offre il servizio</h2>
<p>TaxScan è offerto da {chi}. Per qualsiasi domanda sui termini scrivi a <a href="mailto:{_e(mail)}">{_e(mail)}</a>.</p>

<h2>2. Cosa fa TaxScan</h2>
<p>TaxScan aiuta chi ha la partita IVA in regime forfettario in Italia a stimare imposte e contributi, a ricordare le scadenze, a verificare se un'attività è associata al coefficiente giusto e a conoscere possibili agevolazioni. Le informazioni sono generali e a scopo informativo. I calcoli sono <b>stime</b> basate sui dati che inserisci tu o che carichi, e sulle regole in vigore alla data indicata nelle pagine del servizio.</p>

<h2>3. Cosa non fa</h2>
<ul>
<li>Non è consulenza fiscale, legale o contabile personalizzata e non crea un rapporto professionale con te.</li>
<li>Non presenta dichiarazioni, non invia F24 e non effettua pagamenti per tuo conto, salvo funzioni che ti vengano indicate esplicitamente come tali e che tu abbia attivato.</li>
<li>Non garantisce risparmi, rimborsi, agevolazioni o esiti con l'Amministrazione finanziaria.</li>
</ul>

<h2>4. La tua responsabilità</h2>
<p>Puoi usare TaxScan da solo, assumendoti la responsabilità di ciò che dichiari e paghi. Sei tenuto a inserire dati corretti e aggiornati e a verificare le cifre prima di agire. Se vuoi, puoi far controllare i risultati a un professionista: è facoltativo, mai obbligatorio.</p>

<h2>5. L'assistente virtuale</h2>
<p>Le risposte di Marcello sono generate automaticamente, possono contenere errori o essere incomplete e non vanno considerate un parere professionale. Non scrivere dati personali sensibili (salute, opinioni, ecc.) nella chat.</p>

<h2>6. Uso corretto</h2>
<p>Ti chiediamo di usare TaxScan per i tuoi scopi personali o professionali, di non tentare di accedere ai dati di altre persone, di non sovraccaricare il servizio e di non caricare materiale illecito o di cui non hai diritto. Possiamo sospendere l'accesso in caso di uso scorretto.</p>

<h2>7. Servizi di terzi</h2>
<p>Alcune funzioni possono basarsi su servizi di terzi (per esempio Fatture in Cloud, se scegli di collegarlo). Il loro uso è regolato dai loro termini. I servizi professionali di LTD24 (per esempio la consulenza gratuita o altri servizi a pagamento) sono separati da TaxScan e hanno condizioni proprie, che ti vengono presentate prima di sottoscriverli.</p>

<h2>8. Dati personali</h2>
<p>Trattiamo i tuoi dati come spiegato nella <a href="/privacy">privacy policy</a>. Puoi chiedere in ogni momento di vedere, correggere o cancellare i tuoi dati.</p>

<h2>9. Limiti di responsabilità</h2>
<p>Nei limiti consentiti dalla legge, non rispondiamo di danni indiretti o di decisioni prese basandosi solo sulle stime di TaxScan, né di interruzioni o errori del servizio, che è offerto <b>«così com'è»</b> e può cambiare. Restano ferme le tutele che la legge ti riconosce come consumatore e che non possono essere escluse.</p>

<h2>10. Proprietà intellettuale</h2>
<p>Il servizio, il marchio, i testi, le grafiche e il personaggio di Marcello sono di {_e(nome)} o dei suoi licenzianti. Puoi usarli solo per utilizzare TaxScan; non puoi copiarli o rivenderli senza autorizzazione. I dati e i documenti che carichi restano tuoi.</p>

<h2>11. Modifiche e fine del servizio</h2>
<p>Possiamo aggiornare il servizio e questi termini, per esempio quando cambiano le norme. Se la modifica è importante aggiorniamo questa pagina e la data in alto. Puoi smettere di usare TaxScan e cancellare i tuoi dati quando vuoi.</p>

<h2>12. Legge applicabile e controversie</h2>
<p>Se sei un consumatore residente in Italia, restano applicabili le norme inderogabili italiane a tua tutela e puoi rivolgerti al giudice del tuo luogo di residenza. Per qualsiasi problema scrivici prima: cerchiamo di risolverlo insieme.</p>
</div>
<p class="s" style="text-align:center;margin-top:18px"><a href="/privacy">Privacy policy</a> · <a href="#" class="tsck-open">Cookie</a> · <a href="/">Torna a TaxScan</a></p>
</main></body></html>
"""
