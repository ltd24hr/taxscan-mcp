"""
TaxScan - email all'utente: benvenuto e promemoria.

Obiettivo: l'utente si ricorda di TaxScan al momento giusto, senza essere sommerso.
  - benvenuto: subito dopo il primo salvataggio dell'email (cosa fa TaxScan, cosa riceverai)
  - scadenza: una scadenza fiscale e' vicina (7 giorni prima e 2 giorni prima)
  - sospeso: manca qualcosa (incassi non inseriti) o non aggiorni da tempo
  - mensile: riepilogo all'inizio di ogni mese

Regole per non dare fastidio: al massimo UNA email per utente per ogni passaggio del cron, mai due
email a meno di 4 giorni una dall'altra (tranne la scadenza a 2 giorni), ogni email ha il link per
disiscriversi con un clic, e ogni promemoria si manda una sola volta (tabella promemoria_inviati).
Non sono consigli fiscali: sono promemoria e riepiloghi delle stime della dashboard.
"""

import hashlib
import hmac
import html as _html
import os
from datetime import date

import auth
import dashboard
import scheda as S
import dati_fisco as D
import db

PUBLIC_URL = dashboard.PUBLIC_URL
_SEGRETO = (os.environ.get("ADMIN_TOKEN") or os.environ.get("RESEND_API_KEY") or "taxscan").encode()
DISTANZA_MINIMA_GIORNI = 4
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]


# ---------------------------------------------------------------- disiscrizione

def firma(email: str) -> str:
    return hmac.new(_SEGRETO, (email or "").strip().lower().encode(), hashlib.sha256).hexdigest()[:32]


def firma_valida(email: str, token: str) -> bool:
    return bool(email) and bool(token) and hmac.compare_digest(firma(email), token)


def _link_disiscrizione(email: str) -> str:
    from urllib.parse import quote
    return f"{PUBLIC_URL}/disiscriviti?e={quote(email)}&t={firma(email)}"


# ---------------------------------------------------------------- aspetto dell'email

def _e(x) -> str:
    return _html.escape(str(x if x is not None else ""))


def eur(n) -> str:
    try:
        t = f"{float(n):.0f}"
    except (TypeError, ValueError):
        return "–"
    neg = t.startswith("-")
    t = t.lstrip("-")
    gruppi = []
    while len(t) > 3:
        gruppi.insert(0, t[-3:])
        t = t[:-3]
    gruppi.insert(0, t)
    return ("-" if neg else "") + ".".join(gruppi) + " €"


def _data_it(iso: str) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{d.day} {MESI[d.month - 1]} {d.year}"
    except ValueError:
        return str(iso or "")


def _cornice(email: str, titolo: str, corpo: str, pulsante: tuple[str, str] | None = None) -> str:
    bottone = ""
    if pulsante:
        bottone = (f"<p style='margin:24px 0'><a href='{_e(pulsante[1])}' style='background:#4355cc;color:#fff;"
                   f"text-decoration:none;padding:13px 22px;border-radius:10px;font-weight:600;display:inline-block'>"
                   f"{_e(pulsante[0])}</a></p>")
    return (
        "<div style='background:#f3f6fa;padding:24px 12px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif'>"
        "<div style='max-width:560px;margin:0 auto;background:#fff;border-radius:14px;padding:28px 24px;color:#1b2430;"
        "line-height:1.55;font-size:16px'>"
        "<div style='font-size:20px;font-weight:700;color:#122452;margin-bottom:4px'>TaxScan</div>"
        f"<h1 style='font-size:21px;margin:12px 0 14px'>{_e(titolo)}</h1>"
        f"{corpo}{bottone}"
        "<p style='font-size:13px;color:#5b6675;border-top:1px solid #e3e8ef;padding-top:14px;margin-top:26px'>"
        "Le cifre sono stime a scopo informativo, non una consulenza: il commercialista controlla e firma. "
        f"Per un confronto con un professionista c'è la <a href='{_e(D.CONTATTI['consulenza_gratuita'])}' "
        "style='color:#122452'>consulenza gratuita</a>.</p>"
        "<p style='font-size:12px;color:#7a8594'>TaxScan è un servizio offerto da "
        f"<a href='{_e(D.CONTATTI['sito'])}' style='color:#7a8594'>LTD24</a>. "
        f"Non vuoi più ricevere queste email? <a href='{_e(_link_disiscrizione(email))}' "
        f"style='color:#7a8594'>Disiscriviti</a>. <a href='{_e(PUBLIC_URL)}/privacy' style='color:#7a8594'>Privacy</a>.</p>"
        "</div></div>"
    )


