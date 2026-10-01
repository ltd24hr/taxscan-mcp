"""
TaxScan - scheda del colloquio iniziale, lettura F24 e quadro generale.

Il server non ha memoria: la scheda vive nella conversazione. Claude la compila man mano
che l'utente risponde o allega documenti, la passa a `verifica_scheda` per sapere cosa manca,
e quando è completa a `genera_quadro`.

Principio del colloquio (dai feedback dei primi utenti, ottobre 2026): TaxScan deve FARE,
non chiedere. Gerarchia fissa per ogni dato:
  1. leggerlo da un documento (certificato di attribuzione P.IVA, dichiarazione, F24)
  2. dedurlo da quello che si sa già (dal codice ATECO: tipo di attività e gestione INPS;
     dall'anno di apertura: anni nel regime e aliquota) e farlo CONFERMARE, mai darlo per scontato
  3. chiederlo a scelta tra opzioni numerate (l'utente risponde "2")
  4. testo libero solo dove non c'è alternativa (un importo) o per "altro"

Percorso tipico con il certificato: 1 conferma + 3-4 scelte + 2 importi (0 con Fatture in Cloud).
Le risposte a scelta vengono tradotte qui nei campi "storici" (aliquota, req5_*, redditi_dipendente...)
così i calcoli del quadro e del piano pagamenti restano identici.

Gruppi: identita (documento o 2 dati) → conferma (deduzioni) → aliquota (1 scelta, solo se
aperta da meno di 5 anni) → previdenza (solo se serve) → situazioni (1 scelta multipla) →
numeri (Fatture in Cloud o 2 importi). L'email si chiede DOPO il quadro, non prima.
"""

from datetime import date

import dati_fisco as D
from calcoli import calcola_forfettario, coefficiente_da_ateco, monitora_soglia, prossime_scadenze

# --------------------------------------------------------------------------- opzioni

ETICHETTE_TIPO = {"professionista": "professionista", "artigiano": "artigiano",
                  "commerciante": "commerciante", "altro": "altro tipo di attività"}
ETICHETTE_GESTIONE = {"separata": "INPS gestione separata", "artigiani": "INPS artigiani",
                      "commercianti": "INPS commercianti", "cassa": "cassa professionale del tuo Ordine",
                      "non_so": "non so"}

OPZIONI_TIPO = [("professionista", "Professionista (lavoro intellettuale, con o senza Ordine)"),
                ("artigiano", "Artigiano (produco, riparo, installo, servizi alla persona)"),
                ("commerciante", "Commerciante (vendo prodotti, bar/ristorazione, agente)"),
                ("altro", "Altro")]
OPZIONI_GESTIONE = [("separata", "INPS gestione separata (freelance senza Ordine)"),
                    ("artigiani", "INPS artigiani"),
                    ("commercianti", "INPS commercianti"),
                    ("cassa", "Cassa professionale del mio Ordine (Inarcassa, Forense, ENPAM...)"),
                    ("non_so", "Non lo so")]

# Casse più comuni con l'aliquota del contributo soggettivo usata come STIMA quando l'utente non
# la conosce (va confermata: cambiano per età, anzianità e anno). Chiave: nome breve.
CASSE = {
    "Inarcassa": {"chi": "architetti e ingegneri", "aliquota": 0.145},
    "Cassa Forense": {"chi": "avvocati", "aliquota": 0.16},
    "ENPAM": {"chi": "medici e odontoiatri", "aliquota": 0.195},
    "ENPAP": {"chi": "psicologi", "aliquota": 0.10},
    "ENPAPI": {"chi": "infermieri", "aliquota": 0.16},
    "ENPAV": {"chi": "veterinari", "aliquota": 0.165},
    "Cassa Dottori Commercialisti": {"chi": "commercialisti", "aliquota": 0.15},
    "Cassa Ragionieri": {"chi": "ragionieri ed esperti contabili", "aliquota": 0.15},
    "ENPACL": {"chi": "consulenti del lavoro", "aliquota": 0.15},
    "EPPI": {"chi": "periti industriali", "aliquota": 0.18},
    "CIPAG": {"chi": "geometri", "aliquota": 0.18},
    "ENPAB": {"chi": "biologi", "aliquota": 0.15},
    "EPAP": {"chi": "agronomi, geologi, chimici, attuari", "aliquota": 0.10},
    "Cassa Notariato": {"chi": "notai", "aliquota": 0.0},
}

# Deduzione dal codice ATECO (prefisso più lungo vince): tipo di attività, gestione previdenziale,
# casse plausibili. Sono regole pratiche, non legge: per questo vengono sempre fatte confermare.
_DEDUZIONI_ATECO = [
    # (prefissi, tipo_attivita, gestione, casse_plausibili, descrizione breve)
    (["69.1"], "professionista", "cassa", ["Cassa Forense"], "attività legale"),
    (["69.2"], "professionista", "cassa", ["Cassa Dottori Commercialisti", "Cassa Ragionieri", "ENPACL"],
     "contabilità, consulenza fiscale o del lavoro"),
    (["71.1"], "professionista", "cassa", ["Inarcassa", "CIPAG", "EPPI"], "architettura e ingegneria"),
    (["75"], "professionista", "cassa", ["ENPAV"], "servizi veterinari"),
    (["86.1", "86.2"], "professionista", "cassa", ["ENPAM"], "attività medica o odontoiatrica"),
    (["86.9"], "professionista", "cassa", ["ENPAP", "ENPAPI", "ENPAM"], "altre attività sanitarie"),
    (["46.1"], "commerciante", "commercianti", [], "agente o rappresentante di commercio"),
    (["66.2"], "commerciante", "commercianti", [], "agente o broker assicurativo"),
    (["68.3"], "commerciante", "commercianti", [], "agenzia immobiliare"),
    (["45", "46", "47"], "commerciante", "commercianti", [], "commercio"),
    (["55", "56"], "commerciante", "commercianti", [], "alloggio, bar o ristorazione"),
    (["10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24",
      "25", "26", "27", "28", "29", "30", "31", "32", "33"], "artigiano", "artigiani", [],
     "produzione o lavorazione artigianale"),
    (["41", "42", "43"], "artigiano", "artigiani", [], "edilizia, impianti o finiture"),
    (["49", "50", "51", "52", "53"], "artigiano", "artigiani", [], "trasporto o logistica"),
    (["81"], "artigiano", "artigiani", [], "pulizie, giardinaggio o servizi agli edifici"),
    (["95"], "artigiano", "artigiani", [], "riparazioni"),
    (["96"], "artigiano", "artigiani", [], "servizi alla persona (parrucchiere, estetista, lavanderia...)"),
    (["58", "59", "60", "61", "62", "63"], "professionista", "separata", [], "informatica, editoria o media"),
    (["64", "65", "66"], "professionista", "separata", [], "consulenza finanziaria o assicurativa"),
    (["70", "72", "73", "74"], "professionista", "separata", [],
     "consulenza, marketing, design, fotografia, traduzioni o altra professione senza Ordine"),
    (["71.2"], "professionista", "separata", [], "collaudi e analisi tecniche"),
    (["85"], "professionista", "separata", [], "istruzione o formazione"),
    (["87", "88"], "professionista", "separata", [], "assistenza sociale"),
    (["90", "91", "92", "93"], "professionista", "separata", [], "arte, sport, intrattenimento o benessere"),
    (["77", "78", "79", "80", "82"], "altro", "non_so", [], "servizi alle imprese"),
]


def deduci_da_ateco(codice_ateco: str) -> dict:
    """Tipo di attività, gestione previdenziale e casse plausibili dedotti dal codice ATECO.
    sicura=False quando la regola è debole e conviene far scegliere invece di confermare."""
    codice = str(codice_ateco or "").strip()
    migliore, lunghezza = None, -1
    for prefissi, tipo, gestione, casse, descrizione in _DEDUZIONI_ATECO:
        for p in prefissi:
            if codice.startswith(p) and len(p) > lunghezza:
                migliore, lunghezza = (tipo, gestione, casse, descrizione), len(p)
    if not migliore:
        return {"tipo_attivita": "altro", "gestione_previdenziale": "non_so", "casse_plausibili": [],
                "descrizione": "attività", "sicura": False}
    tipo, gestione, casse, descrizione = migliore
    return {"tipo_attivita": tipo, "gestione_previdenziale": gestione, "casse_plausibili": casse,
            "descrizione": descrizione, "sicura": gestione != "non_so"}


# --------------------------------------------------------------------------- campi

GRUPPI = ["identita", "conferma", "aliquota", "previdenza", "situazioni", "numeri", "dopo_quadro"]

