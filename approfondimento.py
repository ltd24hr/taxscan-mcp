"""
TaxScan - questionario di approfondimento (circa 5 minuti), dopo l'iscrizione.

Flusso:
  1. circa 45 minuti dopo l'iscrizione parte una sola email (a chi non ha rifiutato le email con spunti):
     "completa la tua situazione in 5 minuti e vedi spunti su IMU, pensione, bandi e rateazione adatti a te";
  2. il link firmato apre /approfondisci: una domanda alla volta (si avanza toccando la risposta);
  3. alla fine le risposte si salvano (tabella approfondimento) e la stessa pagina mostra gli spunti per quella persona.
Gli spunti sono generali e prudenti (mai "ti spetta"): ogni voce dice di controllare la fonte ufficiale o di chiedere a un
professionista. Cifre sulla previdenza: stesse verificate per l'email sulla pensione (da ricontrollare ogni anno).
"""
import html as _html
import json

import db
import dashboard
import dati_fisco as D
import feedback as FB

PUBLIC_URL = dashboard.PUBLIC_URL

DOMANDE = [
    {"id": "immobili", "testo": "Hai immobili?", "tipo": "multi", "opzioni": [
        ["prima_casa", "La casa dove abito"], ["seconda_casa", "Una seconda casa"], ["affitto", "Immobili che affitto"],
        ["terreni", "Terreni o altro"], ["nessuno", "Nessun immobile"]]},
    {"id": "redditi", "testo": "Hai altri redditi, oltre alla partita IVA?", "tipo": "multi", "opzioni": [
        ["dipendente", "Lavoro dipendente"], ["pensione", "Pensione"], ["affitti", "Affitti"],
        ["nessuno", "No, solo la partita IVA"]]},
    {"id": "fondo", "testo": "Versi già a un fondo pensione?", "tipo": "uno", "opzioni": [
        ["si", "Sì"], ["no", "No"], ["nonso", "Non so cos'è"]]},
    {"id": "progetti", "testo": "Cosa pensi di fare nei prossimi 12 mesi?", "tipo": "multi", "opzioni": [
        ["assumere", "Assumere qualcuno"], ["attrezzature", "Comprare attrezzature o software"],
        ["sede", "Aprire o cambiare sede"], ["crescere", "Fatturare molto di più"], ["niente", "Niente di particolare"]]},
    {"id": "interesse", "testo": "Cosa ti interessa di più?", "tipo": "multi", "opzioni": [
        ["tasse", "Pagare meno tasse (nei limiti di legge)"], ["bandi", "Bandi e finanziamenti"],
        ["pensione", "Pensione"], ["immobili", "Immobili e IMU"]]},
]


def _e(x) -> str:
    return _html.escape(str(x if x is not None else ""))


def _link(email: str) -> str:
    import promemoria as P
    from urllib.parse import quote
    return f"{PUBLIC_URL}/approfondisci?e={quote(email)}&t={P.firma(email)}"


# ------------------------------------------------------------------ spunti per la persona

