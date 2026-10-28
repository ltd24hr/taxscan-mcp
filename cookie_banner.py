"""
TaxScan - banner di consenso ai cookie (GDPR / ePrivacy).

Regole rispettate:
  - nessuno strumento non necessario parte prima della scelta;
  - "Accetta" e "Solo necessari" hanno lo stesso peso grafico;
  - le statistiche d'uso sono una scelta separata, spenta di default;
  - la scelta si puo' cambiare quando si vuole (link "Cookie" in fondo alle pagine);
  - la scelta e' salvata nel browser (localStorage 'ts_cookie') e vale 12 mesi.
La pagina puo' leggere la scelta da window.TS_CONSENT = {s: 0|1, t: timestamp} (null se non ancora scelta).
"""

SNIPPET = r"""
<style id="tsck-css">
#tsck{position:fixed;left:12px;right:12px;bottom:12px;z-index:2147483000;max-width:760px;margin:0 auto;background:#fff;color:#122452;border:2px solid #4355cc;border-radius:16px;box-shadow:0 12px 36px rgba(18,36,82,.28);padding:16px 18px;font:15px/1.5 "Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
#tsck[hidden]{display:none}
#tsck h2{font-size:16px;margin:0 0 6px}
#tsck p{margin:0 0 10px}
#tsck a{color:#4355cc;font-weight:600}
#tsck .tsck-b{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}
#tsck button{font:inherit;font-weight:700;font-size:15px;color:#122452;background:#fff;border:2px solid #4355cc;border-radius:12px;padding:11px 20px;cursor:pointer;flex:1 1 150px}
#tsck button:hover{background:#e8ebfa}
#tsck button.tsck-l{flex:0 0 auto;border-color:transparent;background:none;text-decoration:underline;color:#3d4a73;padding-inline:8px}
#tsck button:focus-visible,#tsck a:focus-visible,#tsck input:focus-visible{outline:3px solid #05d5c8;outline-offset:2px}
#tsck .tsck-p{border-top:1px solid #d8e2ed;margin-top:10px;padding-top:10px}
#tsck .tsck-p[hidden]{display:none}
#tsck label{display:flex;gap:10px;align-items:flex-start;margin:6px 0;cursor:pointer}
#tsck input{width:20px;height:20px;margin-top:2px;flex:none}
#tsck small{display:block;color:#3d4a73}
@media (prefers-color-scheme:dark){#tsck{background:#122452;color:#fff;border-color:#8c99f0}#tsck button{background:#122452;color:#fff;border-color:#8c99f0}#tsck button:hover{background:#1d2d6b}#tsck a{color:#a6b4ff}#tsck small,#tsck button.tsck-l{color:#c9d3ec}#tsck .tsck-p{border-color:#26396f}}
</style>
<div id="tsck" role="dialog" aria-modal="false" aria-labelledby="tsck-t" hidden>
  <h2 id="tsck-t">Cookie e strumenti tecnici</h2>
  <p>Usiamo strumenti <b>tecnici necessari</b> per far funzionare TaxScan (per esempio ricordare le tue scelte). Non usiamo cookie di profilazione né di terzi. Se vuoi, puoi autorizzare anche delle <b>statistiche d'uso</b> per aiutarci a migliorare il servizio. Dettagli nella <a href="/privacy">privacy policy</a>.</p>
  <div class="tsck-p" id="tsck-p" hidden>
    <label><input type="checkbox" checked disabled> <span><b>Necessari</b> (sempre attivi)<small>Servono per far funzionare le pagine e ricordare queste scelte.</small></span></label>
    <label><input type="checkbox" id="tsck-s"> <span><b>Statistiche d'uso</b><small>Dati anonimi su quali pagine e passaggi usi, raccolti da noi, senza strumenti di terzi. Spenti finché non li accetti.</small></span></label>
  </div>
  <div class="tsck-b">
    <button type="button" id="tsck-no">Solo necessari</button>
    <button type="button" id="tsck-si">Accetta tutti</button>
    <button type="button" id="tsck-pr" class="tsck-l" aria-expanded="false" aria-controls="tsck-p">Personalizza</button>
  </div>
</div>
<script id="tsck-js">
(function(){
  var K='ts_cookie',MESI12=365*864e5,box=document.getElementById('tsck');if(!box)return;
  function get(){try{var o=JSON.parse(localStorage.getItem(K)||'null');if(o&&Date.now()-o.t<MESI12)return o}catch(e){}return null}
  function set(s){var o={s:s?1:0,t:Date.now(),v:1};try{localStorage.setItem(K,JSON.stringify(o))}catch(e){}window.TS_CONSENT=o;try{document.dispatchEvent(new CustomEvent('ts-consent',{detail:o}))}catch(e){}box.hidden=true}
  function show(){var o=get();document.getElementById('tsck-s').checked=!!(o&&o.s===1);box.hidden=false;try{document.getElementById('tsck-no').focus()}catch(e){}}
  window.TS_CONSENT=get();
  document.getElementById('tsck-no').onclick=function(){set(false)};
  document.getElementById('tsck-si').onclick=function(){set(true)};
  var pr=document.getElementById('tsck-pr'),pn=document.getElementById('tsck-p');
  pr.onclick=function(){var open=pn.hidden;if(open){pn.hidden=false;pr.textContent='Salva la mia scelta';pr.setAttribute('aria-expanded','true')}else{set(document.getElementById('tsck-s').checked)}};
  window.tsCookie=function(){pn.hidden=true;pr.textContent='Personalizza';pr.setAttribute('aria-expanded','false');show();return false};
  document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('.tsck-open');if(a){e.preventDefault();window.tsCookie()}});
  if(!window.TS_CONSENT)box.hidden=false;
})();
</script>
"""


def inietta(html: str) -> str:
    """Mette il banner prima di </body> (una sola volta)."""
    if "tsck-css" in html:
        return html
    i = html.rfind("</body>")
    return html[:i] + SNIPPET + html[i:] if i >= 0 else html + SNIPPET


LINK_LEGALI = ('<p class="legal"><a href="/termini">Termini e condizioni</a> · <a href="/privacy">Privacy policy</a> · '
               '<a href="#" class="tsck-open">Cookie</a></p>')
CSS_LEGALI = ".legal{font-size:13px;color:var(--ink2,#3d4a73);margin:16px 0 0}.legal a{color:inherit;font-weight:600}"