# "opzioni": lista di (valore, etichetta) - la domanda va mostrata con le opzioni numerate e
# l'utente risponde con un numero. "obbligatorio" può essere True/False o una condizione (vedi
# _obbligatorio). I campi del gruppo dopo_quadro non vengono mai richiesti da verifica_scheda:
# si chiedono una volta, dopo il quadro, se l'utente ha voglia.
CAMPI = [
    # --- identita: dal certificato di attribuzione, o due dati
    {"chiave": "data_apertura", "gruppo": "identita", "obbligatorio": True, "tipo": "data",
     "domanda": "In che anno hai aperto la partita IVA? (se hai il certificato di attribuzione, allegalo "
                "e leggo tutto io)",
     "dove_trovarlo": "Area riservata agenziaentrate.gov.it (SPID/CIE) → Richiesta certificati → "
                      "Certificato di attribuzione della partita IVA. Oppure chiedilo a chi ti segue."},
    {"chiave": "codice_ateco", "gruppo": "identita", "obbligatorio": True,
     "domanda": "Qual è il tuo codice ATECO? Se non lo sai, dimmi in due parole cosa fai e lo cerco io.",
     "dove_trovarlo": "Certificato di attribuzione P.IVA, voce 'codice attività'. Se hai più codici, "
                      "serve quello dell'attività con più ricavi."},
    {"chiave": "partita_iva", "gruppo": "identita", "obbligatorio": False},
    {"chiave": "codice_fiscale", "gruppo": "identita", "obbligatorio": False},
    {"chiave": "anno_ingresso_forfettario", "gruppo": "identita", "obbligatorio": False, "tipo": "anno"},
    {"chiave": "tipo_attivita", "gruppo": "identita", "obbligatorio": False, "valori": list(ETICHETTE_TIPO)},
    {"chiave": "gestione_previdenziale", "gruppo": "identita", "obbligatorio": False,
     "valori": list(ETICHETTE_GESTIONE)},

    # --- conferma delle deduzioni (una sola interazione)
    {"chiave": "conferma_deduzioni", "gruppo": "conferma", "obbligatorio": "se_dedotti", "tipo": "bool",
     "domanda": "(costruita da verifica_scheda: 'Ho capito così: ... Giusto?')",
     "opzioni": [("si", "Sì, è tutto giusto"), ("no", "No, correggo qualcosa")]},

    # --- aliquota: 1 scelta al posto di 4 domande, solo se aperta da meno di 5 anni
    {"chiave": "origine_attivita", "gruppo": "aliquota", "obbligatorio": "se_aliquota_ignota_e_meno_di_5_anni",
     "domanda": "Prima di aprire la partita IVA, questa attività:",
     "opzioni": [("mai_fatta", "Non l'avevo mai fatta"),
                 ("da_dipendente", "La facevo da dipendente, per lo stesso datore di lavoro o gli stessi clienti"),
                 ("altra_piva_o_simile", "La facevo già con un'altra partita IVA, o facevo qualcosa di molto "
                                         "simile, negli ultimi 3 anni"),
                 ("altro", "Altro / non saprei")],
     "dove_trovarlo": "Decide tra aliquota del 5% (nuove attività, primi 5 anni) e del 15%. Se hai "
                      "l'ultima dichiarazione, quadro LM rigo LM39, dimmi direttamente l'aliquota."},
    {"chiave": "aliquota", "gruppo": "aliquota", "obbligatorio": False, "valori": ["5", "15", "incerto"]},
    {"chiave": "req5_prima_attivita", "gruppo": "aliquota", "obbligatorio": False, "tipo": "bool"},
    {"chiave": "req5_no_attivita_simile_3_anni", "gruppo": "aliquota", "obbligatorio": False, "tipo": "bool"},
    {"chiave": "req5_non_prosecuzione_dipendente", "gruppo": "aliquota", "obbligatorio": False, "tipo": "bool"},

    # --- previdenza: solo le domande che servono davvero
    {"chiave": "nome_cassa", "gruppo": "previdenza", "obbligatorio": "se_cassa",
     "domanda": "Quale cassa?",
     "opzioni": "casse_plausibili"},
    {"chiave": "aliquota_cassa", "gruppo": "previdenza", "obbligatorio": False, "tipo": "numero"},
    {"chiave": "riduzione_35", "gruppo": "previdenza", "obbligatorio": "se_artigiani_commercianti",
     "domanda": "Hai chiesto all'INPS la riduzione del 35% dei contributi riservata ai forfettari?",
     "opzioni": [("si", "Sì"), ("no", "No"), ("non_so", "Non lo so")]},
    {"chiave": "altra_copertura_previdenziale", "gruppo": "previdenza", "obbligatorio": False, "tipo": "bool"},

    # --- situazioni particolari: 1 scelta multipla al posto di 5 domande
    {"chiave": "situazioni_particolari", "gruppo": "situazioni", "obbligatorio": True, "tipo": "lista",
     "domanda": "Qualcuna di queste ti riguarda? (puoi indicarne più d'una, es. '1 e 4')",
     "opzioni": [("dipendente_o_pensione", "Ho anche un lavoro dipendente o una pensione"),
                 ("societa", "Ho quote in una società di persone, in uno studio associato, o controllo una SRL"),
                 ("ex_datore", "Fatturo soprattutto a un mio ex datore di lavoro degli ultimi due anni"),
                 ("dipendenti_collaboratori", "Ho dipendenti o collaboratori che pago"),
                 ("nessuna", "Nessuna di queste")]},
    {"chiave": "redditi_dipendente_pensione", "gruppo": "situazioni", "obbligatorio": "se_dipendente", "tipo": "numero",
     "domanda": "Il reddito lordo da dipendente o pensione dell'anno scorso, più o meno, era:",
     "opzioni": [("sotto_30000", "Sotto 30.000 €"), ("tra_30000_e_35000", "Tra 30.000 e 35.000 €"),
                 ("sopra_35000", "Sopra 35.000 €"), ("non_so", "Non lo so")],
     "dove_trovarlo": "Certificazione Unica (CU), punto 1 o 2."},
    {"chiave": "rapporto_dipendente_cessato", "gruppo": "situazioni", "obbligatorio": "se_sopra_limite", "tipo": "bool",
     "domanda": "Quel rapporto di lavoro è finito?",
     "opzioni": [("si", "Sì, è cessato"), ("no", "No, continua")]},
    {"chiave": "partecipazioni_societarie", "gruppo": "situazioni", "obbligatorio": False, "tipo": "bool"},
    {"chiave": "prevalenza_ex_datore", "gruppo": "situazioni", "obbligatorio": False, "tipo": "bool"},
    {"chiave": "spese_personale", "gruppo": "situazioni", "obbligatorio": "se_dipendenti", "tipo": "numero",
     "domanda": "Quanto spendi all'anno, lordo, per dipendenti e collaboratori?",
     "opzioni": [("sotto_20000", "Meno di 20.000 €"), ("sopra_20000", "Più di 20.000 €")]},

    # --- numeri: Fatture in Cloud, oppure i due soli importi che restano da chiedere
    {"chiave": "usa_fatture_in_cloud", "gruppo": "numeri", "obbligatorio": "se_ricavi_mancanti",
     "domanda": "Per gli incassi: usi Fatture in Cloud? Se sì lo collego e leggo tutto io.",
     "opzioni": [("si", "Sì, collegalo"), ("no", "No, uso un altro programma o nessuno")]},
    {"chiave": "ricavi_anno_precedente", "gruppo": "numeri", "obbligatorio": "se_non_aperta_quest_anno", "tipo": "numero",
     "domanda": "Più o meno, quanto hai incassato in totale l'anno scorso?",
     "dove_trovarlo": "Somma delle fatture incassate (non emesse) nell'anno. Ultima dichiarazione: quadro LM, "
                      "rigo LM22 colonna 3."},
    {"chiave": "ricavi_anno_corrente", "gruppo": "numeri", "obbligatorio": True, "tipo": "numero",
     "domanda": "E quest'anno, da gennaio a oggi, più o meno quanto hai incassato?"},
    {"chiave": "contributi_versati_anno_precedente", "gruppo": "numeri", "obbligatorio": False, "tipo": "numero"},
    {"chiave": "f24_pagati", "gruppo": "numeri", "obbligatorio": False, "tipo": "lista"},

    # --- dopo il quadro, facoltativo, una volta sola
    {"chiave": "gestione_attuale", "gruppo": "dopo_quadro", "obbligatorio": False,
     "valori": ["consulente_vuole_smettere", "da_solo", "ex_commercialista_ora_solo", "consulente_soddisfatto"],
     "domanda": "Ultima cosa, se ti va: oggi chi gestisce la tua partita IVA?",
     "opzioni": [("consulente_vuole_smettere", "Ho un consulente ma vorrei farne a meno"),
                 ("da_solo", "La gestisco da solo"),
                 ("ex_commercialista_ora_solo", "Avevo un commercialista e ora sono da solo"),
                 ("consulente_soddisfatto", "Ho un consulente e voglio solo capirci di più")]},
    {"chiave": "motivo", "gruppo": "dopo_quadro", "obbligatorio": False},
    {"chiave": "programma_fatturazione", "gruppo": "dopo_quadro", "obbligatorio": False},
]

CAMPI_PER_CHIAVE = {c["chiave"]: c for c in CAMPI}

# --------------------------------------------------------------------------- codici tributo

