"""TaxScan - pagamenti: chi ha attivato TaxScan (47 EUR per 12 mesi), l'email di acquisto dopo l'analisi e il report a chi paga.

Il percorso:
1. la persona fa l'Ottimizzazione fiscale e vede quanto puo' risparmiare (gratis);
2. chiede il report: se non ha ancora pagato, i dati del report si salvano e le arriva l'EMAIL DI ACQUISTO
   (il suo risparmio, l'offerta di lancio, la garanzia, il pulsante per la pagina pubblica /acquista);
3. paga (Stripe): il pagamento arriva al webhook, la situazione si segna come «attiva» e il report PDF parte via email;
4. da quel momento si aprono anche «Da fare» e «Bandi e agevolazioni».

Si attiva da solo quando su Render c'e' ACQUISTA_LINK (il link di pagamento): senza, tutto resta aperto come prima.
Su Render servono anche STRIPE_WEBHOOK_SECRET (la chiave «whsec_...» del webhook Stripe, evento checkout.session.completed).
Nel Payment Link di Stripe conviene impostare, dopo il pagamento, il ritorno a  https://taxscan.it/prova?pagato=1
Chi paga in altro modo (bonifico) si attiva a mano: /admin/pagato?chiave=...&email=...  (oppure &c=...).
"""
import datetime
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import urlencode

import db

PREZZO = 47
PREZZO_PIENO = 589
OFFERTA = "Offerta di lancio: 12 mesi a 47 € invece di 589 €"
GARANZIA = ("Garanzia soddisfatto o rimborsato: se non ottieni un risparmio fiscale almeno doppio rispetto al costo "
            "del software, ti rimborsiamo tutto e non paghi.")
_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,}$")


def attivo() -> bool:
    """Il pagamento e' attivo solo quando esiste il link di pagamento: prima, nessuna sezione si chiude."""
    return (os.environ.get("ACQUISTA_LINK") or "").strip().startswith("https://")


# ------------------------------------------------------------------ archivio (tabella prova_doc)

def _get(path: str):
    try:
        import prova
        prova._tabella()
        with db._connetti() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT dati FROM prova_doc WHERE path = %s", (path,))
                r = cur.fetchone()
        return r[0] if r else None
    except Exception as e:
        print(f"pagamenti: lettura {path} non riuscita: {e}")
        return None


def _set(path: str, dati: dict) -> None:
    import prova
    from psycopg2.extras import Json
    prova._tabella()
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO prova_doc (path, dati) VALUES (%s, %s) "
                        "ON CONFLICT (path) DO UPDATE SET dati = EXCLUDED.dati, aggiornato = now()", (path, Json(dati)))
        conn.commit()


def _email_di(c: str) -> str:
    try:
        import azioni
        return azioni.email_attiva(c) or ""
    except Exception:
        return ""


def _c_di_email(email: str) -> str:
    """La situazione di chi ha confermato questa email nell'app (o e' iscritto con quella email)."""
    email = (email or "").strip().lower()
    if not email:
        return ""
    try:
        with db._connetti() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT c FROM prova_email WHERE email = %s ORDER BY "
                            "coalesce((to_jsonb(prova_email)->>'verificata')::boolean, false) DESC, creato DESC LIMIT 1", (email,))
                r = cur.fetchone()
                if r:
                    return r[0]
        return db.dashboard_di_utente(email) or ""
    except Exception:
        return ""


def pagato(c: str) -> bool:
    if not c or not _ID.match(c):
        return False
    if _get("pagato/" + c):
        return True
    em = _email_di(c)
    return bool(em and _get("pagato_email/" + em))


def scadenza(c: str) -> str:
    d = _get("pagato/" + c) or (_get("pagato_email/" + _email_di(c)) if _email_di(c) else None) or {}
    return str(d.get("fino_al") or "")


def link_checkout(c: str = "", email: str = "", fonte: str = "app") -> str:
    import emailtpl
    q = {k: v for k, v in (("c", c), ("email", email), ("utm_source", fonte)) if v}
    return f"{emailtpl.PUBLIC_URL}/acquista" + ("?" + urlencode(q) if q else "")


