"""
TaxScan - il colloquio come pagina web con pulsanti veri.

Perché: dentro la chat di Claude un connettore personalizzato non può mostrare pulsanti (le
"MCP Apps" sono rese solo per i connettori del catalogo ufficiale, ottobre 2026). Gli utenti
però vogliono toccare una risposta, non scriverla. Quindi il colloquio vive anche su una pagina:
il connettore genera un link (come per il calendario), l'utente risponde con i pulsanti, carica
il certificato di attribuzione se ce l'ha, e torna nella chat dove Claude trova la scheda pronta.

Le domande NON sono duplicate: la pagina chiede al server, passo per passo, "qual è la prossima
domanda?" e il server risponde con scheda.verifica_scheda - le stesse domande, le stesse opzioni,
le stesse deduzioni del colloquio in chat. Se un giorno Claude.ai aprirà le MCP Apps ai
connettori personalizzati, questa stessa pagina può spostarsi dentro la chat.

Rotte (registrate in server.py):
  GET  /colloquio/nuovo                 crea un colloquio e rimanda alla sua pagina
  GET  /colloquio/{id}                  la pagina
  GET  /api/colloquio/{id}              stato + prossima domanda
  POST /api/colloquio/{id}              {"scheda": {...}} → salva e restituisce la prossima domanda
  POST /api/colloquio/{id}/certificato  {"pdf_base64": "..."} → legge il certificato di attribuzione
"""

import base64
import io
import os
import re
import secrets
import string

import dashboard
import db
import scheda as S

PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://taxscan-mcp.onrender.com").rstrip("/")
_ALFABETO = string.ascii_letters + string.digits


def nuovo_id() -> str:
    return "".join(secrets.choice(_ALFABETO) for _ in range(12))


def crea_colloquio() -> dict:
    """Crea un colloquio vuoto e restituisce id e link della pagina."""
    id_colloquio = nuovo_id()
    db.crea_colloquio_web(id_colloquio)
    return {"id_colloquio": id_colloquio, "link": f"{PUBLIC_URL}/colloquio/{id_colloquio}"}


def _etichette() -> dict:
    """Etichette leggibili per i valori a scelta, per il riepilogo della pagina (unica fonte: scheda.py)."""
    out = {"tipo_attivita": dict(S.ETICHETTE_TIPO), "gestione_previdenziale": dict(S.ETICHETTE_GESTIONE)}
    for c in S.CAMPI:
        if isinstance(c.get("opzioni"), list):
            out[c["chiave"]] = {v: e for v, e in c["opzioni"]}
    return out


def _evento(tipo: str, riferimento: str | None = None, dettaglio: dict | None = None) -> None:
    """Traccia l'uso senza mai rompere il flusso."""
    try:
        db.registra_evento(tipo, riferimento, dettaglio)
    except Exception:
        pass


def _link_dashboard(id_colloquio: str, stato: str) -> str | None:
    """Percorso della dashboard di questo colloquio, se esiste (ha lo stesso id del colloquio)."""
    if stato != "completato":
        return None
    try:
        return f"/d/{id_colloquio}" if dashboard.dati_dashboard(id_colloquio) is not None else None
    except Exception:
        return None


def stato_colloquio(id_colloquio: str) -> dict | None:
    """Scheda salvata, stato e prossima domanda (via verifica_scheda). None se l'id non esiste."""
    riga = db.carica_colloquio_web(id_colloquio)
    if riga is None:
        return None
    if riga["stato"] == "aperto" and not riga["scheda"]:
        _evento("web_aperto", id_colloquio)
    verifica = S.verifica_scheda(riga["scheda"])
    return {"id_colloquio": id_colloquio, "stato": riga["stato"], "scheda": riga["scheda"],
            "verifica": verifica, "etichette": _etichette(), "settori": S.SETTORI_RAPIDI,
            "dashboard": _link_dashboard(id_colloquio, riga["stato"])}