CODICI_TRIBUTO = {
    "1790": ("imposta_sostitutiva", "acconto_1", "Imposta sostitutiva forfettario - 1° acconto"),
    "1791": ("imposta_sostitutiva", "acconto_2", "Imposta sostitutiva forfettario - 2° acconto o unica soluzione"),
    "1792": ("imposta_sostitutiva", "saldo", "Imposta sostitutiva forfettario - saldo"),
    "AF":   ("inps_artigiani", "fisso", "INPS artigiani - contributi fissi sul minimale"),
    "AP":   ("inps_artigiani", "eccedenza", "INPS artigiani - contributi sul reddito eccedente il minimale (saldo/acconti)"),
    "CF":   ("inps_commercianti", "fisso", "INPS commercianti - contributi fissi sul minimale"),
    "CP":   ("inps_commercianti", "eccedenza", "INPS commercianti - contributi sul reddito eccedente il minimale (saldo/acconti)"),
    "PXX":  ("inps_separata", "saldo", "INPS gestione separata - saldo"),
    "P10":  ("inps_separata", "acconto_1", "INPS gestione separata - 1° acconto"),
    "P11":  ("inps_separata", "acconto_2", "INPS gestione separata - 2° acconto"),
    "PXXR": ("inps_separata", "saldo", "INPS gestione separata - saldo (rateizzato)"),
    "P10R": ("inps_separata", "acconto_1", "INPS gestione separata - 1° acconto (rateizzato)"),
    "P11R": ("inps_separata", "acconto_2", "INPS gestione separata - 2° acconto (rateizzato)"),
    "DPPI": ("interessi", "rateazione_inps", "INPS gestione separata - interessi di rateazione"),
    "APR":  ("inps_artigiani", "eccedenza", "INPS artigiani - eccedenza (rateizzato)"),
    "CPR":  ("inps_commercianti", "eccedenza", "INPS commercianti - eccedenza (rateizzato)"),
    "API":  ("interessi", "rateazione_inps", "INPS artigiani - interessi di rateazione"),
    "CPI":  ("interessi", "rateazione_inps", "INPS commercianti - interessi di rateazione"),
    "1668": ("interessi", "rateazione", "Interessi per rateazione delle imposte"),
    "1944": ("interessi", "ravvedimento", "Interessi da ravvedimento"),
    "8944": ("sanzioni", "ravvedimento", "Sanzione da ravvedimento (imposte sui redditi)"),
    "1040": ("ritenuta", "altro", "Ritenute su redditi di lavoro autonomo (non tipico del forfettario)"),
    "6099": ("iva", "annuale", "IVA annuale - NON dovuta dai forfettari: da verificare"),
    "1013": ("imposta_sostitutiva", "acconto_regime_vantaggio", "Regime di vantaggio (minimi) - attenzione, regime diverso"),
}


# --------------------------------------------------------------------------- helpers

def _eur(v, dec=0):
    """1234.5 -> '1.234,50' (formato italiano)."""
    txt = f"{float(v or 0):,.{dec}f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) and "," in str(v) else float(v)
    except (TypeError, ValueError):
        return None


def _bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("si", "sì", "true", "1", "yes", "vero"):
        return True
    if s in ("no", "false", "0", "falso"):
        return False
    return None


def _anno(v):
    if v is None or v == "":
        return None
    s = str(v)
    for token in s.replace("/", "-").split("-"):
        if len(token) == 4 and token.isdigit():
            return int(token)
    return int(s) if s.isdigit() and len(s) == 4 else None


def _lista(v):
    """Accetta una lista, una stringa con virgole, o un singolo valore."""
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()]


_FASCE_REDDITO = {"sotto_30000": 25000.0, "tra_30000_e_35000": 32500.0, "sopra_35000": 40000.0}
_FASCE_PERSONALE = {"sotto_20000": 10000.0, "sopra_20000": 25000.0}


def _anni_nel_regime(s: dict, anno: int | None = None) -> int | None:
    anno = anno or date.today().year
    ingresso = s.get("anno_ingresso_forfettario")
    return (anno - ingresso) if ingresso else None


def _obbligatorio(campo, scheda):
    o = campo["obbligatorio"]
    if o is True or o is False:
        return o
    s = scheda
    if o == "se_dedotti":
        return bool(s.get("dedotti")) and s.get("conferma_deduzioni") is not True
    if o == "se_aliquota_ignota_e_meno_di_5_anni":
        anni = _anni_nel_regime(s)
        return s.get("aliquota") is None and anni is not None and anni < 5
    if o == "se_cassa":
        return s.get("gestione_previdenziale") == "cassa"
    if o == "se_artigiani_commercianti":
        return s.get("gestione_previdenziale") in ("artigiani", "commercianti")
    if o == "se_dipendente":
        return "dipendente_o_pensione" in (s.get("situazioni_particolari") or [])
    if o == "se_sopra_limite":
        return (s.get("redditi_dipendente_pensione") or 0) > D.LIMITE_REDDITI_DIPENDENTE
    if o == "se_dipendenti":
        return "dipendenti_collaboratori" in (s.get("situazioni_particolari") or [])
    if o == "se_ricavi_mancanti":
        return s.get("ricavi_anno_corrente") is None
    if o == "se_non_aperta_quest_anno":
        anni = _anni_nel_regime(s)
        return anni is None or anni > 0
    return False


def _normalizza(scheda: dict) -> dict:
    """Pulisce i tipi, deduce quello che si può dedurre e traduce le risposte a scelta nei campi
    storici usati dai calcoli. Idempotente: si può richiamare sulla scheda già normalizzata."""
    s = dict(scheda or {})
    for c in CAMPI:
        k, t = c["chiave"], c.get("tipo")
        if k not in s:
            continue
        if t == "bool":
            s[k] = _bool(s[k])
        elif t == "numero":
            v = s[k]
            if isinstance(v, str) and v in _FASCE_REDDITO and k == "redditi_dipendente_pensione":
                s[k] = _FASCE_REDDITO[v]
            elif isinstance(v, str) and v in _FASCE_PERSONALE and k == "spese_personale":
                s[k] = _FASCE_PERSONALE[v]
            elif isinstance(v, str) and v == "non_so":
                s[k] = None
                s[k + "_incerto"] = True
            else:
                s[k] = _num(v)
        elif t == "anno":
            s[k] = _anno(s[k])
        elif t == "lista" and k == "situazioni_particolari":
            s[k] = _lista(s[k])
        elif k == "aliquota" and s[k] is not None:
            s[k] = str(s[k]).replace("%", "").strip()

    # --- identita
    if s.get("codice_ateco"):
        s["codice_ateco"] = str(s["codice_ateco"]).strip()
    if not s.get("anno_ingresso_forfettario") and s.get("data_apertura"):
        s["anno_ingresso_forfettario"] = _anno(s["data_apertura"])

    # --- deduzioni da ATECO (solo per i campi che l'utente non ha dato)
    dedotti = list(s.get("dedotti") or [])
    if s.get("codice_ateco"):
        d = deduci_da_ateco(s["codice_ateco"])
        if not s.get("tipo_attivita"):
            s["tipo_attivita"] = d["tipo_attivita"]
            dedotti.append("tipo_attivita")
        if not s.get("gestione_previdenziale"):
            s["gestione_previdenziale"] = d["gestione_previdenziale"]
            dedotti.append("gestione_previdenziale")
        s["_descrizione_attivita"] = d["descrizione"]
        s["_casse_plausibili"] = d["casse_plausibili"]
    anni = _anni_nel_regime(s)
    if anni is not None and "anni_nel_regime" not in dedotti:
        dedotti.append("anni_nel_regime")
    s["dedotti"] = sorted(set(dedotti))

    # --- aliquota
    if s.get("aliquota") is None and anni is not None and anni >= 5:
        s["aliquota"] = "15"
    origine = s.get("origine_attivita")
    if origine and s.get("aliquota") is None:
        if origine == "mai_fatta":
            s.update(aliquota="5", req5_prima_attivita=True, req5_no_attivita_simile_3_anni=True,
                     req5_non_prosecuzione_dipendente=True)
        elif origine == "da_dipendente":
            s.update(aliquota="15", req5_prima_attivita=True, req5_no_attivita_simile_3_anni=True,
                     req5_non_prosecuzione_dipendente=False)
        elif origine == "altra_piva_o_simile":
            s.update(aliquota="15", req5_prima_attivita=False, req5_no_attivita_simile_3_anni=False,
                     req5_non_prosecuzione_dipendente=True)
        else:
            s["aliquota"] = "incerto"

    # --- previdenza
    if s.get("gestione_previdenziale") == "cassa" and s.get("nome_cassa") and not s.get("aliquota_cassa"):
        nome = str(s["nome_cassa"]).strip()
        for cassa, info in CASSE.items():
            if cassa.lower() in nome.lower() or nome.lower() in cassa.lower():
                s["aliquota_cassa"] = info["aliquota"]
                s["aliquota_cassa_stimata"] = True
                break
    if isinstance(s.get("riduzione_35"), str) or s.get("riduzione_35") is None and "riduzione_35" in scheda:
        v = str(scheda.get("riduzione_35") or "").strip().lower()
        if v == "non_so":
            s["riduzione_35"] = False
            s["riduzione_35_incerta"] = True
        else:
            s["riduzione_35"] = _bool(v)

    # --- situazioni particolari → campi storici
    sit = s.get("situazioni_particolari")
    if sit:
        if "nessuna" in sit:
            sit = ["nessuna"]
            s["situazioni_particolari"] = sit
        s["partecipazioni_societarie"] = "societa" in sit
        s["prevalenza_ex_datore"] = "ex_datore" in sit
        if "dipendente_o_pensione" not in sit:
            s["redditi_dipendente_pensione"] = 0.0
        if "dipendenti_collaboratori" not in sit:
            s["spese_personale"] = 0.0
    elif sit is None and any(k in s for k in ("partecipazioni_societarie", "prevalenza_ex_datore",
                                              "redditi_dipendente_pensione")):
        # scheda salvata con il vecchio colloquio: ricostruisco la risposta a scelta
        ricostruita = []
        if (s.get("redditi_dipendente_pensione") or 0) > 0:
            ricostruita.append("dipendente_o_pensione")
        if s.get("partecipazioni_societarie"):
            ricostruita.append("societa")
        if s.get("prevalenza_ex_datore"):
            ricostruita.append("ex_datore")
        if (s.get("spese_personale") or 0) > 0:
            ricostruita.append("dipendenti_collaboratori")
        s["situazioni_particolari"] = ricostruita or ["nessuna"]

    # --- numeri
    if anni == 0 and s.get("ricavi_anno_precedente") is None:
        s["ricavi_anno_precedente"] = 0.0
    if s.get("usa_fatture_in_cloud") is not None:
        s["usa_fatture_in_cloud"] = "si" if _bool(s["usa_fatture_in_cloud"]) or str(s["usa_fatture_in_cloud"]).lower() == "si" else "no"

    # vecchie schede: tipo e gestione dati dall'utente valgono come confermati
    if s.get("conferma_deduzioni") is None and "dedotti" not in (scheda or {}) and scheda.get("tipo_attivita") \
            and scheda.get("gestione_previdenziale"):
        s["conferma_deduzioni"] = True
    return s