# ---------------------------------------------------------------- benvenuto

def manda_benvenuto(email: str, id_dashboard: str, nome: str = "") -> None:
    nome = S.pulisci_nome(nome)
    link = f"{PUBLIC_URL}/d/{id_dashboard}"
    corpo = (
        (f"<p>Ciao {_e(nome)},</p>" if nome else "") +
        "<p>Grazie per esserti iscritto. D'ora in poi hai un posto dove tenere sotto controllo la tua partita IVA "
        "forfettaria, senza dover capire tutto da solo.</p>"
        "<p><b>Cosa fa TaxScan per te</b></p>"
        "<ul style='padding-left:20px'>"
        "<li>Ti dice <b>quanto mettere da parte</b> da ogni fattura per imposte e contributi.</li>"
        "<li>Ti mostra le <b>prossime scadenze</b> e quanto pagare, e le puoi mettere nel calendario.</li>"
        "<li>Controlla la <b>soglia degli 85.000 €</b> e ti avvisa se ti stai avvicinando.</li>"
        "<li>Cerca <b>bandi e agevolazioni</b> per la tua zona e il tuo settore (da verificare sempre).</li>"
        "<li>Risponde alle tue domande con l'<b>assistente virtuale</b>, basato su intelligenza artificiale.</li>"
        "</ul>"
        "<p><b>Cosa riceverai da noi</b></p>"
        "<ul style='padding-left:20px'>"
        "<li>Un promemoria <b>prima di ogni scadenza</b>.</li>"
        "<li>Un riepilogo breve <b>all'inizio di ogni mese</b>.</li>"
        "<li>Un messaggio se manca qualcosa (per esempio gli incassi) o se cambia una regola importante.</li>"
        "</ul>"
        "<p>Poche email, solo quando servono. Puoi smettere di riceverle quando vuoi dal link in fondo.</p>"
        "<p><b>Per tornare</b> basta il pulsante qui sotto, oppure scrivi la tua email nella pagina "
        f"<a href='{_e(PUBLIC_URL)}/accedi' style='color:#122452'>Accedi</a> e ti mandiamo un codice.</p>"
        "<p>Più i tuoi numeri sono aggiornati, più le stime sono precise: ogni tanto aggiorna quanto hai incassato.</p>"
        "<p style='background:#e8ebfa;border-radius:10px;padding:12px 14px;font-size:15px'>TaxScan prepara e spiega; "
        "non sostituisce il commercialista, che controlla e firma. Se hai un dubbio importante, "
        f"<a href='{_e(D.CONTATTI['consulenza_gratuita'])}' style='color:#122452'>prenota una consulenza gratuita</a> "
        "con un professionista di LTD24.</p>"
    )
    auth.manda_email(email, (f"Benvenuto {nome} su TaxScan" if nome else "Benvenuto su TaxScan"), _cornice(
        email, (f"Benvenuto {nome} su TaxScan" if nome else "Benvenuto su TaxScan"), corpo, ("Apri la tua situazione", link)))


# ---------------------------------------------------------------- promemoria periodici

def _scadenza_prossima(dati: dict) -> dict | None:
    sc = dati.get("prossima_scadenza")
    return sc if sc and sc.get("giorni") is not None else None