def consigli(r: dict, id_dashboard: str = "") -> list[dict]:
    """Spunti generali in base alle risposte. Ogni voce: titolo + testo (testo semplice)."""
    imm, red = set(r.get("immobili") or []), set(r.get("redditi") or [])
    prog, inte = set(r.get("progetti") or []), set(r.get("interesse") or [])
    fondo = r.get("fondo")
    out = []
    if "prima_casa" in imm:
        out.append({"titolo": "IMU sulla casa dove abiti",
                    "testo": "L'abitazione principale non di lusso (cioè non categorie A/1, A/8, A/9) di norma è esente da IMU: "
                             "controlla di non pagarla per errore. Se è di lusso si paga con aliquota e detrazione ridotte."})
    if "seconda_casa" in imm:
        out.append({"titolo": "IMU sulla seconda casa",
                    "testo": "Si paga in due rate (16 giugno e 16 dicembre) e l'aliquota la decide il tuo Comune: guardala sul sito comunale. "
                             "Se la dai in comodato a un parente in linea retta, in alcuni casi la base imponibile si riduce del 50%, "
                             "ma servono requisiti precisi."})
    if "affitto" in imm or "affitti" in red:
        out.append({"titolo": "Immobili affittati",
                    "testo": "Il reddito da affitto non rientra nel regime forfettario: si dichiara a parte. Con la cedolare secca "
                             "l'imposta sull'affitto è sostitutiva (di norma 21%, 10% per i canoni concordati nei casi previsti). "
                             "Conviene guardare il quadro completo prima di scegliere."})
    if imm & {"seconda_casa", "affitto", "terreni"}:
        out.append({"titolo": "Costi degli immobili e forfettario",
                    "testo": "Nel forfettario i costi non si deducono: in generale l'IMU su un immobile usato per l'attività non riduce "
                             "l'imposta sostitutiva. Per gli immobili affittati valgono regole separate."})
    altri = bool(red & {"dipendente", "pensione"})
    if altri:
        out.append({"titolo": "Fondo pensione: qui puoi dedurre",
                    "testo": "Hai altri redditi tassati con IRPEF (lavoro dipendente o pensione): i versamenti a un fondo pensione "
                             "possono essere dedotti da quel reddito, fino a 5.300 € l'anno dal 2026 (limite da verificare ogni anno). "
                             "I rendimenti sono tassati al 20% (12,5% sui titoli di Stato) e le prestazioni al 15%, ridotto fino al 9% "
                             "dopo 35 anni di partecipazione."})
    elif fondo != "si" and ("pensione" in inte or fondo == "nonso"):
        out.append({"titolo": "Pensione e fondo pensione",
                    "testo": "Come forfettario senza altri redditi IRPEF non puoi dedurre i versamenti al fondo: restano utili per la "
                             "pensione futura, ma senza sconto fiscale subito. I rendimenti sono tassati al 20% (12,5% sui titoli di "
                             "Stato) e le prestazioni al 15%, ridotto fino al 9% dopo 35 anni. Se versi, comunica al fondo entro il "
                             "31 dicembre dell'anno dopo i contributi non dedotti, per non pagarci le tasse due volte."})
    if fondo == "si" and not altri:
        out.append({"titolo": "Hai già un fondo pensione",
                    "testo": "Se non dedurrai i versamenti (forfettario senza altri redditi), comunica al fondo entro il 31 dicembre "
                             "dell'anno successivo i contributi non dedotti: così quella parte non viene tassata di nuovo all'uscita."})
    if prog & {"assumere", "attrezzature", "sede"} or "bandi" in inte:
        out.append({"titolo": "Bandi e finanziamenti",
                    "testo": "Per assunzioni, attrezzature o una nuova sede esistono spesso bandi e incentivi, nazionali e della tua "
                             "Regione. Una ricerca settimanale controlla quelli aperti: li trovi nella sezione bandi della tua pagina. "
                             "Sono spunti da verificare sul testo ufficiale."})
    if "crescere" in prog:
        out.append({"titolo": "Se fatturi molto di più",
                    "testo": "Tieni d'occhio la soglia degli 85.000 € all'anno: se la superi si esce dal forfettario dall'anno dopo; "
                             "oltre 100.000 € si esce subito, in corso d'anno. Nella tua pagina c'è il controllo della soglia."})
    if "tasse" in inte:
        out.append({"titolo": "Pagare meno tasse, in concreto",
                    "testo": "Nel forfettario le deduzioni contano poco: i margini veri sono altri. Saldo e primo acconto si possono "
                             "pagare a rate (c'è il bottone nella tua pagina, vicino all'F24), e vale la pena controllare di non "
                             "perdere la riduzione dei contributi INPS se sei artigiano o commerciante e rientri nei requisiti."})
    if not out:
        out.append({"titolo": "Grazie, abbiamo aggiornato la tua situazione",
                    "testo": "Dalle tue risposte non ci sono spunti particolari per ora. Se la tua situazione cambia, puoi rifare il "
                             "questionario dallo stesso link."})
    return out