def _opzioni_di(campo: dict, s: dict) -> list:
    """Le opzioni (valore, etichetta) da mostrare per questo campo, calcolate se dipendono dalla scheda."""
    opz = campo.get("opzioni")
    if opz == "casse_plausibili":
        plausibili = s.get("_casse_plausibili") or []
        altre = [c for c in CASSE if c not in plausibili]
        lista = [(c, f"{c} ({CASSE[c]['chi']})") for c in plausibili[:4]]
        lista += [(c, f"{c} ({CASSE[c]['chi']})") for c in altre[:3]]
        return lista + [("altro", "Un'altra cassa (dimmi quale)")]
    return list(opz or [])


def _testo_domanda(domanda: str, opzioni: list) -> str:
    if not opzioni:
        return domanda
    righe = [f"{i + 1}) {etichetta}" for i, (_, etichetta) in enumerate(opzioni)]
    return domanda + "\n" + "\n".join(righe)


def _domanda_conferma(s: dict) -> str:
    anno_ap = _anno(s.get("data_apertura"))
    anni = _anni_nel_regime(s)
    pezzi = [s.get("descrizione_attivita_certificato") or s.get("_descrizione_attivita") or "attività",
             f"codice ATECO {s['codice_ateco']}",
             ETICHETTE_TIPO.get(s.get("tipo_attivita"), s.get("tipo_attivita")),
             ETICHETTE_GESTIONE.get(s.get("gestione_previdenziale"), s.get("gestione_previdenziale"))]
    if anno_ap:
        pezzi.append(f"partita IVA aperta nel {anno_ap}")
    if anni is not None:
        pezzi.append("primo anno nel forfettario" if anni == 0
                     else ("nel forfettario da un anno" if anni == 1 else f"nel forfettario da {anni} anni"))
    return "Ho capito così: " + ", ".join(p for p in pezzi if p) + ". Giusto?"


# --------------------------------------------------------------------------- API

PRIMA_DOMANDA = {
    "domanda": "Come preferisci iniziare?",
    "opzioni": [("certificato", "Allego il certificato di attribuzione della partita IVA (faccio quasi tutto io)"),
                ("domande", "Non ce l'ho sotto mano: rispondo a un paio di domande"),
                ("riprendo", "Ho già usato TaxScan, voglio riprendere da dove ero")],
}


def avvia_colloquio() -> dict:
    """Istruzioni e scheda vuota per iniziare il colloquio."""
    return {
        "istruzioni_per_l_assistente": [
            "TaxScan deve FARE, non chiedere: prima legge dai documenti, poi deduce e fa confermare, poi "
            "chiede a scelta tra opzioni numerate; testo libero solo per gli importi o per 'altro'.",
            "Mostra la prima domanda con le sue 3 opzioni. 'certificato' → chiedi di allegarlo e leggi tu: "
            "data inizio attività, codice attività (ATECO), partita IVA, codice fiscale del titolare (nel "
            "certificato trasmesso da un intermediario ci sono due codici fiscali: quello del commercialista "
            "e quello del titolare, non confonderli). 'domande' → chiedi anno di apertura e codice ATECO; se "
            "l'utente non conosce il codice, fatti descrivere l'attività, proponi tu il codice ATECO più "
            "probabile e fallo confermare. 'riprendo' → chiedi l'email, fai il login (verifica_email + "
            "conferma_codice) e carica la scheda con carica_scheda_salvata.",
            "Dopo ogni risposta chiama verifica_scheda con TUTTA la scheda accumulata. Ti restituisce "
            "'testo_pronto': la prossima domanda già scritta con le opzioni numerate. Mostrala così com'è, "
            "una domanda alla volta. L'utente risponde con un numero (o con le parole): metti nella scheda "
            "il 'valore' dell'opzione scelta (non il numero, non l'etichetta). Per situazioni_particolari "
            "può sceglierne più d'una: metti la lista dei valori.",
            "Quando verifica_scheda restituisce 'proposta_deduzioni', è il passo di conferma: mostra il "
            "testo e le due opzioni. Se l'utente conferma, metti conferma_deduzioni=true. Se corregge, "
            "mostra 'opzioni_correzione' per il campo da cambiare, aggiorna tipo_attivita e/o "
            "gestione_previdenziale con il valore scelto e metti conferma_deduzioni=true.",
            "Se la risposta è 'altro' o non rientra nelle opzioni, fai UNA domanda aperta e breve, poi "
            "torna alle opzioni.",
            "Se l'utente allega un PDF (certificato, dichiarazione dei redditi, F24, estratto INPS), leggilo "
            "tu e riempi i campi: non chiedere mai un dato che è già nel documento. Dalla dichiarazione: "
            "ricavi (quadro LM rigo LM22 col. 3) e aliquota (LM39). Dagli F24: righe in f24_pagati.",
            "Per i ricavi: se usa_fatture_in_cloud='si', proponi il collegamento (collega_fatture_in_cloud, "
            "serve il login) e leggi i ricavi con importa_fatture_fic; altrimenti chiedi i due importi "
            "come 'più o meno', accettando cifre tonde.",
            "Non chiedere MAI l'email prima del quadro, a meno che l'utente scelga 'riprendo' o voglia "
            "collegare Fatture in Cloud. L'email si chiede dopo genera_quadro, con un motivo: 'vuoi che "
            "ricordi tutto per la prossima volta e ti avvisi delle scadenze?'.",
            "Quando verifica_scheda dice completa=true, chiama genera_quadro e spiega il risultato in modo "
            "discorsivo: prima la situazione maturata fino a oggi, poi cosa succede alle prossime "
            "scadenze, poi le cose da fare. Mostra sempre il disclaimer. Poi, una volta sola e solo se "
            "l'utente ha voglia, la domanda facoltativa 'gestione_attuale' (ci serve per capire chi usa "
            "TaxScan).",
            "Non dare mai l'impressione di sostituire il professionista: TaxScan prepara e spiega, il "
            "professionista controlla e firma.",
        ],
        "gruppi": GRUPPI,
        "scheda_vuota": {c["chiave"]: None for c in CAMPI if not c["chiave"].startswith("_")},
        "prima_domanda": PRIMA_DOMANDA["domanda"],
        "opzioni_prima_domanda": [{"numero": i + 1, "valore": v, "etichetta": e}
                                  for i, (v, e) in enumerate(PRIMA_DOMANDA["opzioni"])],
        "testo_pronto": _testo_domanda(PRIMA_DOMANDA["domanda"], PRIMA_DOMANDA["opzioni"]),
    }


