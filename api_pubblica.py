"""TaxScan - API per gli assistenti IA (e per chi vuole collegare altri programmi).

L'utente genera una chiave dal Profilo (scheda «Assistenti IA e API»): con quella chiave un assistente IA puo' fare
quello che la persona fa nell'app: leggere la situazione fiscale e le scadenze, segnare incassi, gestire clienti e
fatture, far leggere fatture caricate. Come Brevo: la chiave si vede una volta sola, ha un nome, puo' essere di sola
lettura o di lettura e modifica, si elimina quando si vuole, e chi la crea o la elimina riceve un'email.

Le chiavi non si salvano in chiaro: in archivio c'e' solo l'impronta SHA-256.
  apikey/<impronta>   -> {c, nome, accesso, creato, id}
  apikeys_di/<c>      -> {"chiavi": [{id, h, nome, accesso, creato, fine, usato}]}
Rotte: /api/v1/... (chiave nell'intestazione Authorization: Bearer tsk_... oppure X-API-Key), /api (documentazione),
/api/openapi.json (descrizione per gli assistenti), /api/prova/chiavi (gestione dall'app).
"""
from __future__ import annotations

import datetime
import hashlib
import html
import json
import re
import secrets
import time

import db

PREFISSO = "tsk_"
MAX_CHIAVI = 10
LIMITE_ORA = 300          # richieste per ora per chiave
_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
_USO: dict = {}           # impronta -> [tempi] (limite di richieste)
_TOCCATA: dict = {}       # impronta -> ultima scrittura di «usato» (una volta l'ora basta)


def _get(path: str):
    import pagamenti
    return pagamenti._get(path)


def _set(path: str, dati: dict) -> None:
    import pagamenti
    pagamenti._set(path, dati)


def _h(chiave: str) -> str:
    return hashlib.sha256(chiave.encode()).hexdigest()


def _email(c: str) -> str:
    import pagamenti
    return pagamenti._email_di(c)


def _avvisa(c: str, oggetto: str, testo: str) -> None:
    em = _email(c)
    if not em:
        return
    try:
        import auth
        import emailtpl
        auth.manda_email(em, oggetto, emailtpl.cornice(oggetto, testo))
    except Exception as e:
        print(f"api: email non inviata: {e}")


# ------------------------------------------------------------------ gestione delle chiavi (dall'app)

def elenco(c: str) -> dict:
    rec = _get("apikeys_di/" + c) or {}
    return {"ok": True, "chiavi": [{k: x.get(k) for k in ("id", "nome", "accesso", "creato", "fine", "usato")}
                                   for x in rec.get("chiavi") or []]}


def crea(c: str, nome: str, accesso: str) -> dict:
    import prova
    if not _ID.match(c or "") or not db.carica_dashboard(c):
        return {"ok": False, "errore": "Serve la tua situazione salvata."}
    if not prova._mail_verificata(c):
        return {"ok": False, "errore": "Prima conferma la tua email nel Profilo: le chiavi danno accesso ai tuoi dati, "
                                        "e ti avviso via email ogni volta che ne crei o elimini una."}
    rec = _get("apikeys_di/" + c) or {"chiavi": []}
    if len(rec.get("chiavi") or []) >= MAX_CHIAVI:
        return {"ok": False, "errore": f"Hai già {MAX_CHIAVI} chiavi: eliminane una che non usi più."}
    nome = re.sub(r"\s+", " ", str(nome or "")).strip()[:60] or "Assistente IA"
    accesso = "scrittura" if accesso == "scrittura" else "lettura"
    chiave = PREFISSO + secrets.token_urlsafe(30)
    h = _h(chiave)
    oggi = datetime.date.today().isoformat()
    voce = {"id": h[:12], "h": h, "nome": nome, "accesso": accesso, "creato": oggi, "fine": chiave[-4:], "usato": ""}
    _set("apikey/" + h, {"c": c, "nome": nome, "accesso": accesso, "creato": oggi, "id": voce["id"]})
    rec.setdefault("chiavi", []).append(voce)
    _set("apikeys_di/" + c, rec)
    try:
        db.registra_evento("api_chiave_creata", c, {"accesso": accesso})
    except Exception:
        pass
    _avvisa(c, "Hai creato una chiave API di TaxScan",
            f"<p>Ciao,</p><p>è stata creata la chiave API <b>{html.escape(nome)}</b> "
            f"({'lettura e modifica' if accesso == 'scrittura' else 'solo lettura'}), che finisce con <b>…{html.escape(voce['fine'])}</b>.</p>"
            "<p>Con questa chiave un assistente IA può lavorare sui tuoi dati di TaxScan. Se non sei stato tu, "
            "eliminala subito dal Profilo, scheda «Assistenti IA e API».</p>")
    return {"ok": True, "chiave": chiave, **{k: voce[k] for k in ("id", "nome", "accesso", "creato", "fine")}}