def per_pagina(c: str) -> dict:
    """Per la pagina dell'app: se il pagamento e' attivo, se questa persona ha gia' pagato e dove si paga."""
    if not attivo():
        return {"on": False, "ok": True, "link": ""}
    ok = pagato(c)
    return {"on": True, "ok": ok, "link": "" if ok else link_checkout(c, _email_di(c), "app"), "fino": scadenza(c) if ok else ""}


# ------------------------------------------------------------------ il report: si salva, e parte a chi paga

def salva_dati_report(c: str, pulito: dict) -> None:
    if c and _ID.match(c):
        try:
            _set("report/" + c, {"dati": pulito, "salvato": datetime.datetime.now().isoformat(timespec="seconds")})
        except Exception as e:
            print(f"pagamenti: dati del report non salvati: {e}")


def _eur(x) -> str:
    return f"{int(round(float(x or 0))):,}".replace(",", ".") + " €"


def email_acquisto(c: str, email: str, pulito: dict) -> bool:
    """L'email dopo l'analisi: il suo risparmio, l'offerta di lancio, la garanzia e il pulsante per acquistare.
    Una al giorno al massimo per situazione (se l'analisi si ripete, non la tempestiamo)."""
    import requests
    import auth
    import emailtpl
    if not (auth.RESEND_API_KEY and email and _EMAIL.match(email)):
        return False
    ultimo = _get("email_acquisto/" + c) or {}
    ris = float(pulito.get("risparmio") or 0)
    if ultimo.get("t") and time.time() - float(ultimo["t"]) < 86400 and abs(float(ultimo.get("ris") or 0) - ris) < 1:
        return True
    nome = (str(pulito.get("nome") or "").split(" ")[0] or "").capitalize()
    lav = str(((pulito.get("principale") or {}).get("nome")) or "").strip().rstrip(".")
    lav = (lav[0].lower() + lav[1:]) if len(lav) > 1 and not lav[:2].isupper() else lav
    link = link_checkout(c, email, "email_acquisto")
    sit = pulito.get("situazione") or {}
    bottone = (f"<p style='margin:22px 0'><a href='{emailtpl._e(link)}' style='display:inline-block;background:#4355cc;color:#ffffff;"
               "text-decoration:none;font-weight:700;font-size:17px;padding:14px 24px;border-radius:12px'>Attiva TaxScan a 47 €</a></p>")
    corpo = (f"<p>Ciao{(' ' + emailtpl._e(nome)) if nome else ''},</p>"
             + (f"<p>ho finito l'analisi del tuo lavoro{(' di ' + emailtpl._e(lav)) if lav else ''}: con le fatture impostate come ti propongo "
                f"puoi pagare circa <b>{_eur(ris)} in meno l'anno</b>, cioè {_eur(ris / 12)} in più ogni mese nel tuo netto.</p>"
                if ris > 0 else
                f"<p>ho finito l'analisi del tuo lavoro{(' di ' + emailtpl._e(lav)) if lav else ''}. Con le prestazioni che fai oggi il risparmio è "
                "piccolo, ma ci sono altre cose che possiamo sistemare insieme: scadenze, acconti, contributi.</p>")
             + "<p>Attivando TaxScan ricevi <b>il report completo</b>, con il tuo nome e la tua situazione: cosa ho trovato, come rifare le "
               "fatture e il calcolo passo per passo. E si aprono <b>Da fare</b>, con i passi in ordine da seguire con me, e "
               "<b>Bandi e agevolazioni</b> per la tua attività.</p>"
             + "<p style='font-size:17px'><b>Offerta di lancio: 12 mesi a 47&nbsp;€</b> invece di <s style='color:#8a93ad'>589&nbsp;€</s></p>"
             + f"<p>{emailtpl._e(GARANZIA)}</p>"
             + bottone
             + (f"<p>{emailtpl._e(sit.get('prossima'))}</p>" if sit.get("prossima") else "")
             + "<p style='color:#5b6475;font-size:13px'>Le cifre sono stime fatte sui dati che mi hai dato, non una promessa di risultato. "
               "Se vuoi, un commercialista può verificarle con te.</p>")
    oggetto = ((f"{nome}, " if nome else "") + (f"hai {_eur(ris)} l'anno di risparmio da sbloccare" if ris > 0 else "la tua analisi TaxScan è pronta"))
    try:
        r = requests.post(auth.RESEND_URL, headers={"Authorization": f"Bearer {auth.RESEND_API_KEY}"}, timeout=20,
                          json={"from": auth.MITTENTE, "to": email, "subject": oggetto,
                                "html": emailtpl.cornice("La tua analisi è pronta", corpo)})
        r.raise_for_status()
        _set("email_acquisto/" + c, {"t": time.time(), "ris": ris, "email": email})
        db.registra_evento("email_acquisto", c, {"risparmio": int(ris)})
        return True
    except Exception as e:
        print(f"pagamenti: email di acquisto non inviata: {e}")
        return False


