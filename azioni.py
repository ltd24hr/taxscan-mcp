"""TaxScan - email per le azioni compiute e promemoria per quelle non fatte (prototipo /prova).

- La pagina /prova avvisa il server ogni volta che l'utente fa qualcosa (fattura caricata, risparmio calcolato,
  task completato...): qui si salva l'azione e, se l'utente ha lasciato l'email, parte la conferma.
- Una volta al giorno (dentro /cron/promemoria) partono i promemoria per quello che non e' stato fatto.
- Ogni email si manda una sola volta per utente e azione, ha il link per disiscriversi, e un link che
  riporta l'utente al punto da cui riprendere.
- Il link Trustpilot parte SOLO dopo un beneficio quantificato (il primo task completato), e solo se su Render
  c'e' la variabile TRUSTPILOT_URL.
"""
import html
import os
import re
import threading

import db
import emailtpl

AZIONI = {"fattura_caricata", "analisi_avviata", "risparmio_calcolato", "task_cod", "task_contratto", "task_fatture",
          "contratto_firmato", "contratto_inviato", "beneficio_ottenuto", "trustpilot_click"}
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
_ok = False
_lock = threading.Lock()


def _e(x):
    return html.escape(str(x if x is not None else ""))


def _tabelle():
    global _ok
    if _ok:
        return
    with _lock:
        if _ok:
            return
        with db._connetti() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS prova_azioni (c TEXT NOT NULL, azione TEXT NOT NULL, "
                            "euro INTEGER NOT NULL DEFAULT 0, creato TIMESTAMPTZ NOT NULL DEFAULT now(), "
                            "PRIMARY KEY (c, azione))")
                cur.execute("CREATE TABLE IF NOT EXISTS prova_email (c TEXT PRIMARY KEY, email TEXT NOT NULL, "
                            "creato TIMESTAMPTZ NOT NULL DEFAULT now())")
            conn.commit()
        _ok = True


def _link(c: str) -> str:
    return f"{emailtpl.PUBLIC_URL}/prova?c={c}&vai=g"


def _eur(n) -> str:
    import promemoria as P
    return P.eur(n)


def email_di(c: str) -> str:
    _tabelle()
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM prova_email WHERE c = %s", (c,))
            r = cur.fetchone()
    return (r[0] if r else "") or ""


def _azioni_di(c: str) -> dict:
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT azione, euro FROM prova_azioni WHERE c = %s", (c,))
            return {a: e for a, e in cur.fetchall()}


def _giorni(c: str, azione: str) -> float:
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT extract(epoch FROM now() - creato) / 86400 FROM prova_azioni WHERE c = %s AND azione = %s",
                        (c, azione))
            r = cur.fetchone()
    return float(r[0]) if r else 0.0


def _recensione(email: str, c: str, euro: int) -> bool:
    tp = os.environ.get("TRUSTPILOT_URL", "").strip()
    if not tp or euro <= 0:
        return False
    import auth
    import promemoria as P
    if db.email_disattivate(email) or not db.prenota_promemoria(email, "az_trustpilot", c):
        return False
    corpo = (f"<p><b>Hai già attivato {_e(_eur(euro))} di risparmio l'anno.</b></p>"
             "<p>Se TaxScan ti è stato utile, ci aiuti a migliorare con una recensione su Trustpilot: bastano 30 secondi.</p>"
             f"<p style='margin:20px 0'><a href='{_e(tp)}' style='background:#4355cc;color:#ffffff;text-decoration:none;"
             "padding:14px 24px;font-weight:700;display:inline-block'>Lascia una recensione</a></p>")
    try:
        auth.manda_email(email, f"Hai risparmiato {_eur(euro)}: ci dai un parere?",
                         P._cornice(email, "Grazie, ci dai un parere?", corpo, ("Torna a TaxScan", _link(c))))
        return True
    except Exception:
        db.annulla_promemoria(email, "az_trustpilot", c)
        raise


def _manda(email: str, c: str, chiave: str, oggetto: str, titolo: str, corpo: str, bottone: str) -> bool:
    """Una email, una volta sola per utente e chiave. False se disiscritto o gia' mandata."""
    import auth
    import promemoria as P
    if not email or db.email_disattivate(email) or not db.prenota_promemoria(email, chiave, c):
        return False
    try:
        auth.manda_email(email, oggetto, P._cornice(email, titolo, corpo, (bottone, _link(c))))
        try:
            db.registra_evento("prova_email", c, {"chiave": chiave})
        except Exception:
            pass
        return True
    except Exception:
        db.annulla_promemoria(email, chiave, c)
        raise