def elimina(c: str, kid: str) -> dict:
    rec = _get("apikeys_di/" + c) or {"chiavi": []}
    resta, tolta = [], None
    for x in rec.get("chiavi") or []:
        if x.get("id") == kid and not tolta:
            tolta = x
        else:
            resta.append(x)
    if not tolta:
        return {"ok": False, "errore": "Chiave non trovata."}
    _set("apikey/" + tolta["h"], {"revocata": True, "quando": datetime.date.today().isoformat()})
    rec["chiavi"] = resta
    _set("apikeys_di/" + c, rec)
    _avvisa(c, "Hai eliminato una chiave API di TaxScan",
            f"<p>Ciao,</p><p>la chiave API <b>{html.escape(tolta.get('nome') or '')}</b> (…{html.escape(tolta.get('fine') or '')}) "
            "è stata eliminata: da adesso non funziona più.</p>")
    return {"ok": True, **elenco(c)}


def chiavi_app(c: str, op: str, dati: dict) -> dict:
    if not _ID.match(c or ""):
        return {"ok": False}
    if op == "crea":
        return crea(c, dati.get("nome", ""), dati.get("accesso", ""))
    if op == "elimina":
        return elimina(c, str(dati.get("id", "")))
    if op == "permesso":
        return imposta_permesso(c, str(dati.get("azione", "")), str(dati.get("valore", "")))
    if op in ("approva", "rifiuta"):
        return decidi(c, str(dati.get("id", "")), op == "approva")
    out = elenco(c)
    out.update({"permessi": permessi(c), "azioni": [[a, n] for a, n, _ in AZIONI],
                "attesa": [{k: x.get(k) for k in ("id", "azione", "t", "chiave", "riassunto")} | {"nome": _NOMI.get(x.get("azione"), "")}
                           for x in in_attesa(c)]})
    return out



# ------------------------------------------------------------------ cosa l'assistente puo' fare da solo (come Finom: «Consenti» o «Chiedi»)
AZIONI = [("bozza", "Preparare bozze di fatture e preventivi", "consenti"),
          ("cliente", "Creare o modificare un cliente", "consenti"),
          ("incasso", "Segnare un incasso", "consenti"),
          ("incassa", "Segnare una fattura come incassata", "consenti"),
          ("emetti", "Emettere una fattura (numero definitivo)", "chiedi")]
_NOMI = {a: n for a, n, _ in AZIONI}


def permessi(c: str) -> dict:
    rec = _get("apiperm/" + c) or {}
    return {a: (rec.get(a) if rec.get(a) in ("consenti", "chiedi") else dflt) for a, _, dflt in AZIONI}


def imposta_permesso(c: str, azione: str, valore: str) -> dict:
    if azione not in _NOMI or valore not in ("consenti", "chiedi"):
        return {"ok": False}
    p = permessi(c)
    p[azione] = valore
    _set("apiperm/" + c, p)
    return {"ok": True, "permessi": p}