# ------------------------------------------------------------------ email

def manda(email: str, id_dashboard: str) -> bool:
    """Una sola email di invito al questionario. False se disiscritto, senza consenso o gia' mandata."""
    import promemoria as P
    import auth
    email = (email or "").strip().lower()
    if not email or db.email_disattivate(email) or not db.novita_consentite(email):
        return False
    if not db.prenota_promemoria(email, "approfondimento", "1"):
        return False
    try:
        nome = FB._nome(id_dashboard)
        bottone = ("display:inline-block;padding:14px 30px;font-weight:700;text-decoration:none;"
                   "background:#4355cc;color:#ffffff")
        corpo = ((f"<p>Ciao {_e(nome)},</p>" if nome else "")
                 + "<p>La tua pagina è pronta, ma ci sono cose che non possiamo sapere: <b>immobili, altri redditi, fondo pensione, "
                   "progetti dei prossimi mesi</b>.</p>"
                   "<p><b>Rispondi a 5 domande a scelta (circa 5 minuti)</b> e ti mostriamo subito spunti su <b>IMU, pensione, "
                   "bandi e pagamento a rate</b> pensati per la tua situazione.</p>"
                 + f"<p style='margin:20px 0'><a href='{_e(_link(email))}' style='{bottone}'>Completa la mia situazione</a></p>"
                 + "<p style='font-size:14px;color:#3d4a73'>Sono spunti generali, non consulenza: se vuoi, un professionista "
                   "può controllarli con te. Le risposte restano collegate alla tua email e le puoi cambiare quando vuoi.</p>")
        auth.manda_email(email, "TaxScan: completa la tua situazione (5 minuti)",
                         P._cornice(email, "Completa la tua situazione", corpo))
        try:
            db.registra_evento("approfondimento_invito", id_dashboard, {})
        except Exception:
            pass
        return True
    except Exception:
        db.annulla_promemoria(email, "approfondimento", "1")
        raise


# ------------------------------------------------------------------ salvataggio

def salva(email: str, token: str, risposte: dict) -> dict:
    import promemoria as P
    if not P.firma_valida(email, token):
        return {"ok": False, "errore": "Link non valido."}
    pulite = {}
    for q in DOMANDE:
        v = (risposte or {}).get(q["id"])
        valide = [o[0] for o in q["opzioni"]]
        if q["tipo"] == "multi":
            v = [x for x in (v if isinstance(v, list) else []) if x in valide]
            if "nessuno" in v and len(v) > 1:
                v = [x for x in v if x != "nessuno"]
        else:
            v = v if v in valide else None
        if v:
            pulite[q["id"]] = v
    if not pulite:
        return {"ok": False, "errore": "Rispondi ad almeno una domanda."}
    db.salva_approfondimento(email, pulite)
    id_dash = db.dashboard_di_utente(email) or ""
    try:
        db.registra_evento("approfondimento_completato", id_dash, {})
    except Exception:
        pass
    return {"ok": True, "consigli": consigli(pulite, id_dash), "dashboard": f"{PUBLIC_URL}/d/{id_dash}" if id_dash else ""}


# ------------------------------------------------------------------ pagina

def pagina(email: str, token: str) -> str:
    import promemoria as P
    if not P.firma_valida(email, token):
        return (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<style>{FB._CSS}</style><body><div class='logo'>Tax<span>Scan</span></div><h1>Link non valido</h1>"
                "<p class='sub'>Questo link non funziona. Scrivici a info@ltd24ore.com.</p></body>")
    prec = db.approfondimento_di(email) or {}
    dati = json.dumps({"domande": DOMANDE, "e": email, "t": token, "risposte": prec,
                       "cons": D.CONTATTI["consulenza_gratuita"]}, ensure_ascii=False).replace("</", "<\\/")
    testa = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Completa la tua situazione - TaxScan</title>