def consegna_report(c: str, email: str) -> bool:
    """Dopo il pagamento: il report PDF parte via email (se l'analisi c'e' gia'), altrimenti un benvenuto che dice cosa fare."""
    import prova
    import report_pdf
    import requests
    import auth
    import emailtpl
    salvato = (_get("report/" + c) or {}).get("dati") if c else None
    if salvato:
        try:
            pdf = report_pdf.genera_v2(salvato)
            ok = prova._manda_report(email, pdf, salvato.get("nome") or "", float(salvato.get("risparmio") or 0),
                                     (salvato.get("principale") or {}).get("nome") or "", salvato.get("situazione"), c)
            db.registra_evento("report_dopo_pagamento", c or email, {"inviato": ok})
            return ok
        except Exception as e:
            print(f"pagamenti: report dopo il pagamento non inviato: {e}")
    if not auth.RESEND_API_KEY:
        return False
    link = f"{emailtpl.PUBLIC_URL}/prova" + (f"?c={c}&vai=g" if c else "")
    try:
        requests.post(auth.RESEND_URL, headers={"Authorization": f"Bearer {auth.RESEND_API_KEY}"}, timeout=20,
                      json={"from": auth.MITTENTE, "to": email, "subject": "TaxScan è attivo: iniziamo",
                            "html": emailtpl.cornice("TaxScan è attivo", "<p>Ciao,</p><p>grazie: TaxScan è attivo per 12 mesi.</p>"
                                                     "<p>Il primo passo è l'<b>Ottimizzazione fiscale</b>: carica due o tre fatture e trovo dove "
                                                     "puoi pagare meno. Appena finisce, ti mando il report completo.</p>"
                                                     f"<p><a href='{emailtpl._e(link)}' style='color:#4355cc;font-weight:700'>Inizia l'Ottimizzazione fiscale</a></p>")}).raise_for_status()
        return True
    except Exception as e:
        print(f"pagamenti: benvenuto dopo il pagamento non inviato: {e}")
        return False


def segna_pagato(c: str = "", email: str = "", fonte: str = "", importo: float = PREZZO, rif: str = "") -> dict:
    """La persona ha pagato: 12 mesi da oggi. Si ricorda per la situazione e per l'email (cosi' vale su ogni dispositivo)."""
    email = (email or "").strip().lower()
    if email and not _EMAIL.match(email):
        email = ""
    c = c if (c and _ID.match(c)) else _c_di_email(email)
    if not c and not email:
        return {"ok": False, "errore": "Mi serve l'email o la situazione di chi ha pagato."}
    oggi = datetime.date.today()
    fino = oggi.replace(year=oggi.year + 1) if not (oggi.month == 2 and oggi.day == 29) else oggi.replace(year=oggi.year + 1, day=28)
    rec = {"dal": oggi.isoformat(), "fino_al": fino.isoformat(), "fonte": fonte, "importo": importo, "rif": rif[:80], "email": email, "c": c}
    if rif and _get("pagamento/" + rif):
        return {"ok": True, "gia": True, "c": c}
    if c:
        _set("pagato/" + c, rec)
    if email:
        _set("pagato_email/" + email, rec)
    if rif:
        _set("pagamento/" + rif, rec)
    try:
        db.registra_evento("pagato", c or email, {"fonte": fonte, "importo": importo})
    except Exception:
        pass
    dest = email or (_email_di(c) if c else "")
    inviato = consegna_report(c, dest) if dest else False
    return {"ok": True, "c": c, "email": dest, "report_inviato": inviato, "fino_al": fino.isoformat()}


