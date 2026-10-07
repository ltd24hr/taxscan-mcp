"""
TaxScan - informativa sulla privacy (pagina /privacy).

I dati del titolare si possono impostare con variabili d'ambiente su Render senza toccare il codice:
  TITOLARE_NOME       (default "24 Tax and Consulting Ltd")
  TITOLARE_INDIRIZZO  (se vuoto, la riga non compare)
  TITOLARE_NUMERO     (default 12326663: company number)
  PRIVACY_EMAIL       (default info@ltd24ore.com)
"""

import html
import os

import dati_fisco as D

AGGIORNATA = "5 ottobre 2026"


def _e(x) -> str:
    return html.escape(str(x))


def pagina() -> str:
    nome = os.environ.get("TITOLARE_NOME", "24 Tax and Consulting Ltd")
    indirizzo = os.environ.get("TITOLARE_INDIRIZZO", "").strip()
    numero = os.environ.get("TITOLARE_NUMERO", "12326663").strip()
    mail = os.environ.get("PRIVACY_EMAIL", D.CONTATTI["email"])
    dati_titolare = f"<b>{_e(nome)}</b>, società registrata nel Regno Unito"
    if numero:
        dati_titolare += f" (company number {_e(numero)})"
    if indirizzo:
        dati_titolare += f", {_e(indirizzo)}"
    dati_titolare += ", che opera con il marchio LTD24"
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy - TaxScan</title>
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
table{{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}} td,th{{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}}
</style></head><body><main>
<a href="/" style="text-decoration:none"><div class="logo">Tax<span>Scan</span></div></a>
<h1>Come trattiamo i tuoi dati</h1>
<p class="s">Informativa ai sensi degli artt. 13 e 14 del Regolamento UE 2016/679 (GDPR). Aggiornata il {AGGIORNATA}.</p>
<div class="card">

<h2>In breve</h2>
<ul>
<li>Usiamo i tuoi dati <b>solo per farti funzionare TaxScan</b>: calcolare le stime, mostrarti la dashboard, ricordarti le scadenze e rispondere alle tue domande.</li>
<li>Non vendiamo i tuoi dati e non li usiamo per pubblicità.</li>
<li>Puoi chiederci di vedere, correggere o <b>cancellare tutto</b> quando vuoi, e smettere di ricevere le email con un clic.</li>
<li>L'assistente della dashboard è un <b>sistema di intelligenza artificiale</b>, non una persona.</li>
</ul>

<h2>Chi è il titolare</h2>
<p>Il titolare del trattamento è {dati_titolare}, che offre TaxScan. Per qualsiasi richiesta sulla privacy scrivi a <a href="mailto:{_e(mail)}">{_e(mail)}</a>.</p>

<h2>Quali dati raccogliamo</h2>
<table>
<tr><th>Dato</th><th>Quando</th></tr>
<tr><td>Risposte all'intervista: attività, codice ATECO, data di apertura, gestione previdenziale, comune, incassi dell'anno</td><td>Quando compili l'intervista o carichi il certificato di attribuzione della partita IVA</td></tr>
<tr><td>Certificato di attribuzione della partita IVA (PDF)</td><td>Solo se lo carichi: leggiamo i dati utili e non conserviamo il file</td></tr>
<tr><td>Nome e cognome del titolare, se compaiono sul certificato</td><td>Li leggiamo per fartele confermare; in dashboard ed email ti salutiamo solo con il nome</td></tr>
<tr><td>Email</td><td>Quando salvi la tua situazione o usi "Accedi"</td></tr>
<tr><td>Domande all'assistente e relative risposte</td><td>Quando usi la chat</td></tr>
<tr><td>Risposte al sondaggio di feedback (scelte, commento, eventuale consenso a essere ricontattato)</td><td>Solo se rispondi: sono collegate alla tua email per poterti rispondere e le leggiamo noi</td></tr>
<tr><td>Dati di utilizzo (per esempio: pagina aperta, passo completato, email inviata)</td><td>Mentre usi il servizio, per capire dove migliorarlo</td></tr>
<tr><td>Dati di Fatture in Cloud (fatture, incassi)</td><td>Solo se scegli di collegare il tuo account</td></tr>
</table>
<p>Dal certificato leggiamo nome e cognome del titolare, ma non conserviamo il codice fiscale, la partita IVA né il file. Non ti chiediamo dati particolari (salute, opinioni, ecc.). <b>Nella chat non scrivere questo tipo di informazioni.</b></p>

