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

ALTER TABLE utenti ADD COLUMN IF NOT EXISTS dashboard_id TEXT;

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

CREATE TABLE IF NOT EXISTS incentivi_settore (
    id SERIAL PRIMARY KEY,
    titolo TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    requisiti TEXT,
    codici_ateco TEXT NOT NULL,
    url_fonte TEXT,
    attivo BOOLEAN NOT NULL DEFAULT true,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE incentivi_settore ADD COLUMN IF NOT EXISTS ambito TEXT NOT NULL DEFAULT 'nazionale';
ALTER TABLE incentivi_settore ADD COLUMN IF NOT EXISTS regioni TEXT NOT NULL DEFAULT '';
ALTER TABLE incentivi_settore ADD COLUMN IF NOT EXISTS scadenza DATE;

CREATE TABLE IF NOT EXISTS colloqui_web (
    id TEXT PRIMARY KEY,
    scheda JSONB NOT NULL DEFAULT '{}'::jsonb,
    stato TEXT NOT NULL DEFAULT 'aperto',
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    aggiornato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dashboard (
    id TEXT PRIMARY KEY,
    dati JSONB NOT NULL,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messaggi (
    id SERIAL PRIMARY KEY,
    dashboard_id TEXT NOT NULL,
    ruolo TEXT NOT NULL,
    testo TEXT NOT NULL,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_messaggi_dashboard ON chat_messaggi (dashboard_id, creato_il);

CREATE TABLE IF NOT EXISTS eventi (
    id SERIAL PRIMARY KEY,
    tipo TEXT NOT NULL,
    riferimento TEXT,
    dettaglio JSONB,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS promemoria_inviati (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    tipo TEXT NOT NULL,
    chiave TEXT NOT NULL,
    inviato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (email, tipo, chiave)
);

CREATE TABLE IF NOT EXISTS feedback (
    email TEXT PRIMARY KEY,
    dashboard_id TEXT,
    consiglia TEXT,
    risposte JSONB NOT NULL DEFAULT '{}'::jsonb,
    commento TEXT,
    ricontatto BOOLEAN NOT NULL DEFAULT FALSE,
    risposto_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS email_opt_out (
    email TEXT PRIMARY KEY,
    disattivato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incentivi_mostrati (
    id SERIAL PRIMARY KEY,
    incentivo_id INTEGER NOT NULL REFERENCES incentivi_settore(id),
    email TEXT NOT NULL,
    mostrato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (incentivo_id, email)
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


def salva_scheda(email: str, scheda: dict) -> bool:
    """Salva o aggiorna la scheda per questa email. Restituisce True se l'utente è nuovo (prima
    scheda salvata), False se era già registrato."""
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email mancante")
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM utenti WHERE email = %s", (email,))
            nuovo = cur.fetchone() is None
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
    return nuovo


def imposta_dashboard_utente(email: str, id_dashboard: str) -> None:
    """Ricorda qual e' la dashboard di questo utente, per ritrovarla quando rientra con l'email."""
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE utenti SET dashboard_id = %s WHERE email = %s", (id_dashboard, email))
        conn.commit()


def dashboard_di_utente(email: str) -> str | None:
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT dashboard_id FROM utenti WHERE email = %s", (email,))
            riga = cur.fetchone()
    return riga[0] if riga and riga[0] else None


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

def candidato_gia_noto(url: str) -> bool:
    """True se questo url è già stato esaminato in un'esecuzione precedente del job (rilevante
    o no), per non rileggerlo ogni volta."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM avvisi_candidati WHERE url = %s", (url,))
            return cur.fetchone() is not None


def salva_candidato(fonte: str, titolo: str, url: str, pubblicato_il: str,
                    stato: str = "nuovo") -> bool:
    """Registra una voce esaminata dal job periodico, se non già presente (dedup per url).
    stato='nuovo' per le voci rilevanti da rivedere, 'irrilevante' per quelle scartate dal
    filtro (tenute solo per non rileggerle ad ogni esecuzione). Restituisce True se inserita ora,
    False se era già nota."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO avvisi_candidati (fonte, titolo, url, pubblicato_il, stato) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (url) DO NOTHING",
                (fonte, titolo, url, pubblicato_il, stato),
            )
            inserita = cur.rowcount > 0
        conn.commit()
    return inserita


def conteggio_candidati() -> dict:
    """Diagnostica: quante voci sono state esaminate finora, per stato."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT stato, count(*) FROM avvisi_candidati GROUP BY stato")
            righe = cur.fetchall()
    return {stato: n for stato, n in righe}


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


# --------------------------------------------------------------------- Dashboard (istantanea)

def salva_dashboard(id_dashboard: str, dati: dict) -> None:
    """Istantanea della situazione dell'utente, dietro un id casuale e non indovinabile.
    Non contiene nome ne' email: solo cifre e scadenze."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO dashboard (id, dati) VALUES (%s, %s) "
                        "ON CONFLICT (id) DO UPDATE SET dati = EXCLUDED.dati, creato_il = now()",
                        (id_dashboard, Json(dati)))
        conn.commit()


def carica_dashboard(id_dashboard: str) -> dict | None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT dati FROM dashboard WHERE id = %s", (id_dashboard,))
            riga = cur.fetchone()
    return riga[0] if riga else None


# --------------------------------------------------------------------- Chat con l'assistente

def salva_chat(id_dashboard: str, ruolo: str, testo: str) -> None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO chat_messaggi (dashboard_id, ruolo, testo) VALUES (%s, %s, %s)",
                        (id_dashboard, ruolo, testo))
        conn.commit()


def conta_domande_oggi(id_dashboard: str | None) -> int:
    """Domande fatte oggi (giorno UTC) da una dashboard, o su tutto il servizio se id_dashboard e' None."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            if id_dashboard is None:
                cur.execute("SELECT count(*) FROM chat_messaggi WHERE ruolo = 'utente' "
                            "AND creato_il >= date_trunc('day', now())")
            else:
                cur.execute("SELECT count(*) FROM chat_messaggi WHERE ruolo = 'utente' AND dashboard_id = %s "
                            "AND creato_il >= date_trunc('day', now())", (id_dashboard,))
            return cur.fetchone()[0]


# --------------------------------------------------------------------- Eventi (uso e abbandoni)

def registra_evento(tipo: str, riferimento: str | None = None, dettaglio: dict | None = None) -> None:
    """Segna un evento d'uso (pagina aperta, domanda mostrata, quadro generato, utente registrato...).
    Non deve mai rompere il flusso: chi chiama lo avvolge in try/except."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO eventi (tipo, riferimento, dettaglio) VALUES (%s, %s, %s)",
                        (tipo, riferimento, Json(dettaglio) if dettaglio is not None else None))
        conn.commit()


def statistiche_eventi(giorni: int = 30) -> dict:
    """Conteggi per tipo di evento negli ultimi N giorni, e per i colloqui web non completati
    l'ultima domanda vista (= dove la gente si ferma)."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tipo, count(*) FROM eventi WHERE creato_il > now() - (%s || ' days')::interval "
                "GROUP BY tipo ORDER BY tipo", (giorni,))
            per_tipo = {t: n for t, n in cur.fetchall()}
            cur.execute(
                """
                WITH ultimi AS (
                    SELECT DISTINCT ON (riferimento) riferimento, dettaglio->>'campo' AS campo
                    FROM eventi
                    WHERE tipo = 'web_domanda' AND riferimento IS NOT NULL
                      AND creato_il > now() - (%s || ' days')::interval
                    ORDER BY riferimento, creato_il DESC
                )
                SELECT u.campo, count(*) FROM ultimi u
                WHERE u.riferimento NOT IN (
                    SELECT riferimento FROM eventi WHERE tipo = 'web_completato' AND riferimento IS NOT NULL)
                GROUP BY u.campo ORDER BY count(*) DESC
                """, (giorni,))
            abbandoni = [{"ultima_domanda_vista": c, "colloqui": n} for c, n in cur.fetchall()]
    return {"giorni": giorni, "per_tipo": per_tipo, "colloqui_web_fermi_per_domanda": abbandoni}


# --------------------------------------------------------------------- Colloquio web

def crea_colloquio_web(id_colloquio: str) -> None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO colloqui_web (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                        (id_colloquio,))
        conn.commit()


def carica_colloquio_web(id_colloquio: str) -> dict | None:
    """Scheda e stato di un colloquio compilato dalla pagina web, o None se l'id non esiste."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT scheda, stato, aggiornato_il FROM colloqui_web WHERE id = %s",
                        (id_colloquio,))
            riga = cur.fetchone()
    if not riga:
        return None
    return {"scheda": riga[0] or {}, "stato": riga[1], "aggiornato_il": riga[2]}


def salva_colloquio_web(id_colloquio: str, scheda: dict, stato: str) -> None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE colloqui_web SET scheda = %s, stato = %s, aggiornato_il = now() WHERE id = %s",
                (Json(scheda), stato, id_colloquio),
            )
        conn.commit()


# --------------------------------------------------------------------- Incentivi di settore

def aggiungi_incentivo(titolo: str, descrizione: str, requisiti: str, codici_ateco: str,
                       url_fonte: str, ambito: str = "nazionale", regioni: str = "",
                       scadenza: str | None = None) -> int:
    """Inserisce un incentivo nella lista curata a mano. codici_ateco è una stringa con i
    prefissi ATECO separati da virgola (es. "43,43.3" per edilizia/finiture): un utente con
    codice che inizia per uno di questi prefissi lo vedrà ("" = tutti i settori). ambito:
    nazionale / regionale / locale. regioni: nomi separati da virgola ("" = tutte). scadenza:
    data ISO dopo la quale non si mostra piu'. Restituisce l'id creato."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO incentivi_settore (titolo, descrizione, requisiti, codici_ateco, "
                "url_fonte, ambito, regioni, scadenza) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (titolo, descrizione, requisiti, codici_ateco, url_fonte, ambito or "nazionale",
                 regioni or "", scadenza or None),
            )
            id_nuovo = cur.fetchone()[0]
        conn.commit()
    return id_nuovo


def lista_incentivi() -> list[dict]:
    """Diagnostica/amministrazione: tutti gli incentivi curati, attivi e non."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titolo, codici_ateco, attivo, creato_il FROM incentivi_settore "
                "ORDER BY creato_il DESC"
            )
            righe = cur.fetchall()
    return [{"id": r[0], "titolo": r[1], "codici_ateco": r[2], "attivo": r[3],
             "creato_il": r[4]} for r in righe]


def disattiva_incentivo(id_incentivo: int) -> None:
    """Disattiva un incentivo (es. perché scaduto o inserito per errore): non verrà più
    mostrato a nessuno, anche se qualcuno non l'aveva ancora visto."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE incentivi_settore SET attivo = false WHERE id = %s", (id_incentivo,))
        conn.commit()


def incentivi_non_mostrati(email: str, codice_ateco: str, regione: str = "") -> list[dict]:
    """Gli incentivi attivi il cui codice ATECO corrisponde (per prefisso) a quello dell'utente,
    e che non gli sono ancora stati mostrati."""
    email = (email or "").strip().lower()
    codice_ateco = (codice_ateco or "").strip()
    if not email:
        return []
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titolo, descrizione, requisiti, url_fonte, codici_ateco, ambito, regioni, scadenza "
                "FROM incentivi_settore WHERE attivo = true AND (scadenza IS NULL OR scadenza >= CURRENT_DATE) "
                "AND id NOT IN "
                "(SELECT incentivo_id FROM incentivi_mostrati WHERE email = %s)",
                (email,),
            )
            righe = cur.fetchall()
    risultato = []
    for r in righe:
        if _incentivo_pertinente(r[5], r[7], codice_ateco, regione):
            risultato.append({"id": r[0], "titolo": r[1], "descrizione": r[2], "requisiti": r[3],
                              "url_fonte": r[4], "ambito": r[6],
                              "scadenza": r[8].isoformat() if r[8] else None})
    return risultato


def _incentivo_pertinente(codici_ateco: str, regioni: str, codice_ateco: str, regione: str) -> bool:
    """Settore: prefisso ATECO ("" = tutti). Regione: elenco ("" = tutte; se l'utente non ha
    una regione nota, le voci regionali non si mostrano)."""
    prefissi = [p.strip() for p in (codici_ateco or "").split(",") if p.strip()]
    if prefissi and not any((codice_ateco or "").startswith(p) for p in prefissi):
        return False
    elenco = [x.strip().lower() for x in (regioni or "").split(",") if x.strip()]
    if elenco and (regione or "").strip().lower() not in elenco:
        return False
    return True


def incentivi_per_profilo(codice_ateco: str, regione: str = "") -> list[dict]:
    """Lista curata pertinente a settore e regione, senza segnare nulla come mostrato
    (serve alla ricerca di agevolazioni, che si puo' ripetere)."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titolo, descrizione, requisiti, url_fonte, codici_ateco, ambito, regioni, scadenza "
                "FROM incentivi_settore WHERE attivo = true AND (scadenza IS NULL OR scadenza >= CURRENT_DATE)")
            righe = cur.fetchall()
    return [{"id": r[0], "titolo": r[1], "descrizione": r[2], "requisiti": r[3], "url_fonte": r[4],
             "ambito": r[6], "scadenza": r[8].isoformat() if r[8] else None}
            for r in righe if _incentivo_pertinente(r[5], r[7], codice_ateco, regione)]


def segna_incentivo_mostrato(incentivo_id: int, email: str) -> None:
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO incentivi_mostrati (incentivo_id, email) VALUES (%s, %s) "
                "ON CONFLICT (incentivo_id, email) DO NOTHING",
                (incentivo_id, email),
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


# --------------------------------------------------------------------- Promemoria per email

def email_disattivate(email: str) -> bool:
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM email_opt_out WHERE email = %s", (email,))
            return cur.fetchone() is not None


def disattiva_email(email: str) -> None:
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO email_opt_out (email) VALUES (%s) ON CONFLICT DO NOTHING", (email,))
        conn.commit()


def riattiva_email(email: str) -> None:
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM email_opt_out WHERE email = %s", (email,))
        conn.commit()


def prenota_promemoria(email: str, tipo: str, chiave: str) -> bool:
    """Segna il promemoria come mandato. False se c'era gia' (nessun doppio invio)."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO promemoria_inviati (email, tipo, chiave) VALUES (%s, %s, %s) "
                        "ON CONFLICT DO NOTHING", ((email or "").strip().lower(), tipo, chiave))
            nuovo = cur.rowcount == 1
        conn.commit()
    return nuovo


def promemoria_gia_inviato(email: str, tipo: str, chiave: str) -> bool:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM promemoria_inviati WHERE email = %s AND tipo = %s AND chiave = %s",
                        ((email or "").strip().lower(), tipo, chiave))
            return cur.fetchone() is not None


def annulla_promemoria(email: str, tipo: str, chiave: str) -> None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM promemoria_inviati WHERE email = %s AND tipo = %s AND chiave = %s",
                        ((email or "").strip().lower(), tipo, chiave))
        conn.commit()


def giorni_dall_ultimo_promemoria(email: str) -> int | None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT extract(day FROM now() - max(inviato_il)) FROM promemoria_inviati "
                        "WHERE email = %s", ((email or "").strip().lower(),))
            riga = cur.fetchone()
    return int(riga[0]) if riga and riga[0] is not None else None


def utenti_bandi_intro_da_mandare() -> list[dict]:
    """Utenti iscritti da 15 minuti a 2 giorni che non hanno ancora avuto l'email sui bandi (e non si sono disiscritti)."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.email, u.dashboard_id FROM promemoria_inviati b JOIN utenti u ON u.email = b.email "
                "WHERE b.tipo = 'benvenuto' AND b.inviato_il < now() - interval '15 minutes' "
                "AND b.inviato_il > now() - interval '2 days' AND u.dashboard_id IS NOT NULL "
                "AND u.email NOT IN (SELECT email FROM email_opt_out) "
                "AND NOT EXISTS (SELECT 1 FROM promemoria_inviati x WHERE x.email = u.email AND x.tipo = 'bandi_intro')")
            righe = cur.fetchall()
    return [{"email": r[0], "dashboard_id": r[1]} for r in righe]