def _scegli(email: str, scheda: dict, dati: dict, creato_il, aggiornato_il, oggi: date) -> dict | None:
    """Decide quale (al massimo uno) promemoria mandare a questo utente adesso."""
    link = f"{PUBLIC_URL}/d/"
    sc = _scadenza_prossima(dati)
    if sc and 0 <= sc["giorni"] <= 7:
        fascia = "2" if sc["giorni"] <= 2 else "7"
        chiave = f"{sc.get('data')}-{fascia}"
        if not db.promemoria_gia_inviato(email, "scadenza", chiave):
            quando = "oggi" if sc["giorni"] == 0 else ("domani" if sc["giorni"] == 1 else f"tra {sc['giorni']} giorni")
            importo = f" Importo stimato: <b>{eur(sc.get('importo'))}</b>." if sc.get("importo") else ""
            quota = str(dati.get("quota_per_fattura") or "").replace(".", ",")
            extra = (f"<p>Per non trovarti scoperto, metti da parte circa <b>{_e(quota)}</b> di ogni fattura che incassi.</p>"
                     if quota else "")
            corpo = (f"<p>La prossima scadenza è <b>{_e(sc.get('etichetta'))}</b>, {quando} "
                     f"({_e(_data_it(sc.get('data')))}).{importo}</p>{extra}"
                     "<p>Nella tua pagina trovi il dettaglio e il pulsante per metterla nel calendario. "
                     "Il pagamento lo prepara e lo controlla il tuo commercialista.</p>")
            return {"tipo": "scadenza", "chiave": chiave,
                    "oggetto": f"TaxScan: {sc.get('etichetta')} {quando}", "titolo": f"Scadenza {quando}",
                    "corpo": corpo, "pulsante": "Vedi i dettagli"}

    giorni_ultimo = db.giorni_dall_ultimo_promemoria(email)
    if giorni_ultimo is not None and giorni_ultimo < DISTANZA_MINIMA_GIORNI:
        return None

    # in sospeso: incassi di quest'anno mai inseriti (dopo una settimana) oppure numeri fermi da 45 giorni
    giorni_iscritto = (oggi - creato_il.date()).days if creato_il else 0
    fermo = (oggi - aggiornato_il.date()).days if aggiornato_il else 0
    mancano_incassi = scheda.get("ricavi_anno_corrente") in (None, "")
    if mancano_incassi and giorni_iscritto >= 7:
        chiave = f"incassi-{oggi.year}-{oggi.month}"
        if not db.promemoria_gia_inviato(email, "sospeso", chiave):
            corpo = ("<p>Per darti stime precise mi manca una cosa: <b>quanto hai incassato quest'anno</b>. "
                     "Ci vuole mezzo minuto: scrivi la cifra nella tua pagina e ricalcolo subito imposte, "
                     "contributi e quanto mettere da parte.</p>")
            return {"tipo": "sospeso", "chiave": chiave, "oggetto": "TaxScan: ti manca un dato per le stime",
                    "titolo": "Un dato e le stime sono complete", "corpo": corpo, "pulsante": "Inserisci gli incassi"}
    elif fermo >= 45:
        chiave = f"fermo-{oggi.year}-{oggi.month}"
        if not db.promemoria_gia_inviato(email, "sospeso", chiave):
            corpo = (f"<p>Sono passati {fermo} giorni dall'ultimo aggiornamento dei tuoi numeri. Se hai fatturato "
                     "di recente, aggiorna quanto hai incassato: le stime (e la distanza dalla soglia degli "
                     "85.000 €) si ricalcolano subito.</p>")
            return {"tipo": "sospeso", "chiave": chiave, "oggetto": "TaxScan: aggiorna i tuoi incassi",
                    "titolo": "Ti va di aggiornare i numeri?", "corpo": corpo, "pulsante": "Aggiorna i numeri"}

    # riepilogo mensile
    chiave = f"{oggi.year}-{oggi.month:02d}"
    if not db.promemoria_gia_inviato(email, "mensile", chiave):
        righe = []
        if sc:
            righe.append(f"<li>Prossima scadenza: <b>{_e(sc.get('etichetta'))}</b>, {_e(_data_it(sc.get('data')))}</li>")
        quota_txt = str(dati.get("quota_per_fattura") or "").replace(".", ",")
        if quota_txt:
            righe.append(f"<li>Da mettere da parte su ogni fattura: <b>{_e(quota_txt)}</b></li>")
        so = dati.get("soglia") or {}
        if so.get("ricavi") is not None and so.get("limite"):
            righe.append(f"<li>Incassato quest'anno: <b>{eur(so['ricavi'])}</b> su un limite di {eur(so['limite'])}</li>")
        if so.get("livello") not in (None, "OK") and so.get("messaggio"):
            righe.append(f"<li>Attenzione: {_e(so['messaggio'])}</li>")
        corpo = (f"<p>Ecco la tua situazione a inizio {MESI[oggi.month - 1]}.</p>"
                 f"<ul style='padding-left:20px'>{''.join(righe)}</ul>"
                 "<p>Se hai incassato qualcosa nel frattempo, aggiorna i numeri: ci vuole un minuto.</p>"
                 if righe else
                 f"<p>Inizia {MESI[oggi.month - 1]}: è un buon momento per dare un'occhiata alla tua situazione "
                 "e aggiornare gli incassi.</p>")
        return {"tipo": "mensile", "chiave": chiave,
                "oggetto": f"TaxScan: la tua situazione a {MESI[oggi.month - 1]}",
                "titolo": f"La tua situazione, {MESI[oggi.month - 1]}", "corpo": corpo, "pulsante": "Apri la dashboard"}
    return None