def registra_risposte(id_colloquio: str, scheda_utente: dict) -> dict | None:
    """Salva la scheda così com'è (normalizzata) e restituisce la prossima domanda."""
    if db.carica_colloquio_web(id_colloquio) is None:
        return None
    verifica = S.verifica_scheda(scheda_utente or {})
    normalizzata = verifica["scheda_normalizzata"]
    # testo libero della descrizione attività (quando non si conosce l'ATECO) va conservato
    for extra in ("descrizione_attivita", "codice_ateco_da_trovare", "nota_utente", "comune", "provincia",
                  "descrizione_attivita_certificato", "codice_ateco_stimato"):
        if (scheda_utente or {}).get(extra) is not None:
            normalizzata[extra] = scheda_utente[extra]
    nome = S.pulisci_nome((scheda_utente or {}).get("nome"))
    if nome:
        normalizzata["nome"] = nome
    if verifica["completa"]:
        stato = "completato"
        _evento("web_completato", id_colloquio)
    elif normalizzata.get("codice_ateco_da_trovare"):
        stato = "da_completare_in_chat"
        _evento("web_completato", id_colloquio, {"ateco_da_trovare": True})
    else:
        stato = "aperto"
        _evento("web_domanda", id_colloquio, {"campo": verifica.get("campo_prossimo")})
    db.salva_colloquio_web(id_colloquio, normalizzata, stato)
    link = None
    if stato == "completato":
        # La dashboard ha lo stesso id del colloquio: il link della pagina resta la "casa" dell'utente.
        try:
            esito = dashboard.crea_dashboard(normalizzata, 0.0, id_dashboard=id_colloquio)
            if "errore" not in esito:
                link = f"/d/{id_colloquio}"
                _evento("dashboard_creata", id_colloquio, {"stato": esito.get("stato"), "da": "web"})
        except Exception as e:
            print(f"dashboard non creata per {id_colloquio}: {e}")
    return {"id_colloquio": id_colloquio, "stato": stato, "scheda": normalizzata, "verifica": verifica,
            "etichette": _etichette(), "settori": S.SETTORI_RAPIDI, "dashboard": link}


# --------------------------------------------------------------------- certificato PDF

# Tarato sul certificato vero rilasciato via Entratel (ottobre 2026), che ha questo aspetto:
#   P.IVA: 10702731216    INIZIO ATTIVITA' DEL 02-01-2025
#   TIPO ATTIVITA': 702209 - ALTRE ATTIVITA' DI CONSULENZA AMMINISTRATIVA
#   DOMICILIO FISCALE:       COMUNE: NAPOLI                            PROV: NA
#   CODICE FISCALE TITOLARE: ZZIMCL90B15F839W
# e sulle varianti con "Partita IVA", "Codice attività: 96.02.02", "Data inizio attività: 10/02/2025".
_RE_PIVA = re.compile(r"(?:partita\s*i\.?v\.?a\.?|p\.?\s*iva)\D{0,60}?(\d{11})", re.I | re.S)
_RE_CF = re.compile(r"\b([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])\b")
_RE_CF_TITOLARE = re.compile(r"codice\s*fiscale\s*(?:del\s*)?(?:titolare|contribuente)\D{0,30}?([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])", re.I | re.S)
_RE_ATECO = re.compile(r"(?:codice\s*(?:di\s*)?attivit|tipo\s*attivit|ateco)[^\d\n]{0,80}?(\d{2}\.\d{2}\.\d{2}|\d{2}\.\d{2}\.\d|\d{2}\.\d{2}|\d{6})(?:\s*-\s*([^\n]{3,80}))?", re.I | re.S)
_RE_ATECO_LIBERO = re.compile(r"\b(\d{2}\.\d{2}\.\d{2})\b")
_RE_DATA_INIZIO = re.compile(r"inizio\s*attivit[àa']*\D{0,60}?(\d{2}[/.-]\d{2}[/.-]\d{4})", re.I | re.S)
_RE_DATA_LIBERA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_RE_COMUNE = re.compile(r"comune\s*:\s*([A-ZÀ-Ü' ]{2,40}?)\s{2,}", re.I)
# nome di battesimo: "NOME: MARIO" (e "COGNOME: ROSSI" a parte). Solo il nome, il cognome non si conserva.
_RE_NOME = re.compile(r"(?<![A-Za-z])(?i:nome)\s*:\s*([A-ZÀ-Ü'][A-ZÀ-Ü']+)(?: [A-ZÀ-Ü'][A-ZÀ-Ü']+)?(?=\s{2,}|\s*\n|\s*$)")
_RE_PROV = re.compile(r"prov(?:incia)?\.?\s*:\s*([A-Z]{2})\b", re.I)