# ------------------------------------------------------------------ Stripe

def _firma_ok(corpo: bytes, intestazione: str, segreto: str, tolleranza: int = 600) -> bool:
    try:
        parti = dict(p.split("=", 1) for p in intestazione.split(",") if "=" in p)
        t = int(parti.get("t", "0"))
        firme = [p.split("=", 1)[1] for p in intestazione.split(",") if p.startswith("v1=")]
        if not firme or abs(time.time() - t) > tolleranza:
            return False
        atteso = hmac.new(segreto.encode(), f"{t}.".encode() + corpo, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(atteso, f) for f in firme)
    except Exception:
        return False


def webhook_stripe(corpo: bytes, intestazione: str) -> tuple[int, dict]:
    segreto = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not segreto:
        return 503, {"ok": False, "errore": "webhook non configurato"}
    if not _firma_ok(corpo, intestazione or "", segreto):
        return 400, {"ok": False, "errore": "firma non valida"}
    ev = json.loads(corpo.decode("utf-8"))
    if ev.get("type") not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        return 200, {"ok": True, "ignorato": ev.get("type")}
    s = (ev.get("data") or {}).get("object") or {}
    if s.get("payment_status") not in ("paid", "no_payment_required"):
        return 200, {"ok": True, "in_attesa": True}
    email = ((s.get("customer_details") or {}).get("email") or s.get("customer_email") or "").strip().lower()
    esito = segna_pagato(str(s.get("client_reference_id") or ""), email, "stripe", (s.get("amount_total") or PREZZO * 100) / 100, str(s.get("id") or ""))
    return 200, esito


def registra(mcp) -> None:
    from starlette.responses import JSONResponse, HTMLResponse
    import asyncio

    @mcp.custom_route("/api/stripe/webhook", methods=["POST"])
    async def stripe_webhook(request):
        corpo = await request.body()
        try:
            stato, esito = await asyncio.to_thread(webhook_stripe, corpo, request.headers.get("stripe-signature", ""))
        except Exception as e:
            print(f"pagamenti: webhook stripe in errore: {e}")
            return JSONResponse({"ok": False}, status_code=500)
        return JSONResponse(esito, status_code=stato)

    @mcp.custom_route("/admin/pagato", methods=["GET"])
    async def admin_pagato(request):
        """Attivazione a mano (per esempio un bonifico): /admin/pagato?chiave=...&email=...  oppure &c=..."""
        import avvisi
        q = request.query_params
        if not avvisi._ammin_ok(q.get("chiave", "")):
            return HTMLResponse("<p>Chiave non valida.</p>", status_code=403)
        esito = await asyncio.to_thread(segna_pagato, q.get("c", ""), q.get("email", ""), "manuale", PREZZO, "")
        import html as _h
        return HTMLResponse("<!doctype html><meta charset=utf-8><body style='font:16px system-ui;padding:24px'>"
                            + ("<p>✓ Attivato fino al " + _h.escape(esito.get("fino_al", "")) + " per " + _h.escape(esito.get("email") or esito.get("c") or "")
                               + (". Report inviato." if esito.get("report_inviato") else ".") + "</p>" if esito.get("ok") else
                               "<p>Non attivato: " + _h.escape(esito.get("errore", "")) + "</p>"))