def esegui(prova: bool = False) -> dict:
    """Passaggio giornaliero: sceglie e manda i promemoria. Con prova=True non manda nulla e dice cosa farebbe."""
    oggi = date.today()
    esito = {"utenti": 0, "mandati": 0, "falliti": [], "previsti": []}
    for u in db.utenti_per_promemoria():
        esito["utenti"] += 1
        email = u["email"]
        try:
            dati = db.carica_dashboard(u["dashboard_id"]) or {}
            # si rifa' la dashboard cosi' i giorni alla scadenza sono di oggi, non di quando e' stata creata
            nuovi = (dashboard.costruisci(dict(u["scheda"] or {}), 0.0) if prova
                     else dashboard._ricostruisci(u["dashboard_id"], dati, dict(u["scheda"] or {})))
            if "errore" in nuovi:
                continue
            p = _scegli(email, u["scheda"] or {}, nuovi, u["creato_il"], u["aggiornato_il"], oggi)
            if not p:
                continue
            if prova:
                esito["previsti"].append({"email": email, "tipo": p["tipo"], "chiave": p["chiave"]})
                continue
            if not db.prenota_promemoria(email, p["tipo"], p["chiave"]):
                continue
            try:
                saluto = S.pulisci_nome((u["scheda"] or {}).get("nome"))
                if saluto:
                    p["corpo"] = f"<p>Ciao {_e(saluto)},</p>" + p["corpo"]
                auth.manda_email(email, p["oggetto"], _cornice(
                    email, p["titolo"], p["corpo"], (p["pulsante"], f"{PUBLIC_URL}/d/{u['dashboard_id']}")))
                esito["mandati"] += 1
                try:
                    db.registra_evento("promemoria_mandato", u["dashboard_id"], {"tipo": p["tipo"]})
                except Exception:
                    pass
            except Exception as e:
                db.annulla_promemoria(email, p["tipo"], p["chiave"])
                esito["falliti"].append({"email": email, "errore": str(e)[:120]})
        except Exception as e:
            esito["falliti"].append({"email": email, "errore": str(e)[:120]})
    return esito


# ---------------------------------------------------------------- pagina di disiscrizione

def pagina_disiscrizione(email: str, token: str, fatto: bool = False, riattivato: bool = False) -> str:
    if not firma_valida(email, token):
        corpo = "<p>Questo link non è valido. Scrivici a info@ltd24ore.com e ti togliamo noi.</p>"
    elif fatto:
        corpo = ("<p>Fatto: non riceverai più promemoria da TaxScan. Il tuo spazio resta disponibile quando "
                 "vuoi tornare.</p>"
                 f"<form method='post'><input type='hidden' name='e' value='{_e(email)}'>"
                 f"<input type='hidden' name='t' value='{_e(token)}'><input type='hidden' name='azione' value='riattiva'>"
                 "<button style='padding:12px 18px;border-radius:10px;border:1px solid #4355cc;background:#fff;"
                 "color:#122452;font-size:16px'>Ho cambiato idea, riattiva</button></form>")
    elif riattivato:
        corpo = "<p>Perfetto, i promemoria sono di nuovo attivi.</p>"
    else:
        corpo = (f"<p>Vuoi smettere di ricevere i promemoria TaxScan su <b>{_e(email)}</b>?</p>"
                 f"<form method='post'><input type='hidden' name='e' value='{_e(email)}'>"
                 f"<input type='hidden' name='t' value='{_e(token)}'><input type='hidden' name='azione' value='disattiva'>"
                 "<button style='padding:13px 20px;border-radius:10px;border:0;background:#4355cc;color:#fff;"
                 "font-size:16px;font-weight:600'>Sì, disiscrivimi</button></form>")
    return ("<!doctype html><html lang='it'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>Email TaxScan</title></head>"
            "<body style='margin:0;background:#f3f6fa;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;"
            "color:#1b2430'><div style='max-width:480px;margin:40px auto;background:#fff;border-radius:14px;"
            "padding:28px 24px;line-height:1.55'><div style='font-size:20px;font-weight:700;color:#122452'>TaxScan</div>"
            f"{corpo}</div></body></html>")
