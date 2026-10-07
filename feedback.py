"""
TaxScan - sondaggio di feedback dopo l'iscrizione.

Flusso (semplice, poche domande a scelta multipla, un campo libero alla fine):
  1. 24 ore dopo l'iscrizione: email neutra "consiglieresti TaxScan a un collega?" con due pulsanti, Si / No.
  2. I pulsanti aprono /feedback: una domanda alla volta (si avanza toccando la risposta). Aprire il link NON registra nulla
     (i programmi di posta aprono i link per controllarli): la risposta si salva solo quando l'utente preme Invia.
  3. Nessuna risposta dopo 3 giorni: un solo promemoria, uguale al primo.
  4. Nessuna risposta nemmeno dopo il promemoria (6 giorni dall'invito): l'utente compare nella pagina privata
     /admin/feedback come "da contattare", per un contatto personale via email (se non si e' disiscritto).
Regole: nessun premio, nessun filtro per punteggio, invito uguale per tutti (sono anche le regole di Trustpilot,
che aggiungeremo piu' avanti come invito neutro uguale per tutti).
"""
import html as _html
import json
import re

import db
import dashboard
import scheda as S

PUBLIC_URL = dashboard.PUBLIC_URL

DOMANDE = [
    {"id": "piaciuto", "testo": "Cosa ti è piaciuto di più?", "tipo": "multi", "opzioni": [
        ["mettere_da_parte", "Sapere quanto mettere da parte"], ["scadenze", "Le scadenze e il calendario"],
        ["soglia", "Il controllo della soglia degli 85.000 €"], ["bandi", "I bandi e le agevolazioni"],
        ["assistente", "L'assistente (la chat)"], ["semplicita", "La semplicità"],
        ["niente", "Niente in particolare"]]},
    {"id": "chiarezza", "testo": "Quanto ti è sembrato chiaro?", "tipo": "uno", "opzioni": [
        ["chiarissimo", "Chiarissimo"], ["abbastanza", "Abbastanza"], ["poco", "Poco chiaro"],
        ["confuso", "Confuso"]]},
    {"id": "manca", "testo": "Cosa ti manca di più?", "tipo": "multi", "opzioni": [
        ["fatturazione", "Collegare il mio programma di fatturazione"], ["f24", "Preparare l'F24 già pronto"],
        ["commercialista", "Parlare con un commercialista"], ["spiegazioni", "Spiegazioni più semplici"],
        ["telefono", "Avvisi sul telefono"], ["niente", "Niente, va bene così"]]},
]
_ETICHETTE = {d["id"]: dict(d["opzioni"]) for d in DOMANDE}


def _e(x) -> str:
    return _html.escape(str(x if x is not None else ""))


def _link(email: str, risposta: str = "") -> str:
    import promemoria as P
    from urllib.parse import quote
    base = f"{PUBLIC_URL}/feedback?e={quote(email)}&t={P.firma(email)}"
    return base + (f"&r={risposta}" if risposta in ("si", "no") else "")


# ------------------------------------------------------------------ email

def _nome(id_dashboard: str) -> str:
    try:
        return S.pulisci_nome(((db.carica_dashboard(id_dashboard) or {}).get("_scheda") or {}).get("nome"))
    except Exception:
        return ""


def manda(email: str, id_dashboard: str, promemoria: bool = False) -> bool:
    """Manda la richiesta di feedback (o il promemoria). False se disiscritto o gia' mandata."""
    import promemoria as P
    import auth
    email = (email or "").strip().lower()
    tipo = "feedback_reminder" if promemoria else "feedback"
    if not email or db.email_disattivate(email) or not db.prenota_promemoria(email, tipo, "1"):
        return False
    try:
        nome = _nome(id_dashboard)
        bottone = ("display:inline-block;padding:14px 30px;margin:0 8px 8px 0;font-weight:700;text-decoration:none;"
                   "background:#4355cc;color:#ffffff;border-radius:0;min-width:80px;text-align:center")
        if promemoria:
            intro = ("<p>Ti scrivo di nuovo, una volta sola: la tua risposta ci aiuta a capire cosa migliorare. "
                     "Basta un clic.</p>")
            oggetto, titolo = "TaxScan: una risposta veloce?", "Una risposta veloce?"
        else:
            intro = ("<p>Hai avuto modo di guardare la tua pagina su TaxScan.</p>")
            oggetto, titolo = "Com'è andata con TaxScan?", "Una domanda veloce"
        corpo = ((f"<p>Ciao {_e(nome)},</p>" if nome else "") + intro +
                 "<p><b>Se un collega con la partita IVA ti chiedesse com'è, consiglieresti TaxScan?</b></p>"
                 f"<p style='margin:18px 0 6px'><a href='{_e(_link(email, 'si'))}' style='{bottone}'>Sì</a>"
                 f"<a href='{_e(_link(email, 'no'))}' style='{bottone}'>No</a></p>"
                 "<p style='font-size:14px;color:#3d4a73'>Dopo il clic ti chiediamo due minuti per dirci perché, "
                 "con poche domande a scelta. Le risposte le leggiamo noi.</p>")
        auth.manda_email(email, oggetto, P._cornice(email, titolo, corpo))
        try:
            db.registra_evento("feedback_richiesto" if not promemoria else "feedback_promemoria", id_dashboard, {})
        except Exception:
            pass
        return True
    except Exception:
        db.annulla_promemoria(email, tipo, "1")
        raise


