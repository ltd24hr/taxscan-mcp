"""Motore di calcolo TaxScan. Nessun dato personale viene salvato: tutto è calcolato al volo."""

from datetime import date

import dati_fisco as D


# ---------------------------------------------------------------- coefficiente

def _pulisci_ateco(codice: str) -> str:
    return "".join(c for c in (codice or "") if c.isdigit() or c == ".").strip(".")


def coefficiente_da_ateco(codice_ateco: str) -> dict:
    """Restituisce il coefficiente di redditività del codice ATECO indicato."""
    codice = _pulisci_ateco(codice_ateco)
    if not codice:
        return {"errore": "Codice ATECO mancante o non valido.",
                "suggerimento": "Indica almeno le prime due cifre, es. 62 o 47.91.10."}

    trovato = None
    for prefissi, coeff, gruppo in D.GRUPPI_COEFFICIENTE:
        for p in sorted(prefissi, key=len, reverse=True):
            if codice.startswith(p):
                trovato = (coeff, gruppo, p)
                break
        if trovato:
            break
    if not trovato:
        trovato = (D.COEFFICIENTE_RESIDUALE[0], D.COEFFICIENTE_RESIDUALE[1], "residuale")

    coeff, gruppo, prefisso = trovato
    risultato = {
        "codice_ateco": codice,
        "coefficiente": coeff,
        "coefficiente_percentuale": f"{coeff * 100:.0f}%",
        "gruppo": gruppo,
        "quota_spese_forfettarie": f"{(1 - coeff) * 100:.0f}%",
        "riferimento": "Allegato 4 Legge 190/2014",
        "disclaimer": D.DISCLAIMER,
    }
    if codice.startswith(("46", "47")):
        risultato["attenzione"] = (
            "Nelle divisioni 46 e 47 convivono coefficienti diversi (40%, 54%, 62%). "
            "Dal 1° aprile 2025 vale la classificazione ATECO 2025: conta il coefficiente del "
            "codice ATECO 2007/2022 da cui la partita IVA è stata riclassificata. Da verificare "
            "con il professionista."
        )
    if prefisso == "residuale":
        risultato["attenzione"] = (
            "Codice non riconducibile a un gruppo specifico: applicato il coefficiente residuale "
            "del 67%. Da confermare con il professionista."
        )
    return risultato


# ---------------------------------------------------------------- contributi

def _contributi_gestione_separata(reddito: float, altra_copertura: bool) -> dict:
    imponibile = min(reddito, D.GESTIONE_SEPARATA["massimale"])
    aliquota = (D.GESTIONE_SEPARATA["aliquota_pensionati_o_altra_cassa"] if altra_copertura
                else D.GESTIONE_SEPARATA["aliquota_senza_altra_copertura"])
    return {"gestione": "Gestione separata INPS", "aliquota": aliquota,
            "imponibile_previdenziale": round(imponibile, 2),
            "contributi_fissi": 0.0,
            "contributi_variabili": round(imponibile * aliquota, 2),
            "totale_contributi": round(imponibile * aliquota, 2),
            "note": [D.GESTIONE_SEPARATA["nota"]]}


def _contributi_artigiani_commercianti(reddito: float, tipo: str, riduzione_35: bool,
                                       iscritto_ante_1996: bool) -> dict:
    p = D.ARTIGIANI_COMMERCIANTI
    conf = p[tipo]
    massimale = p["massimale_ante_1996"] if iscritto_ante_1996 else p["massimale_post_1996"]
    reddito = min(reddito, massimale)

    fisso = conf["fisso_annuo"]
    eccedenza = max(0.0, reddito - p["minimale_reddito"])
    fino_soglia = min(eccedenza, max(0.0, p["soglia_aliquota_maggiorata"] - p["minimale_reddito"]))
    oltre_soglia = max(0.0, reddito - p["soglia_aliquota_maggiorata"])
    variabili = fino_soglia * conf["aliquota"] + oltre_soglia * conf["aliquota_oltre_soglia"]

    _eur = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    minimale = f"{p['minimale_reddito']:,.0f}".replace(",", ".")
    note = [f"Il contributo fisso di {_eur(fisso)} euro è dovuto anche con reddito inferiore al "
            f"minimale di {minimale} euro."]
    if riduzione_35:
        sconto = p["riduzione_forfettari"]
        fisso, variabili = fisso * (1 - sconto), variabili * (1 - sconto)
        note.append("Applicata la riduzione del 35% per i forfettari (domanda all'INPS entro il "
                    "28 febbraio). Riduce anche l'accredito ai fini pensionistici.")
    else:
        note.append("Non applicata la riduzione del 35%: se spetta, va richiesta all'INPS entro "
                    "il 28 febbraio.")

    return {"gestione": f"INPS {tipo}", "aliquota": conf["aliquota"],
            "imponibile_previdenziale": round(reddito, 2),
            "contributi_fissi": round(fisso, 2),
            "contributi_variabili": round(variabili, 2),
            "totale_contributi": round(fisso + variabili, 2),
            "note": note}


