"""
TaxScan - verifica dell'email con codice a 6 cifre (OTP) via Resend, e sessioni brevi.

Sostituisce l'email-come-chiave: prima di leggere o scrivere la scheda di qualcuno, o di
collegare Fatture in Cloud, l'utente deve dimostrare di avere accesso a quella casella di
posta. Non è un vero account con password, ma è un passo concreto avanti nella sicurezza:
chi non controlla l'email indicata non può più chiedere a TaxScan i dati di qualcun altro.

Flusso: manda_codice(email) genera un codice a 6 cifre, lo tiene in memoria per poco tempo e
lo manda via email. verifica_codice(email, codice) lo controlla e, se giusto, crea una
sessione (un token lungo e casuale) valida per 24 ore, salvata su database. Da quel momento
in poi le chiamate che leggono o scrivono dati sensibili richiedono quel token.
"""

import os
import secrets
import string
import time

import requests

import db

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_URL = "https://api.resend.com/emails"
MITTENTE = "TaxScan <no-reply@taxscan.ltd24.co.uk>"

_ALFABETO_TOKEN = string.ascii_letters + string.digits
_CODICE_DURATA_SECONDI = 10 * 60  # 10 minuti per usare il codice ricevuto
_SESSIONE_DURATA_ORE = 24

_CODICI_STORE: dict[str, tuple[str, float]] = {}  # email -> (codice, creato_alle)


def _pulisci_codici_scaduti() -> None:
    scadenza = time.time() - _CODICE_DURATA_SECONDI
    for k in [k for k, (_, t) in _CODICI_STORE.items() if t < scadenza]:
        del _CODICI_STORE[k]


def manda_codice(email: str) -> dict:
    """Genera un codice a 6 cifre, lo tiene in memoria e lo manda via email. Da richiamare ogni
    volta che serve verificare o riverificare un'email (sessione mancante o scaduta)."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY non configurato sul server.")
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("email non valida")
    _pulisci_codici_scaduti()
    codice = f"{secrets.randbelow(1_000_000):06d}"
    _CODICI_STORE[email] = (codice, time.time())
    risposta = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": MITTENTE,
            "to": email,
            "subject": f"Il tuo codice TaxScan: {codice}",
            "html": (
                f"<p>Il tuo codice di verifica TaxScan è:</p>"
                f"<p style='font-size:28px;font-weight:bold;letter-spacing:4px'>{codice}</p>"
                f"<p>Scade tra 10 minuti. Se non l'hai richiesto tu, ignora questa email.</p>"
            ),
        },
        timeout=15,
    )
    risposta.raise_for_status()
    return {"inviato": True, "email": email}


def verifica_codice(email: str, codice: str) -> str:
    """Controlla il codice inserito dall'utente. Se giusto (e non scaduto), crea e restituisce
    un token di sessione valido 24 ore. Il codice si usa una sola volta. Solleva ValueError se
    il codice è sbagliato, scaduto o mai richiesto."""
    email = (email or "").strip().lower()
    codice = (codice or "").strip()
    _pulisci_codici_scaduti()
    voce = _CODICI_STORE.get(email)
    if not voce or voce[0] != codice:
        raise ValueError("Codice sbagliato o scaduto. Richiedi un nuovo codice con verifica_email.")
    del _CODICI_STORE[email]
    token = "".join(secrets.choice(_ALFABETO_TOKEN) for _ in range(40))
    db.crea_sessione(token, email, _SESSIONE_DURATA_ORE)
    return token


def email_autenticata(email: str, token_sessione: str) -> bool:
    """True se il token di sessione è valido, non scaduto, e corrisponde a questa email."""
    email = (email or "").strip().lower()
    if not token_sessione:
        return False
    email_sessione = db.email_da_sessione(token_sessione)
    return bool(email_sessione) and email_sessione == email