<style>{FB._CSS}</style></head><body>
<div class="logo">Tax<span>Scan</span></div>
<h1>Completa la tua situazione</h1>
<p class="sub">5 domande, circa 5 minuti. Poi vedi gli spunti per te.</p>
<div id="app"></div>
<p class="nota" style="margin-top:22px">Le risposte sono collegate alla tua email e le usiamo per mostrarti spunti più adatti.
<a href="/privacy">Come trattiamo i dati</a>.</p>
"""
    return testa + """<script>
const D=__DATI__;
function h(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
const S=JSON.parse(JSON.stringify(D.risposte||{}));
const N=D.domande.length;let i=0;
function barra(){return '<div class="prog"><div style="width:'+Math.round((i+1)/N*100)+'%"></div></div><p class="nota">Domanda '+(i+1)+' di '+N+'</p>'}
function disegna(){
  const q=D.domande[i],multi=q.tipo==='multi';
  let x=barra()+'<div class="card an"><h2>'+h(q.testo)+(multi?' <span class="nota">(anche più di una)</span>':'')+'</h2><div class="opz">'
    +q.opzioni.map(o=>{const sel=multi?(S[q.id]||[]).includes(o[0]):S[q.id]===o[0];
      return '<button data-v="'+o[0]+'" aria-pressed="'+sel+'">'+h(o[1])+'</button>'}).join('')+'</div>'
    +(multi?'<button class="invia" id="avanti">'+(i===N-1?'Vedi i miei spunti':'Avanti')+'</button>':'')+'<p class="msg" id="msg"></p></div>'
    +(i>0?'<button class="ind" id="ind">&larr; Indietro</button>':'');
  document.getElementById('app').innerHTML=x;
  const ind=document.getElementById('ind');if(ind)ind.onclick=()=>{i--;disegna()};
  document.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>{
    const v=b.dataset.v;
    if(multi){let a=S[q.id]||[];
      if(v==='nessuno')a=a.includes(v)?[]:['nessuno'];
      else{a=a.filter(z=>z!=='nessuno');a=a.includes(v)?a.filter(z=>z!==v):a.concat(v)}
      S[q.id]=a;disegna()}
    else{S[q.id]=v;disegna();setTimeout(avanza,220)}});
  const av=document.getElementById('avanti');if(av)av.onclick=avanza;
}
function avanza(){if(i<N-1){i++;disegna()}else fine()}
async function fine(){
  const m=document.getElementById('msg');if(m)m.textContent='Un attimo...';
  try{
    const r=await fetch('/api/approfondisci',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({e:D.e,t:D.t,risposte:S})});
    const j=await r.json();
    if(!j.ok){if(m)m.textContent=j.errore||'Non sono riuscito a salvare, riprova.';return}
    document.getElementById('app').innerHTML='<div class="ok"><svg class="fatto" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="22"/><path pathLength="1" d="M14.5 24.5l6.5 6.5 12.5-13.5"/></svg><h1>Fatto, grazie!</h1><p>Ecco gli spunti per la tua situazione.</p></div>'
      +j.consigli.map(c=>'<div class="card an"><h2>'+h(c.titolo)+'</h2><p>'+h(c.testo)+'</p></div>').join('')
      +'<p class="nota">Sono spunti generali, non consulenza: le cifre e le regole vanno verificate. Se vuoi guardarli con un professionista c\\'è la <a href="'+h(D.cons)+'">consulenza gratuita</a> di LTD24.</p>'
      +(j.dashboard?'<p style="margin-top:14px"><a class="invia" style="display:block;text-align:center;text-decoration:none" href="'+h(j.dashboard)+'">Torna alla tua pagina</a></p>':'');
  }catch(e){if(m)m.textContent='Connessione assente, riprova.'}
}
disegna();
</script></body></html>""".replace("__DATI__", dati)
