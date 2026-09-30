"""
TaxScan - avvisi su cambiamenti normativi rilevanti per il regime forfettario.

Flusso in due tempi, per sicurezza (mai mandare un'informazione sbagliata o fuorviante ai
clienti senza controllo):
1. controlla_fonti() gira periodicamente (chiamata da un cron esterno su /cron/controlla_avvisi)
   e mette in tabella avvisi_candidati le voci nuove delle fonti ufficiali che toccano parole
   chiave del forfettario. Nessuna email parte da qui.
2. Un umano (o Claude, aprendo il link e leggendo) rivede i candidati con avvisi_da_rivedere,
   scrive un titolo e un riassunto in linguaggio semplice, e solo con pubblica_avviso l'avviso
   viene mandato via email a tutti gli utenti iscritti.

Fonti: per ora solo la Gazzetta Ufficiale (Serie Generale), che ha un RSS pubblico e affidabile.
Agenzia delle Entrate e MEF bloccano le richieste automatiche (403) - da rivalutare più avanti,
magari con un servizio di terze parti o iscrivendosi alla loro mailing list con un indirizzo
dedicato.
"""

import os
import re
import xml.etree.ElementTree as ET

import requests

import auth
import db

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

FONTI = [
    ("Gazzetta Ufficiale - Serie Generale", "https://www.gazzettaufficiale.it/rss/SG"),
]

# Parole chiave usate per capire se una voce riguarda il regime forfettario. Il filtro è
# volutamente ampio (meglio un falso positivo scartato a mano che un cambiamento importante
# perso): un umano rivede comunque ogni candidato prima che parta qualunque email.
PAROLE_CHIAVE = [
    "forfettari", "forfetari", "regime dei minimi", "flat tax", "coefficiente di redditività",
    "coefficiente di redditivita", "partita iva", "partite iva", "regime agevolato",
    "nuove iniziative produttive", "gestione separata", "contributi inps artigiani",
    "contributi inps commercianti", "imposta sostitutiva", "soglia dei ricavi",
    "85.000 euro", "85000 euro", "100.000 euro", "100000 euro", "acconto imposte",
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TaxScanBot/1.0; +https://taxscan.ltd24.co.uk)"}


def _testo_contiene_parola_chiave(testo: str) -> bool:
    testo = (testo or "").lower()
    return any(p in testo for p in PAROLE_CHIAVE)


def _ammin_ok(admin_token: str) -> bool:
    return bool(ADMIN_TOKEN) and admin_token == ADMIN_TOKEN


def controlla_fonti() -> dict:
    """Legge le fonti configurate, e mette in tabella (avvisi_candidati) le voci nuove il cui
    titolo o testo tocca una parola chiave del forfettario. Non manda nessuna email: prepara
    solo la lista da rivedere. Pensata per essere chiamata da un cron esterno."""
    trovati_totali, nuovi_totali = 0, 0
    per_fonte = []
    for nome_fonte, url_feed in FONTI:
        try:
            risposta = requests.get(url_feed, headers=_HEADERS, timeout=20)
            risposta.raise_for_status()
            radice = ET.fromstring(risposta.content)
        except Exception as e:
            per_fonte.append({"fonte": nome_fonte, "errore": str(e)})
            continue
        voci_trovate, voci_nuove = 0, 0
        for item in radice.iter("item"):
            titolo = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pubblicato = (item.findtext("pubDate") or "").strip()
            if not titolo or not link:
                continue
            voci_trovate += 1
            rilevante = _testo_contiene_parola_chiave(titolo)
            if not rilevante:
                # il titolo da solo spesso non basta (es. "DECRETO-LEGGE 29 settembre 2026,
                # n.168" non dice nulla): proviamo a leggere il testo della pagina collegata.
                try:
                    pagina = requests.get(link, headers=_HEADERS, timeout=15)
                    rilevante = _testo_contiene_parola_chiave(pagina.text)
                except Exception:
                    rilevante = False
            if not rilevante:
                continue
            if db.salva_candidato(nome_fonte, titolo, link, pubblicato):
                voci_nuove += 1
        trovati_totali += voci_trovate
        nuovi_totali += voci_nuove
        per_fonte.append({"fonte": nome_fonte, "voci_esaminate": voci_trovate,
                          "candidati_nuovi": voci_nuove})
    return {"voci_esaminate_totale": trovati_totali, "candidati_nuovi_totale": nuovi_totali,
            "per_fonte": per_fonte}


def manda_avviso_a_tutti(id_candidato: int, titolo_utente: str, riassunto: str, url: str) -> dict:
    """Manda l'email a tutti gli utenti iscritti (chi ha una scheda salvata e non ha disattivato
    gli avvisi). Da chiamare solo dopo approva_candidato."""
    destinatari = db.utenti_iscritti_avvisi()
    mandate, fallite = 0, []
    html = (
        f"<p>{riassunto}</p>"
        f"<p><a href='{url}'>Leggi la fonte ufficiale</a></p>"
        f"<p style='color:#666;font-size:12px'>Ricevi questa email perché hai usato TaxScan. "
        f"Per non riceverne più, scrivilo nella tua prossima conversazione con TaxScan.</p>"
    )
    for email in destinatari:
        try:
            auth.manda_email(email, f"TaxScan: {titolo_utente}", html)
            db.registra_invio_avviso(id_candidato, email)
            mandate += 1
        except Exception as e:
            fallite.append({"email": email, "errore": str(e)})
    return {"mandate": mandate, "totale_destinatari": len(destinatari), "fallite": fallite}