def esegui(c: str, azione: str, dati: dict) -> dict:
    import fatturazione
    import prova
    if azione == "incasso":
        return prova.incasso(c, dati.get("importo"), str(dati.get("data") or ""))
    if azione == "cliente":
        return fatturazione.operazione(c, "cliente", {"cliente": dati.get("cliente") or dati})
    if azione == "bozza":
        op = "preventivo" if dati.get("_preventivo") else "fattura"
        chiave = "preventivo" if op == "preventivo" else "fattura"
        corpo = dati.get(chiave) if isinstance(dati.get(chiave), dict) else {k: v for k, v in dati.items() if not k.startswith("_") and k != "id"}
        return fatturazione.operazione(c, op, {"id": str(dati.get("id") or ""), chiave: corpo})
    if azione in ("emetti", "incassa"):
        return fatturazione.operazione(c, azione, {"id": str(dati.get("id") or ""), "data": str(dati.get("data") or "")})
    return {"ok": False, "errore": "Azione non prevista."}


def in_attesa(c: str) -> list:
    rec = _get("apiattesa/" + c) or {}
    limite = time.time() - 7 * 86400
    return [x for x in rec.get("lista") or [] if x.get("t", 0) > limite]


def chiedi(c: str, u: dict, azione: str, dati: dict) -> dict:
    L = in_attesa(c)
    if len(L) >= 50:
        return {"ok": False, "errore": "Ci sono già troppe richieste da approvare."}
    nome = ""
    for k in (_get("apikeys_di/" + c) or {}).get("chiavi") or []:
        if k.get("h") == u.get("h"):
            nome = k.get("nome") or ""
    voce = {"id": secrets.token_hex(6), "azione": azione, "dati": dati, "t": time.time(), "chiave": nome,
            "riassunto": _riassunto(azione, dati, c)}
    L.append(voce)
    _set("apiattesa/" + c, {"lista": L})
    _avvisa(c, "Il tuo assistente IA chiede il permesso",
            f"<p>Ciao,</p><p>l'assistente che usa la chiave <b>{html.escape(nome or 'API')}</b> vuole: "
            f"<b>{html.escape(_NOMI.get(azione, azione))}</b> ({html.escape(voce['riassunto'])}).</p>"
            "<p>Per approvare o rifiutare apri TaxScan: Profilo, scheda «Assistenti IA e API». "
            "Se non fai niente, tra 7 giorni la richiesta scade.</p>")
    return {"ok": True, "in_attesa": True, "richiesta": voce["id"],
            "messaggio": "Questa azione va approvata dalla persona in TaxScan (Profilo, Assistenti IA e API). Le abbiamo mandato un'email."}


def _riassunto(azione: str, dati: dict, c: str = "") -> str:
    try:
        if azione == "incasso":
            return f"{float(dati.get('importo') or 0):.2f} €".replace(".", ",")
        if azione == "cliente":
            cl = dati.get("cliente") or dati
            return str(cl.get("denominazione") or " ".join(x for x in (cl.get("nome"), cl.get("cognome")) if x) or "cliente")[:80]
        if azione in ("emetti", "incassa"):
            import fatturazione
            d = fatturazione.carica(c)
            f = fatturazione._cerca(d.get("fatture") or [], str(dati.get("id") or ""))
            if f:
                return f"bozza per {fatturazione.nome_cliente(f.get('cliente'))}, {fatturazione.eur(fatturazione.totali(f, d.get('io') or {})['totale'])}"
        return "dettagli nella richiesta"
    except Exception:
        return "dettagli nella richiesta"



def decidi(c: str, rid: str, approva: bool) -> dict:
    L = in_attesa(c)
    voce = next((x for x in L if x.get("id") == rid), None)
    if not voce:
        return {"ok": False, "errore": "Richiesta non trovata o scaduta."}
    _set("apiattesa/" + c, {"lista": [x for x in L if x.get("id") != rid]})
    if not approva:
        return {"ok": True, "fatto": False, "attesa": in_attesa(c)}
    esito = esegui(c, voce["azione"], voce.get("dati") or {})
    ok = isinstance(esito, dict) and esito.get("ok") is not False
    return {"ok": True, "fatto": ok, "errore": "" if ok else (esito or {}).get("errore", "Non è andata a buon fine."), "attesa": in_attesa(c)}

# ------------------------------------------------------------------ autenticazione delle chiamate

