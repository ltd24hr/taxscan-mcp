"""
TaxScan - calendario delle scadenze in formato iCalendar (.ics).

Gli eventi restano in memoria sul server, dietro un id breve e casuale: il link
è corto (poche lettere), a prova di troncamento quando viene toccato o inoltrato
dal telefono. Non e' un database: se il server si riavvia (redeploy, riavvio per
inattivita'), i link generati prima smettono di funzionare e vanno rigenerati -
per l'uso previsto (aprirlo subito dopo averlo ricevuto) non e' un problema.
"""

import os
import secrets
import string
import time
from datetime import date, datetime, timezone

PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://taxscan-mcp.onrender.com").rstrip("/")

_ALFABETO = string.ascii_letters + string.digits
_STORE: dict[str, tuple[list, float]] = {}
_DURATA_SECONDI = 7 * 24 * 3600  # 7 giorni


def _pulisci_scaduti() -> None:
    scadenza = time.time() - _DURATA_SECONDI
    for k in [k for k, (_, t) in _STORE.items() if t < scadenza]:
        del _STORE[k]


def crea_id_breve(eventi: list) -> str:
    """Salva gli eventi in memoria e restituisce un id breve (8 caratteri) per il link."""
    _pulisci_scaduti()
    id_breve = "".join(secrets.choice(_ALFABETO) for _ in range(8))
    while id_breve in _STORE:
        id_breve = "".join(secrets.choice(_ALFABETO) for _ in range(8))
    _STORE[id_breve] = (eventi, time.time())
    return id_breve


def eventi_da_id(id_breve: str) -> list:
    if id_breve not in _STORE:
        raise KeyError("id non trovato o scaduto")
    eventi, _ = _STORE[id_breve]
    return eventi


# --------------------------------------------------------------------------- ics

def _esc(txt: str) -> str:
    return (str(txt).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """RFC 5545: righe max 75 byte, continuazione con spazio iniziale."""
    out, chunk = [], ""
    for ch in line:
        if len((chunk + ch).encode("utf-8")) > 74:
            out.append(chunk)
            chunk = " " + ch
        else:
            chunk += ch
    out.append(chunk)
    return "\r\n".join(out)


def genera_ics(eventi: list) -> str:
    """eventi: [{"data": "2026-11-30", "titolo": "...", "descrizione": "...", "allarmi_giorni": [30, 7, 1]}]"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    righe = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TaxScan//Scadenze forfettario//IT",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:TaxScan - scadenze"]
    for i, e in enumerate(eventi):
        d = date.fromisoformat(e["data"])
        giorno = d.strftime("%Y%m%d")
        uid = f"taxscan-{giorno}-{i}@taxscan"
        righe += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{giorno}",
                  f"SUMMARY:{_esc(e.get('titolo', 'Scadenza fiscale'))}"]
        if e.get("descrizione"):
            righe.append(f"DESCRIPTION:{_esc(e['descrizione'])}")
        righe.append("CATEGORIES:TaxScan")
        for g in e.get("allarmi_giorni", []):
            righe += ["BEGIN:VALARM", "ACTION:DISPLAY",
                      f"DESCRIPTION:{_esc(e.get('titolo', 'Scadenza'))} tra {g} giorni",
                      f"TRIGGER;VALUE=DURATION:-P{int(g)}D", "END:VALARM"]
        if e.get("allarme_stesso_giorno", True):
            righe += ["BEGIN:VALARM", "ACTION:DISPLAY",
                      f"DESCRIPTION:{_esc(e.get('titolo', 'Scadenza'))} - oggi",
                      "TRIGGER;VALUE=DURATION:PT9H", "END:VALARM"]  # ore 9 del giorno stesso
        righe.append("END:VEVENT")
    righe.append("END:VCALENDAR")
    return "\r\n".join(_fold(r) for r in righe) + "\r\n"


# --------------------------------------------------------------------------- costruzione dal piano

def eventi_dal_piano(piano: dict, includi_accantonamento: bool = True) -> list:
    """Trasforma l'output di piano_pagamenti in eventi di calendario."""
    eventi = []
    for s in piano.get("scadenze", []):
        importo = f"{s['importo']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        dettaglio = "\n".join(s.get("dettaglio", []))
        eventi.append({
            "data": s["data"],
            "titolo": f"Pagare {importo} € - {s['etichetta']}",
            "descrizione": (dettaglio + "\n\nPaga con F24 (home banking o Entratel).\n"
                            "Se cade di sabato o festivo slitta al primo giorno lavorativo.\n"
                            "Stima TaxScan: verifica gli importi definitivi con il tuo professionista."),
            "allarmi_giorni": [30, 7, 1],
        })
    if includi_accantonamento:
        for m in piano.get("piano_mensile", []):
            if not m.get("da_accantonare"):
                continue
            nome, anno = m["mese"].split()
            mese_n = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                      "settembre", "ottobre", "novembre", "dicembre"].index(nome) + 1
            quota = f"{m['da_accantonare']:,.0f}".replace(",", ".")
            data_ev = date(int(anno), mese_n, 1)
            if data_ev < date.today():
                data_ev = date.today()  # il mese in corso: promemoria da oggi, non nel passato
            eventi.append({
                "data": data_ev.isoformat(),
                "titolo": f"Metti da parte {quota} € per le tasse",
                "descrizione": (f"Accantonamento del mese secondo il piano TaxScan.\n"
                                f"Fondo previsto a fine mese: {m['fondo_a_fine_mese']:,.0f} €.".replace(",", ".")
                                + (f"\nIn uscita questo mese: {m['in_uscita']:,.0f} €".replace(",", ".") if m["in_uscita"] else "")),
                "allarmi_giorni": [],
            })
    eventi.sort(key=lambda e: e["data"])
    return eventi


def link_calendario(eventi: list) -> dict:
    id_breve = crea_id_breve(eventi)
    url = f"{PUBLIC_URL}/c/{id_breve}"
    return {
        "link_calendario": url,
        "eventi": len(eventi),
        "come_usarlo": {
            "iphone": "Tocca il link: Safari scarica il file. Apri il file scaricato (icona freccia in basso "
                      "a destra in Safari, o dall'app File) e scegli 'Aggiungi tutto' per aggiungere gli eventi.",
            "android": "Tocca il link: il file .ics si scarica e Google Calendar propone di importare gli eventi. "
                       "Se non succede, apri il file scaricato dalle notifiche.",
            "computer": "Apri il link e importa il file in Google Calendar (Impostazioni → Importa), "
                        "Outlook o Apple Calendario.",
        },
        "cosa_contiene": "Ogni scadenza con importo e codici tributo, con promemoria 30, 7 e 1 giorno prima e la "
                         "mattina stessa; più un promemoria il primo di ogni mese con la cifra da mettere da parte.",
        "nota": "Gli eventi sono fissi nel telefono: se i ricavi cambiano molto, rigenera il calendario e "
                "cancella i vecchi eventi TaxScan (sono nella categoria 'TaxScan').",
    }