def _contributi_cassa(reddito: float, aliquota_cassa: float) -> dict:
    return {"gestione": "Cassa professionale", "aliquota": aliquota_cassa,
            "imponibile_previdenziale": round(reddito, 2),
            "contributi_fissi": 0.0,
            "contributi_variabili": round(reddito * aliquota_cassa, 2),
            "totale_contributi": round(reddito * aliquota_cassa, 2),
            "note": ["Stima semplificata: ogni cassa ha regole, minimi e integrativi propri. "
                     "Verifica con il tuo ente di previdenza."]}


# ---------------------------------------------------------------- calcolo principale

def calcola_forfettario(ricavi_incassati: float, codice_ateco: str = "",
                        coefficiente: float | None = None, gestione: str = "separata",
                        aliquota_imposta: float | None = None, nuova_attivita: bool = False,
                        riduzione_35: bool = False, altra_copertura_previdenziale: bool = False,
                        aliquota_cassa: float = 0.0, iscritto_ante_1996: bool = False,
                        contributi_versati_nell_anno: float | None = None) -> dict:
    """Calcola reddito, contributi e imposta sostitutiva di un forfettario."""
    if ricavi_incassati is None or ricavi_incassati < 0:
        return {"errore": "Indica i ricavi o compensi incassati nell'anno."}

    if coefficiente is None:
        info = coefficiente_da_ateco(codice_ateco)
        if "errore" in info:
            return info
        coefficiente = info["coefficiente"]
    else:
        info = {"coefficiente": coefficiente, "gruppo": "coefficiente indicato manualmente",
                "coefficiente_percentuale": f"{coefficiente * 100:.0f}%"}

    reddito_lordo = ricavi_incassati * coefficiente

    gestione = (gestione or "separata").lower()
    if gestione in ("artigiani", "commercianti"):
        contributi = _contributi_artigiani_commercianti(reddito_lordo, gestione, riduzione_35,
                                                        iscritto_ante_1996)
    elif gestione == "cassa":
        contributi = _contributi_cassa(reddito_lordo, aliquota_cassa)
    else:
        contributi = _contributi_gestione_separata(reddito_lordo, altra_copertura_previdenziale)

    deducibili = (contributi["totale_contributi"] if contributi_versati_nell_anno is None
                  else contributi_versati_nell_anno)
    imponibile = max(0.0, reddito_lordo - deducibili)
    aliquota = aliquota_imposta if aliquota_imposta is not None else (
        D.ALIQUOTA_STARTUP if nuova_attivita else D.ALIQUOTA_ORDINARIA)
    imposta = imponibile * aliquota

    note = list(contributi["note"])
    if contributi_versati_nell_anno is None:
        note.append("I contributi si deducono per cassa, cioè per l'importo effettivamente "
                    "versato nell'anno: qui è stato usato l'importo dovuto per l'anno, quindi il "
                    "risultato è una stima.")
    if nuova_attivita:
        note.append("Aliquota 5%: spetta nei primi 5 anni solo se ricorrono i requisiti di "
                    "novità dell'attività previsti dalla legge.")

    return {
        "anno": D.ANNO,
        "ricavi_incassati": round(ricavi_incassati, 2),
        "coefficiente_applicato": info.get("coefficiente_percentuale"),
        "gruppo_ateco": info.get("gruppo"),
        "reddito_forfettario_lordo": round(reddito_lordo, 2),
        "contributi_previdenziali": contributi,
        "imponibile_imposta_sostitutiva": round(imponibile, 2),
        "aliquota_imposta": f"{aliquota * 100:.0f}%",
        "imposta_sostitutiva": round(imposta, 2),
        "totale_da_versare": round(contributi["totale_contributi"] + imposta, 2),
        "netto_stimato": round(ricavi_incassati - contributi["totale_contributi"] - imposta, 2),
        "pressione_fiscale_su_incassato":
            f"{((contributi['totale_contributi'] + imposta) / ricavi_incassati * 100):.1f}%"
            if ricavi_incassati else "n/d",
        "note": note,
        "prossimo_passo": "Per il calcolo definitivo e la dichiarazione serve un professionista "
                          "abilitato: " + D.CONTATTI["consulenza_gratuita"],
        "disclaimer": D.DISCLAIMER,
    }