def autentica(intestazioni) -> tuple[dict | None, int, str]:
    """(utente, codice_http, errore). utente = {c, accesso, h}."""
    k = str(intestazioni.get("x-api-key") or "").strip()
    a = str(intestazioni.get("authorization") or "").strip()
    if not k and a.lower().startswith("bearer "):
        k = a[7:].strip()
    if not k.startswith(PREFISSO) or len(k) > 80:
        return None, 401, "Manca la chiave API: mettila nell'intestazione Authorization: Bearer tsk_..."
    h = _h(k)
    rec = _get("apikey/" + h)
    if not rec or rec.get("revocata") or not rec.get("c"):
        return None, 401, "Chiave API non valida o eliminata."
    c = rec["c"]
    ora = time.time()
    uso = [t for t in _USO.get(h, []) if ora - t < 3600]
    if len(uso) >= LIMITE_ORA:
        return None, 429, "Troppe richieste in un'ora: riprova più tardi."
    _USO[h] = uso + [ora]
    if not db.carica_dashboard(c):
        return None, 401, "La situazione collegata a questa chiave non esiste più."
    if ora - _TOCCATA.get(h, 0) > 3600:
        _TOCCATA[h] = ora
        try:
            lst = _get("apikeys_di/" + c) or {}
            for x in lst.get("chiavi") or []:
                if x.get("h") == h:
                    x["usato"] = datetime.date.today().isoformat()
            _set("apikeys_di/" + c, lst)
        except Exception:
            pass
    return {"c": c, "accesso": rec.get("accesso") or "lettura", "h": h}, 200, ""


# ------------------------------------------------------------------ cosa restituisce l'API

def situazione(c: str) -> dict:
    d = db.carica_dashboard(c) or {}
    ac = d.get("anno_corrente") or {}
    so = d.get("soglia") or {}
    pr = d.get("profilo") or {}
    ps = d.get("prossima_scadenza") or {}
    num = d.get("numeri") or {}
    return {
        "anno": d.get("anno"),
        "incassi_anno": num.get("ricavi_anno_corrente") or ac.get("ricavi_finora"),
        "imposta_stimata": ac.get("imposta"), "contributi_stimati": ac.get("contributi"), "netto_stimato": ac.get("netto"),
        "quota_da_mettere_da_parte": d.get("quota_per_fattura"),
        "soglia": {"limite": so.get("limite") or 85000, "margine": so.get("margine"), "previsione_fine_anno": so.get("previsione"),
                   "livello": so.get("livello"), "messaggio": so.get("messaggio")},
        "profilo": {k: pr.get(k) for k in ("codice_ateco", "coefficiente", "aliquota", "gestione", "nome_cassa", "anni_nel_regime")},
        "prossima_scadenza": {k: ps.get(k) for k in ("data", "etichetta", "importo", "giorni")} if ps else None,
        "piano_mensile": d.get("mensile") or [],
        "avvisi": d.get("avvisi") or [],
        "nota": "Stime di TaxScan, non una consulenza: per i casi particolari fai controllare a un professionista.",
    }


def scadenze(c: str) -> dict:
    d = db.carica_dashboard(c) or {}
    import prova
    sch = d.get("_scheda") or {}
    return {"scadenze": [{k: s.get(k) for k in ("data", "etichetta", "importo", "giorni", "dettaglio")} for s in d.get("scadenze") or []],
            "bolli": prova._bolli_pagina(sch), "passate_non_pagate": prova._passate(sch),
            "f24": f"/d/{c}/f24?data=AAAA-MM-GG"}


# ------------------------------------------------------------------ documentazione

