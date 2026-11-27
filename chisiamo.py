"""Pagina «Chi c'è dietro TaxScan»: chi offre il servizio, come lavoriamo, come contattarci."""
import html
import os

import dati_fisco as D
import privacy


def _e(x) -> str:
    return html.escape(str(x or ""), quote=True)


def pagina() -> str:
    base = privacy.pagina()
    head = base.split("</style>", 1)[0]
    nome = os.environ.get("TITOLARE_NOME", "24 Tax and Consulting Ltd")
    numero = os.environ.get("TITOLARE_NUMERO", "12326663").strip()
    mail = os.environ.get("PRIVACY_EMAIL", D.CONTATTI["email"])
    soc = f"<b>{_e(nome)}</b>, società registrata nel Regno Unito" + (f" (company number {_e(numero)})" if numero else "") + ", con il marchio LTD24"
    stile = """
.pt{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:12px 0}
.pt div{background:var(--bg);border-radius:12px;padding:14px}
.pt b{display:block;margin-bottom:4px}
.az{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.az a{display:inline-block;font-weight:700;padding:11px 16px;border-radius:12px;text-decoration:none;border:1px solid var(--line);color:var(--ink)}
.az a.pri{background:var(--accent);border-color:var(--accent);color:#fff}
"""
    corpo = f"""</style></head><body><main>
<a href="/" style="text-decoration:none"><div class="logo">Tax<span>Scan</span></div></a>
<h1>Chi c'è dietro TaxScan</h1>
<p class="s">TaxScan è il primo agente IA dedicato al risparmio fiscale di chi ha la partita IVA in regime forfettario.</p>
<div class="card">
<h2>Chi siamo</h2>
<p>TaxScan è un servizio di {soc}, che si occupa di consulenza fiscale e societaria. Abbiamo costruito TaxScan perché
la maggior parte dei forfettari non sa quanto pagherà, quando, e se sta pagando più del dovuto.</p>

<h2>Come lavoriamo</h2>
<div class="pt">
<div><b>L'IA prepara e spiega</b>Legge i tuoi documenti, fa i calcoli, ti ricorda le scadenze e ti spiega il perché dei numeri, in parole semplici.</div>
<div><b>Le persone controllano</b>Quando il caso è particolare, o vuoi una verifica, puoi parlare con un consulente vero. La prima chiamata è gratuita.</div>
<div><b>Niente promesse</b>Le cifre sono stime sui tuoi dati. Se il risparmio non c'è, te lo diciamo. Le decisioni restano tue.</div>
</div>

<h2>I tuoi dati</h2>
<p>I tuoi dati li vedi solo tu. Dei file che carichi per l'analisi teniamo solo i numeri che servono ai calcoli; le
fatture che crei in TaxScan le puoi cancellare quando vuoi, insieme all'account. Tutti i dettagli sono nella
<a href="/privacy">privacy policy</a>.</p>

<h2>Contatti</h2>
<p>Scrivici a <a href="mailto:{_e(mail)}">{_e(mail)}</a>.</p>
<div class="az"><a class="pri" href="/colloquio/nuovo?utm_source=chi_siamo">Scopri quanto puoi risparmiare</a><a href="https://calendly.com/ltd24ore?utm_source=taxscan_chi_siamo" target="_blank" rel="noopener">Parla con un consulente</a><a href="/commercialisti">Sei un commercialista?</a></div>
</div>
</main></body></html>"""
    return head.replace("<title>Privacy - TaxScan</title>", "<title>Chi c'è dietro TaxScan</title>") + stile + corpo
