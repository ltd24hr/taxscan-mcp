"""
TaxScan - integrazione con Fatture in Cloud (OAuth 2.0 + lettura fatture emesse).

Flusso: collega_fatture_in_cloud genera un link di autorizzazione con uno "state"
temporaneo che lega la richiesta all'email dell'utente (senza questo, non sapremmo
a chi appartiene il codice che Fatture in Cloud restituisce dopo il login).
L'utente autorizza, Fatture in Cloud richiama /oauth/fic/callback sul nostro server
con un codice; lo scambiamo con un access_token (di breve durata) e un refresh_token
(di lunga durata, usato per rinnovare l'accesso senza richiedere un nuovo login).

Riferimenti: https://developers.fattureincloud.it/docs/authentication/code-flow/vanilla-code/
            https://developers.fattureincloud.it/docs/basics/scopes/
"""

import os
import secrets
import string
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

import db

CLIENT_ID = os.environ.get("FIC_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("FIC_CLIENT_SECRET", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://taxscan-mcp.onrender.com").rstrip("/")
REDIRECT_URI = f"{PUBLIC_URL}/oauth/fic/callback"

AUTH_URL = "https://api-v2.fattureincloud.it/oauth/authorize"
TOKEN_URL = "https://api-v2.fattureincloud.it/oauth/token"
API_BASE = "https://api-v2.fattureincloud.it"

# issued_documents.invoices:r legge le fatture emesse; situation:r legge il riepilogo del
# cruscotto Fatture in Cloud. Entrambe in sola lettura: TaxScan non scrive né modifica nulla.
SCOPE = "issued_documents.invoices:r situation:r"

_ALFABETO = string.ascii_letters + string.digits
_STATE_STORE: dict[str, tuple[str, float]] = {}  # state -> (email, creato_alle)
_STATE_DURATA_SECONDI = 15 * 60  # tempo massimo per completare il login su Fatture in Cloud


def _pulisci_stati_scaduti() -> None:
    scadenza = time.time() - _STATE_DURATA_SECONDI
    for k in [k for k, (_, t) in _STATE_STORE.items() if t < scadenza]:
        del _STATE_STORE[k]


def link_autorizzazione(email: str) -> str:
    """Costruisce il link a cui mandare l'utente per autorizzare TaxScan su Fatture in Cloud."""
    if not CLIENT_ID:
        raise RuntimeError("FIC_CLIENT_ID non configurato sul server.")
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email mancante")
    _pulisci_stati_scaduti()
    state = "".join(secrets.choice(_ALFABETO) for _ in range(24))
    _STATE_STORE[state] = (email, time.time())
    parametri = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(parametri)}"


def email_da_state(state: str) -> str | None:
    """Consuma lo state (si usa una sola volta) e restituisce l'email a cui era legato."""
    voce = _STATE_STORE.pop(state, None)
    return voce[0] if voce else None


def _scade_il(expires_in: int):
    # margine di 60 secondi per non usare mai un token già scaduto per un pelo
    return datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 60))


def scambia_codice(email: str, code: str) -> dict:
    """Scambia il codice ricevuto sul callback con access_token e refresh_token, e li salva."""
    risposta = requests.post(TOKEN_URL, json={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=15)
    risposta.raise_for_status()
    dati = risposta.json()
    db.salva_fic_token(email, dati["access_token"], dati["refresh_token"],
                        _scade_il(dati.get("expires_in", 3600)))
    return dati


def _rinnova(email: str, refresh_token: str) -> str:
    risposta = requests.post(TOKEN_URL, json={
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    }, timeout=15)
    risposta.raise_for_status()
    dati = risposta.json()
    collegamento = db.carica_fic_token(email)
    db.salva_fic_token(email, dati["access_token"], dati.get("refresh_token", refresh_token),
                        _scade_il(dati.get("expires_in", 3600)),
                        collegamento["company_id"] if collegamento else None,
                        collegamento["azienda_nome"] if collegamento else None)
    return dati["access_token"]


def token_valido(email: str) -> str | None:
    """Restituisce un access_token pronto all'uso (rinnovandolo se scaduto), o None se
    l'utente non ha mai collegato Fatture in Cloud."""
    collegamento = db.carica_fic_token(email)
    if not collegamento:
        return None
    scade_il = collegamento["scade_il"]
    if scade_il.tzinfo is None:
        scade_il = scade_il.replace(tzinfo=timezone.utc)
    if scade_il <= datetime.now(timezone.utc):
        return _rinnova(email, collegamento["refresh_token"])
    return collegamento["access_token"]


def lista_aziende(access_token: str) -> list:
    """Elenca le aziende Fatture in Cloud accessibili con questo token."""
    risposta = requests.get(f"{API_BASE}/user/companies",
                             headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    risposta.raise_for_status()
    dati = risposta.json().get("data", {})
    aziende = dati.get("companies") if isinstance(dati, dict) else dati
    return aziende or []


def fatture_incassate_anno(access_token: str, company_id: int, anno: int) -> dict:
    """Somma gli importi incassati (per cassa) nell'anno indicato, dalle fatture emesse.
    Prima versione: legge i pagamenti registrati su ogni fattura e somma quelli con data di
    incasso nell'anno richiesto, indipendentemente da quando la fattura è stata emessa - è il
    modo corretto di calcolare i ricavi di un forfettario. Da verificare con un account reale
    la prima volta che viene usata, perché i nomi esatti dei campi vanno confermati sul campo."""
    totale = 0.0
    fatture_lette = 0
    pagina = 1
    while True:
        risposta = requests.get(
            f"{API_BASE}/c/{company_id}/issued_documents",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"type": "invoice", "page": pagina, "per_page": 100},
            timeout=20,
        )
        risposta.raise_for_status()
        corpo = risposta.json()
        documenti = corpo.get("data", []) or []
        if not documenti:
            break
        for doc in documenti:
            fatture_lette += 1
            pagamenti = doc.get("payments_list") or doc.get("payments") or []
            for pagamento in pagamenti:
                data_pagata = pagamento.get("paid_date") or pagamento.get("payment_date")
                importo = pagamento.get("amount")
                if data_pagata and importo and str(data_pagata).startswith(str(anno)):
                    totale += float(importo)
        pagina_corrente = corpo.get("current_page")
        ultima_pagina = corpo.get("last_page")
        if not pagina_corrente or not ultima_pagina or pagina_corrente >= ultima_pagina:
            break
        pagina += 1
    return {
        "anno": anno,
        "ricavi_incassati_stimati": round(totale, 2),
        "fatture_esaminate": fatture_lette,
        "nota": "Somma dei pagamenti registrati su Fatture in Cloud con data di incasso in "
                f"questo anno, dalle fatture emesse. Controlla che corrisponda a quanto ti aspetti "
                "prima di usarlo per i calcoli: è la prima volta che questa lettura viene fatta "
                "con dati reali e va verificata.",
    }