# ---------------------------------------------------------------- soglia

def monitora_soglia(ricavi_incassati_ytd: float, mese_di_riferimento: int | None = None,
                    crescita_mensile_attesa: float = 0.0) -> dict:
    """Proietta i ricavi di fine anno e valuta il rischio di superare 85.000 / 100.000 euro."""
    mese = mese_di_riferimento or date.today().month
    mese = max(1, min(12, mese))
    if ricavi_incassati_ytd < 0:
        return {"errore": "Indica i ricavi incassati da inizio anno."}

    media_mensile = ricavi_incassati_ytd / mese
    mesi_restanti = 12 - mese
    previsione, mensile, mese_sforamento = ricavi_incassati_ytd, media_mensile, None
    for i in range(1, mesi_restanti + 1):
        mensile *= (1 + crescita_mensile_attesa)
        previsione += mensile
        if mese_sforamento is None and previsione > D.SOGLIA_RICAVI:
            mese_sforamento = mese + i

    margine = D.SOGLIA_RICAVI - ricavi_incassati_ytd
    if ricavi_incassati_ytd > D.SOGLIA_USCITA_IMMEDIATA:
        livello, messaggio = "SUPERATA_USCITA_IMMEDIATA", (
            "Superati i 100.000 euro: uscita immediata dal regime, con obbligo di IVA "
            "dall'operazione che ha determinato il superamento. Contatta subito un professionista.")
    elif ricavi_incassati_ytd > D.SOGLIA_RICAVI:
        livello, messaggio = "SUPERATA_85K", (
            "Superati gli 85.000 euro restando sotto i 100.000: si resta nel forfettario per "
            f"l'anno in corso e si passa al regime ordinario dal {D.ANNO + 1}.")
    elif previsione > D.SOGLIA_USCITA_IMMEDIATA:
        livello, messaggio = "RISCHIO_ALTO", (
            "Con questo andamento si rischia di superare i 100.000 euro, che comporta l'uscita "
            "immediata dal regime.")
    elif previsione > D.SOGLIA_RICAVI:
        livello, messaggio = "RISCHIO_MEDIO", (
            "Con questo andamento gli 85.000 euro verrebbero superati entro fine anno: "
            "il passaggio all'ordinario scatterebbe dall'anno successivo.")
    else:
        livello, messaggio = "OK", "Nessun rischio di superamento con l'andamento attuale."

    return {
        "ricavi_ytd": round(ricavi_incassati_ytd, 2),
        "mese_di_riferimento": mese,
        "media_mensile": round(media_mensile, 2),
        "crescita_mensile_attesa": crescita_mensile_attesa,
        "previsione_fine_anno": round(previsione, 2),
        "soglia_85k": D.SOGLIA_RICAVI,
        "soglia_uscita_immediata": D.SOGLIA_USCITA_IMMEDIATA,
        "margine_residuo": round(margine, 2),
        "mese_stimato_superamento": mese_sforamento,
        "livello_rischio": livello,
        "messaggio": messaggio,
        "prossimo_passo": ("Pianifica per tempo la transizione: "
                           + D.CONTATTI["consulenza_gratuita"]) if livello != "OK" else
                          "Ricontrolla tra qualche mese o dopo un trimestre di forte crescita.",
        "disclaimer": D.DISCLAIMER,
    }


# ---------------------------------------------------------------- scadenze e requisiti