def _conferma(c: str, azione: str, euro: int) -> bool:
    email = email_di(c)
    if not email:
        return False
    tp = os.environ.get("TRUSTPILOT_URL", "").strip()
    t = {
        "fattura_caricata": ("Fattura ricevuta", "Abbiamo ricevuto la tua fattura",
                             "<p>Grazie, la fattura è arrivata. Il prossimo passo: dimmi cosa fai davvero per i clienti, "
                             "così calcolo quanto puoi risparmiare.</p>", "Continua"),
        "risparmio_calcolato": ("Analisi pronta: puoi risparmiare " + _eur(euro), f"Analisi pronta: {_eur(euro)} l'anno",
                                f"<p>Ho scomposto la tua attività e ho trovato un risparmio stimato di <b>{_e(_eur(euro))} l'anno</b> "
                                "tra imposta e contributi. Per ottenerlo ci sono poche azioni da fare: le trovi tutte in ordine.</p>"
                                "<p style='font-size:13px;color:#3d4a73'>È una stima, da verificare prima di agire.</p>",
                                "Vedi cosa fare"),
        "task_cod": ("Codice attività: fatto", "Hai fatto un passo per risparmiare",
                     f"<p>Hai segnato come fatta l'aggiunta del nuovo codice. Vale circa <b>{_e(_eur(euro))} l'anno</b>.</p>", "Vai avanti"),
        "task_contratto": ("Contratto: fatto", "Contratto sistemato",
                           f"<p>Il contratto ora separa le prestazioni. Vale circa <b>{_e(_eur(euro))} l'anno</b>.</p>", "Vai avanti"),
        "task_fatture": ("Fatture: fatto", "Fatture sistemate",
                         f"<p>Le prossime fatture avranno una riga per prestazione. Vale circa <b>{_e(_eur(euro))} l'anno</b>.</p>", "Vai avanti"),
        "contratto_firmato": ("Contratto firmato", "Contratto firmato",
                              "<p>Il contratto è firmato. Resta da inviarlo al cliente.</p>", "Invialo ora"),
        "contratto_inviato": ("Contratto inviato", "Contratto inviato",
                              "<p>Il contratto è stato inviato al cliente. Quando il cliente risponde, segna il task come chiuso.</p>", "Torna alla strategia"),
    }
    if azione == "beneficio_ottenuto":
        return False  # la recensione parte dal passaggio giornaliero, almeno un giorno dopo (vedi promemoria)
    if azione in ("fattura_caricata", "risparmio_calcolato"):
        return False  # l'utente e' nell'app in quel momento (e il risparmio ha gia' il suo report via email): niente email in piu'
    if azione not in t:
        return False
    o, ti, corpo, b = t[azione]
    return _manda(email, c, "az_" + azione, "TaxScan: " + o, ti, corpo, b)


def registra(c: str, azione: str, euro=0) -> dict:
    """Salva l'azione e manda la conferma, se c'e' l'email. Accetta solo azioni note e id esistenti."""
    c = (c or "").strip()
    if not _ID.match(c) or azione not in AZIONI:
        return {"ok": False}
    try:
        euro = max(0, min(int(float(euro or 0)), 1_000_000))
    except (TypeError, ValueError):
        euro = 0
    if db.carica_dashboard(c) is None:
        return {"ok": False}
    _tabelle()
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO prova_azioni (c, azione, euro) VALUES (%s, %s, %s) "
                        "ON CONFLICT (c, azione) DO UPDATE SET euro = EXCLUDED.euro", (c, azione, euro))
        conn.commit()
    inviata = False
    try:
        inviata = _conferma(c, azione, euro)
    except Exception as e:
        print(f"azioni: email non mandata ({azione}): {e}")
    return {"ok": True, "email": inviata}


def salva_email(c: str, email: str) -> dict:
    c = (c or "").strip()
    email = (email or "").strip().lower()
    if not _ID.match(c) or not _EMAIL.match(email):
        return {"ok": False, "errore": "Scrivi un'email valida."}
    if db.carica_dashboard(c) is None:
        return {"ok": False}
    _tabelle()
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO prova_email (c, email) VALUES (%s, %s) "
                        "ON CONFLICT (c) DO UPDATE SET email = EXCLUDED.email", (c, email))
        conn.commit()
    # benvenuto: una cosa vera sui suoi dati, non un elenco di funzioni (parte in un filo a parte)
    try:
        import email_ispira
        email_ispira.benvenuto(c, email)
    except Exception as e:
        print(f"azioni: benvenuto non mandato: {e}")
    return {"ok": True}


# ------------------------------------------------------------------ promemoria per le azioni non fatte

def promemoria(prova: bool = False, gia: set | None = None) -> dict:
    """Una email al giorno al massimo per utente. Si chiama da /cron/promemoria."""
    gia = gia if gia is not None else set()
    esito = {"mandati": 0, "previsti": [], "falliti": [], "email": set()}
    _tabelle()
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT c, email, extract(epoch FROM now() - creato) / 86400 FROM prova_email")
            utenti = cur.fetchall()
    for c, email, giorni in utenti:
        if email in gia:
            continue
        az = _azioni_di(c)
        scelta = None
        if "beneficio_ottenuto" in az and os.environ.get("TRUSTPILOT_URL") and _giorni(c, "beneficio_ottenuto") >= 1:
            if prova:
                esito["previsti"].append({"email": email, "tipo": "trustpilot", "chiave": c})
                esito["email"].add(email)
            else:
                try:
                    if _recensione(email, c, az.get("beneficio_ottenuto", 0)):
                        esito["mandati"] += 1
                        esito["email"].add(email)
                        continue
                except Exception as e:
                    esito["falliti"].append({"email": email, "errore": str(e)[:120]})
            if prova:
                continue
        # le scoperte: una al giorno nei primi tre giorni, poi al massimo una a settimana (al posto dei vecchi solleciti)
        try:
            import email_ispira
            if email_ispira.tocca(c, email, float(giorni or 0)):
                r = email_ispira.manda(c, email, prova)
                if r:
                    if prova:
                        esito["previsti"].append(r)
                    else:
                        esito["mandati"] += 1
                    esito["email"].add(email)
                    continue
        except Exception as e:
            esito["falliti"].append({"email": email, "errore": str(e)[:120]})
    return esito