def verifica_scheda(scheda: dict) -> dict:
    """Normalizza la scheda, deduce il deducibile, elenca i campi mancanti e prepara la prossima
    domanda già scritta con le opzioni numerate."""
    s = _normalizza(scheda)
    mancanti, avvisi = [], []
    for c in CAMPI:
        if c["gruppo"] == "dopo_quadro" or not _obbligatorio(c, s):
            continue
        v = s.get(c["chiave"])
        if v is None or v == "" or v == []:
            mancanti.append(c)
        elif c.get("valori") and str(v) not in c["valori"]:
            avvisi.append(f"Valore non riconosciuto per {c['chiave']}: '{v}'. Ammessi: {', '.join(c['valori'])}.")

    if s.get("codice_ateco"):
        info = coefficiente_da_ateco(s["codice_ateco"])
        if "errore" in info:
            avvisi.append("Codice ATECO non valido: " + info["errore"])
        elif info.get("attenzione"):
            avvisi.append(info["attenzione"])
    if s.get("aliquota_cassa_stimata"):
        avvisi.append(f"Aliquota della cassa stimata al {s['aliquota_cassa'] * 100:.1f}%: i contributi sono "
                      "indicativi, l'aliquota vera dipende da età e anzianità di iscrizione.")
    if s.get("redditi_dipendente_pensione_incerto"):
        avvisi.append("L'utente non sa il reddito da dipendente/pensione: il limite dei 35.000 € va verificato "
                      "sulla Certificazione Unica.")
    if s.get("aliquota") == "incerto":
        avvisi.append("Aliquota non determinabile dalla risposta: nel quadro verrà stimata e segnalata come da "
                      "verificare con un professionista.")

    prossimo = mancanti[0] if mancanti else None
    esito = {
        "scheda_normalizzata": {k: v for k, v in s.items() if not k.startswith("_")},
        "completa": not mancanti,
        "campi_mancanti": [{"campo": c["chiave"], "gruppo": c["gruppo"]} for c in mancanti],
        "prossima_domanda": None, "opzioni": [], "testo_pronto": None, "campo_prossimo": None,
        "dove_trovarlo": None, "avvisi": avvisi,
        "gruppo_corrente": prossimo["gruppo"] if prossimo else "completo",
    }
    if not prossimo:
        return esito

    esito["campo_prossimo"] = prossimo["chiave"]
    esito["dove_trovarlo"] = prossimo.get("dove_trovarlo")
    if prossimo["chiave"] == "conferma_deduzioni":
        domanda = _domanda_conferma(s)
        opzioni = _opzioni_di(prossimo, s)
        if s.get("gestione_previdenziale") == "non_so":
            # deduzione debole: meglio far scegliere subito la gestione che chiedere una conferma
            domanda = (f"Codice ATECO {s['codice_ateco']}: non riesco a dedurre con sicurezza la tua gestione "
                       "previdenziale. A quale sei iscritto?")
            opzioni = OPZIONI_GESTIONE
            esito["campo_prossimo"] = "gestione_previdenziale"
            esito["nota"] = ("Metti il valore scelto in gestione_previdenziale e conferma_deduzioni=true; se "
                             "sceglie 'non_so', lascia non_so: il quadro stimerà come gestione separata e lo "
                             "segnalerà.")
        esito["proposta_deduzioni"] = {
            "descrizione_attivita": s.get("descrizione_attivita_certificato") or s.get("_descrizione_attivita"),
            "codice_ateco": s.get("codice_ateco"),
            "tipo_attivita": s.get("tipo_attivita"),
            "tipo_attivita_etichetta": ETICHETTE_TIPO.get(s.get("tipo_attivita"), s.get("tipo_attivita")),
            "gestione_previdenziale": s.get("gestione_previdenziale"),
            "gestione_previdenziale_etichetta": ETICHETTE_GESTIONE.get(s.get("gestione_previdenziale"),
                                                                       s.get("gestione_previdenziale")),
            "anno_apertura": _anno(s.get("data_apertura")),
            "anno_ingresso_forfettario": s.get("anno_ingresso_forfettario"),
            "anni_nel_regime": _anni_nel_regime(s),
        }
        esito["opzioni_correzione"] = {
            "tipo_attivita": [{"numero": i + 1, "valore": v, "etichetta": e} for i, (v, e) in enumerate(OPZIONI_TIPO)],
            "gestione_previdenziale": [{"numero": i + 1, "valore": v, "etichetta": e}
                                       for i, (v, e) in enumerate(OPZIONI_GESTIONE)],
        }
    else:
        domanda = prossimo["domanda"]
        opzioni = _opzioni_di(prossimo, s)
    esito["prossima_domanda"] = domanda
    esito["opzioni"] = [{"numero": i + 1, "valore": v, "etichetta": e} for i, (v, e) in enumerate(opzioni)]
    esito["testo_pronto"] = _testo_domanda(domanda, opzioni)
    return esito


_ALIAS_F24 = {
    "codice_tributo": ["codice_tributo", "codice", "tributo", "cod_tributo", "causale", "causale_contributo", "codice_causale", "code"],
    "anno_riferimento": ["anno_riferimento", "anno", "periodo_riferimento", "periodo", "anno_di_riferimento", "year"],
    "importo": ["importo", "importo_debito", "importo_a_debito", "importi_a_debito", "debito", "amount", "importo_versato"],
    "rateazione": ["rateazione", "rata", "rateazione_regione", "rate"],
    "data_versamento": ["data_versamento", "data", "data_pagamento", "eseguito_il", "date"],
}


def _normalizza_riga_f24(r: dict) -> dict:
    """Accetta le chiavi con cui Claude potrebbe passare una riga F24 e le riporta a quelle standard."""
    if not isinstance(r, dict):
        return {}
    low = {str(k).strip().lower().replace(" ", "_"): v for k, v in r.items()}
    out = {}
    for std, alias in _ALIAS_F24.items():
        for a in alias:
            if a in low and low[a] not in (None, ""):
                out[std] = low[a]
                break
    return out


def interpreta_f24(righe: list, data_versamento: str = "") -> dict:
    """Classifica le righe di uno o più F24 dai codici tributo.

    righe: [{"codice_tributo": "1792", "anno_riferimento": 2025, "importo": 1234.56, "rateazione": "0101", "data_versamento": "2026-06-30"}]
    """
    esito, totale, sconosciuti = [], 0.0, []
    for r in righe or []:
        r = _normalizza_riga_f24(r)
        codice = str(r.get("codice_tributo", "")).strip().upper()
        importo = _num(r.get("importo")) or 0.0
        anno = _anno(r.get("anno_riferimento"))
        data = r.get("data_versamento") or data_versamento or None
        info = CODICI_TRIBUTO.get(codice)
        if not info:
            sconosciuti.append(codice)
            esito.append({"codice_tributo": codice, "importo": importo, "anno_riferimento": anno,
                          "data_versamento": data, "categoria": "sconosciuto", "natura": "sconosciuto",
                          "descrizione": "Codice non riconosciuto: chiedi all'utente o verifica sul sito AdE."})
            continue
        categoria, natura, descr = info
        voce = {"codice_tributo": codice, "importo": importo, "anno_riferimento": anno,
                "data_versamento": data, "categoria": categoria, "natura": natura, "descrizione": descr}
        if codice == "6099":
            voce["allarme"] = "Un forfettario non versa IVA annuale: se questo F24 è tuo, qualcosa non torna."
        if codice == "1013":
            voce["allarme"] = "Codice del vecchio regime dei minimi, non del forfettario: verificare il regime applicato."
        if r.get("rateazione"):
            voce["rateazione"] = str(r["rateazione"])
        totale += importo
        esito.append(voce)

    rateizzati = [v for v in esito if v.get("rateazione") and v["rateazione"] not in ("0101", "0100", "0000", "")]
    ha_interessi = any(v["codice_tributo"] == "1668" for v in esito)
    ha_interessi_inps = any(v["natura"] == "rateazione_inps" for v in esito)
    inps_rateizzati = [v for v in rateizzati if v["categoria"].startswith("inps")]
    per_categoria = {}
    for v in esito:
        per_categoria[v["categoria"]] = round(per_categoria.get(v["categoria"], 0.0) + v["importo"], 2)

    spiegazione = []
    for v in esito:
        if v["categoria"] == "imposta_sostitutiva" and v["anno_riferimento"]:
            if v["natura"] == "saldo":
                spiegazione.append(f"{_eur(v['importo'], 2)} € di saldo dell'imposta sostitutiva per l'anno {v['anno_riferimento']}.")
            elif v["natura"].startswith("acconto"):
                n = "primo" if v["natura"] == "acconto_1" else "secondo"
                spiegazione.append(f"{_eur(v['importo'], 2)} € di {n} acconto dell'imposta sostitutiva per l'anno {v['anno_riferimento']}.")
        elif v["categoria"].startswith("inps"):
            spiegazione.append(f"{_eur(v['importo'], 2)} € di contributi INPS ({v['descrizione'].split(' - ')[1]}), anno {v['anno_riferimento'] or 'n/d'}.")
        elif v["categoria"] in ("sanzioni", "interessi"):
            spiegazione.append(f"{_eur(v['importo'], 2)} € di {v['categoria']} ({v['natura']}): segnale di un pagamento tardivo o rateizzato.")

    imposte_rateizzate = [v for v in rateizzati if v["categoria"] == "imposta_sostitutiva"]
    if imposte_rateizzate and not ha_interessi:
        spiegazione.append("L'imposta sostitutiva risulta rateizzata ma non vedo il codice 1668 degli interessi di rateazione: "
                           "se mancano davvero, va sistemato con un piccolo ravvedimento.")
    if inps_rateizzati and not ha_interessi_inps:
        spiegazione.append("I contributi INPS risultano rateizzati ma non vedo la causale degli interessi (DPPI per la gestione "
                           "separata, API/CPI per artigiani e commercianti): da verificare.")
    return {"righe": esito, "totale_versato": round(totale, 2), "per_categoria": per_categoria,
            "codici_sconosciuti": sconosciuti, "rateizzato": bool(rateizzati), "spiegazione": spiegazione}


# --------------------------------------------------------------------------- quadro

