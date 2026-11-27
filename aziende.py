"""Pagina «Per le aziende»: chi lavora con tanti collaboratori in partita IVA (agenzie, studi, piattaforme,
cooperative) puo' offrire loro TaxScan. Il modulo manda la richiesta all'amministratore."""
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
<h1>Lavori con collaboratori in partita IVA?</h1>
<p class="s">Agenzie, studi, piattaforme, cooperative: se lavori con tanti professionisti in regime forfettario, puoi offrire loro TaxScan, l'agente IA che li aiuta con scadenze, F24, quanto mettere da parte e fatture fatte bene.</p>
<div class="card">
<h2>Perché conviene anche a te</h2>
<div class="pt">
<div><b>Fatture giuste al primo colpo</b>Con TaxScan i tuoi collaboratori fanno fatture con le diciture del forfettario, il bollo e i dati corretti. Meno fatture da correggere e rimandare indietro.</div>
<div><b>Collaboratori più sereni</b>Sanno quanto mettere da parte ogni mese e quando pagare. Meno sorprese a giugno e novembre, meno richieste di anticipi.</div>
<div><b>Un vantaggio in più da offrire</b>Uno strumento utile da dare a chi lavora con te, senza costi di gestione: ognuno usa il suo spazio, i suoi dati restano suoi.</div>
</div>
<p>I dati di ogni collaboratore restano privati: l'azienda non vede le sue tasse né le sue fatture.</p>
<h2>Parliamone</h2>
<p>Lasciaci i tuoi dati: ti scriviamo per capire di quanti collaboratori si tratta e proporti condizioni dedicate.</p>
<form id="f" novalidate>
<label for="n">Nome e cognome</label><input id="n" name="nome" autocomplete="name" required maxlength="80">
<label for="s">Azienda</label><input id="s" name="studio" autocomplete="organization" maxlength="120">
<label for="m">Email</label><input id="m" name="email" type="email" autocomplete="email" required maxlength="120">
<label for="c">Quanti collaboratori in partita IVA, più o meno</label><input id="c" name="citta" inputmode="numeric" maxlength="40" placeholder="Per esempio: 15">
<label for="t">Qualcosa in più (facoltativo)</label><textarea id="t" name="nota" rows="3" maxlength="800" placeholder="Per esempio: settore, come lavorano con voi, cosa vi servirebbe"></textarea>
<button type="submit" id="b">Invia la richiesta</button>
<p id="o" role="status" class="ok"></p>
<p class="s">Useremo questi dati solo per ricontattarti su questa proposta. <a href="/privacy">Privacy</a></p>
</form>
</div>
</main>
<script>
(function(){var f=document.getElementById('f'),b=document.getElementById('b'),o=document.getElementById('o');
f.onsubmit=function(e){e.preventDefault();var d={tipo:'azienda'};['nome','studio','email','citta','nota'].forEach(function(k){d[k]=(f.elements[k].value||'').trim()});
if(!d.nome||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$/.test(d.email)){o.textContent='Scrivi nome ed email.';return}
b.disabled=true;o.textContent='Invio…';
fetch('/api/commercialisti',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)}).then(function(r){return r.json()}).then(function(j){
if(j&&j.ok){f.querySelectorAll('input,textarea,button').forEach(function(x){x.disabled=true});o.textContent='Grazie! Ti scriviamo noi nei prossimi giorni.'}else{b.disabled=false;o.textContent=(j&&j.errore)||'Non è partita: riprova tra poco.'}})
.catch(function(){b.disabled=false;o.textContent='Non è partita: riprova tra poco.'})}})();
</script>
</body></html>"""
    return head.replace("<title>Privacy - TaxScan</title>", "<title>Per le aziende - TaxScan</title>") + stile + corpo
