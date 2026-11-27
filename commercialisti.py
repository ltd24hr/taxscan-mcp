"""Pagina «Sei un commercialista? Collabora con noi»: TaxScan cerca commercialisti partner a cui affidare le persone
che vogliono un professionista vero accanto all'agente IA. Il modulo manda la candidatura all'amministratore."""
import html

import privacy


def _e(x) -> str:
    return html.escape(str(x or ""), quote=True)


def pagina() -> str:
    # stesso aspetto della pagina privacy: prendo il suo <head> (font, colori, tema scuro)
    base = privacy.pagina()
    head = base.split("</style>", 1)[0]
    stile = """
form{display:grid;gap:10px;margin-top:8px}
label{font-weight:600;font-size:14px}
input,textarea{font:inherit;font-size:15px;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);width:100%}
button{font:inherit;font-weight:700;font-size:16px;padding:12px 18px;border-radius:12px;border:0;background:var(--accent);color:#fff;cursor:pointer;justify-self:start}
button:disabled{opacity:.6}
.ok{font-weight:600}
.pt{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:12px 0}
.pt div{background:var(--bg);border-radius:12px;padding:14px}
.pt b{display:block;margin-bottom:4px}
"""
    corpo = """</style></head><body><main>
<a href="/" style="text-decoration:none"><div class="logo">Tax<span>Scan</span></div></a>
<h1>Sei un commercialista? Collabora con noi</h1>
<p class="s">TaxScan è l'agente IA che accompagna chi ha la partita IVA in regime forfettario: scadenze, F24, quanto mettere da parte, risparmio fiscale. Ma l'IA non sostituisce un professionista: per questo stiamo costruendo una rete di commercialisti partner.</p>
<div class="card">
<h2>Come funziona</h2>
<div class="pt">
<div><b>Clienti che chiedono un professionista</b>Quando una persona vuole far controllare i suoi numeri o ha un caso particolare, può chiedere un commercialista vero. Lo indirizziamo ai partner della sua zona o del suo settore.</div>
<div><b>Dati già in ordine</b>Il cliente arriva con il riepilogo della sua situazione e l'elenco delle fatture, pronti da controllare. Meno tempo a raccogliere documenti, più tempo per la consulenza.</div>
<div><b>Tu decidi</b>Accetti solo i clienti che vuoi, con le tue condizioni. TaxScan prepara e spiega; la consulenza e la responsabilità professionale restano tue.</div>
</div>
<h2>Candidati</h2>
<p>Lasciaci i tuoi dati: ti richiamiamo per conoscerci e capire insieme come lavorare.</p>
<form id="f" novalidate>
<label for="n">Nome e cognome</label><input id="n" name="nome" autocomplete="name" required maxlength="80">
<label for="s">Studio</label><input id="s" name="studio" autocomplete="organization" maxlength="120">
<label for="m">Email</label><input id="m" name="email" type="email" autocomplete="email" required maxlength="120">
<label for="c">Città</label><input id="c" name="citta" autocomplete="address-level2" maxlength="80">
<label for="t">Di cosa ti occupi (facoltativo)</label><textarea id="t" name="nota" rows="3" maxlength="800" placeholder="Per esempio: forfettari del settore digitale, artigiani, professionisti sanitari…"></textarea>
<button type="submit" id="b">Invia la candidatura</button>
<p id="o" role="status" class="ok"></p>
<p class="s">Useremo questi dati solo per ricontattarti su questa collaborazione. <a href="/privacy">Privacy</a></p>
</form>
</div>
</main>
<script>
(function(){var f=document.getElementById('f'),b=document.getElementById('b'),o=document.getElementById('o');
f.onsubmit=function(e){e.preventDefault();var d={};['nome','studio','email','citta','nota'].forEach(function(k){d[k]=(f.elements[k].value||'').trim()});
if(!d.nome||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$/.test(d.email)){o.textContent='Scrivi nome ed email.';return}
b.disabled=true;o.textContent='Invio…';
fetch('/api/commercialisti',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)}).then(function(r){return r.json()}).then(function(j){
if(j&&j.ok){f.querySelectorAll('input,textarea,button').forEach(function(x){x.disabled=true});o.textContent='Grazie! Ti scriviamo noi nei prossimi giorni.'}else{b.disabled=false;o.textContent=(j&&j.errore)||'Non è partita: riprova tra poco.'}})
.catch(function(){b.disabled=false;o.textContent='Non è partita: riprova tra poco.'})}})();
</script>
</body></html>"""
    return head.replace("<title>Privacy - TaxScan</title>", "<title>Commercialisti partner - TaxScan</title>") + stile + corpo