def _acconti_imposta(imposta_anno_precedente: float) -> dict:
    """Acconto imposta sostitutiva forfettari: 100% dell'imposta dell'anno prima, in due rate UGUALI (50/50,
    art. 58 DL 124/2019, come per i soggetti ISA). Niente acconto sotto 51,65 €; unica rata a novembre sotto 257,52 €."""
    if imposta_anno_precedente <= 51.65:
        return {"dovuto": 0.0, "rate": [], "regola": "Imposta dell'anno precedente fino a 51,65 €: nessun acconto dovuto."}
    if imposta_anno_precedente <= 257.52:
        return {"dovuto": round(imposta_anno_precedente, 2),
                "rate": [{"scadenza": "30 novembre", "importo": round(imposta_anno_precedente, 2)}],
                "regola": "Imposta dell'anno precedente fino a 257,52 €: acconto in unica soluzione entro il 30 novembre."}
    meta = round(imposta_anno_precedente / 2, 2)
    return {"dovuto": round(imposta_anno_precedente, 2),
            "rate": [{"scadenza": "30 giugno", "importo": meta}, {"scadenza": "30 novembre", "importo": meta}],
            "regola": "Acconto pari al 100% dell'imposta dell'anno precedente, in due rate uguali: 50% entro il 30 giugno "
                      "e 50% entro il 30 novembre (per i forfettari vale il riparto 50/50, non 40/60)."}


def _acconti_inps_separata(contributi_anno_precedente: float) -> dict:
    """Acconti gestione separata: 80% dei contributi dell'anno prima, due rate uguali a giugno e novembre."""
    dovuto = round(contributi_anno_precedente * 0.80, 2)
    if dovuto <= 0:
        return {"dovuto": 0.0, "rate": [], "regola": "Nessun acconto INPS: nessun contributo dovuto per l'anno precedente."}
    meta = round(dovuto / 2, 2)
    return {"dovuto": dovuto,
            "rate": [{"scadenza": "30 giugno", "importo": meta}, {"scadenza": "30 novembre", "importo": meta}],
            "regola": "Acconto contributi gestione separata pari all'80% dei contributi dell'anno precedente, in due rate uguali."}


def _calcolo(s: dict, ricavi: float, contributi_versati: float | None = None) -> dict:
    gestione = s.get("gestione_previdenziale") or "separata"
    if gestione == "non_so":
        gestione = "separata"
    aliquota_5 = str(s.get("aliquota")) == "5"
    return calcola_forfettario(
        ricavi_incassati=ricavi, codice_ateco=s.get("codice_ateco", ""), gestione=gestione,
        nuova_attivita=aliquota_5, riduzione_35=bool(s.get("riduzione_35")),
        altra_copertura_previdenziale=bool(s.get("altra_copertura_previdenziale")),
        aliquota_cassa=float(s.get("aliquota_cassa") or 0.0),
        contributi_versati_nell_anno=contributi_versati)