def invia(prova: bool = False, gia: set | None = None) -> dict:
    """Passaggio giornaliero: richieste di feedback e promemoria. `gia` = email che hanno gia' ricevuto
    un'altra email in questo passaggio (al massimo una email per utente per passaggio)."""
    gia = gia if gia is not None else set()
    esito = {"mandati": 0, "previsti": [], "falliti": [], "email": set()}
    for elenco, promemoria in ((db.utenti_feedback_da_mandare(), False), (db.utenti_feedback_reminder(), True)):
        for r in elenco:
            if r["email"] in gia or r["email"] in esito["email"]:
                continue
            if prova:
                esito["previsti"].append({"email": r["email"], "tipo": "feedback_reminder" if promemoria else "feedback",
                                          "chiave": "1"})
                esito["email"].add(r["email"])
                continue
            try:
                if manda(r["email"], r["dashboard_id"], promemoria):
                    esito["mandati"] += 1
                    esito["email"].add(r["email"])
            except Exception as e:
                esito["falliti"].append({"email": r["email"], "errore": str(e)[:120]})
    return esito


# ------------------------------------------------------------------ salvataggio

def salva(email: str, token: str, consiglia: str, risposte: dict, commento: str, ricontatto: bool) -> dict:
    import promemoria as P
    if not P.firma_valida(email, token):
        return {"ok": False, "errore": "Link non valido."}
    if consiglia not in ("si", "no"):
        return {"ok": False, "errore": "Scegli se consiglieresti TaxScan."}
    pulite = {}
    for q in DOMANDE:
        v = (risposte or {}).get(q["id"])
        valide = [o[0] for o in q["opzioni"]]
        if q["tipo"] == "multi":
            v = [x for x in (v if isinstance(v, list) else []) if x in valide][:len(valide)]
        else:
            v = v if v in valide else None
        if v:
            pulite[q["id"]] = v
    testo = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(commento or "")).strip()[:1000]
    id_dash = db.dashboard_di_utente(email) or ""
    db.salva_feedback(email, id_dash, consiglia, pulite, testo, bool(ricontatto))
    try:
        db.registra_evento("feedback_inviato", id_dash, {"consiglia": consiglia})
    except Exception:
        pass
    return {"ok": True}


# ------------------------------------------------------------------ pagine

_CSS = """
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{--bg:#eef2f8;--card:#fff;--ink:#122452;--ink2:#3d4a73;--line:#d8e2ed;--accent:#4355cc;--soft:#e8ebfa;--teal:#05d5c8;
--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#0a1330;--card:#122452;--ink:#fff;--ink2:#c9d3ec;--line:#25397a;--accent:#5566dd;--soft:#1c3070}}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-txt);padding:16px 16px 48px;max-width:560px;margin:0 auto}
h1,h2{font-family:var(--f-tit)} h1{font-size:24px;margin:10px 0 4px;line-height:1.2}
.logo{font-family:var(--f-tit);font-weight:800;font-size:20px;margin:6px 0 14px}.logo span{color:var(--accent)}
.sub{color:var(--ink2)}
.card{background:var(--card);border:1px solid var(--line);padding:18px;margin:14px 0}
h2{font-size:16px;margin-bottom:10px}
.opz{display:flex;flex-wrap:wrap;gap:8px}
.opz button{font:inherit;font-size:14px;padding:10px 14px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;text-align:left}
.opz button[aria-pressed="true"]{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:700}
.due button{flex:1;font-size:16px;padding:14px;text-align:center}
textarea{width:100%;min-height:96px;padding:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;resize:vertical}
label.chk{display:flex;gap:10px;align-items:flex-start;margin-top:12px;font-size:14px;color:var(--ink2)}
label.chk input{margin-top:4px;width:18px;height:18px;accent-color:var(--accent)}
.invia{width:100%;border:0;background:var(--accent);color:#fff;font:inherit;font-weight:700;padding:15px;cursor:pointer;margin-top:6px}
.invia[disabled]{opacity:.6}
.msg{font-size:14px;color:var(--ink2);margin-top:10px;min-height:20px}
.nota{font-size:13px;color:var(--ink2)} a{color:var(--accent)}
.prog{height:6px;background:var(--line);margin:14px 0 6px}.prog div{height:100%;background:var(--accent);transition:width .3s}
.ind{background:none;border:0;color:var(--accent);font:inherit;font-size:14px;cursor:pointer;padding:6px 0}
.an{animation:ent .25s ease-out}@keyframes ent{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.ok{background:var(--teal);color:#122452;padding:22px;margin:18px 0}.ok h1{margin-top:0}
"""


