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