def openapi(base: str) -> dict:
    def op(summary, desc="", body=None, scrive=False, params=None):
        o = {"summary": summary, "description": desc + (" Richiede una chiave di lettura e modifica." if scrive else ""),
             "responses": {"200": {"description": "OK"}, "202": {"description": "In attesa: la persona deve approvare l'azione in TaxScan"}, "401": {"description": "Chiave mancante o non valida"},
                           "403": {"description": "La chiave è di sola lettura"}, "429": {"description": "Troppe richieste"}}}
        if params:
            o["parameters"] = params
        if body:
            o["requestBody"] = {"required": True, "content": {"application/json": {"schema": body}}}
        return o
    pid = [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}]
    riga = {"type": "object", "properties": {"descrizione": {"type": "string"}, "quantita": {"type": "number"}, "prezzo": {"type": "number"}}}
    return {
        "openapi": "3.1.0",
        "info": {"title": "TaxScan API", "version": "1.0.0",
                 "description": "API di TaxScan per chi ha la partita IVA in regime forfettario in Italia. Gli importi sono in euro. "
                                "I calcoli sono stime, non consulenza fiscale."},
        "servers": [{"url": base}],
        "components": {"securitySchemes": {"chiave": {"type": "http", "scheme": "bearer"}}},
        "security": [{"chiave": []}],
        "paths": {
            "/api/v1/situazione": {"get": op("La situazione fiscale",
                                              "Incassi dell'anno, imposta e contributi stimati, netto, quota da mettere da parte, soglia degli 85.000 €, prossima scadenza, piano mensile e avvisi.")},
            "/api/v1/scadenze": {"get": op("Le scadenze", "Scadenze di imposta e contributi con importi, bollo trimestre per trimestre e scadenze passate non segnate come pagate.")},
            "/api/v1/incassi": {"post": op("Segna un incasso", "Aggiunge un incasso all'anno e rifà tutti i calcoli.",
                                           {"type": "object", "required": ["importo"], "properties": {"importo": {"type": "number"}, "data": {"type": "string", "format": "date"}}}, True)},
            "/api/v1/clienti": {"get": op("I clienti in rubrica"),
                                "post": op("Crea o modifica un cliente", "Senza id crea un cliente nuovo.",
                                           {"type": "object", "properties": {"cliente": {"type": "object", "properties": {
                                               "id": {"type": "string"}, "tipo": {"type": "string", "enum": ["azienda", "privato"]},
                                               "denominazione": {"type": "string"}, "nome": {"type": "string"}, "cognome": {"type": "string"},
                                               "piva": {"type": "string"}, "cf": {"type": "string"}, "nazione": {"type": "string"},
                                               "indirizzo": {"type": "string"}, "cap": {"type": "string"}, "comune": {"type": "string"},
                                               "provincia": {"type": "string"}, "sdi": {"type": "string"}, "pec": {"type": "string"}, "email": {"type": "string"}}}}}, True)},
            "/api/v1/fatture": {"get": op("Le fatture", "Bozze ed emesse, con totali e stato dell'incasso."),
                                "post": op("Crea o modifica una bozza di fattura", "Il numero si assegna quando la emetti.",
                                           {"type": "object", "properties": {"id": {"type": "string"}, "fattura": {"type": "object", "properties": {
                                               "cliente_id": {"type": "string"}, "data": {"type": "string", "format": "date"},
                                               "righe": {"type": "array", "items": riga}, "rivalsa": {"type": "boolean"},
                                               "bollo_cliente": {"type": "boolean"}, "scadenza": {"type": "string", "format": "date"},
                                               "iban": {"type": "string"}, "note": {"type": "string"}}}}}, True)},
            "/api/v1/fatture/{id}/emetti": {"post": op("Emetti una bozza", "Assegna il numero e la rende definitiva.", None, True, pid)},
            "/api/v1/fatture/{id}/incassa": {"post": op("Segna una fattura come incassata", "", {"type": "object", "properties": {"data": {"type": "string", "format": "date"}}}, True, pid)},
            "/api/v1/fatture/{id}/pdf": {"get": op("Il PDF della fattura", "", None, False, pid)},
            "/api/v1/fatture/{id}/xml": {"get": op("Il file XML FatturaPA da caricare sul portale dell'Agenzia delle Entrate", "", None, False, pid)},
            "/api/v1/fatture/analizza": {"post": op("Leggi fatture caricate",
                                                    "Legge fatture XML, PDF o foto (in base64) e dice per servizio quanto hai incassato e con che coefficiente. Non salva i file.",
                                                    {"type": "object", "required": ["files"], "properties": {"files": {"type": "array", "items": {"type": "object", "properties": {
                                                        "nome": {"type": "string"}, "tipo": {"type": "string"}, "dati": {"type": "string", "description": "contenuto in base64"}}}}}})},
            "/api/v1/servizi": {"get": op("I servizi salvati", "Descrizione e prezzo dei servizi che la persona usa nelle fatture.")},
            "/api/v1/preventivi": {"get": op("I preventivi"),
                                   "post": op("Crea o modifica un preventivo", "Stessi campi della fattura; scadenza = valido fino al.",
                                              {"type": "object", "properties": {"id": {"type": "string"}, "preventivo": {"type": "object"}}}, True)},
            "/api/v1/piva/{piva}": {"get": op("Dati pubblici da una partita IVA", "Denominazione e indirizzo dal registro europeo VIES.", None, False,
                                              [{"name": "piva", "in": "path", "required": True, "schema": {"type": "string"}}])},
        },
    }