def pagina(email: str, token: str, r: str = "") -> str:
    import promemoria as P
    if not P.firma_valida(email, token):
        return (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<style>{_CSS}</style><body><div class='logo'>Tax<span>Scan</span></div><h1>Link non valido</h1>"
                "<p class='sub'>Questo link non funziona. Se vuoi dirci cosa ne pensi scrivici a info@ltd24ore.com.</p></body>")
    prec = db.feedback_di(email) or {}
    dati = json.dumps({"domande": DOMANDE, "e": email, "t": token,
                       "r": prec.get("consiglia") or (r if r in ("si", "no") else ""),
                       "risposte": prec.get("risposte") or {}, "commento": prec.get("commento") or "",
                       "ricontatto": bool(prec.get("ricontatto")), "gia": bool(prec)},
                      ensure_ascii=False).replace("</", "<\\/")
    titolo = "Grazie, puoi aggiornare la risposta" if prec else "Due minuti per dirci com'è andata"
    testa = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Cosa ne pensi - TaxScan</title>
<style>{_CSS}</style></head><body>
<div class="logo">Tax<span>Scan</span></div>
<h1>{titolo}</h1>
<div id="app"></div>
<p class="nota" style="margin-top:22px">Le risposte sono collegate alla tua email, solo per poterti rispondere: le leggiamo noi
di TaxScan e LTD24. <a href="/privacy">Come trattiamo i dati</a>.</p>
"""
    return testa + """<script>
