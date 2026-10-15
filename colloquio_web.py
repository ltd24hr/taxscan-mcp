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
        cognome = S.pulisci_cognome((scheda_utente or {}).get("cognome"))
        if cognome:
            normalizzata["cognome"] = cognome
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
# Nome di battesimo del TITOLARE. Nel certificato trasmesso da un intermediario compare prima il nome di chi ha
# trasmesso ("cognome e nome : PELUSO SABATO", il commercialista) e solo dopo, sotto "CODICE FISCALE TITOLARE",
# quello del titolare: "COGNOME E NOME:   IZZO      MARCELLO" (cognome e nome separati da piu' spazi).
# Si cerca quindi SOLO dopo "codice fiscale titolare" (si prendono nome e cognome del titolare): se non si trova, meglio nessun nome che quello sbagliato.
_RE_TITOLARE = re.compile(r"codice\s*fiscale\s*(?:del\s*)?titolare", re.I)
_RE_COGNOME_NOME = re.compile(r"(?i:cognome\s*e\s*nome)\s*:\s*([A-ZÀ-Ü' ]+?)\s{2,}([A-ZÀ-Ü']+(?: [A-ZÀ-Ü']+)?)[ \t]*(?=\n|$)")
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
    t = _RE_TITOLARE.search(testo)
    if t:
        m = _RE_COGNOME_NOME.search(testo, t.end())
        if m:
            nome = S.pulisci_nome(m.group(2).split()[0])
            cognome = S.pulisci_cognome(m.group(1))
            if nome:
                trovati["nome"] = nome
                if cognome:
                    trovati["cognome"] = cognome
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
  :root { --verde:#4355cc; --verde-chiaro:#e8ebfa; --grigio:#3d4a73; --bordo:#d8e2ed; --testo:#122452; --fondo:#eef2f8; --f-tit:"Rethink Sans","Poppins",system-ui,sans-serif; --f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
  @font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
  @font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
  @font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
  @font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
  h1,h2,h3,header .logo { font-family:var(--f-tit); }
  * { box-sizing:border-box; }
  body { margin:0; font-family:var(--f-txt); background:var(--fondo); color:var(--testo); }
  .pagina { max-width:560px; margin:0 auto; padding:20px 16px 60px; }
  header { display:flex; align-items:center; justify-content:space-between; margin-bottom:18px; }
  header .logo { font-weight:700; color:var(--testo); font-size:18px; letter-spacing:.2px; }
  header .logo span { color:#05d5c8; }
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

  /* ---- grafica: icone delle domande, illustrazioni, movimenti (tutto SVG + CSS dentro la pagina) ---- */
  .barra > div { background:linear-gradient(90deg,var(--verde),#05d5c8); }
  button.opz:active, button.primario:active, label.primario:active { transform:scale(.985); }
  button:focus-visible, label.opz:has(input:focus-visible), a:focus-visible { outline:3px solid #05d5c8; outline-offset:2px; }
  button.opz:hover .n, label.opz:hover .n { background:#fff; }
  .opz .n svg { display:block; }
  .opz .n.gr { flex:0 0 44px; height:44px; border-radius:12px; }
  .opz .n.gr svg { width:40px; height:40px; }
  .opz .n.set { flex:0 0 40px; height:40px; border-radius:12px; }
  .opz .n.set svg { width:24px; height:24px; }
  .s-t { fill:none; stroke:var(--testo); stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
  .s-a { fill:none; stroke:#04bdb2; stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }
  .s-pieno { fill:#fff; }
  .s-p { fill:var(--testo); }
  .qi { width:56px; height:56px; border-radius:16px; background:var(--verde-chiaro); margin:0 0 14px; }
  .qi svg { display:block; width:100%; height:100%; }
  .q-t { fill:none; stroke:var(--testo); stroke-width:2.2; stroke-linecap:round; stroke-linejoin:round; }
  .q-c { fill:#fff; }
  .q-m { fill:var(--verde-chiaro); }
  .q-a { fill:none; stroke:#05d5c8; stroke-width:2.4; stroke-linecap:round; stroke-linejoin:round; }
  .q-r { fill:none; stroke:#b9c4ee; stroke-width:2.2; stroke-linecap:round; }
  .q-s { fill:#c9d3ee; }
  .q-d { stroke-dasharray:1; }
  .q-p, .q-cade, .q-su, .q-cerca { transform-box:fill-box; transform-origin:50% 50%; }
  .q-lancetta { transform-box:fill-box; transform-origin:50% 100%; }
  .q-luce { opacity:0; }
  .ill { display:flex; justify-content:center; margin:0 0 12px; }
  .ill svg { display:block; height:132px; width:auto; }
  .ill .campo { fill:#dfe5f6; transition:fill .35s; }
  .ill .angoli { opacity:.5; transition:opacity .2s; }
  .ill .raggio { opacity:0; }
  .ill .timbro { opacity:0; transform:scale(1.7) rotate(-18deg); transition:opacity .2s, transform .4s cubic-bezier(.2,.9,.3,1.4); }
  .ill.legge .angoli { opacity:1; }
  .ill.letto .cifre { fill:#4355cc; } .ill.letto .riga { fill:#b9c4ee; } .ill.letto .ateco { fill:#05d5c8; }
  .ill.letto .timbro { opacity:1; transform:rotate(-8deg); }
  .pronto { display:flex; gap:12px; margin:0 0 16px; }
  .pronto svg { width:54px; height:54px; padding:9px; border-radius:15px; background:var(--verde-chiaro); }
  @media (prefers-reduced-motion:no-preference) {
    .scheda.entra > *:not(.qi):not(.opzioni):not(.ill):not(.pronto) { animation:entra .3s ease-out both; }
    .scheda.entra > .opzioni > * { animation:entra .3s ease-out .2s both; }
    .scheda.entra > .opzioni > :nth-child(1) { animation-delay:.04s; } .scheda.entra > .opzioni > :nth-child(2) { animation-delay:.08s; }
    .scheda.entra > .opzioni > :nth-child(3) { animation-delay:.12s; } .scheda.entra > .opzioni > :nth-child(4) { animation-delay:.16s; }
    .qi { animation:qi-entra .35s cubic-bezier(.2,.9,.3,1.3) both; }
    .q-d { animation:q-d .45s ease-out .25s both; } .q-d2 { animation-delay:.45s; }
    .q-p { animation:q-p .4s cubic-bezier(.2,.9,.3,1.5) .3s both; }
    .q-cade { animation:q-cade .5s cubic-bezier(.3,.7,.4,1.3) .2s both; }
    .q-su { animation:q-su 1.2s ease-in-out .35s 2; }
    .q-cerca { animation:q-cerca 1.4s ease-in-out .25s; }
    .q-lancetta { animation:q-lancetta .9s ease-out .2s both; }
    .q-luce { animation:q-luce 1.5s ease-in-out .2s both; }
    .ill .raggio { animation:ill-raggio 3.4s linear infinite; }
    .ill.legge .raggio { animation-duration:1.1s; }
    .ill.letto .raggio { animation:none; }
    .pronto svg { animation:pronto .45s cubic-bezier(.2,.9,.3,1.4) both; }
    .pronto svg:nth-child(2) { animation-delay:.18s; } .pronto svg:nth-child(3) { animation-delay:.36s; }
  }
  @keyframes entra { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
  @keyframes qi-entra { from { opacity:0; transform:scale(.8); } to { opacity:1; transform:none; } }
  @keyframes q-d { from { stroke-dashoffset:1; opacity:0; } 15% { opacity:1; } to { stroke-dashoffset:0; opacity:1; } }
  @keyframes q-p { from { transform:scale(0); } to { transform:scale(1); } }
  @keyframes q-cade { from { transform:translateY(-12px); opacity:0; } to { transform:none; opacity:1; } }
  @keyframes q-su { 0%,100% { transform:none; } 50% { transform:translateY(-3px); } }
  @keyframes q-cerca { 0%,100% { transform:none; } 30% { transform:translate(3px,-2px); } 65% { transform:translate(-2px,2px); } }
  @keyframes q-lancetta { from { transform:rotate(-300deg); } to { transform:none; } }
  @keyframes q-luce { 0% { transform:translateY(-9px); opacity:0; } 15% { opacity:1; } 50% { transform:translateY(17px); } 85% { opacity:1; } 100% { transform:translateY(-9px); opacity:0; } }
  @keyframes ill-raggio { 0% { transform:translateY(-50px); opacity:0; } 8% { opacity:1; } 80% { opacity:1; } 88%,100% { transform:translateY(166px); opacity:0; } }
  @keyframes pronto { from { opacity:0; transform:scale(.6) translateY(6px); } to { opacity:1; transform:none; } }
</style>
</head>
<body>
<div class="pagina">
  <header><div class="logo">Tax<span>Scan</span></div><div class="passo" id="passo"></div></header>
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

// ---------------------------------------------------------------- icone e illustrazioni (SVG disegnati qui, nessun file esterno)
const ICO = {
  calendario: '<rect class="q-t q-c" x="9" y="12" width="30" height="27" rx="5"/><path class="q-t" d="M9 20h30M17 8v7M31 8v7"/><rect class="q-p" x="15" y="25" width="7" height="7" rx="2" fill="#efac35"/><rect x="26" y="25" width="7" height="7" rx="2" class="q-s"/>',
  lente: '<g class="q-cerca"><circle class="q-t q-c" cx="21" cy="21" r="11"/><path class="q-t" d="M29.5 29.5l9 9" style="stroke-width:3.2"/><path class="q-a q-d" pathLength="1" d="M14.5 20.5a6.5 6.5 0 0 1 6-6"/></g>',
  appunti: '<rect class="q-t q-c" x="11" y="10" width="26" height="30" rx="4.5"/><rect class="q-t q-m" x="18" y="6" width="12" height="8" rx="3"/><path class="q-a q-d" pathLength="1" d="M17 26.5l5 5 9.5-10.5" style="stroke-width:3"/>',
  scudo: '<path class="q-t q-c" d="M24 7l13 5v10c0 9-5.5 15-13 19-7.5-4-13-10-13-19V12Z"/><path class="q-a q-d" pathLength="1" d="M18 23.5l4.5 4.5 8-9" style="stroke-width:3"/>',
  orologio: '<circle class="q-t q-c" cx="24" cy="25" r="14.5"/><path class="q-t" d="M24 7.5v3M17 6.5h14"/><path class="q-a q-lancetta" d="M24 25V16" style="stroke-width:2.8"/><path class="q-t" d="M24 25l6 3.5"/><circle cx="24" cy="25" r="2" fill="#efac35"/>',
  lista: '<rect class="q-t q-c" x="9" y="9" width="8" height="8" rx="2.5"/><rect class="q-t q-c" x="9" y="20" width="8" height="8" rx="2.5"/><rect class="q-t q-c" x="9" y="31" width="8" height="8" rx="2.5"/><path class="q-r" d="M22 13h17M22 24h17M22 35h11"/><path class="q-a q-d" pathLength="1" d="M11 13l1.8 1.8 3-3.4"/><path class="q-a q-d q-d2" pathLength="1" d="M11 24l1.8 1.8 3-3.4"/>',
  valigetta: '<path class="q-t" d="M18 16v-3a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v3"/><rect class="q-t q-c" x="8" y="16" width="32" height="22" rx="4.5"/><path class="q-a q-d" pathLength="1" d="M8 26h32"/><rect class="q-p" x="20.5" y="23" width="7" height="6" rx="2" fill="#efac35"/>',
  persone: '<circle class="q-a q-p" cx="32.5" cy="16" r="4.8"/><path class="q-a q-d" pathLength="1" d="M33.5 25.5c5 .5 8.5 4 8.5 10.5"/><circle class="q-t q-c" cx="19" cy="18" r="6"/><path class="q-t q-c" d="M7 39c0-7.5 5-12 12-12s12 4.5 12 12"/>',
  nuvola: '<path class="q-t q-c" d="M15 37a8.5 8.5 0 0 1-1.2-16.9A11 11 0 0 1 35 18.5a9.3 9.3 0 0 1-1 18.5Z"/><g class="q-su"><path class="q-a" d="M24 33.5v-10M19.5 27.5l4.5-4.5 4.5 4.5" style="stroke-width:2.8"/></g>',
  monete: '<g transform="translate(6 7)"><path d="M5 26v4.5a13 5.5 0 0 0 26 0V26Z" fill="#c98a1b"/><ellipse cx="18" cy="26" rx="13" ry="5.5" fill="#efac35"/><path d="M5 19v4.5a13 5.5 0 0 0 26 0V19Z" fill="#c98a1b"/><ellipse cx="18" cy="19" rx="13" ry="5.5" fill="#efac35"/><g class="q-cade"><path d="M5 12v4.5a13 5.5 0 0 0 26 0V12Z" fill="#c98a1b"/><ellipse cx="18" cy="12" rx="13" ry="5.5" fill="#f6c25a"/></g></g>',
  percento: '<circle class="q-t q-c" cx="24" cy="24" r="16"/><path class="q-a q-d" pathLength="1" d="M17.5 30.5l13-13" style="stroke-width:2.8"/><circle class="q-p" cx="18.5" cy="18.5" r="3" fill="#efac35"/><circle class="q-p" cx="29.5" cy="29.5" r="3" fill="#efac35"/>',
  documento: '<path class="q-t q-c" d="M15 9h13l8 8v19a3 3 0 0 1-3 3H15a3 3 0 0 1-3-3V12a3 3 0 0 1 3-3Z"/><path class="q-t" d="M28 9v6a2 2 0 0 0 2 2h6"/><path class="q-r" d="M17 24h14M17 29h9M17 34h12"/><path class="q-a q-luce" d="M7 21h34" style="stroke-width:2.8"/>',
  carica: '<path class="q-t q-c" d="M15 9h13l8 8v19a3 3 0 0 1-3 3H15a3 3 0 0 1-3-3V12a3 3 0 0 1 3-3Z"/><path class="q-t" d="M28 9v6a2 2 0 0 0 2 2h6"/><g class="q-su"><path class="q-a" d="M24 34.5v-11M19 28l5-5 5 5" style="stroke-width:2.8"/></g>',
  tocco: '<rect class="q-t q-c" x="8" y="11" width="32" height="10" rx="5"/><rect class="q-t q-c" x="8" y="27" width="32" height="10" rx="5"/><circle class="q-p" cx="14" cy="16" r="2.4" fill="#05d5c8"/><circle cx="14" cy="32" r="2.4" class="q-s"/><path class="q-r" d="M20 16h13M20 32h9"/>',
  fatto: '<circle class="q-t q-c" cx="24" cy="24" r="17"/><path class="q-a q-d" pathLength="1" d="M15.5 24.5l6 6 11.5-12.5" style="stroke-width:3.4"/>'
};
const ICO_CAMPO = {data_apertura: "calendario", codice_ateco: "lente", conferma_deduzioni: "appunti", gestione_previdenziale: "scudo", nome_cassa: "scudo",
  altra_copertura_previdenziale: "scudo", riduzione_35: "percento", origine_attivita: "orologio", situazioni_particolari: "lista",
  redditi_dipendente_pensione: "valigetta", rapporto_dipendente_cessato: "valigetta", prevalenza_ex_datore: "valigetta",
  spese_personale: "persone", gestione_attuale: "persone", usa_fatture_in_cloud: "nuvola",
  ricavi_anno_precedente: "monete", ricavi_anno_corrente: "monete", contributi_versati_anno_precedente: "monete"};
function ico(nome) { return '<div class="qi"><svg viewBox="0 0 48 48" aria-hidden="true">' + (ICO[nome] || ICO.documento) + '</svg></div>'; }
function icona(campo) { return ico(ICO_CAMPO[campo] || (String(campo || "").indexOf("ricavi") === 0 ? "monete" : "documento")); }

// un'icona per ciascun settore dell'elenco rapido (chiave: prime due cifre del codice ATECO)
const ICO_SETTORE = {
  "70": '<rect class="s-t" x="3" y="7.5" width="18" height="12.5" rx="2.5"/><path class="s-t" d="M9 7.5V6a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 6v1.5"/><path class="s-a" d="M3 13h18"/>',
  "62": '<rect class="s-t" x="3" y="4.5" width="18" height="15" rx="2.5"/><path class="s-a" d="M9.5 9.5L7 12l2.5 2.5M14.5 9.5L17 12l-2.5 2.5"/>',
  "74": '<path class="s-t" d="M4 10v4h3l7 4V6l-7 4H4Z"/><path class="s-t" d="M7.5 14.5l1 4.5H11"/><path class="s-a" d="M17 9.5a3.5 3.5 0 0 1 0 5"/>',
  "85": '<path class="s-t" d="M2.5 9.5L12 5l9.5 4.5L12 14Z"/><path class="s-t" d="M6.5 11.5v5c1.5 1.5 3.5 2 5.5 2s4-.5 5.5-2v-5"/><path class="s-a" d="M21.5 9.5v5.5"/>',
  "47": '<path class="s-t" d="M5 8.5h14l-1 11.5H6Z"/><path class="s-a" d="M9 11V7.5a3 3 0 0 1 6 0V11"/>',
  "46": '<rect class="s-t" x="3" y="5" width="18" height="14" rx="2.5"/><circle class="s-t" cx="8.5" cy="10.5" r="2"/><path class="s-t" d="M5.5 16c.5-2.2 5.5-2.2 6 0"/><path class="s-a" d="M14.5 10h3.5M14.5 14h3.5"/>',
  "43": '<path class="s-t" d="M4.5 15.5v-1a7.5 7.5 0 0 1 15 0v1"/><path class="s-t" d="M12 7v4"/><rect class="s-a" x="2.5" y="15.5" width="19" height="3.5" rx="1.7"/>',
  "56": '<path class="s-t" d="M5 10h11v4a5.5 5.5 0 0 1-11 0Z"/><path class="s-t" d="M16 11h1.5a2.5 2.5 0 0 1 0 5h-2"/><path class="s-t" d="M4 20.5h13"/><path class="s-a" d="M8.5 4c-1 1.2 1 1.8 0 3.2M12.5 4c-1 1.2 1 1.8 0 3.2"/>',
  "96": '<circle class="s-t" cx="6.5" cy="6.5" r="2.7"/><circle class="s-t" cx="6.5" cy="17.5" r="2.7"/><path class="s-t" d="M8.7 8.2L20.5 17"/><path class="s-a" d="M8.7 15.8L20.5 7"/>',
  "49": '<path class="s-t" d="M2.5 6.5h11v10h-11Z"/><path class="s-t" d="M13.5 10h4l3 3v3.5h-7"/><circle class="s-a s-pieno" cx="7" cy="17.5" r="2.1"/><circle class="s-a s-pieno" cx="16.8" cy="17.5" r="2.1"/>',
  "90": '<path class="s-t" d="M11 5.5l2.3 4.7 5.2.8-3.8 3.6.9 5.2-4.6-2.4-4.6 2.4.9-5.2L3.5 11l5.2-.8Z"/><path class="s-a" d="M19.5 3v3M18 4.5h3"/>',
  "82": '<circle class="s-t" cx="12" cy="12" r="9"/><circle class="s-p" cx="7.8" cy="12" r="1.3"/><circle class="s-p" cx="12" cy="12" r="1.3"/><circle class="s-p" cx="16.2" cy="12" r="1.3"/>'
};
function icoSettore(codice) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICO_SETTORE[String(codice || "").slice(0, 2)] || ICO_SETTORE["82"]) + '</svg>'; }

// il certificato che viene letto: fermo nell'introduzione, veloce mentre si legge il PDF, timbrato quando i dati sono stati trovati
const ILL_CERT = '<div class="ill" id="ill"><svg viewBox="0 16 176 204" aria-hidden="true"><defs>' +
  '<linearGradient id="illLuce" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05d5c8" stop-opacity="0"/><stop offset="1" stop-color="#05d5c8" stop-opacity=".5"/></linearGradient>' +
  '<clipPath id="illFoglio"><path d="M0 8a8 8 0 0 1 8-8H94L118 24V152a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8Z"/></clipPath></defs>' +
  '<circle cx="87" cy="118" r="86" fill="#e8ebfa"/>' +
  '<g class="angoli" fill="none" stroke="#05d5c8" stroke-width="3" stroke-linecap="round"><path d="M10 39V29a8 8 0 0 1 8-8H28"/><path d="M146 21H156a8 8 0 0 1 8 8V39"/><path d="M164 197V207a8 8 0 0 1-8 8H146"/><path d="M28 215H18a8 8 0 0 1-8-8V197"/></g>' +
  '<g transform="rotate(-4 87 118)"><g transform="translate(28 38)">' +
  '<path d="M0 8a8 8 0 0 1 8-8H94L118 24V152a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8Z" transform="translate(3 5)" fill="rgba(18,36,82,.10)"/>' +
  '<path d="M0 8a8 8 0 0 1 8-8H94L118 24V152a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8Z" fill="#fff" stroke="#d8e2ed"/>' +
  '<path d="M94 0V16a8 8 0 0 0 8 8H118Z" fill="#c9d6ea"/><rect x="14" y="16" width="46" height="9" rx="4.5" fill="#122452"/>' +
  '<rect class="campo cifre" x="14" y="36" width="88" height="10" rx="2.5"/>' +
  '<rect class="campo riga" x="14" y="57" width="84" height="5" rx="2.5"/><rect class="campo riga" x="14" y="67" width="60" height="5" rx="2.5"/>' +
  '<rect class="campo ateco" x="14" y="84" width="62" height="16" rx="8"/><circle cx="23" cy="92" r="3" fill="#fff"/><rect x="30" y="89.5" width="36" height="5" rx="2.5" fill="#fff"/>' +
  '<rect class="campo riga" x="14" y="112" width="52" height="5" rx="2.5"/><rect class="campo riga" x="14" y="122" width="38" height="5" rx="2.5"/><rect class="campo riga" x="14" y="132" width="46" height="5" rx="2.5"/>' +
  '<g transform="translate(90 132)"><g class="timbro"><circle r="14" fill="#fff" stroke="#efac35" stroke-width="2.6"/><path d="M-6.5 .5l4.5 4.5 8.5-9.5" fill="none" stroke="#efac35" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></g></g>' +
  '<g clip-path="url(#illFoglio)"><g class="raggio"><rect width="118" height="44" fill="url(#illLuce)"/><rect y="42.5" width="118" height="3" fill="#05d5c8"/></g></g>' +
  '</g></g></svg></div>';

// le tre risposte che compaiono mentre si prepara la situazione (stesse della pagina iniziale)
const ILL_PRONTO = '<div class="pronto" aria-hidden="true">' +
  '<svg viewBox="0 0 36 36"><path d="M5 25v4.5a13 5.5 0 0 0 26 0V25Z" fill="#c98a1b"/><ellipse cx="18" cy="25" rx="13" ry="5.5" fill="#efac35"/><path d="M5 18.5v4.5a13 5.5 0 0 0 26 0v-4.5Z" fill="#c98a1b"/><ellipse cx="18" cy="18.5" rx="13" ry="5.5" fill="#efac35"/><path d="M5 12v4.5a13 5.5 0 0 0 26 0V12Z" fill="#c98a1b"/><ellipse cx="18" cy="12" rx="13" ry="5.5" fill="#f6c25a"/></svg>' +
  '<svg viewBox="0 0 36 36"><rect x="3" y="5" width="30" height="28" rx="6" fill="#e8ebfa"/><path d="M3 11a6 6 0 0 1 6-6h18a6 6 0 0 1 6 6v3H3Z" fill="#4355cc"/><rect x="10" y="2" width="3" height="7" rx="1.5" fill="#122452"/><rect x="23" y="2" width="3" height="7" rx="1.5" fill="#122452"/><text x="18" y="28.5" text-anchor="middle" font-size="12" font-weight="700" fill="#122452">30</text></svg>' +
  '<svg viewBox="0 0 36 36"><path d="M9 13h18v2c3 1.5 4 4 4 7v8a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4v-8c0-3 1-5.5 4-7Z" fill="#e8ebfa"/><path d="M5.5 22h25v8a4 4 0 0 1-4 4h-17a4 4 0 0 1-4-4Z" fill="#05d5c8"/><path d="M9 13h18v2c3 1.5 4 4 4 7v8a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4v-8c0-3 1-5.5 4-7Z" fill="none" stroke="#122452" stroke-width="2"/><rect x="7" y="7" width="22" height="6" rx="2.5" fill="#122452"/><circle cx="14.5" cy="27.5" r="3.4" fill="#efac35"/><circle cx="21.5" cy="29" r="3.4" fill="#f6c25a"/></svg>' +
  '</div>';

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
  $("scheda").innerHTML = ILL_CERT + `
    <h1>La tua situazione fiscale in 2 minuti</h1>
    <p>Rispondi toccando le risposte. Nessuna domanda difficile: quello che si può capire da solo, lo capisce TaxScan.</p>
    <p class="hint">Se hai il <b>certificato di attribuzione della partita IVA</b> (PDF dell'Agenzia delle Entrate), caricalo: leggo io codice ATECO, data di apertura e partita IVA.</p>
    <div class="opzioni">
      <label class="opz" for="pdf"><span class="n gr"><svg viewBox="0 0 48 48" aria-hidden="true">${ICO.carica}</svg></span><span>Carico il certificato di attribuzione (PDF)</span></label>
      <input type="file" id="pdf" accept="application/pdf" class="nascosto">
      <button class="opz" id="senza"><span class="n gr"><svg viewBox="0 0 48 48" aria-hidden="true">${ICO.tocco}</svg></span><span>Non ce l'ho sotto mano: rispondo a un paio di domande</span></button>
    </div>
    <div id="esito"></div>`;
  nav([]);
  $("pdf").onchange = caricaCertificato;
  $("senza").onclick = () => { fase = "domanda"; invia(); };
}

async function caricaCertificato(ev) {
  const file = ev.target.files[0]; if (!file) return;
  $("esito").innerHTML = '<p class="hint">Leggo il certificato...</p>';
  const ill = $("ill"); if (ill) ill.classList.add("legge");
  const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(",")[1]); fr.readAsDataURL(file); });
  try {
    const r = await api("POST", {pdf_base64: b64}, "/certificato");
    const t = r.trovati || {};
    if (!Object.keys(t).length) {
      if (ill) ill.classList.remove("legge");
      $("esito").innerHTML = `<div class="errore">${esc(r.errore || "Non sono riuscito a leggere i dati dal certificato.")} Nessun problema: ti faccio due domande.</div>`;
      setTimeout(() => { fase = "domanda"; invia(); }, 1800); return;
    }
    const righe = [];
    if (t.codice_ateco) righe.push("Codice ATECO: <b>" + esc(t.codice_ateco) + "</b>" + (t.descrizione_attivita_certificato ? " - " + esc(t.descrizione_attivita_certificato) : ""));
    if (t.data_apertura) righe.push("Apertura: <b>" + esc(t.data_apertura.split("-").reverse().join("/")) + "</b>");
    if (t.nome) righe.push("Nome: <b>" + esc([t.nome, t.cognome].filter(Boolean).join(" ")) + "</b>");
    if (t.partita_iva) righe.push("Partita IVA: <b>" + esc(t.partita_iva) + "</b>");
    if (t.comune) righe.push("Domicilio fiscale: <b>" + esc(t.comune) + (t.provincia ? " (" + esc(t.provincia) + ")" : "") + "</b>");
    $("esito").innerHTML = `<div class="trovato">Ho letto dal certificato:<br>${righe.join("<br>")}</div>`;
    if (ill) { ill.classList.remove("legge"); ill.classList.add("letto"); }
    Object.assign(scheda, t);
    setTimeout(() => { fase = "domanda"; invia(); }, 1400);
  } catch (e) {
    if (ill) ill.classList.remove("legge");
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
  let html = icona(campo) + `<h1>${esc(v.prossima_domanda)}</h1>`;
  if (v.dove_trovarlo) html += `<p class="hint">${esc(v.dove_trovarlo)}</p>`;

  if (campo === "conferma_deduzioni" || (campo === "gestione_previdenziale" && v.proposta_deduzioni)) {
    if (campo === "conferma_deduzioni") {
      const d = v.proposta_deduzioni || {};
      const anni = d.anni_nel_regime === 0 ? "primo anno" : d.anni_nel_regime === 1 ? "da un anno" : d.anni_nel_regime != null ? `da ${d.anni_nel_regime} anni` : "";
      const righe = [["Nome e cognome", [scheda.nome, scheda.cognome].filter(Boolean).join(" ")], ["Attività", d.descrizione_attivita], ["Codice ATECO", d.codice_ateco], ["Tipo", d.tipo_attivita_etichetta],
                     ["Previdenza", d.gestione_previdenziale_etichetta], ["Partita IVA aperta nel", d.anno_apertura], ["Nel forfettario", anni]];
      html = icona(campo) + `<h1>Ho capito così. Giusto?</h1><div class="riepilogo">` +
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
      ((ultima && ultima.settori) || []).map((s, i) => `<button class="opz" data-i="${i}"><span class="n set">${icoSettore(s.codice)}</span><span>${esc(s.etichetta)}</span></button>`).join("") + '</div></div>';
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
    `<div class="gruppo"><h3>Anno di apertura della partita IVA</h3><input class="testo" id="anno" value="${esc(String(scheda.data_apertura || "").slice(0,4))}" inputmode="numeric" maxlength="4"></div>` +
    `<div class="gruppo"><h3>Nome e cognome (facoltativo)</h3><input class="testo" id="nome-in" value="${esc(scheda.nome || "")}" maxlength="24" autocomplete="given-name" placeholder="Nome"><input class="testo" id="cognome-in" value="${esc(scheda.cognome || "")}" maxlength="40" autocomplete="family-name" placeholder="Cognome"><p class="hint" id="err-nome" style="color:#8a1f1f"></p></div>`;
  document.querySelectorAll("input[type=radio]").forEach(r => r.onchange = () => {
    document.querySelectorAll(`input[name=${r.name}]`).forEach(x => x.parentElement.classList.toggle("sel", x.checked)); });
  nav([{testo: "Indietro", azione: () => mostraDomanda(v)},
       {testo: "Conferma", classe: "primario", azione: () => {
          const t = document.querySelector("input[name=tipo]:checked"), g = document.querySelector("input[name=gest]:checked");
          const anno = parseInt($("anno").value, 10);
          const agg = {conferma_deduzioni: true};
          const nomeIn = ($("nome-in").value || "").trim(), cognomeIn = ($("cognome-in").value || "").trim();
          if ((nomeIn && !/^[A-Za-zÀ-ÖØ-öø-ÿ'’\- ]{2,24}$/.test(nomeIn)) || (cognomeIn && !/^[A-Za-zÀ-ÖØ-öø-ÿ'’\- ]{2,40}$/.test(cognomeIn))) { $("err-nome").textContent = "Scrivi solo lettere, senza numeri o simboli."; return; }
          if (nomeIn !== (scheda.nome || "")) agg.nome = nomeIn;
          if (cognomeIn !== (scheda.cognome || "")) agg.cognome = cognomeIn;
          if (t) agg.tipo_attivita = t.value; if (g) agg.gestione_previdenziale = g.value;
          if (anno >= 1980 && anno <= new Date().getFullYear() && String(anno) !== String(scheda.data_apertura || "").slice(0,4)) { agg.data_apertura = String(anno); agg.anno_ingresso_forfettario = anno; }
          rispondi(agg); }}]);
}

function mostraFine(inChat) {
  fase = "fine"; barra(1);
  if (!inChat && ultima && ultima.dashboard) {
    $("passo").textContent = "";
    $("scheda").innerHTML = ILL_PRONTO + '<h1>Sto preparando la tua situazione…</h1><p class="hint">Un attimo: calcolo quanto hai maturato, le scadenze e quanto mettere da parte.</p>';
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
  $("scheda").innerHTML = ico(inChat ? "lente" : "fatto") + `<h1>${inChat ? "Quasi fatto" : "Fatto, grazie"}</h1>
    <p>${inChat ? "Il codice ATECO lo trova TaxScan nella chat partendo dalla tua descrizione." : "Ho tutto quello che serve per la tua situazione."}</p>
    <p><b>Torna nella conversazione con TaxScan e scrivi "ho finito"</b>: troverà queste risposte e ti spiegherà quanto mettere da parte e quando.</p>
    <div class="riepilogo">${righe}</div>`;
  nav([{testo: "Correggi una risposta", azione: () => { if (storia.length) { scheda = storia.pop(); passo = Math.max(0, passo - 1); } invia(); }}]);
}

// ogni nuova schermata entra con un piccolo movimento (solo quando c'è una domanda, non durante l'attesa)
new MutationObserver(() => { const b = $("scheda"); if (!b.querySelector("h1")) return; b.classList.remove("entra"); void b.offsetWidth; b.classList.add("entra"); })
  .observe($("scheda"), {childList: true});

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
