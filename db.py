"""
TaxScan - persistenza della scheda utente su Postgres (Supabase).

Chiave di ricerca: l'email dell'utente. Non è un vero login (chiunque conosca
l'email altrui potrebbe in teoria chiedere la sua scheda) - è un compromesso
accettato per la fase di validazione, primo passo verso un account vero che
servirà comunque per collegare Fatture in Cloud più avanti.
"""

import os

import psycopg2
from psycopg2.extras import Json

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS utenti (
    email TEXT PRIMARY KEY,
    scheda JSONB NOT NULL DEFAULT '{}'::jsonb,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    aggiornato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fic_collegamenti (
    email TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    scade_il TIMESTAMPTZ NOT NULL,
    company_id BIGINT,
    azienda_nome TEXT,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    aggiornato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessioni (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    scade_il TIMESTAMPTZ NOT NULL,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _connetti():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL non configurato: il server non può salvare né ritrovare le schede.")
    return psycopg2.connect(DATABASE_URL)


def inizializza() -> None:
    """Crea la tabella se non esiste già. Va chiamata una volta all'avvio del server."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
        conn.commit()


def carica_scheda(email: str) -> dict | None:
    """Restituisce la scheda salvata per questa email, o None se non esiste."""
    email = (email or "").strip().lower()
    if not email:
        return None
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT scheda FROM utenti WHERE email = %s", (email,))
            riga = cur.fetchone()
    return riga[0] if riga else None


def salva_scheda(email: str, scheda: dict) -> None:
    """Salva o aggiorna la scheda per questa email."""
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email mancante")
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO utenti (email, scheda, aggiornato_il)
                VALUES (%s, %s, now())
                ON CONFLICT (email) DO UPDATE
                SET scheda = EXCLUDED.scheda, aggiornato_il = now()
                """,
                (email, Json(scheda)),
            )
        conn.commit()


# --------------------------------------------------------------------- Fatture in Cloud

def salva_fic_token(email: str, access_token: str, refresh_token: str, scade_il,
                     company_id: int | None = None, azienda_nome: str | None = None) -> None:
    """Salva o aggiorna il collegamento Fatture in Cloud per questa email."""
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email mancante")
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fic_collegamenti
                    (email, access_token, refresh_token, scade_il, company_id, azienda_nome, aggiornato_il)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (email) DO UPDATE
                SET access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    scade_il = EXCLUDED.scade_il,
                    company_id = COALESCE(EXCLUDED.company_id, fic_collegamenti.company_id),
                    azienda_nome = COALESCE(EXCLUDED.azienda_nome, fic_collegamenti.azienda_nome),
                    aggiornato_il = now()
                """,
                (email, access_token, refresh_token, scade_il, company_id, azienda_nome),
            )
        conn.commit()


def carica_fic_token(email: str) -> dict | None:
    """Restituisce il collegamento Fatture in Cloud salvato per questa email, o None."""
    email = (email or "").strip().lower()
    if not email:
        return None
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT access_token, refresh_token, scade_il, company_id, azienda_nome
                FROM fic_collegamenti WHERE email = %s
                """,
                (email,),
            )
            riga = cur.fetchone()
    if not riga:
        return None
    return {
        "access_token": riga[0], "refresh_token": riga[1], "scade_il": riga[2],
        "company_id": riga[3], "azienda_nome": riga[4],
    }


# --------------------------------------------------------------------- Sessioni (login)

def crea_sessione(token: str, email: str, durata_ore: int) -> None:
    """Registra una nuova sessione valida per durata_ore, dopo che l'utente ha confermato il
    codice ricevuto via email."""
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessioni (token, email, scade_il) "
                "VALUES (%s, %s, now() + (%s || ' hours')::interval)",
                (token, email, durata_ore),
            )
        conn.commit()


def email_da_sessione(token: str) -> str | None:
    """Restituisce l'email legata a questo token se la sessione esiste e non è scaduta,
    altrimenti None."""
    if not token:
        return None
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email FROM sessioni WHERE token = %s AND scade_il > now()",
                (token,),
            )
            riga = cur.fetchone()
    return riga[0] if riga else None


def imposta_azienda_fic(email: str, company_id: int, azienda_nome: str) -> None:
    """Registra quale azienda Fatture in Cloud usare, dopo che l'utente ha scelto tra più aziende."""
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fic_collegamenti SET company_id = %s, azienda_nome = %s, aggiornato_il = now() "
                "WHERE email = %s",
                (company_id, azienda_nome, email),
            )
        conn.commit()