<h2>A cosa servono e su quale base</h2>
<ul>
<li><b>Fornirti il servizio che hai chiesto</b> (stime, dashboard, calendario, assistente, ritrovare i tuoi dati): è necessario per eseguire la tua richiesta.</li>
<li><b>Mandarti email legate al servizio</b>: codice di accesso, benvenuto, promemoria di scadenze, riepilogo mensile, avvisi su cambi di norme che ti riguardano una sola email con spunti su bandi e agevolazioni e una richiesta di feedback (con un promemoria). Puoi disiscriverti con un clic da ogni email.</li>
<li><b>Migliorare TaxScan</b> guardando come viene usato (dati di utilizzo e domande all'assistente): è un nostro legittimo interesse.</li>
<li><b>Rispettare obblighi di legge</b> e difenderci in caso di necessità.</li>
</ul>

<h2>L'assistente virtuale</h2>
<p>Quando fai una domanda nella chat, il testo della domanda e le cifre della tua dashboard vengono inviati a un fornitore di intelligenza artificiale (Anthropic) che genera la risposta. Le risposte sono automatiche, a scopo informativo e <b>non sono consulenza fiscale</b>: per le decisioni importanti ci vuole il tuo commercialista. Nessuna decisione che ti riguarda viene presa in modo automatico.</p>

<h2>Con chi condividiamo i dati</h2>
<p>Solo con i fornitori tecnici che ci servono per far funzionare il servizio, nominati responsabili del trattamento:</p>
<ul>
<li>hosting del servizio (Render) e database (Supabase);</li>
<li>invio delle email (Resend);</li>
<li>assistente virtuale (Anthropic);</li>
<li>Fatture in Cloud, solo se colleghi il tuo account.</li>
</ul>
<p>Alcuni fornitori possono trattare dati fuori dallo Spazio Economico Europeo, con le garanzie previste dal GDPR. Se premi "Parla con un professionista" o prenoti una consulenza gratuita, quella prenotazione avviene sul calendario del professionista e vale la sua informativa.</p>

<h2>Per quanto tempo li conserviamo</h2>
<p>Finché usi TaxScan e fino a quando non ci chiedi di cancellarli. Se smetti di usare il servizio, i dati restano il tempo necessario a eventuali verifiche e poi li cancelliamo o li rendiamo anonimi. Puoi cancellare tutto da solo, in qualsiasi momento, con il pulsante "Cancella i miei dati" in fondo alla tua pagina.</p>

<h2>I tuoi diritti</h2>
<p>Puoi chiederci in ogni momento di accedere ai tuoi dati, correggerli, cancellarli, limitarne l'uso, riceverli in un formato leggibile (portabilità) e opporti al trattamento. Per cancellare i dati basta il pulsante in fondo alla tua pagina; per le altre richieste scrivi a <a href="mailto:{_e(mail)}">{_e(mail)}</a> dall'email con cui ti sei iscritto. Hai anche il diritto di presentare reclamo al <a href="https://www.garanteprivacy.it" target="_blank" rel="noopener">Garante per la protezione dei dati personali</a>.</p>

<h2>Sicurezza</h2>
<p>La tua pagina ha un indirizzo riservato e non indovinabile, l'accesso con email richiede un codice monouso e i dati viaggiano su connessione cifrata. Nessun sistema è sicuro al 100%: se succede qualcosa che ti riguarda, ti avvisiamo come previsto dalla legge.</p>

<h2>Cookie</h2>
<p>TaxScan non usa cookie di profilazione né strumenti di tracciamento di terzi.</p>

<h2>Modifiche</h2>
<p>Se cambiamo qualcosa di importante aggiorniamo questa pagina e la data in alto.</p>
</div>
<p class="s" style="text-align:center;margin-top:18px">TaxScan è un servizio offerto da <a href="{_e(D.CONTATTI['sito'])}">LTD24</a> · <a href="/">Torna a TaxScan</a></p>
</main></body></html>
"""