def pagina_doc(base: str) -> str:
    import privacy
    head = privacy.pagina().split("</style>", 1)[0]
    stile = """
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px}
pre{background:var(--bg);border-radius:10px;padding:12px 14px;overflow-x:auto;white-space:pre}
table{width:100%;border-collapse:collapse;font-size:14.5px}td{padding:9px 6px;border-top:1px solid var(--line);vertical-align:top}
td:first-child{white-space:nowrap;font-weight:600}td small{display:block;color:var(--mute)}
.m{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 7px;border-radius:6px;background:var(--bg);margin-right:6px}
"""
    righe = [("GET", "/api/v1/situazione", "La situazione fiscale: incassi, imposta e contributi stimati, netto, quota da mettere da parte, soglia, prossima scadenza.", ""),
             ("GET", "/api/v1/scadenze", "Scadenze con importi, bollo trimestre per trimestre, scadenze passate da sistemare.", ""),
             ("POST", "/api/v1/incassi", "Segna un incasso: {\"importo\": 1200, \"data\": \"2026-11-27\"}. Rifà tutti i calcoli.", "modifica"),
             ("GET", "/api/v1/clienti", "I clienti in rubrica.", ""),
             ("POST", "/api/v1/clienti", "Crea o modifica un cliente.", "modifica"),
             ("GET", "/api/v1/fatture", "Bozze ed emesse, con totali e incassi.", ""),
             ("POST", "/api/v1/fatture", "Crea o modifica una bozza: cliente, righe, data.", "modifica"),
             ("POST", "/api/v1/fatture/{id}/emetti", "Emette la bozza con il numero successivo.", "modifica"),
             ("POST", "/api/v1/fatture/{id}/incassa", "Segna la fattura come incassata.", "modifica"),
             ("GET", "/api/v1/fatture/{id}/pdf · /xml", "Il PDF per il cliente o il file XML per l'Agenzia delle Entrate.", ""),
             ("POST", "/api/v1/fatture/analizza", "Legge fatture caricate (XML, PDF, foto in base64) senza salvarle.", ""),
             ("GET", "/api/v1/servizi", "I servizi salvati, con descrizione e prezzo.", ""),
             ("GET · POST", "/api/v1/preventivi", "I preventivi; con POST ne crei o modifichi uno.", "modifica"),
             ("GET", "/api/v1/piva/{numero}", "Denominazione e indirizzo dal registro europeo VIES.", "")]
    tab = "".join(f'<tr><td><span class="m">{m}</span>{html.escape(p)}</td><td>{html.escape(d)}'
                  f'{"<small>Serve una chiave di lettura e modifica.</small>" if s else ""}</td></tr>' for m, p, d, s in righe)
    es = html.escape(f'curl {base}/api/v1/situazione \\\n  -H "Authorization: Bearer tsk_la_tua_chiave"')
    corpo = f"""</style><meta name="description" content="API di TaxScan: fai lavorare il tuo assistente IA sulla tua partita IVA in forfettario."></head><body><main>
<a href="/" style="text-decoration:none"><div class="logo">Tax<span>Scan</span></div></a>
<h1>API di TaxScan per gli assistenti IA</h1>
<p class="s">Con una chiave API il tuo assistente IA (o un altro programma) può fare quello che fai tu in TaxScan: leggere la tua situazione e le scadenze, segnare incassi, preparare ed emettere fatture, far leggere le fatture caricate.</p>
<div class="card">
<h2>Come si comincia</h2>
<p>1. Apri TaxScan, vai nel <b>Profilo</b>, scheda <b>Assistenti IA e API</b>, e crea una chiave. Scegli se l'assistente può solo leggere o anche modificare.</p>
<p>2. Copia la chiave: si vede una volta sola. Trattala come una password: chi la ha può vedere i tuoi dati fiscali.</p>
<p>3. Dalla all'assistente insieme a questo indirizzo, che descrive tutto quello che può fare: <code>{html.escape(base)}/api/openapi.json</code></p>
<pre>{es}</pre>
<p class="s">Usi Claude? Puoi anche aggiungere TaxScan come connettore: in quel caso non serve la chiave.</p>
</div>
<div class="card"><h2>Cosa può fare</h2><table>{tab}</table>
<p class="s">Per ogni azione che modifica qualcosa la persona sceglie se l'assistente può farla da solo o se deve chiedere: in quel caso la risposta è <code>202</code> con <code>"in_attesa": true</code>, e l'azione parte solo quando la persona la approva in TaxScan. Emettere una fattura, di base, va sempre approvato.</p>
<p class="s">Al massimo {LIMITE_ORA} richieste l'ora per chiave. Le risposte sono in JSON, gli importi in euro. I calcoli sono stime e non sostituiscono un professionista.</p></div>
<div class="card"><h2>Sicurezza</h2>
<p>Le chiavi non sono salvate in chiaro. Ti scriviamo un'email ogni volta che ne crei o ne elimini una. Puoi eliminarle quando vuoi dal Profilo: da quel momento smettono di funzionare. Se pensi che una chiave sia finita nelle mani sbagliate, eliminala e creane una nuova.</p></div>
</main></body></html>"""
    return head.replace("<title>Privacy - TaxScan</title>", "<title>API per gli assistenti IA - TaxScan</title>") + stile + corpo