# --------------------------------------------------------------------- Sondaggio di feedback

def salva_feedback(email: str, id_dashboard: str, consiglia: str, risposte: dict, commento: str, ricontatto: bool) -> None:
    """Salva (o aggiorna) la risposta al sondaggio di un utente. Una sola riga per email."""
    email = (email or "").strip().lower()
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (email, dashboard_id, consiglia, risposte, commento, ricontatto) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (email) DO UPDATE SET dashboard_id = EXCLUDED.dashboard_id, "
                "consiglia = EXCLUDED.consiglia, risposte = EXCLUDED.risposte, commento = EXCLUDED.commento, "
                "ricontatto = EXCLUDED.ricontatto, risposto_il = now()",
                (email, id_dashboard, consiglia, Json(risposte or {}), commento or "", bool(ricontatto)))
        conn.commit()


def feedback_di(email: str) -> dict | None:
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT consiglia, risposte, commento, ricontatto FROM feedback WHERE email = %s",
                        ((email or "").strip().lower(),))
            r = cur.fetchone()
    return {"consiglia": r[0], "risposte": r[1] or {}, "commento": r[2] or "", "ricontatto": bool(r[3])} if r else None


def utenti_feedback_da_mandare() -> list[dict]:
    """Iscritti da piu' di 24 ore (e meno di 7 giorni) senza ancora la richiesta di feedback."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.email, u.dashboard_id FROM promemoria_inviati b JOIN utenti u ON u.email = b.email "
                "WHERE b.tipo = 'benvenuto' AND b.inviato_il < now() - interval '24 hours' "
                "AND b.inviato_il > now() - interval '7 days' AND u.dashboard_id IS NOT NULL "
                "AND u.email NOT IN (SELECT email FROM email_opt_out) "
                "AND u.email NOT IN (SELECT email FROM feedback) "
                "AND NOT EXISTS (SELECT 1 FROM promemoria_inviati x WHERE x.email = u.email AND x.tipo = 'feedback')")
            righe = cur.fetchall()
    return [{"email": r[0], "dashboard_id": r[1]} for r in righe]


def utenti_feedback_reminder() -> list[dict]:
    """Chi ha avuto la richiesta da 3 giorni (ma non da piu' di 10) e non ha risposto, senza ancora il promemoria."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.email, u.dashboard_id FROM promemoria_inviati b JOIN utenti u ON u.email = b.email "
                "WHERE b.tipo = 'feedback' AND b.inviato_il < now() - interval '3 days' "
                "AND b.inviato_il > now() - interval '10 days' AND u.dashboard_id IS NOT NULL "
                "AND u.email NOT IN (SELECT email FROM email_opt_out) "
                "AND u.email NOT IN (SELECT email FROM feedback) "
                "AND NOT EXISTS (SELECT 1 FROM promemoria_inviati x WHERE x.email = u.email AND x.tipo = 'feedback_reminder')")
            righe = cur.fetchall()
    return [{"email": r[0], "dashboard_id": r[1]} for r in righe]