def _formatta_ateco(grezzo: str) -> str:
    cifre = grezzo.replace(".", "")
    if len(cifre) == 6 and cifre.isdigit():
        return f"{cifre[:2]}.{cifre[2:4]}.{cifre[4:]}"
    return grezzo


def _estrai_testo_pdf(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader  # import qui: il server parte anche se pypdf manca
    lettore = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((pagina.extract_text() or "") for pagina in lettore.pages)


def leggi_certificato(pdf_bytes: bytes) -> dict:
    """Lettura best-effort del certificato di attribuzione della partita IVA (PDF dell'Agenzia
    delle Entrate): partita IVA, codice fiscale del titolare, codice ATECO, data di inizio attività.
    Restituisce solo quello che trova; il resto si chiede. Da tarare su certificati veri."""
    try:
        testo = _estrai_testo_pdf(pdf_bytes)
    except Exception as e:
        return {"trovati": {}, "errore": f"PDF non leggibile: {e}"}
    if not testo.strip():
        return {"trovati": {}, "errore": "Il PDF sembra una scansione senza testo: rispondi alle domande."}
    trovati = {}
    m = _RE_PIVA.search(testo)
    if m:
        trovati["partita_iva"] = m.group(1)
    m = _RE_ATECO.search(testo)
    if m:
        trovati["codice_ateco"] = _formatta_ateco(m.group(1))
        if m.group(2):
            descr = " ".join(m.group(2).split()).strip(" -")
            trovati["descrizione_attivita_certificato"] = descr.lower().capitalize()
    else:
        m = _RE_ATECO_LIBERO.search(testo)
        if m:
            trovati["codice_ateco"] = m.group(1)
    m = _RE_DATA_INIZIO.search(testo) or _RE_DATA_LIBERA.search(testo)
    if m:
        g, me, a = re.split(r"[/.-]", m.group(1))
        trovati["data_apertura"] = f"{a}-{me}-{g}"
    m = _RE_CF_TITOLARE.search(testo)
    if m:
        trovati["codice_fiscale"] = m.group(1).upper()
    else:
        codici = []
        for cf in _RE_CF.findall(testo.upper()):
            if cf not in codici:
                codici.append(cf)
        if codici:
            # nel certificato trasmesso da un intermediario c'è anche il CF del commercialista: compare
            # per primo (ricevuta di trasmissione). Se ce ne sono due, il titolare è l'ultimo.
            trovati["codice_fiscale"] = codici[-1]
            if len(codici) > 1:
                trovati["codici_fiscali_trovati"] = codici
    m = _RE_NOME.search(testo)
    if m:
        nome = S.pulisci_nome(m.group(1))
        if nome:
            trovati["nome"] = nome
    m = _RE_COMUNE.search(testo)
    if m:
        trovati["comune"] = m.group(1).strip().title()
    m = _RE_PROV.search(testo)
    if m:
        trovati["provincia"] = m.group(1).upper()
    return {"trovati": trovati, "caratteri_letti": len(testo)}


# --------------------------------------------------------------------- pagina

PAGINA_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TaxScan - la tua situazione in 2 minuti</title>
<style>
  :root { --verde:#0f4c3a; --verde-chiaro:#e6f2ee; --grigio:#5b6770; --bordo:#d9dee3; --testo:#1a1a1a; --fondo:#f6f7f8; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--fondo); color:var(--testo); }
  .pagina { max-width:560px; margin:0 auto; padding:20px 16px 60px; }
  header { display:flex; align-items:center; justify-content:space-between; margin-bottom:18px; }
  header .logo { font-weight:700; color:var(--verde); font-size:18px; letter-spacing:.2px; }
  header .passo { color:var(--grigio); font-size:13px; }
  header button.fatto { font:inherit; font-size:14px; font-weight:600; padding:8px 14px; border-radius:10px; border:none; background:var(--verde); color:#fff; cursor:pointer; }
  .barra { height:6px; background:#e3e7ea; border-radius:3px; overflow:hidden; margin-bottom:28px; }
  .barra > div { height:100%; background:var(--verde); width:0; transition:width .3s; }
  .scheda { background:#fff; border:1px solid var(--bordo); border-radius:14px; padding:22px 18px; box-shadow:0 1px 2px rgba(0,0,0,.04); }
  h1 { font-size:21px; line-height:1.3; margin:0 0 6px; }
  p { line-height:1.5; margin:8px 0; }
  .hint { color:var(--grigio); font-size:14px; }
  .opzioni { display:flex; flex-direction:column; gap:10px; margin-top:18px; }
  button.opz, label.opz { display:flex; align-items:center; gap:12px; width:100%; text-align:left; font:inherit; font-size:16px;
    padding:14px 16px; border:1.5px solid var(--bordo); background:#fff; border-radius:12px; cursor:pointer; color:var(--testo); }
  button.opz:hover, label.opz:hover { border-color:var(--verde); background:var(--verde-chiaro); }
  button.opz .n, label.opz .n { flex:0 0 28px; height:28px; border-radius:50%; background:var(--verde-chiaro); color:var(--verde); font-weight:700;
    display:flex; align-items:center; justify-content:center; font-size:14px; }
  label.opz input { width:20px; height:20px; accent-color:var(--verde); }
  label.opz.sel { border-color:var(--verde); background:var(--verde-chiaro); }
  input.testo { width:100%; font:inherit; font-size:18px; padding:14px; border:1.5px solid var(--bordo); border-radius:12px; margin-top:14px; }
  input.testo:focus { outline:none; border-color:var(--verde); }
  .riga { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
  button.primario, button.secondario, label.primario { font:inherit; font-size:16px; padding:13px 18px; border-radius:12px; cursor:pointer; border:1.5px solid var(--verde); }
  button.primario, label.primario { background:var(--verde); color:#fff; flex:1; text-align:center; }
  button.secondario { background:#fff; color:var(--verde); }
  button.link { background:none; border:none; color:var(--grigio); font:inherit; font-size:14px; cursor:pointer; padding:8px 0; text-decoration:underline; }
  .trovato { background:var(--verde-chiaro); border-radius:10px; padding:12px 14px; margin-top:14px; font-size:15px; }
  .errore { background:#fdecec; color:#8a1f1f; border-radius:10px; padding:12px 14px; margin-top:14px; font-size:15px; }
  .riepilogo { margin-top:16px; font-size:15px; }
  .riepilogo div { padding:8px 0; border-bottom:1px solid #eef1f3; display:flex; justify-content:space-between; gap:12px; }
  .riepilogo div span:last-child { color:var(--grigio); text-align:right; }
  .gruppo { margin-top:16px; }
  .gruppo h3 { font-size:15px; margin:0 0 8px; color:var(--grigio); font-weight:600; }
  .nascosto { display:none; }
  footer { color:var(--grigio); font-size:12px; margin-top:22px; text-align:center; line-height:1.5; }
</style>
</head>
<body>
<div class="pagina">
  <header><div class="logo">TaxScan</div><div class="passo" id="passo"></div></header>
  <div class="barra"><div id="barra"></div></div>
  <div class="scheda" id="scheda"><p class="hint">Un attimo...</p></div>
  <div class="riga" id="nav"></div>
  <footer>TaxScan prepara e spiega: il professionista controlla e firma. Niente di quello che scrivi qui è una dichiarazione fiscale. <a href="/privacy" style="color:inherit">Privacy</a></footer>
  <p class="by" style="font-size:12px;color:#7c7a74;margin-top:10px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">TaxScan è un servizio offerto da <a href="https://ltd24.co.uk" target="_blank" rel="noopener" style="display:inline-flex;font-weight:700;color:inherit;text-decoration:none"><img src="/logo-ltd24.png" alt="LTD24" style="height:20px;width:auto" onerror="this.replaceWith(document.createTextNode('LTD24'))"></a></p>
</div>
<script>
const ID = "{{ID}}";
const API = "/api/colloquio/" + ID;
let scheda = {};
let storia = [];        // snapshot della scheda prima di ogni risposta, per "indietro"
let ultima = null;      // ultima risposta del server
let fase = "intro";     // intro | domanda | correzione | fine
const PASSI_STIMATI = 7;
let passo = 0;

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function barra(frazione) { $("barra").style.width = Math.round(Math.min(1, frazione) * 100) + "%"; }

async function api(metodo, corpo, suffisso = "") {
  const r = await fetch(API + suffisso, { method: metodo, headers: {"Content-Type": "application/json"},
                                           body: corpo ? JSON.stringify(corpo) : undefined });
  if (!r.ok) throw new Error("Errore " + r.status);
  return r.json();
}

function nav(bottoni) {
  const n = $("nav"); n.innerHTML = "";
  bottoni.forEach(b => { const el = document.createElement("button"); el.className = b.classe || "secondario";
    el.textContent = b.testo; el.onclick = b.azione; n.appendChild(el); });
}

function indietro() {
  if (!storia.length) { fase = "intro"; mostraIntro(); return; }
  scheda = storia.pop(); passo = Math.max(0, passo - 1);
  invia();
}

// ---------------------------------------------------------------- intro
function mostraIntro() {
  $("passo").textContent = ""; barra(0.05);
  $("scheda").innerHTML = `
    <h1>La tua situazione fiscale in 2 minuti</h1>
    <p>Rispondi toccando le risposte. Nessuna domanda difficile: quello che si può capire da solo, lo capisce TaxScan.</p>
    <p class="hint">Se hai il <b>certificato di attribuzione della partita IVA</b> (PDF dell'Agenzia delle Entrate), caricalo: leggo io codice ATECO, data di apertura e partita IVA.</p>
    <div class="opzioni">
      <label class="opz" for="pdf"><span class="n">1</span><span>Carico il certificato di attribuzione (PDF)</span></label>
      <input type="file" id="pdf" accept="application/pdf" class="nascosto">
      <button class="opz" id="senza"><span class="n">2</span><span>Non ce l'ho sotto mano: rispondo a un paio di domande</span></button>
    </div>
    <div id="esito"></div>`;
  nav([]);
  $("pdf").onchange = caricaCertificato;
  $("senza").onclick = () => { fase = "domanda"; invia(); };
}

async function caricaCertificato(ev) {
  const file = ev.target.files[0]; if (!file) return;
  $("esito").innerHTML = '<p class="hint">Leggo il certificato...</p>';
  const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(",")[1]); fr.readAsDataURL(file); });
  try {
    const r = await api("POST", {pdf_base64: b64}, "/certificato");
    const t = r.trovati || {};
    if (!Object.keys(t).length) {
      $("esito").innerHTML = `<div class="errore">${esc(r.errore || "Non sono riuscito a leggere i dati dal certificato.")} Nessun problema: ti faccio due domande.</div>`;
      setTimeout(() => { fase = "domanda"; invia(); }, 1800); return;
    }
    const righe = [];
    if (t.codice_ateco) righe.push("Codice ATECO: <b>" + esc(t.codice_ateco) + "</b>" + (t.descrizione_attivita_certificato ? " - " + esc(t.descrizione_attivita_certificato) : ""));
    if (t.data_apertura) righe.push("Apertura: <b>" + esc(t.data_apertura.split("-").reverse().join("/")) + "</b>");
    if (t.nome) righe.push("Nome: <b>" + esc(t.nome) + "</b>");
    if (t.partita_iva) righe.push("Partita IVA: <b>" + esc(t.partita_iva) + "</b>");
    if (t.comune) righe.push("Domicilio fiscale: <b>" + esc(t.comune) + (t.provincia ? " (" + esc(t.provincia) + ")" : "") + "</b>");
    $("esito").innerHTML = `<div class="trovato">Ho letto dal certificato:<br>${righe.join("<br>")}</div>`;
    Object.assign(scheda, t);
    setTimeout(() => { fase = "domanda"; invia(); }, 1400);
  } catch (e) {
    $("esito").innerHTML = `<div class="errore">Non sono riuscito a leggere il file. Ti faccio due domande.</div>`;
    setTimeout(() => { fase = "domanda"; invia(); }, 1800);
  }
}

// ---------------------------------------------------------------- ciclo domanda → risposta
async function invia() {
  $("scheda").innerHTML = '<p class="hint">Un attimo...</p>'; nav([]);
  try { ultima = await api("POST", {scheda}); } catch (e) { $("scheda").innerHTML = '<div class="errore">Connessione persa: riprova tra un momento.</div>'; return; }
  scheda = ultima.scheda;
  if (ultima.stato === "da_completare_in_chat") return mostraFine(true);
  if (ultima.verifica.completa) return mostraFine(false);
  mostraDomanda(ultima.verifica);
}

function rispondi(aggiornamenti) {
  storia.push(JSON.parse(JSON.stringify(scheda)));
  Object.assign(scheda, aggiornamenti); passo += 1;
  invia();
}

function mostraDomanda(v) {
  fase = "domanda";
  const campo = v.campo_prossimo;
  $("passo").textContent = "Domanda " + (passo + 1); barra(0.1 + 0.85 * (passo / PASSI_STIMATI));
  const box = $("scheda");
  const opz = v.opzioni || [];
  let html = `<h1>${esc(v.prossima_domanda)}</h1>`;
  if (v.dove_trovarlo) html += `<p class="hint">${esc(v.dove_trovarlo)}</p>`;

  if (campo === "conferma_deduzioni" || (campo === "gestione_previdenziale" && v.proposta_deduzioni)) {
    if (campo === "conferma_deduzioni") {
      const d = v.proposta_deduzioni || {};
      const anni = d.anni_nel_regime === 0 ? "primo anno" : d.anni_nel_regime === 1 ? "da un anno" : d.anni_nel_regime != null ? `da ${d.anni_nel_regime} anni` : "";
      const righe = [["Attività", d.descrizione_attivita], ["Codice ATECO", d.codice_ateco], ["Tipo", d.tipo_attivita_etichetta],
                     ["Previdenza", d.gestione_previdenziale_etichetta], ["Partita IVA aperta nel", d.anno_apertura], ["Nel forfettario", anni]];
      html = `<h1>Ho capito così. Giusto?</h1><div class="riepilogo">` +
        righe.filter(r => r[1]).map(r => `<div><span>${esc(r[0])}</span><span>${esc(r[1])}</span></div>`).join("") + "</div>";
    }
    html += '<div class="opzioni">' + opz.map(o => `<button class="opz" data-v="${esc(o.valore)}"><span class="n">${o.numero}</span><span>${esc(o.etichetta)}</span></button>`).join("") + "</div>";
    box.innerHTML = html;
    box.querySelectorAll("button.opz").forEach(b => b.onclick = () => {
      const val = b.dataset.v;
      if (campo === "gestione_previdenziale") return rispondi({gestione_previdenziale: val, conferma_deduzioni: true});
      if (val === "si") return rispondi({conferma_deduzioni: true});
      mostraCorrezione(v);
    });
  } else if (campo === "situazioni_particolari") {
    html += '<div class="opzioni">' + opz.map(o => `<label class="opz"><input type="checkbox" value="${esc(o.valore)}"><span>${esc(o.etichetta)}</span></label>`).join("") + "</div>";
    box.innerHTML = html;
    const caselle = [...box.querySelectorAll("input[type=checkbox]")];
    caselle.forEach(c => c.onchange = () => {
      if (c.value === "nessuna" && c.checked) caselle.forEach(x => { if (x !== c) x.checked = false; });
      if (c.value !== "nessuna" && c.checked) caselle.find(x => x.value === "nessuna").checked = false;
      caselle.forEach(x => x.parentElement.classList.toggle("sel", x.checked));
    });
    nav([{testo: "Indietro", azione: indietro},
         {testo: "Avanti", classe: "primario", azione: () => { const sc = caselle.filter(c => c.checked).map(c => c.value);
            if (!sc.length) return alert("Scegli almeno una risposta (anche 'Nessuna di queste')."); rispondi({situazioni_particolari: sc}); }}]);
    return;
  } else if (opz.length) {
    html += '<div class="opzioni">' + opz.map(o => `<button class="opz" data-v="${esc(o.valore)}"><span class="n">${o.numero}</span><span>${esc(o.etichetta)}</span></button>`).join("") + "</div>";
    html += '<div id="altro" class="nascosto"><input class="testo" id="altro-testo" placeholder="Scrivi qui"><div class="riga"><button class="primario" id="altro-ok">Avanti</button></div></div>';
    box.innerHTML = html;
    box.querySelectorAll("button.opz").forEach(b => b.onclick = () => {
      const val = b.dataset.v;
      if (val === "altro" && campo === "nome_cassa") { $("altro").classList.remove("nascosto"); $("altro-testo").focus();
        $("altro-ok").onclick = () => { const t = $("altro-testo").value.trim(); if (t) rispondi({nome_cassa: t}); }; return; }
      const agg = {}; agg[campo] = val; rispondi(agg);
    });
  } else if (campo === "codice_ateco") {
    html += '<input class="testo" id="val" placeholder="es. 62.01.00" inputmode="decimal">';
    html += '<div class="riga"><button class="primario" id="ok">Avanti</button></div>';
    html += '<button class="link" id="nonso">Non conosco il codice: scelgo il mio settore</button>';
    html += '<div id="settori" class="nascosto"><p class="hint">Scegli quello che ti somiglia di più: il codice esatto lo potrai controllare dopo.</p><div class="opzioni">' +
      ((ultima && ultima.settori) || []).map((s, i) => `<button class="opz" data-i="${i}"><span class="n">${i + 1}</span><span>${esc(s.etichetta)}</span></button>`).join("") + '</div></div>';
    box.innerHTML = html; $("val").focus();
    $("ok").onclick = () => { const t = $("val").value.trim(); if (t) rispondi({codice_ateco: t}); };
    $("val").onkeydown = e => { if (e.key === "Enter") $("ok").click(); };
    $("nonso").onclick = () => { $("settori").classList.remove("nascosto"); $("nonso").classList.add("nascosto"); $("settori").scrollIntoView({behavior: "smooth"}); };
    box.querySelectorAll("#settori button.opz").forEach(b => b.onclick = () => {
      const s = ultima.settori[parseInt(b.dataset.i, 10)];
      rispondi({codice_ateco: s.codice, codice_ateco_stimato: true, descrizione_attivita: s.etichetta}); });
  } else if (campo === "data_apertura") {
    html += '<input class="testo" id="val" placeholder="es. 2023" inputmode="numeric" maxlength="4">';
    html += '<div class="riga"><button class="primario" id="ok">Avanti</button></div>';
    box.innerHTML = html; $("val").focus();
    $("ok").onclick = () => { const t = $("val").value.trim(); const a = parseInt(t, 10);
      if (!(a >= 1980 && a <= new Date().getFullYear())) return alert("Scrivi l'anno, es. 2023"); rispondi({data_apertura: String(a)}); };
    $("val").onkeydown = e => { if (e.key === "Enter") $("ok").click(); };
  } else {
    // importo
    html += '<input class="testo" id="val" placeholder="es. 18000" inputmode="numeric">';
    html += scheda.usa_fatture_in_cloud === "si"
      ? '<p class="hint">Il collegamento a Fatture in Cloud lo fai dalla chat, dopo: intanto scrivi una cifra approssimativa.</p>'
      : '<p class="hint">Va bene una cifra tonda, più o meno.</p>';
    html += '<div class="riga"><button class="primario" id="ok">Avanti</button></div>';
    box.innerHTML = html; $("val").focus();
    $("ok").onclick = () => { const t = $("val").value.replace(/[^\d]/g, ""); if (t === "") return alert("Scrivi un importo (anche 0).");
      const agg = {}; agg[campo] = parseInt(t, 10); rispondi(agg); };
    $("val").onkeydown = e => { if (e.key === "Enter") $("ok").click(); };
  }
  nav([{testo: "Indietro", azione: indietro}]);
}

function mostraCorrezione(v) {
  fase = "correzione";
  const oc = v.opzioni_correzione || {};
  const gruppo = (titolo, nome, lista, attuale) => `<div class="gruppo"><h3>${titolo}</h3><div class="opzioni">` +
    lista.map(o => `<label class="opz ${o.valore === attuale ? "sel" : ""}"><input type="radio" name="${nome}" value="${esc(o.valore)}" ${o.valore === attuale ? "checked" : ""}><span>${esc(o.etichetta)}</span></label>`).join("") + "</div></div>";
  $("scheda").innerHTML = `<h1>Correggi quello che non torna</h1>` +
    gruppo("Tipo di attività", "tipo", oc.tipo_attivita || [], scheda.tipo_attivita) +
    gruppo("Gestione previdenziale", "gest", oc.gestione_previdenziale || [], scheda.gestione_previdenziale) +
    `<div class="gruppo"><h3>Anno di apertura della partita IVA</h3><input class="testo" id="anno" value="${esc(String(scheda.data_apertura || "").slice(0,4))}" inputmode="numeric" maxlength="4"></div>`;
  document.querySelectorAll("input[type=radio]").forEach(r => r.onchange = () => {
    document.querySelectorAll(`input[name=${r.name}]`).forEach(x => x.parentElement.classList.toggle("sel", x.checked)); });
  nav([{testo: "Indietro", azione: () => mostraDomanda(v)},
       {testo: "Conferma", classe: "primario", azione: () => {
          const t = document.querySelector("input[name=tipo]:checked"), g = document.querySelector("input[name=gest]:checked");
          const anno = parseInt($("anno").value, 10);
          const agg = {conferma_deduzioni: true};
          if (t) agg.tipo_attivita = t.value; if (g) agg.gestione_previdenziale = g.value;
          if (anno >= 1980 && anno <= new Date().getFullYear() && String(anno) !== String(scheda.data_apertura || "").slice(0,4)) { agg.data_apertura = String(anno); agg.anno_ingresso_forfettario = anno; }
          rispondi(agg); }}]);
}

function mostraFine(inChat) {
  fase = "fine"; barra(1);
  if (!inChat && ultima && ultima.dashboard) {
    $("passo").textContent = "";
    $("scheda").innerHTML = '<h1>Sto preparando la tua situazione…</h1><p class="hint">Un attimo: calcolo quanto hai maturato, le scadenze e quanto mettere da parte.</p>';
    nav([]);
    setTimeout(() => { window.location.href = ultima.dashboard; }, 900);
    return;
  }
  $("passo").innerHTML = '<button class="fatto" id="chiudi">Fatto ✓</button>';
  $("chiudi").onclick = () => { window.close(); setTimeout(() => { window.location.href = "https://claude.ai/"; }, 300); };
  const E = (ultima && ultima.etichette) || {};
  const et = (campo, val) => {
    if (val === null || val === undefined || val === "" || (Array.isArray(val) && !val.length)) return null;
    if (campo === "riduzione_35" && scheda.riduzione_35_incerta) return "non lo so";
    if (campo === "data_apertura") { const s = String(val); return s.length === 10 ? s.split("-").reverse().join("/") : s; }
    if (typeof val === "number") return val.toLocaleString("it-IT") + (campo.startsWith("ricavi") ? " €" : "");
    if (Array.isArray(val)) return val.map(x => (E[campo] || {})[x] || x).join(", ");
    if (val === true) return "sì"; if (val === false) return "no";
    return (E[campo] || {})[val] || String(val);
  };
  const voci = [["codice_ateco","Codice ATECO"],["data_apertura","Apertura"],["tipo_attivita","Attività"],["gestione_previdenziale","Previdenza"],
                ["nome_cassa","Cassa"],["aliquota","Aliquota"],["riduzione_35","Riduzione INPS 35%"],["situazioni_particolari","Situazioni"],
                ["ricavi_anno_precedente","Incassato l'anno scorso"],["ricavi_anno_corrente","Incassato quest'anno"],["descrizione_attivita","Attività descritta"]];
  const righe = voci.map(([k, l]) => { const v = et(k, scheda[k]); return v ? `<div><span>${l}</span><span>${esc(v)}${k === "aliquota" ? "%" : ""}</span></div>` : ""; }).join("");
  $("scheda").innerHTML = `<h1>${inChat ? "Quasi fatto" : "Fatto, grazie"}</h1>
    <p>${inChat ? "Il codice ATECO lo trova TaxScan nella chat partendo dalla tua descrizione." : "Ho tutto quello che serve per la tua situazione."}</p>
    <p><b>Torna nella conversazione con TaxScan e scrivi "ho finito"</b>: troverà queste risposte e ti spiegherà quanto mettere da parte e quando.</p>
    <div class="riepilogo">${righe}</div>`;
  nav([{testo: "Correggi una risposta", azione: () => { if (storia.length) { scheda = storia.pop(); passo = Math.max(0, passo - 1); } invia(); }}]);
}

// ---------------------------------------------------------------- avvio
(async () => {
  try {
    const st = await api("GET");
    scheda = st.scheda || {};
    if (st.stato === "completato" || st.stato === "da_completare_in_chat") { ultima = st; return mostraFine(st.stato === "da_completare_in_chat"); }
    if (Object.keys(scheda).length) { fase = "domanda"; return invia(); }
    mostraIntro();
  } catch (e) {
    $("scheda").innerHTML = '<div class="errore">Link non valido o scaduto: torna su TaxScan e chiedi un nuovo link.</div>';
  }
})();
</script>
</body>
</html>
"""


def pagina(id_colloquio: str) -> str:
    id_pulito = "".join(ch for ch in id_colloquio if ch.isalnum())[:32]  # l'id finisce dentro uno script
    return PAGINA_HTML.replace("{{ID}}", id_pulito)