# ------------------------------------------------------------------ rotte

def registra(mcp) -> None:
    import asyncio
    from starlette.responses import HTMLResponse, JSONResponse, Response
    import fatturazione
    import prova

    def base(request) -> str:
        import emailtpl
        return emailtpl.PUBLIC_URL

    async def utente(request, scrive=False):
        u, cod, err = await asyncio.to_thread(autentica, request.headers)
        if not u:
            return None, JSONResponse({"ok": False, "errore": err}, status_code=cod)
        if scrive and u["accesso"] != "scrittura":
            return None, JSONResponse({"ok": False, "errore": "Questa chiave è di sola lettura."}, status_code=403)
        return u, None

    async def corpo(request) -> dict:
        try:
            x = await request.json()
            return x if isinstance(x, dict) else {}
        except Exception:
            return {}

    def risposta(esito, chiavi=None):
        if isinstance(esito, dict) and esito.get("ok") is False:
            return JSONResponse(esito, status_code=400)
        if chiavi and isinstance(esito, dict) and isinstance(esito.get("dati"), dict):
            return JSONResponse({"ok": True, **{k: esito["dati"].get(k) for k in chiavi}, **({"id": esito["id"]} if esito.get("id") else {})})
        return JSONResponse(esito)

    def traccia(u, cosa):
        try:
            db.registra_evento("api_" + cosa, u["c"], {})
        except Exception:
            pass


    async def fai(u, azione, dati):
        traccia(u, azione)
        if permessi(u["c"]).get(azione) == "chiedi":
            esito = await asyncio.to_thread(chiedi, u["c"], u, azione, dati)
            return JSONResponse(esito, status_code=202 if esito.get("ok") else 400)
        return risposta(await asyncio.to_thread(esegui, u["c"], azione, dati), ["fatture", "clienti", "preventivi"] if azione != "incasso" else None)

    @mcp.custom_route("/api", methods=["GET"])
    async def api_doc(request):
        return HTMLResponse(pagina_doc(base(request)))

    @mcp.custom_route("/api/openapi.json", methods=["GET"])
    async def api_openapi(request):
        return JSONResponse(openapi(base(request)), headers={"Access-Control-Allow-Origin": "*"})

    @mcp.custom_route("/api/prova/chiavi", methods=["POST"])
    async def api_chiavi_app(request):
        x = await corpo(request)
        return JSONResponse(await asyncio.to_thread(chiavi_app, str(x.get("c", "")), str(x.get("op", "")), x.get("dati") or {}))

    @mcp.custom_route("/api/v1/situazione", methods=["GET"])
    async def v1_situazione(request):
        u, e = await utente(request)
        if e:
            return e
        traccia(u, "situazione")
        return JSONResponse({"ok": True, **(await asyncio.to_thread(situazione, u["c"]))})

    @mcp.custom_route("/api/v1/scadenze", methods=["GET"])
    async def v1_scadenze(request):
        u, e = await utente(request)
        if e:
            return e
        return JSONResponse({"ok": True, **(await asyncio.to_thread(scadenze, u["c"]))})

    @mcp.custom_route("/api/v1/incassi", methods=["POST"])
    async def v1_incassi(request):
        u, e = await utente(request, True)
        if e:
            return e
        return await fai(u, "incasso", await corpo(request))

    @mcp.custom_route("/api/v1/clienti", methods=["GET", "POST"])
    async def v1_clienti(request):
        scrive = request.method == "POST"
        u, e = await utente(request, scrive)
        if e:
            return e
        if not scrive:
            return risposta(await asyncio.to_thread(fatturazione.operazione, u["c"], "get", {}), ["clienti"])
        return await fai(u, "cliente", await corpo(request))

    @mcp.custom_route("/api/v1/fatture", methods=["GET", "POST"])
    async def v1_fatture(request):
        scrive = request.method == "POST"
        u, e = await utente(request, scrive)
        if e:
            return e
        if not scrive:
            return risposta(await asyncio.to_thread(fatturazione.operazione, u["c"], "get", {}), ["fatture", "prossimo", "io_completo"])
        return await fai(u, "bozza", await corpo(request))

    @mcp.custom_route("/api/v1/fatture/analizza", methods=["POST"])
    async def v1_analizza(request):
        u, e = await utente(request)
        if e:
            return e
        x = await corpo(request)
        traccia(u, "analizza")
        return risposta(await asyncio.to_thread(prova.fatture, u["c"], x.get("files")))

    @mcp.custom_route("/api/v1/fatture/{fid}/{azione}", methods=["GET", "POST"])
    async def v1_fattura_azione(request):
        fid, az = request.path_params.get("fid", ""), request.path_params.get("azione", "")
        if az in ("pdf", "xml") and request.method == "GET":
            u, e = await utente(request)
            if e:
                return e
            r = await asyncio.to_thread(fatturazione.file_fattura, u["c"], fid, az)
            if not r:
                return JSONResponse({"ok": False, "errore": "Fattura non trovata o non ancora emessa."}, status_code=404)
            dati, nome, mt = r
            return Response(dati, media_type=mt, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
        if az in ("emetti", "incassa") and request.method == "POST":
            u, e = await utente(request, True)
            if e:
                return e
            x = await corpo(request)
            return await fai(u, az, {"id": fid, "data": str(x.get("data") or "")})
        return JSONResponse({"ok": False, "errore": "Azione non prevista."}, status_code=404)


    @mcp.custom_route("/api/v1/servizi", methods=["GET"])
    async def v1_servizi(request):
        u, e = await utente(request)
        if e:
            return e
        return risposta(await asyncio.to_thread(fatturazione.operazione, u["c"], "get", {}), ["servizi"])

    @mcp.custom_route("/api/v1/preventivi", methods=["GET", "POST"])
    async def v1_preventivi(request):
        scrive = request.method == "POST"
        u, e = await utente(request, scrive)
        if e:
            return e
        if not scrive:
            return risposta(await asyncio.to_thread(fatturazione.operazione, u["c"], "get", {}), ["preventivi"])
        x = await corpo(request)
        x["_preventivo"] = True
        return await fai(u, "bozza", x)

    @mcp.custom_route("/api/v1/piva/{piva}", methods=["GET"])
    async def v1_piva(request):
        u, e = await utente(request)
        if e:
            return e
        return risposta(await asyncio.to_thread(fatturazione.cerca_piva, u["c"], request.path_params.get("piva", ""),
                                                request.query_params.get("paese", "IT")))