def prossime_scadenze(gestione: str = "separata", giorni: int = 120,
                      data_riferimento: str = "") -> dict:
    """Elenca le scadenze fiscali e contributive nei prossimi giorni indicati."""
    oggi = date.fromisoformat(data_riferimento) if data_riferimento else date.today()
    gestione = (gestione or "separata").lower()
    elenco = []
    for s in D.SCADENZE:
        if gestione not in s["gestioni"]:
            continue
        giorno, mese = int(s["data"][:2]), int(s["data"][3:])
        for anno in (oggi.year, oggi.year + 1):
            d = date(anno, mese, giorno)
            if 0 <= (d - oggi).days <= giorni:
                elenco.append({"data": d.isoformat(), "giorni_mancanti": (d - oggi).days,
                               "tipo": s["tipo"], "descrizione": s["descrizione"]})
    elenco.sort(key=lambda x: x["data"])
    return {"data_riferimento": oggi.isoformat(), "gestione": gestione,
            "finestra_giorni": giorni, "scadenze": elenco,
            "nota": "Se la scadenza cade di sabato o in un giorno festivo slitta al primo giorno "
                    "lavorativo successivo. Verifica sempre il calendario fiscale ufficiale.",
            "disclaimer": D.DISCLAIMER}


def verifica_requisiti(ricavi_anno_precedente: float | None = None,
                       spese_personale: float | None = None,
                       redditi_dipendente_o_pensione: float | None = None,
                       partecipazioni_societarie: bool = False,
                       controllo_srl_stessa_attivita: bool = False,
                       attivita_prevalente_verso_ex_datore: bool = False) -> dict:
    """Verifica i principali requisiti di accesso e permanenza nel regime forfettario."""
    esiti = []

    def aggiungi(nome, ok, dettaglio):
        esiti.append({"requisito": nome, "esito": "OK" if ok else "NON RISPETTATO",
                      "dettaglio": dettaglio})

    if ricavi_anno_precedente is not None:
        aggiungi("Ricavi anno precedente entro 85.000 euro",
                 ricavi_anno_precedente <= D.SOGLIA_RICAVI,
                 f"Dichiarati {ricavi_anno_precedente:,.0f} euro.".replace(",", "."))
    if spese_personale is not None:
        aggiungi("Spese per personale entro 20.000 euro",
                 spese_personale <= D.LIMITE_SPESE_PERSONALE,
                 f"Dichiarate {spese_personale:,.0f} euro.".replace(",", "."))
    if redditi_dipendente_o_pensione is not None:
        aggiungi("Redditi da lavoro dipendente o pensione entro 35.000 euro",
                 redditi_dipendente_o_pensione <= D.LIMITE_REDDITI_DIPENDENTE,
                 f"Dichiarati {redditi_dipendente_o_pensione:,.0f} euro. Il limite non si applica "
                 "se il rapporto di lavoro è cessato. Nel 2027 torna a 30.000 euro."
                 .replace(",", "."))
    aggiungi("Nessuna partecipazione in società di persone o associazioni professionali",
             not partecipazioni_societarie, "Dichiarazione dell'utente.")
    aggiungi("Nessun controllo di SRL con attività riconducibile",
             not controllo_srl_stessa_attivita, "Dichiarazione dell'utente.")
    aggiungi("Attività non prevalente verso l'ex datore di lavoro",
             not attivita_prevalente_verso_ex_datore, "Dichiarazione dell'utente.")

    problemi = [e for e in esiti if e["esito"] != "OK"]
    return {"esiti": esiti, "requisiti_non_rispettati": len(problemi),
            "conclusione": ("Nessuna criticità sui requisiti verificati." if not problemi else
                            "Sono emerse criticità: il regime forfettario potrebbe non essere "
                            "applicabile. Serve la verifica di un professionista."),
            "elenco_completo_requisiti": D.REQUISITI_ACCESSO,
            "prossimo_passo": D.CONTATTI["consulenza_gratuita"],
            "disclaimer": D.DISCLAIMER}


def richiedi_consulenza(argomento: str = "") -> dict:
    return {"prenotazione": D.CONTATTI["consulenza_gratuita"], "costo": "Gratuita",
            "email": D.CONTATTI["email"], "sito": D.CONTATTI["sito"],
            "argomento": argomento or None,
            "consiglio": "Prepara codice ATECO, ricavi incassati dell'anno e gestione "
                         "previdenziale: bastano per una prima valutazione."}
