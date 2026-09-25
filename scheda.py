"""
TaxScan - scheda del colloquio iniziale, lettura F24 e quadro generale.

Il server non ha memoria: la scheda vive nella conversazione. Claude la compila man mano
che l'utente risponde o allega documenti, la passa a `verifica_scheda` per sapere cosa manca,
e quando è completa a `genera_quadro`.

Struttura del colloquio (dalle interviste e dal prototipo di Marcello):
  1. gestione   - chi gestisce oggi la partita IVA e perché è qui
  2. identita   - P.IVA, apertura, ingresso nel forfettario, ATECO, tipo attività
  3. aliquota   - 5% o 15% + i tre requisiti del 5%
  4. previdenza - gestione INPS o cassa, riduzione 35%
  5. requisiti  - cause ostative e limiti (dipendente/pensione fino a 35.000)
  6. numeri     - ricavi anno precedente e corrente, F24 pagati
"""

from datetime import date

import dati_fisco as D
from calcoli import calcola_forfettario, coefficiente_da_ateco, monitora_soglia, prossime_scadenze

# --------------------------------------------------------------------------- campi

GRUPPI = ["gestione", "identita", "aliquota", "previdenza", "requisiti", "numeri"]

CAMPI = [
    # gruppo gestione
    {"chiave": "gestione_attuale", "gruppo": "gestione", "obbligatorio": True,
     "valori": ["consulente_vuole_smettere", "da_solo", "ex_commercialista_ora_solo", "consulente_soddisfatto"],
     "domanda": "Oggi chi gestisce la tua partita IVA? Hai un consulente ma vorresti farne a meno, "
                "la gestisci già da solo, avevi un commercialista e ora sei da solo, oppure hai un "
                "consulente e vuoi solo capirci di più?"},
    {"chiave": "motivo", "gruppo": "gestione", "obbligatorio": False,
     "domanda": "Cosa ti ha portato qui: il costo, la poca disponibilità di chi ti segue, o la voglia di capire meglio?"},

    # gruppo identita
    {"chiave": "data_apertura", "gruppo": "identita", "obbligatorio": True, "tipo": "data",
     "domanda": "Quando hai aperto la partita IVA? Se hai il certificato di attribuzione in PDF, allegalo: leggo tutto da lì.",
     "dove_trovarlo": "Area riservata agenziaentrate.gov.it (SPID/CIE) → Richiesta certificati → "
                      "Certificato di attribuzione della partita IVA. Oppure chiedilo al commercialista."},
    {"chiave": "anno_ingresso_forfettario", "gruppo": "identita", "obbligatorio": True, "tipo": "anno",
     "domanda": "Sei in forfettario dall'apertura o sei passato da un altro regime? In che anno?",
     "default_da": "data_apertura"},
    {"chiave": "codice_ateco", "gruppo": "identita", "obbligatorio": True,
     "domanda": "Qual è il tuo codice ATECO principale? È scritto sul certificato di attribuzione.",
     "dove_trovarlo": "Certificato di attribuzione P.IVA, voce 'codice attività'. Se hai più codici, "
                      "serve quello dell'attività con più ricavi."},
    {"chiave": "tipo_attivita", "gruppo": "identita", "obbligatorio": True,
     "valori": ["professionista", "artigiano", "commerciante", "altro"],
     "domanda": "La tua è un'attività professionale, artigianale o commerciale?"},
    {"chiave": "partita_iva", "gruppo": "identita", "obbligatorio": False,
     "domanda": "Se vuoi, indica la partita IVA: serve solo per il riepilogo, non è obbligatoria."},

    # gruppo aliquota
    {"chiave": "aliquota", "gruppo": "aliquota", "obbligatorio": True, "valori": ["5", "15", "incerto"],
     "domanda": "Applichi l'aliquota agevolata del 5% (nuove attività, primi 5 anni) o quella ordinaria del 15%? "
                "Se non lo sai, dimmelo e lo capiamo insieme.",
     "dove_trovarlo": "Ultima dichiarazione dei redditi, quadro LM, rigo LM39 (aliquota). Attenzione: nella "
                      "precompilata il rigo è vuoto, perché l'aliquota la sceglie il contribuente."},
    {"chiave": "req5_prima_attivita", "gruppo": "aliquota", "obbligatorio": "se_5_o_incerto", "tipo": "bool",
     "domanda": "È la prima volta che eserciti questa attività con partita IVA?"},
    {"chiave": "req5_no_attivita_simile_3_anni", "gruppo": "aliquota", "obbligatorio": "se_5_o_incerto", "tipo": "bool",
     "domanda": "Nei tre anni prima dell'apertura NON hai svolto la stessa attività, nemmeno da dipendente o con altra partita IVA?"},
    {"chiave": "req5_non_prosecuzione_dipendente", "gruppo": "aliquota", "obbligatorio": "se_5_o_incerto", "tipo": "bool",
     "domanda": "L'attività NON è la prosecuzione di un lavoro che facevi da dipendente?"},

    # gruppo previdenza
    {"chiave": "gestione_previdenziale", "gruppo": "previdenza", "obbligatorio": True,
     "valori": ["separata", "artigiani", "commercianti", "cassa", "non_so"],
     "domanda": "A quale gestione previdenziale sei iscritto: INPS gestione separata, INPS artigiani, INPS commercianti, "
                "o una cassa professionale del tuo Ordine?",
     "dove_trovarlo": "Regola pratica: professione con Ordine o Collegio → cassa dell'Ordine; attività artigianale o "
                      "commerciale → INPS artigiani/commercianti; freelance senza Ordine → gestione separata. "
                      "Conferma su inps.it → Fascicolo previdenziale del cittadino → Posizione assicurativa."},
    {"chiave": "nome_cassa", "gruppo": "previdenza", "obbligatorio": "se_cassa",
     "domanda": "Quale cassa? (Inarcassa, Cassa Forense, ENPAM, Cassa Commercialisti...)"},
    {"chiave": "aliquota_cassa", "gruppo": "previdenza", "obbligatorio": False, "tipo": "numero",
     "domanda": "Se la conosci, l'aliquota contributiva della tua cassa (es. 0.16 per 16%)."},
    {"chiave": "riduzione_35", "gruppo": "previdenza", "obbligatorio": "se_artigiani_commercianti", "tipo": "bool",
     "domanda": "Hai chiesto all'INPS la riduzione del 35% dei contributi riservata ai forfettari?"},
    {"chiave": "altra_copertura_previdenziale", "gruppo": "previdenza", "obbligatorio": False, "tipo": "bool",
     "domanda": "Sei anche pensionato o iscritto a un'altra previdenza obbligatoria (es. da dipendente)?"},

    # gruppo requisiti
    {"chiave": "redditi_dipendente_pensione", "gruppo": "requisiti", "obbligatorio": True, "tipo": "numero",
     "domanda": "L'anno scorso hai avuto anche redditi da lavoro dipendente o pensione? Se sì, circa quanto lordo? "
                "(scrivi 0 se nessuno)"},
    {"chiave": "rapporto_dipendente_cessato", "gruppo": "requisiti", "obbligatorio": False, "tipo": "bool",
     "domanda": "Quel rapporto di lavoro dipendente è cessato?"},
    {"chiave": "partecipazioni_societarie", "gruppo": "requisiti", "obbligatorio": True, "tipo": "bool",
     "domanda": "Hai quote in società di persone, associazioni professionali, o controlli una SRL che fa la tua stessa attività?"},
    {"chiave": "prevalenza_ex_datore", "gruppo": "requisiti", "obbligatorio": True, "tipo": "bool",
     "domanda": "Fatturi in prevalenza a un tuo ex datore di lavoro degli ultimi due anni, o a soggetti a lui collegati?"},
    {"chiave": "spese_personale", "gruppo": "requisiti", "obbligatorio": False, "tipo": "numero",
     "domanda": "Hai dipendenti o collaboratori? Quanto spendi all'anno lordo? (0 se nessuno)"},

    # gruppo numeri
    {"chiave": "ricavi_anno_precedente", "gruppo": "numeri", "obbligatorio": True, "tipo": "numero",
     "domanda": "Quanto hai incassato in totale l'anno scorso? (0 se hai aperto quest'anno)"},
    {"chiave": "ricavi_anno_corrente", "gruppo": "numeri", "obbligatorio": True, "tipo": "numero",
     "domanda": "E quest'anno, da gennaio a oggi, quanto hai incassato?"},
    {"chiave": "programma_fatturazione", "gruppo": "numeri", "obbligatorio": False,
     "domanda": "Con quale programma fai le fatture elettroniche?"},
    {"chiave": "f24_pagati", "gruppo": "numeri", "obbligatorio": False, "tipo": "lista",
     "domanda": "Hai gli F24 pagati nell'ultimo anno? Allegali in PDF o dimmi data, codice tributo, anno di riferimento e importo: "
                "da lì capisco cosa hai già versato.",
     "dove_trovarlo": "Cassetto fiscale → Versamenti → F24, oppure home banking → archivio F24."},
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


def _obbligatorio(campo, scheda):
    o = campo["obbligatorio"]
    if o is True or o is False:
        return o
    if o == "se_5_o_incerto":
        return str(scheda.get("aliquota", "")) in ("5", "incerto")
    if o == "se_cassa":
        return scheda.get("gestione_previdenziale") == "cassa"
    if o == "se_artigiani_commercianti":
        return scheda.get("gestione_previdenziale") in ("artigiani", "commercianti")
    return False


def _normalizza(scheda: dict) -> dict:
    s = dict(scheda or {})
    for c in CAMPI:
        k, t = c["chiave"], c.get("tipo")
        if k not in s:
            continue
        if t == "bool":
            s[k] = _bool(s[k])
        elif t == "numero":
            s[k] = _num(s[k])
        elif t == "anno":
            s[k] = _anno(s[k])
        elif k == "aliquota" and s[k] is not None:
            s[k] = str(s[k]).replace("%", "").strip()
    if not s.get("anno_ingresso_forfettario") and s.get("data_apertura"):
        s["anno_ingresso_forfettario"] = _anno(s["data_apertura"])
    if s.get("codice_ateco"):
        s["codice_ateco"] = str(s["codice_ateco"]).strip()
    return s


# --------------------------------------------------------------------------- API

def avvia_colloquio() -> dict:
    """Istruzioni e scheda vuota per iniziare il colloquio."""
    return {
        "istruzioni_per_l_assistente": [
            "Conduci un colloquio in italiano, una o due domande alla volta, con tono semplice e senza gergo.",
            "Segui l'ordine dei gruppi: gestione, identita, aliquota, previdenza, requisiti, numeri.",
            "Se l'utente allega un PDF (certificato di attribuzione P.IVA, dichiarazione dei redditi, F24, "
            "estratto INPS), leggilo tu e riempi i campi corrispondenti, poi chiedi conferma dei valori letti.",
            "Nel certificato di attribuzione trasmesso da un intermediario ci sono due codici fiscali: quello "
            "del commercialista e quello del titolare. Non confonderli.",
            "Dopo ogni gruppo di risposte chiama verifica_scheda con tutta la scheda accumulata: ti dice cosa manca "
            "e la prossima domanda da fare. Non saltare nessun campo obbligatorio.",
            "Quando verifica_scheda dice che la scheda è completa, chiama genera_quadro e spiega il risultato "
            "in modo discorsivo: prima la situazione maturata fino a oggi, poi cosa succede alle prossime scadenze, "
            "poi le cose da fare. Mostra sempre il disclaimer.",
            "Non dare mai l'impressione di sostituire il professionista: TaxScan prepara e spiega, il "
            "professionista controlla e firma.",
        ],
        "gruppi": GRUPPI,
        "scheda_vuota": {c["chiave"]: None for c in CAMPI},
        "prima_domanda": CAMPI_PER_CHIAVE["gestione_attuale"]["domanda"],
    }


def verifica_scheda(scheda: dict) -> dict:
    """Normalizza la scheda, elenca i campi mancanti e suggerisce la prossima domanda."""
    s = _normalizza(scheda)
    mancanti, avvisi = [], []
    for c in CAMPI:
        if not _obbligatorio(c, s):
            continue
        v = s.get(c["chiave"])
        if v is None or v == "" or v == []:
            mancanti.append({"campo": c["chiave"], "gruppo": c["gruppo"], "domanda": c["domanda"],
                             "dove_trovarlo": c.get("dove_trovarlo")})
        elif c.get("valori") and str(v) not in c["valori"]:
            avvisi.append(f"Valore non riconosciuto per {c['chiave']}: '{v}'. Ammessi: {', '.join(c['valori'])}.")

    if s.get("codice_ateco"):
        info = coefficiente_da_ateco(s["codice_ateco"])
        if "errore" in info:
            avvisi.append("Codice ATECO non valido: " + info["errore"])
        elif info.get("attenzione"):
            avvisi.append(info["attenzione"])

    if s.get("tipo_attivita") and s.get("gestione_previdenziale"):
        coppie_strane = {("professionista", "artigiani"), ("professionista", "commercianti"),
                         ("artigiano", "separata"), ("commerciante", "separata")}
        if (s["tipo_attivita"], s["gestione_previdenziale"]) in coppie_strane:
            avvisi.append(f"Attività '{s['tipo_attivita']}' con gestione '{s['gestione_previdenziale']}' è una "
                          "combinazione insolita: chiedi conferma all'utente.")

    prossimo = mancanti[0] if mancanti else None
    return {
        "scheda_normalizzata": s,
        "completa": not mancanti,
        "campi_mancanti": mancanti,
        "prossima_domanda": prossimo["domanda"] if prossimo else None,
        "dove_trovarlo": prossimo.get("dove_trovarlo") if prossimo else None,
        "avvisi": avvisi,
        "gruppo_corrente": prossimo["gruppo"] if prossimo else "completo",
    }


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

    if rateizzati and not ha_interessi:
        spiegazione.append("Alcuni versamenti risultano rateizzati (campo rateazione diverso da 0101) ma non vedo il codice 1668 "
                           "degli interessi di rateazione: se mancano davvero, va sistemato con un piccolo ravvedimento.")
    return {"righe": esito, "totale_versato": round(totale, 2), "per_categoria": per_categoria,
            "codici_sconosciuti": sconosciuti, "rateizzato": bool(rateizzati), "spiegazione": spiegazione}


# --------------------------------------------------------------------------- quadro

def _acconti_imposta(imposta_anno_precedente: float) -> dict:
    """Regola degli acconti: 100% dell'imposta dell'anno prima; niente sotto 51,65; unica rata a novembre sotto 257,52."""
    if imposta_anno_precedente <= 51.65:
        return {"dovuto": 0.0, "rate": [], "regola": "Imposta dell'anno precedente fino a 51,65 €: nessun acconto dovuto."}
    if imposta_anno_precedente <= 257.52:
        return {"dovuto": round(imposta_anno_precedente, 2),
                "rate": [{"scadenza": "30 novembre", "importo": round(imposta_anno_precedente, 2)}],
                "regola": "Imposta dell'anno precedente fino a 257,52 €: acconto in unica soluzione entro il 30 novembre."}
    return {"dovuto": round(imposta_anno_precedente, 2),
            "rate": [{"scadenza": "30 giugno", "importo": round(imposta_anno_precedente * 0.40, 2)},
                     {"scadenza": "30 novembre", "importo": round(imposta_anno_precedente * 0.60, 2)}],
            "regola": "Acconto pari al 100% dell'imposta dell'anno precedente: 40% entro il 30 giugno, 60% entro il 30 novembre."}


def _calcolo(s: dict, ricavi: float) -> dict:
    gestione = s.get("gestione_previdenziale") or "separata"
    if gestione == "non_so":
        gestione = "separata"
    aliquota_5 = str(s.get("aliquota")) == "5"
    return calcola_forfettario(
        ricavi_incassati=ricavi, codice_ateco=s.get("codice_ateco", ""), gestione=gestione,
        nuova_attivita=aliquota_5, riduzione_35=bool(s.get("riduzione_35")),
        altra_copertura_previdenziale=bool(s.get("altra_copertura_previdenziale")),
        aliquota_cassa=float(s.get("aliquota_cassa") or 0.0))


def genera_quadro(scheda: dict, oggi: str = "") -> dict:
    """Il quadro generale: situazione maturata, spiegazione dei pagamenti, avvisi, prossimi passi."""
    v = verifica_scheda(scheda)
    s = v["scheda_normalizzata"]
    if not v["completa"]:
        return {"errore": "Scheda incompleta: chiama prima verifica_scheda e completa i campi mancanti.",
                "campi_mancanti": [m["campo"] for m in v["campi_mancanti"]]}

    data_oggi = date.fromisoformat(oggi) if oggi else date.today()
    anno = data_oggi.year
    anno_ingresso = s.get("anno_ingresso_forfettario") or anno
    anni_nel_regime = anno - anno_ingresso
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
    if s.get("gestione_previdenziale") in ("artigiani", "commercianti") and s.get("riduzione_35") is False:
        avvisi.append({"livello": "informativo", "titolo": "Riduzione INPS del 35% non attiva",
                       "testo": "Come forfettario puoi chiedere all'INPS lo sconto del 35% sui contributi (domanda entro il "
                                "28 febbraio). Riduce anche l'accredito pensionistico: valuta con un professionista."})

    # --- calcoli
    ricavi_prec = s.get("ricavi_anno_precedente") or 0.0
    ricavi_corr = s.get("ricavi_anno_corrente") or 0.0
    calc_prec = _calcolo(s, ricavi_prec) if ricavi_prec > 0 else None
    calc_corr = _calcolo(s, ricavi_corr) if ricavi_corr > 0 else None
    imposta_prec = calc_prec["imposta_sostitutiva"] if calc_prec else 0.0
    acconti = _acconti_imposta(imposta_prec)

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
                          f"saldo imposta più {_eur(imp * 0.4 if imp > 257.52 else 0)} € di primo acconto, e circa {_eur(contr)} € di "
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
        "f24_letti": letti,
        "confronto_con_versato": confronto,
        "avvisi": avvisi,
        "prossime_scadenze": scadenze,
        "cose_da_fare": passi,
        "disclaimer": D.DISCLAIMER,
    }