def feedback_riepilogo() -> dict:
    """Per la pagina privata: risposte, quanti inviti, e chi non ha risposto nemmeno al promemoria (da contattare)."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(DISTINCT email) FROM promemoria_inviati WHERE tipo = 'feedback'")
            inviati = cur.fetchone()[0]
            cur.execute("SELECT email, consiglia, risposte, commento, ricontatto, risposto_il FROM feedback "
                        "ORDER BY risposto_il DESC")
            risposte = [{"email": r[0], "consiglia": r[1], "risposte": r[2] or {}, "commento": r[3] or "",
                         "ricontatto": bool(r[4]), "risposto_il": r[5].isoformat() if r[5] else ""}
                        for r in cur.fetchall()]
            cur.execute(
                "SELECT b.email, b.inviato_il, (b.email IN (SELECT email FROM email_opt_out)) FROM promemoria_inviati b "
                "WHERE b.tipo = 'feedback' AND b.inviato_il < now() - interval '6 days' "
                "AND b.email NOT IN (SELECT email FROM feedback) "
                "AND EXISTS (SELECT 1 FROM promemoria_inviati x WHERE x.email = b.email AND x.tipo = 'feedback_reminder') "
                "ORDER BY b.inviato_il")
            da_contattare = [{"email": r[0], "invitato_il": r[1].isoformat() if r[1] else "", "disiscritto": bool(r[2])}
                             for r in cur.fetchall()]
    return {"inviati": inviati, "risposte": risposte, "da_contattare": da_contattare}


def utenti_per_promemoria() -> list[dict]:
    """Utenti con dashboard collegata, che non hanno disattivato le email."""
    with _connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email, scheda, dashboard_id, creato_il, aggiornato_il FROM utenti "
                        "WHERE dashboard_id IS NOT NULL AND email NOT IN (SELECT email FROM email_opt_out)")
            righe = cur.fetchall()
    return [{"email": r[0], "scheda": r[1], "dashboard_id": r[2], "creato_il": r[3], "aggiornato_il": r[4]}
            for r in righe]


# --------------------------------------------------------------------- Cancellazione dei dati (GDPR)

def cancella_dati(email: str | None, id_dashboard: str) -> None:
    """Cancella tutto cio' che riguarda una dashboard e, se c'e', l'email collegata. Un'unica transazione."""
    email = (email or "").strip().lower() or None
    with _connetti() as conn:
        with conn.cursor() as cur:
            if email:
                for tabella in ("sessioni", "fic_collegamenti", "avvisi_inviati", "avvisi_opt_out",
                                "incentivi_mostrati", "promemoria_inviati", "email_opt_out", "feedback", "utenti"):
                    cur.execute(f"DELETE FROM {tabella} WHERE email = %s", (email,))
                cur.execute("DELETE FROM eventi WHERE riferimento = %s", (email,))
            cur.execute("DELETE FROM chat_messaggi WHERE dashboard_id = %s", (id_dashboard,))
            cur.execute("DELETE FROM colloqui_web WHERE id = %s", (id_dashboard,))
            cur.execute("DELETE FROM eventi WHERE riferimento = %s", (id_dashboard,))
            cur.execute("DELETE FROM dashboard WHERE id = %s", (id_dashboard,))
        conn.commit()