def genera_quadro(scheda: dict, oggi: str = "") -> dict:
    """Il quadro generale: situazione maturata, spiegazione dei pagamenti, avvisi, prossimi passi."""
    v = verifica_scheda(scheda)
    s = _normalizza(scheda)
    if not v["completa"]:
        return {"errore": "Scheda incompleta: chiama prima verifica_scheda e completa i campi mancanti.",
                "campi_mancanti": [m["campo"] for m in v["campi_mancanti"]]}

    data_oggi = date.fromisoformat(oggi) if oggi else date.today()
    anno = data_oggi.year
    anno_ingresso = s.get("anno_ingresso_forfettario") or anno
    anni_nel_regime = anno - anno_ingresso
    if s.get("aliquota") is None:
        s["aliquota"] = "incerto"
    primo_anno = anni_nel_regime == 0
    secondo_anno = anni_nel_regime == 1

    avvisi = []

    # --- aliquota e requisiti del 5%
    req = [s.get("req5_prima_attivita"), s.get("req5_no_attivita_simile_3_anni"), s.get("req5_non_prosecuzione_dipendente")]
    requisiti_ok = all(r is True for r in req)
    if s.get("aliquota") == "incerto":
        probabile = "5" if (anni_nel_regime < 5 and requisiti_ok) else "15"
        s["aliquota"] = probabile
        avvisi.append({"livello": "informativo", "titolo": f"Aliquota probabile: {probabile}%",
                       "testo": f"Sei nel forfettario da {anni_nel_regime} anni e "
                                + ("rispetti" if requisiti_ok else "non rispetti")
                                + " i requisiti del 5%. Confermalo sull'ultima dichiarazione (quadro LM) o con chi ti segue."})
    elif s.get("aliquota") == "5":
        problemi = []
        if req[0] is False: problemi.append("non è la prima volta che eserciti questa attività")
        if req[1] is False: problemi.append("hai svolto un'attività simile nei tre anni precedenti")
        if req[2] is False: problemi.append("l'attività prosegue un precedente lavoro da dipendente")
        if problemi:
            avvisi.append({"livello": "attenzione", "titolo": "Il 5% potrebbe non spettarti",
                           "testo": "Hai indicato che " + "; ".join(problemi) + ". È l'errore più comune tra i forfettari, "
                                    "spesso scoperto tardi con ricalcolo e sanzioni. Fallo verificare da un professionista."})
        if anni_nel_regime >= 5:
            avvisi.append({"livello": "attenzione", "titolo": "Il periodo del 5% è finito",
                           "testo": f"Il 5% vale per i primi cinque anni: dal {anno_ingresso + 5} si applica il 15%. "
                                    "Verifica che l'aliquota usata quest'anno sia quella giusta."})

    # --- cause ostative e limiti
    rdp = s.get("redditi_dipendente_pensione") or 0
    if rdp > D.LIMITE_REDDITI_DIPENDENTE and not s.get("rapporto_dipendente_cessato"):
        avvisi.append({"livello": "importante", "titolo": "Redditi da dipendente o pensione oltre il limite",
                       "testo": f"Hai indicato circa {_eur(rdp)} € di redditi da lavoro dipendente o pensione: il limite per "
                                f"restare nel forfettario è {_eur(D.LIMITE_REDDITI_DIPENDENTE)} € (dal 2027 torna a 30.000). "
                                "Il limite non si applica se il rapporto è cessato. Da verificare subito con un professionista."})
    if s.get("partecipazioni_societarie"):
        avvisi.append({"livello": "importante", "titolo": "Possibile causa ostativa: partecipazioni",
                       "testo": "Quote in società di persone, associazioni professionali o controllo di SRL con attività "
                                "riconducibile alla tua sono incompatibili con il forfettario. Serve una verifica professionale."})
    if s.get("prevalenza_ex_datore"):
        avvisi.append({"livello": "importante", "titolo": "Possibile causa ostativa: ex datore di lavoro",
                       "testo": "Fatturare in prevalenza a un ex datore di lavoro degli ultimi due anni esclude dal regime. "
                                "Da verificare subito."})
    if (s.get("spese_personale") or 0) > D.LIMITE_SPESE_PERSONALE:
        avvisi.append({"livello": "importante", "titolo": "Spese per personale oltre 20.000 €",
                       "testo": "Superato il limite di spesa per dipendenti e collaboratori: si esce dal regime dall'anno successivo."})
    if s.get("gestione_previdenziale") == "non_so":
        avvisi.append({"livello": "informativo", "titolo": "Gestione previdenziale da confermare",
                       "testo": "Ho stimato i contributi come gestione separata. Verifica su inps.it → Fascicolo previdenziale "
                                "→ Posizione assicurativa, o sul sito della tua cassa."})
    if s.get("gestione_previdenziale") in ("artigiani", "commercianti") and s.get("riduzione_35_incerta"):
        avvisi.append({"livello": "informativo", "titolo": "Riduzione INPS del 35%: da verificare",
                       "testo": "Non sai se hai chiesto lo sconto del 35% sui contributi: ho calcolato senza. "
                                "Controlla su inps.it (Cassetto previdenziale artigiani e commercianti) o chiedi a chi "
                                "ti segue: se è attivo i contributi sono più bassi di quanto stimo."})
    elif s.get("gestione_previdenziale") in ("artigiani", "commercianti") and s.get("riduzione_35") is False:
        avvisi.append({"livello": "informativo", "titolo": "Riduzione INPS del 35% non attiva",
                       "testo": "Come forfettario puoi chiedere all'INPS lo sconto del 35% sui contributi (domanda entro il "
                                "28 febbraio). Riduce anche l'accredito pensionistico: valuta con un professionista."})

    # --- calcoli
    ricavi_prec = s.get("ricavi_anno_precedente") or 0.0
    ricavi_corr = s.get("ricavi_anno_corrente") or 0.0
    calc_prec = _calcolo(s, ricavi_prec, s.get("contributi_versati_anno_precedente")) if ricavi_prec > 0 else None
    calc_corr = _calcolo(s, ricavi_corr) if ricavi_corr > 0 else None
    imposta_prec = calc_prec["imposta_sostitutiva"] if calc_prec else 0.0
    acconti = _acconti_imposta(imposta_prec)
    acconti_inps = None
    if calc_prec and (s.get("gestione_previdenziale") in ("separata", "non_so")):
        acconti_inps = _acconti_inps_separata(calc_prec["contributi_previdenziali"]["totale_contributi"])

    # --- F24 già interpretati
    f24 = s.get("f24_pagati") or []
    letti = interpreta_f24(f24) if f24 else None
    versato_imposta_saldo = versato_acc1 = versato_acc2 = 0.0
    if letti:
        for r in letti["righe"]:
            if r["categoria"] == "imposta_sostitutiva" and r["anno_riferimento"] == anno - 1 and r["natura"] == "saldo":
                versato_imposta_saldo += r["importo"]
            if r["categoria"] == "imposta_sostitutiva" and r["anno_riferimento"] == anno:
                if r["natura"] == "acconto_1": versato_acc1 += r["importo"]
                if r["natura"] == "acconto_2": versato_acc2 += r["importo"]

    # --- spiegazione della situazione maturata
    storia = []
    if primo_anno:
        storia.append(f"Hai aperto nel {anno}: quest'anno non paghi nulla di imposta sostitutiva, perché non c'è ancora "
                      "una dichiarazione. Il conto arriva a giugno dell'anno prossimo, e sarà doppio: il saldo di "
                      f"quest'anno più il primo acconto del {anno + 1}. È la sorpresa più comune del primo anno.")
        if calc_corr:
            imp = calc_corr["imposta_sostitutiva"]; contr = calc_corr["contributi_previdenziali"]["totale_contributi"]
            storia.append(f"Con i {_eur(ricavi_corr)} € incassati finora, a giugno {anno + 1} pagheresti circa {_eur(imp)} € di "
                          f"saldo imposta più {_eur(imp * 0.5 if imp > 257.52 else 0)} € di primo acconto, e circa {_eur(contr)} € di "
                          f"contributi per l'anno {anno} (più gli acconti INPS, se dovuti). Se incassi altro, la cifra cresce in proporzione.")
    else:
        if calc_prec:
            storia.append(f"Per il {anno - 1} hai incassato {_eur(ricavi_prec)} €: reddito forfettario "
                          f"{_eur(calc_prec['reddito_forfettario_lordo'])} € (coefficiente {calc_prec['coefficiente_applicato']}), "
                          f"imposta sostitutiva stimata {_eur(imposta_prec)} € al {calc_prec['aliquota_imposta']}, contributi stimati "
                          f"{_eur(calc_prec['contributi_previdenziali']['totale_contributi'])} €.")
        if secondo_anno:
            storia.append(f"Il {anno} è il tuo secondo anno: a giugno hai pagato (o devi pagare) il saldo {anno - 1} più il "
                          f"primo acconto {anno}, e a novembre il secondo acconto. È l'anno più pesante, perché paghi quasi "
                          "due annualità in una.")
        else:
            storia.append(f"A giugno {anno} era dovuto il saldo {anno - 1} (imposta stimata {_eur(imposta_prec)} € meno gli "
                          f"acconti già versati nel {anno - 1}) più il primo acconto {anno}; a novembre il secondo acconto.")
        if acconti["rate"]:
            rate = " e ".join(f"{_eur(r['importo'])} € entro il {r['scadenza']}" for r in acconti["rate"])
            storia.append(f"Acconti {anno} stimati: {rate}. {acconti['regola']}")
        else:
            storia.append(acconti["regola"])

    # --- confronto con quanto versato
    confronto = []
    if letti:
        if acconti["rate"] and versato_acc1 == 0 and data_oggi.month > 6 and len(acconti["rate"]) == 2:
            confronto.append(f"Non risulta versato il primo acconto {anno} (atteso circa {_eur(acconti['rate'][0]['importo'])} €): "
                             "se è così, va regolarizzato con ravvedimento.")
        if versato_imposta_saldo and imposta_prec:
            acconti_impliciti = imposta_prec - versato_imposta_saldo
            if versato_imposta_saldo > imposta_prec * 1.1 + 50:
                confronto.append(f"Il saldo {anno - 1} versato ({_eur(versato_imposta_saldo)} €) supera l'intera imposta che stimo "
                                 f"({_eur(imposta_prec)} €): o i ricavi indicati sono più bassi del reale, o c'è un errore. Vale un controllo.")
            elif acconti_impliciti > 50:
                confronto.append(f"Il saldo {anno - 1} versato è {_eur(versato_imposta_saldo)} € contro un'imposta stimata di "
                                 f"{_eur(imposta_prec)} €: la differenza, circa {_eur(acconti_impliciti)} €, dovrebbe corrispondere agli "
                                 f"acconti già pagati nel {anno - 1}. Se nel {anno - 1} non hai versato acconti, qualcosa non torna.")
        confronto.extend(letti["spiegazione"])

    # --- anno in corso e soglia
    mese = data_oggi.month
    soglia = monitora_soglia(ricavi_corr, mese) if ricavi_corr > 0 else None
    da_accantonare = None
    if calc_corr:
        da_accantonare = calc_corr["pressione_fiscale_su_incassato"]

    if soglia and calc_prec and soglia["previsione_fine_anno"] < ricavi_prec * 0.8:
        avvisi.append({"livello": "informativo", "titolo": "Quest'anno incassi meno: acconti forse troppo alti",
                       "testo": f"Gli acconti {anno} sono calcolati sui {_eur(ricavi_prec)} € del {anno - 1}, ma a questo ritmo chiuderai "
                                f"intorno a {_eur(soglia['previsione_fine_anno'])} €. Puoi valutare con un professionista il metodo "
                                "previsionale per ridurre il secondo acconto; altrimenti la differenza torna come credito nella "
                                "dichiarazione dell'anno prossimo."})

    # --- prossimi passi
    gest = s.get("gestione_previdenziale") if s.get("gestione_previdenziale") in ("separata", "artigiani", "commercianti", "cassa") else "separata"
    scadenze = prossime_scadenze(gest, 180, data_oggi.isoformat())["scadenze"]
    passi = []
    if avvisi and any(a["livello"] == "importante" for a in avvisi):
        passi.append("Prima di tutto: far verificare da un professionista i punti segnalati come importanti.")
    if da_accantonare:
        passi.append(f"Da ogni fattura incassata metti da parte circa il {da_accantonare}: copre imposta e contributi.")
    if scadenze:
        prima = scadenze[0]
        passi.append(f"Prossima scadenza: {prima['data']} - {prima['descrizione']}.")
    if soglia and soglia["livello_rischio"] != "OK":
        passi.append(soglia["messaggio"])
    if not f24:
        passi.append("Quando hai a portata di mano gli F24 pagati, allegali: posso controllare che acconti e saldo tornino.")
    passi.append("Per la dichiarazione annuale e per qualsiasi dubbio sui requisiti serve un professionista abilitato: "
                 "TaxScan prepara tutto, lui controlla e firma. " + D.CONTATTI["consulenza_gratuita"])

    coeff = coefficiente_da_ateco(s.get("codice_ateco", ""))
    return {
        "profilo": {
            "gestione_attuale": s.get("gestione_attuale"),
            "partita_iva": s.get("partita_iva"),
            "apertura": s.get("data_apertura"),
            "anno_ingresso_forfettario": anno_ingresso,
            "anni_nel_regime": anni_nel_regime,
            "codice_ateco": s.get("codice_ateco"),
            "coefficiente": coeff.get("coefficiente_percentuale"),
            "gruppo_ateco": coeff.get("gruppo"),
            "aliquota": s.get("aliquota") + "%",
            "gestione_previdenziale": s.get("gestione_previdenziale"),
            "nome_cassa": s.get("nome_cassa"),
            "riduzione_35": s.get("riduzione_35"),
            "programma_fatturazione": s.get("programma_fatturazione"),
        },
        "situazione_maturata": storia,
        "anno_precedente": calc_prec,
        "anno_corrente": {"ricavi_finora": ricavi_corr, "stima_a_oggi": calc_corr, "quota_da_accantonare": da_accantonare,
                          "soglia": soglia},
        "acconti_anno_corrente": acconti,
        "acconti_inps_anno_corrente": acconti_inps,
        "f24_letti": letti,
        "confronto_con_versato": confronto,
        "avvisi": avvisi,
        "prossime_scadenze": scadenze,
        "cose_da_fare": passi,
        "disclaimer": D.DISCLAIMER,
    }