const D=__DATI__;
function h(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
const S={r:D.r,risposte:JSON.parse(JSON.stringify(D.risposte)),ricontatto:D.ricontatto,commento:D.commento};
const N=D.domande.length+2;            // 1 si/no + domande + testo libero
let i=(D.r&&!D.gia)?1:0;               // se arriva dal pulsante dell'email, la prima risposta e' gia' data
function barra(){return '<div class="prog"><div style="width:'+Math.round((i+1)/N*100)+'%"></div></div><p class="nota">Domanda '+(i+1)+' di '+N+'</p>'}
function indietro(){return i>0?'<button class="ind" id="ind">&larr; Indietro</button>':''}
function vai(n){i=n;disegna()}
function disegna(){
  let x=barra();
  if(i===0){
    x+='<div class="card an"><h2>Consiglieresti TaxScan a un collega con la partita IVA?</h2><div class="opz due">'
      +'<button data-r="si" aria-pressed="'+(S.r==="si")+'">Sì</button><button data-r="no" aria-pressed="'+(S.r==="no")+'">No</button></div></div>';
  }else if(i<=D.domande.length){
    const q=D.domande[i-1],multi=q.tipo==='multi';
    x+='<div class="card an"><h2>'+h(q.testo)+(multi?' <span class="nota">(anche più di una)</span>':'')+'</h2><div class="opz">'
      +q.opzioni.map(o=>{const sel=multi?(S.risposte[q.id]||[]).includes(o[0]):S.risposte[q.id]===o[0];
        return '<button data-v="'+o[0]+'" aria-pressed="'+sel+'">'+h(o[1])+'</button>'}).join('')+'</div>'
      +(multi?'<button class="invia" id="avanti">Avanti</button>':'')+'</div>';
  }else{
    x+='<div class="card an"><h2>Vuoi dirci altro? <span class="nota">(facoltativo)</span></h2><textarea id="com" maxlength="1000" placeholder="Cosa cambieresti, cosa ti ha colpito, cosa non hai capito...">'+h(S.commento)+'</textarea>'
      +'<label class="chk"><input type="checkbox" id="ric"'+(S.ricontatto?' checked':'')+'><span>Va bene se mi scrivete via email per approfondire.</span></label>'
      +'<button class="invia" id="invia">Invia</button><p class="msg" id="msg"></p></div>';
  }
  x+=indietro();
  document.getElementById('app').innerHTML=x;
  const ind=document.getElementById('ind');if(ind)ind.onclick=()=>{salvaTesto();vai(i-1)};
  if(i===0){document.querySelectorAll('[data-r]').forEach(b=>b.onclick=()=>{S.r=b.dataset.r;disegna();setTimeout(()=>vai(1),220)})}
  else if(i<=D.domande.length){
    const q=D.domande[i-1];
    document.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>{
      const v=b.dataset.v;
      if(q.tipo==='multi'){const a=S.risposte[q.id]||[];S.risposte[q.id]=a.includes(v)?a.filter(z=>z!==v):a.concat(v);disegna()}
      else{S.risposte[q.id]=v;disegna();setTimeout(()=>vai(i+1),220)}});
    const av=document.getElementById('avanti');if(av)av.onclick=()=>vai(i+1);
  }else{document.getElementById('invia').onclick=invia}
}
function salvaTesto(){const c=document.getElementById('com'),r=document.getElementById('ric');if(c)S.commento=c.value;if(r)S.ricontatto=r.checked}
async function invia(){
  salvaTesto();
  const m=document.getElementById('msg'),b=document.getElementById('invia');
  if(!S.r){vai(0);return}
  b.disabled=true;m.textContent='Invio...';
  try{
    const r=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({e:D.e,t:D.t,r:S.r,risposte:S.risposte,commento:S.commento,ricontatto:S.ricontatto})});
    const j=await r.json();
    if(!j.ok){m.textContent=j.errore||'Non sono riuscito a salvare, riprova.';b.disabled=false;return}
    document.getElementById('app').innerHTML='<div class="ok"><h1>Grazie!</h1><p>Abbiamo ricevuto la tua risposta: ci aiuta a migliorare TaxScan. Se ti viene in mente altro, riapri il link che ti abbiamo scritto e aggiorna.</p></div><p><a href="/accedi">Torna a TaxScan</a></p>';
  }catch(e){m.textContent='Connessione assente, riprova.';b.disabled=false}
}
disegna();
</script></body></html>""".replace("__DATI__", dati)


def pagina_admin(riep: dict) -> str:
    risposte = riep["risposte"]
    n = len(risposte)
    si = sum(1 for r in risposte if r["consiglia"] == "si")

    def conteggi(qid):
        c = {}
        for r in risposte:
            v = r["risposte"].get(qid)
            for x in (v if isinstance(v, list) else ([v] if v else [])):
                c[x] = c.get(x, 0) + 1
        return sorted(c.items(), key=lambda kv: -kv[1])

    def blocco(q):
        righe = "".join(
            f"<tr><td>{_e(_ETICHETTE[q['id']].get(k, k))}</td><td>{v}</td>"
            f"<td><div style='background:#4355cc;height:10px;width:{int(100 * v / max(1, n))}%'></div></td></tr>"
            for k, v in conteggi(q["id"]))
        return f"<h2>{_e(q['testo'])}</h2><table>{righe or '<tr><td>Nessun dato</td></tr>'}</table>"

    lista = "".join(
        f"<tr><td>{_e(r['risposto_il'][:10])}</td><td>{_e(r['email'])}</td><td>{'Sì' if r['consiglia'] == 'si' else 'No'}</td>"
        f"<td>{_e(r['commento'])}</td><td>{'sì' if r['ricontatto'] else ''}</td></tr>" for r in risposte)
    dc = "".join(
        f"<tr><td>{_e(r['invitato_il'][:10])}</td><td>{_e(r['email'])}</td>"
        f"<td>{'disiscritto: non scrivere' if r['disiscritto'] else 'può essere contattato'}</td></tr>"
        for r in riep["da_contattare"])
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Feedback - TaxScan</title>
<style>{_CSS} body{{max-width:900px}} table{{width:100%;border-collapse:collapse;background:var(--card);margin-bottom:8px}}
td,th{{padding:8px 10px;border-bottom:1px solid var(--line);font-size:14px;text-align:left;vertical-align:top}}</style></head><body>
<div class="logo">Tax<span>Scan</span> · feedback</div>
<h1>{n} risposte su {riep['inviati']} inviti</h1>
<p class="sub">Consiglierebbero TaxScan: <b>{si}</b> su {n}{f" ({round(100 * si / n)}%)" if n else ""}.</p>
{''.join(blocco(q) for q in DOMANDE)}
<h2>Risposte e commenti</h2>
<table><tr><th>Data</th><th>Email</th><th>Consiglia</th><th>Commento</th><th>Ok contatto</th></tr>{lista or '<tr><td colspan=5>Ancora nessuna risposta</td></tr>'}</table>
<h2>Da contattare di persona</h2>
<p class="nota">Non hanno risposto né alla richiesta né al promemoria.</p>
<table><tr><th>Invitato il</th><th>Email</th><th>Nota</th></tr>{dc or '<tr><td colspan=3>Nessuno per ora</td></tr>'}</table>
</body></html>"""
