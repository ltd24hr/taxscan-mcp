"""TaxScan - pagina iniziale (/): un solo messaggio e un solo pulsante."""

PAGINA_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TaxScan - La tua partita IVA forfettaria sotto controllo</title>
<meta name="description" content="Scopri in 2 minuti quanto hai maturato di tasse, quando paghi e quanto mettere da parte.">
<style>
:root{color-scheme:light;--bg:#f4f3ef;--surface:#fcfcfb;--line:#e4e2dc;--ink:#0b0b0b;--ink2:#52514e;--accent:#2a78d6;--accent-ink:#184f95;--soft:#e6f0fc}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#121211;--surface:#1a1a19;--line:#2e2e2b;--ink:#fff;--ink2:#c3c2b7;--accent:#3987e5;--accent-ink:#86b6ef;--soft:#17283d}}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px 16px 40px;max-width:560px;margin:0 auto}
.logo{font-weight:800;font-size:18px;letter-spacing:-.01em;margin-bottom:28px}
.logo span{color:var(--accent)}
h1{font-size:32px;line-height:1.12;letter-spacing:-.02em;margin-bottom:12px}
.lead{font-size:17px;color:var(--ink2);margin-bottom:22px}
.cta{display:block;text-align:center;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;font-size:18px;padding:16px;border-radius:14px}
.sub{font-size:13px;color:var(--ink2);text-align:center;margin:10px 0 28px}
ul{list-style:none;padding:0}
li{display:flex;gap:12px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:10px}
li i{flex:none;width:34px;height:34px;border-radius:10px;background:var(--soft);color:var(--accent-ink);display:grid;place-items:center;font-style:normal;font-weight:800}
li b{display:block}
li span{font-size:14px;color:var(--ink2)}
.by{font-size:12px;color:var(--ink2);margin-top:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}.by a{display:inline-flex;color:var(--ink);font-weight:700;text-decoration:none}.by img{height:20px;width:auto}
.foot{font-size:12px;color:var(--ink2);margin-top:24px;line-height:1.5}
</style>
</head>
<body>
<div class="logo">Tax<span>Scan</span></div>
<h1>La tua partita IVA forfettaria, sotto controllo.</h1>
<p class="lead">In 2 minuti scopri quanto hai maturato di tasse, quando paghi e quanto mettere da parte. Senza domande difficili.</p>
<a class="cta" href="/colloquio/nuovo">Inizia, è gratis</a>
<p class="sub">Basta il certificato della partita IVA, oppure qualche tocco sul telefono.</p>
<p class="sub" style="margin-top:-18px">Hai già un profilo? <a href="/accedi" style="color:var(--accent-ink);font-weight:700">Accedi</a></p>
<ul>
<li><i>1</i><div><b>Dici chi sei</b><span>Carichi il certificato di attribuzione e scegli fra poche risposte. Il resto lo capiamo noi.</span></div></li>
<li><i>2</i><div><b>Vedi la tua situazione</b><span>Prossima scadenza, quota da mettere da parte su ogni fattura, distanza dagli 85.000 €.</span></div></li>
<li><i>3</i><div><b>Non perdi più nulla</b><span>Scadenze nel calendario del telefono e spunti su bandi e agevolazioni per la tua zona.</span></div></li>
</ul>
<p class="foot">TaxScan prepara e spiega: sono stime a scopo informativo. Il tuo commercialista controlla e firma. Non sostituisce il parere di un professionista abilitato.</p>
<p class="by">TaxScan è un servizio offerto da <a href="https://ltd24.co.uk" target="_blank" rel="noopener"><img src="/logo-ltd24.png" alt="LTD24" onerror="this.replaceWith(document.createTextNode('LTD24'))"></a></p>
</body>
</html>
"""


ACCEDI_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Accedi - TaxScan</title>
<style>
:root{color-scheme:light;--bg:#f4f3ef;--surface:#fcfcfb;--line:#e4e2dc;--ink:#0b0b0b;--ink2:#52514e;--accent:#2a78d6;--accent-ink:#184f95;--crit:#d03b3b}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#121211;--surface:#1a1a19;--line:#2e2e2b;--ink:#fff;--ink2:#c3c2b7;--accent:#3987e5;--accent-ink:#86b6ef}}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px 16px 40px;max-width:480px;margin:0 auto}
.logo{font-weight:800;font-size:18px;margin-bottom:28px}.logo span{color:var(--accent)}
h1{font-size:26px;line-height:1.15;margin-bottom:8px}
.lead{color:var(--ink2);margin-bottom:18px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px}
input{width:100%;padding:14px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;margin-bottom:10px}
button{width:100%;border:0;border-radius:12px;padding:14px;background:var(--accent);color:#fff;font:inherit;font-weight:700;cursor:pointer}
.msg{font-size:14px;color:var(--ink2);margin-top:10px;min-height:20px}.msg.err{color:var(--crit)}
a{color:var(--accent-ink);font-weight:600}
.by{font-size:12px;color:var(--ink2);margin-top:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}.by a{display:inline-flex;color:var(--ink);font-weight:700;text-decoration:none}.by img{height:20px;width:auto}
.nascosto{display:none}
</style>
</head>
<body>
<div class="logo">Tax<span>Scan</span></div>
<h1>Bentornato</h1>
<p class="lead">Scrivi l'email che hai usato: ti mandiamo un codice a 6 cifre. Niente password da ricordare.</p>
<div class="card">
  <div id="passo1"><input id="em" type="email" inputmode="email" autocomplete="email" placeholder="La tua email"><button id="ok1">Ricevi il codice</button></div>
  <div id="passo2" class="nascosto"><p class="lead" style="margin-bottom:10px" id="inviato"></p><input id="cod" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="Codice"><button id="ok2">Entra</button></div>
  <p class="msg" id="msg"></p>
</div>
<p class="lead" style="margin-top:18px;font-size:14px">Non hai ancora un profilo? <a href="/colloquio/nuovo">Inizia da qui</a>, ci vogliono 2 minuti.</p>
<p class="by">TaxScan è un servizio offerto da <a href="https://ltd24.co.uk" target="_blank" rel="noopener"><img src="/logo-ltd24.png" alt="LTD24" onerror="this.replaceWith(document.createTextNode('LTD24'))"></a></p>
<script>
const $=i=>document.getElementById(i);
const msg=(t,e)=>{$("msg").textContent=t;$("msg").className="msg"+(e?" err":"")};
async function post(p,b){const r=await fetch(p,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)});let j={};try{j=await r.json()}catch(e){}return j}
let email="";
$("ok1").onclick=async()=>{email=$("em").value.trim();
  if(!/^\S+@\S+\.\S+$/.test(email))return msg("Scrivi un'email valida.",true);
  msg("Un attimo…");const j=await post("/api/accedi/email",{email});
  if(!j.ok)return msg(j.errore||"Non ci sono riuscito, riprova.",true);
  $("passo1").classList.add("nascosto");$("passo2").classList.remove("nascosto");
  $("inviato").textContent="Se "+email+" ha un profilo, ti abbiamo scritto un codice (guarda anche nello spam).";msg("");$("cod").focus()};
$("em").onkeydown=e=>{if(e.key==="Enter")$("ok1").click()};
$("ok2").onclick=async()=>{msg("Controllo…");const j=await post("/api/accedi/codice",{email,codice:$("cod").value.trim()});
  if(j.ok){msg("Ti porto alla tua situazione…");location.href=j.dashboard}else msg(j.errore||"Codice non valido.",true)};
$("cod").onkeydown=e=>{if(e.key==="Enter")$("ok2").click()};
</script>
</body>
</html>
"""