# --------------------------------------------------------------------------- piano pagamenti

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _scadenze_con_importi(s: dict, data_oggi: date) -> list:
    """Le scadenze dei prossimi 14 mesi con l'importo stimato di ciascuna."""
    anno = data_oggi.year
    ricavi_prec = s.get("ricavi_anno_precedente") or 0.0
    ricavi_corr = s.get("ricavi_anno_corrente") or 0.0
    gest = s.get("gestione_previdenziale") or "separata"
    if gest == "non_so":
        gest = "separata"

    calc_prec = _calcolo(s, ricavi_prec, s.get("contributi_versati_anno_precedente")) if ricavi_prec > 0 else None
    imposta_prec = calc_prec["imposta_sostitutiva"] if calc_prec else 0.0
    contrib_prec = calc_prec["contributi_previdenziali"]["totale_contributi"] if calc_prec else 0.0

    # stima dell'anno in corso proiettando i ricavi a fine anno
    mese = data_oggi.month
    proiezione = (ricavi_corr / mese * 12) if (ricavi_corr > 0 and mese > 0) else 0.0
    calc_corr = _calcolo(s, proiezione) if proiezione > 0 else None
    imposta_corr = calc_corr["imposta_sostitutiva"] if calc_corr else 0.0
    contrib_corr = calc_corr["contributi_previdenziali"]["totale_contributi"] if calc_corr else 0.0

    # quanto è già stato versato in acconti quest'anno (dagli F24 letti)
    versato_acc_imposta = versato_acc_inps = 0.0
    for r in (interpreta_f24(s.get("f24_pagati") or [])["righe"] if s.get("f24_pagati") else []):
        if r["anno_riferimento"] == anno and r["natura"].startswith("acconto"):
            if r["categoria"] == "imposta_sostitutiva":
                versato_acc_imposta += r["importo"]
            elif r["categoria"].startswith("inps"):
                versato_acc_inps += r["importo"]

    acc_imp = _acconti_imposta(imposta_prec)
    acc_inps = _acconti_inps_separata(contrib_prec) if gest in ("separata",) else {"rate": [], "dovuto": 0.0}

    voci = []

    def aggiungi(giorno, mese_n, anno_n, etichetta, importo, dettaglio):
        if importo <= 0.5:
            return
        d = date(anno_n, mese_n, giorno)
        if d < data_oggi:
            return
        voci.append({"data": d.isoformat(), "etichetta": etichetta, "importo": round(importo, 2),
                     "dettaglio": dettaglio, "giorni_mancanti": (d - data_oggi).days})

    # --- resto dell'anno in corso
    resto_acc_imp = max(0.0, acc_imp["dovuto"] - versato_acc_imposta)
    resto_acc_inps = max(0.0, acc_inps.get("dovuto", 0.0) - versato_acc_inps)
    if data_oggi.month <= 11:
        aggiungi(30, 11, anno, f"2° acconto {anno}", resto_acc_imp + resto_acc_inps,
                 [f"{_eur(resto_acc_imp, 2)} € imposta sostitutiva (codice 1791)" if resto_acc_imp else None,
                  f"{_eur(resto_acc_inps, 2)} € contributi INPS (causale P11)" if resto_acc_inps else None])

    # --- giugno dell'anno prossimo: saldo anno in corso + 1° acconto anno prossimo
    saldo_imp = max(0.0, imposta_corr - acc_imp["dovuto"])
    saldo_inps = max(0.0, contrib_corr - acc_inps.get("dovuto", 0.0))
    credito = max(0.0, acc_imp["dovuto"] - imposta_corr) + max(0.0, acc_inps.get("dovuto", 0.0) - contrib_corr)
    acc1_imp_next = _acconti_imposta(imposta_corr)
    acc1_inps_next = _acconti_inps_separata(contrib_corr) if gest == "separata" else {"rate": []}
    q_imp = acc1_imp_next["rate"][0]["importo"] if acc1_imp_next["rate"] else 0.0
    q_inps = acc1_inps_next["rate"][0]["importo"] if acc1_inps_next["rate"] else 0.0
    aggiungi(30, 6, anno + 1, f"Saldo {anno} + 1° acconto {anno + 1}", saldo_imp + saldo_inps + q_imp + q_inps,
             [f"{_eur(saldo_imp, 2)} € saldo imposta {anno} (codice 1792)" if saldo_imp else None,
              f"{_eur(saldo_inps, 2)} € saldo contributi {anno}" if saldo_inps else None,
              f"{_eur(q_imp, 2)} € 1° acconto imposta {anno + 1} (codice 1790)" if q_imp else None,
              f"{_eur(q_inps, 2)} € 1° acconto contributi {anno + 1} (causale P10)" if q_inps else None])

    # --- rate fisse INPS artigiani/commercianti
    if gest in ("artigiani", "commercianti"):
        p = D.ARTIGIANI_COMMERCIANTI
        fisso = p[gest]["fisso_annuo"] * (1 - p["riduzione_forfettari"] if s.get("riduzione_35") else 1)
        rata = fisso / 4
        for giorno, mese_n, anno_n in [(20, 8, anno), (16, 11, anno), (16, 2, anno + 1), (18, 5, anno + 1)]:
            aggiungi(giorno, mese_n, anno_n, "Rata fissa INPS " + gest, rata,
                     [f"{_eur(rata, 2)} € contributi fissi sul minimale"])

    for v in voci:
        v["credito_stimato"] = round(credito, 2) if v["etichetta"].startswith("Saldo") and credito > 1 else 0
    voci.sort(key=lambda v: v["data"])
    for v in voci:
        v["dettaglio"] = [d for d in v["dettaglio"] if d]
    return voci


def piano_pagamenti(scheda: dict, oggi: str = "", accantonamento_attuale: float = 0.0) -> dict:
    """Calendario dell'anno: cosa scade, quando, e quanto mettere da parte ogni mese per arrivarci pronti."""
    v = verifica_scheda(scheda)
    s = _normalizza(scheda)
    if not v["completa"]:
        return {"errore": "Scheda incompleta: completa prima il colloquio.",
                "campi_mancanti": [m["campo"] for m in v["campi_mancanti"]]}

    data_oggi = date.fromisoformat(oggi) if oggi else date.today()
    voci = _scadenze_con_importi(s, data_oggi)
    if not voci:
        return {"scadenze": [], "messaggio": "Nessuna scadenza stimabile nei prossimi mesi con i dati forniti.",
                "disclaimer": D.DISCLAIMER}

    totale = sum(x["importo"] for x in voci)
    ricavi_corr = s.get("ricavi_anno_corrente") or 0.0
    calc_corr = _calcolo(s, ricavi_corr) if ricavi_corr > 0 else None
    quota_fattura = calc_corr["pressione_fiscale_su_incassato"] if calc_corr else None

    # --- mese per mese: quanto accantonare per coprire ogni scadenza in tempo
    fondo = float(accantonamento_attuale or 0.0)
    mesi_piano, cursore = [], date(data_oggi.year, data_oggi.month, 1)
    ultima = date.fromisoformat(voci[-1]["data"])
    da_coprire = [dict(x) for x in voci]
    while cursore <= ultima:
        fine_mese = date(cursore.year + (cursore.month == 12), (cursore.month % 12) + 1, 1)
        in_scadenza = [x for x in da_coprire if cursore.isoformat() <= x["data"] < fine_mese.isoformat()]
        uscite = sum(x["importo"] for x in in_scadenza)
        # Quota necessaria: si guarda OGNI scadenza futura e si prende il ritmo più esigente, così anche
        # una rata grande lontana viene accumulata per tempo invece di arrivare tutta insieme.
        prossime = [x for x in da_coprire if x["data"] >= fine_mese.isoformat()]
        quota, disponibile = 0.0, max(0.0, fondo - uscite)
        cumulato = 0.0
        for p in prossime:
            cumulato += p["importo"]
            d_scad = date.fromisoformat(p["data"])
            mesi_rimasti = max(1, (d_scad.year - cursore.year) * 12 + (d_scad.month - cursore.month))
            necessario = max(0.0, cumulato - disponibile) / mesi_rimasti
            quota = max(quota, necessario)
        mancante_ora = max(0.0, uscite - fondo)
        fondo = max(0.0, fondo - uscite) + quota
        mesi_piano.append({
            "mese": f"{MESI[cursore.month - 1]} {cursore.year}",
            "da_accantonare": round(quota, 2),
            "in_uscita": round(uscite, 2),
            "scadenze_del_mese": [x["etichetta"] for x in in_scadenza],
            "scoperto": round(mancante_ora, 2) if mancante_ora > 0.5 else 0,
            "fondo_a_fine_mese": round(fondo, 2),
        })
        cursore = fine_mese

    prima = voci[0]
    avvisi = []
    scoperti = [m for m in mesi_piano if m["scoperto"]]
    if scoperti and accantonamento_attuale:
        avvisi.append(f"Con {_eur(accantonamento_attuale)} € già da parte, a {scoperti[0]['mese']} mancherebbero "
                      f"{_eur(scoperti[0]['scoperto'])} €: inizia ad accantonare da subito.")
    if prima["giorni_mancanti"] <= 45:
        avvisi.append(f"La prossima scadenza è tra {prima['giorni_mancanti']} giorni ({prima['etichetta']}, "
                      f"{_eur(prima['importo'])} €): verifica di avere la somma disponibile.")
    credito_tot = sum(x.get("credito_stimato", 0) for x in voci)
    if credito_tot > 1:
        avvisi.append(f"Con i ricavi attuali chiuderai l'anno sotto il livello su cui sono calcolati gli acconti: a giugno non "
                      f"pagheresti saldo, e anzi avresti circa {_eur(credito_tot)} € di credito da usare in compensazione. "
                      "Puoi anche valutare con un professionista di ridurre il secondo acconto con il metodo previsionale.")
    if quota_fattura:
        avvisi.append(f"Regola pratica: da ogni fattura incassata metti da parte il {quota_fattura}. "
                      "È il modo più semplice per non trovarti scoperto.")

    return {
        "periodo": f"da {MESI[data_oggi.month - 1]} {data_oggi.year} a {MESI[ultima.month - 1]} {ultima.year}",
        "totale_da_versare": round(totale, 2),
        "quota_per_ogni_fattura": quota_fattura,
        "scadenze": voci,
        "piano_mensile": mesi_piano,
        "avvisi": avvisi,
        "nota": "Gli importi sono stime: quelli dell'anno prossimo si basano sulla proiezione dei ricavi attuali e "
                "cambiano se incassi di più o di meno. Se le scadenze cadono di sabato o in un festivo slittano al "
                "primo giorno lavorativo utile.",
        "disclaimer": D.DISCLAIMER,
    }
