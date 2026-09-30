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

CREATE TABLE IF NOT EXISTS avvisi_candidati (
    id SERIAL PRIMARY KEY,
    fonte TEXT NOT NULL,
    titolo TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    pubblicato_il TEXT,
    trovato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    stato TEXT NOT NULL DEFAULT 'nuovo',
    titolo_utente TEXT,
    riassunto TEXT,
    revisionato_il TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS avvisi_inviati (
    id SERIAL PRIMARY KEY,
    candidato_id INTEGER NOT NULL REFERENCES avvisi_candidati(id),
    email TEXT NOT NULL,
    mandato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    menzionato_in_chat BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS avvisi_opt_out (
    email TEXT PRIMARY KEY,
    disattivato_il TIMESTAMPTZ NOT NULL DEFAULT now()
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


# --------------------------------------------------------------------- Avvisi normativi

def salva_candidato(fonte: str, titolo: str, url: str, pubblicato_il: str) -> bool:
    """Registra una voce trovata dal job periodico, se non già presente (dedup per url).
    Restituisce True se è stata inserita ora (nuova), False se era già nota."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO avvisi_candidati (fonte, titolo, url, pubblicato_il) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (url) DO NOTHING",
                (fonte, titolo, url, pubblicato_il),
            )
            inserita = cur.rowcount > 0
        conn.commit()
    return inserita


def candidati_nuovi() -> list[dict]:
    """Le voci trovate e non ancora revisionate (approvate o scartate)."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, fonte, titolo, url, pubblicato_il, trovato_il "
                "FROM avvisi_candidati WHERE stato = 'nuovo' ORDER BY trovato_il"
            )
            righe = cur.fetchall()
    return [{"id": r[0], "fonte": r[1], "titolo": r[2], "url": r[3],
             "pubblicato_il": r[4], "trovato_il": r[5]} for r in righe]


def dettaglio_candidato(id_candidato: int) -> dict | None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, fonte, titolo, url, pubblicato_il, stato "
                "FROM avvisi_candidati WHERE id = %s",
                (id_candidato,),
            )
            riga = cur.fetchone()
    if not riga:
        return None
    return {"id": riga[0], "fonte": riga[1], "titolo": riga[2], "url": riga[3],
            "pubblicato_il": riga[4], "stato": riga[5]}


def approva_candidato(id_candidato: int, titolo_utente: str, riassunto: str) -> None:
    """Segna un candidato come approvato, con il titolo e il riassunto in linguaggio semplice
    da mandare agli utenti."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE avvisi_candidati SET stato = 'approvato', titolo_utente = %s, "
                "riassunto = %s, revisionato_il = now() WHERE id = %s",
                (titolo_utente, riassunto, id_candidato),
            )
        conn.commit()


def scarta_candidato(id_candidato: int) -> None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE avvisi_candidati SET stato = 'scartato', revisionato_il = now() "
                "WHERE id = %s",
                (id_candidato,),
            )
        conn.commit()


def utenti_iscritti_avvisi() -> list[str]:
    """Le email di tutti gli utenti con una scheda salvata, esclusi quelli che hanno disattivato
    gli avvisi normativi."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email FROM utenti WHERE email NOT IN (SELECT email FROM avvisi_opt_out)"
            )
            righe = cur.fetchall()
    return [r[0] for r in righe]


def registra_invio_avviso(id_candidato: int, email: str) -> None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO avvisi_inviati (candidato_id, email) VALUES (%s, %s)",
                (id_candidato, email),
            )
        conn.commit()


def avvisi_da_menzionare(email: str) -> list[dict]:
    """Gli avvisi già mandati via email a questo utente ma non ancora citati in una
    conversazione."""
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.titolo_utente, c.riassunto, c.url, i.mandato_il
                FROM avvisi_inviati i JOIN avvisi_candidati c ON c.id = i.candidato_id
                WHERE i.email = %s AND i.menzionato_in_chat = false
                ORDER BY i.mandato_il
                """,
                (email,),
            )
            righe = cur.fetchall()
    return [{"titolo": r[0], "riassunto": r[1], "url": r[2], "mandato_il": r[3]} for r in righe]


def segna_avvisi_menzionati(email: str) -> None:
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE avvisi_inviati SET menzionato_in_chat = true "
                "WHERE email = %s AND menzionato_in_chat = false",
                (email,),
            )
        conn.commit()


def disattiva_avvisi(email: str) -> None:
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO avvisi_opt_out (email) VALUES (%s) ON CONFLICT (email) DO NOTHING",
                (email,),
            )
        conn.commit()


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
