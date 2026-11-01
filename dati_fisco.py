"""
TaxScan - dati fiscali del regime forfettario, anno d'imposta 2026.

FONTI (verificate il 23/09/2026):
- Coefficienti: Allegato 4 Legge 190/2014, invariati nel 2026 (DL 81/2025: si continuano
  ad applicare i coefficienti storici basati sulla classificazione ATECO 2007/2022).
- INPS artigiani e commercianti: Circolare INPS n. 14 del 09/02/2026.
- INPS gestione separata: Circolare INPS n. 8 del 03/02/2026.

>>> QUESTO E' L'UNICO FILE DA AGGIORNARE OGNI ANNO. <<<
"""

ANNO = 2026
ULTIMO_AGGIORNAMENTO = "2026-09-23"

# --- Soglie del regime ---
SOGLIA_RICAVI = 85_000          # oltre: si resta nel forfettario per l'anno in corso
SOGLIA_USCITA_IMMEDIATA = 100_000  # oltre: uscita immediata, con IVA dall'operazione che sfora
LIMITE_SPESE_PERSONALE = 20_000
LIMITE_REDDITI_DIPENDENTE = 35_000  # deroga 2026; dal 2027 torna a 30.000

# --- Imposta sostitutiva ---
ALIQUOTA_ORDINARIA = 0.15
ALIQUOTA_STARTUP = 0.05   # primi 5 anni di attività, se ricorrono i requisiti di legge

# --- INPS gestione separata (professionisti senza cassa) ---
GESTIONE_SEPARATA = {
    "aliquota_senza_altra_copertura": 0.2607,   # 25% IVS + 0,72% + 0,35% ISCRO
    "aliquota_pensionati_o_altra_cassa": 0.24,
    "massimale": 122_295,
    "nota": "Nessun contributo minimo: si paga in percentuale sul reddito forfettario.",
}

# --- INPS artigiani e commercianti ---
ARTIGIANI_COMMERCIANTI = {
    "minimale_reddito": 18_808,
    "soglia_aliquota_maggiorata": 56_224,
    "massimale_ante_1996": 93_707,
    "massimale_post_1996": 122_295,
    "riduzione_forfettari": 0.35,  # facoltativa: si chiede una volta (entro il 28/2, o subito dopo l'apertura) e resta finche' non si rinuncia
    # L. 207/2024 c. 186-187 (circ. INPS 83/2025): chi si iscrive per la prima volta nel 2025 paga il 50% della sola quota IVS
    # per 36 mesi dall'avvio; non si somma al 35% dei forfettari ne' alla riduzione dei pensionati over 65
    "riduzione_nuovi_iscritti": {"quota": 0.50, "anno_iscrizione": 2025, "mesi": 36},
    "riduzione_pensionati_65": 0.50,   # art. 59 c. 15 L. 449/1997: pensionati INPS con piu' di 65 anni, a domanda
    "maternita_mensile": 0.62,         # contributo di maternita' (non si riduce)
    "aliquota_non_ivs": {"artigiani": 0.0, "commercianti": 0.0048},  # indennizzo cessazione attivita' (non si riduce)
    "artigiani": {
        "fisso_annuo": 4_521.36,      # IVS sul minimale + maternità
        "aliquota": 0.24,
        "aliquota_oltre_soglia": 0.25,
    },
    "commercianti": {
        "fisso_annuo": 4_611.64,      # IVS + indennizzo cessazione + maternità
        "aliquota": 0.2448,
        "aliquota_oltre_soglia": 0.2548,
    },
}

# --- Coefficienti di redditività (Allegato 4 L. 190/2014) ---
# Ogni voce: (prefissi ATECO, coefficiente, descrizione del gruppo)
GRUPPI_COEFFICIENTE = [
    (["46.1"], 0.62, "Intermediari del commercio"),
    (["47.81"], 0.40, "Commercio ambulante di alimentari e bevande"),
    (["47.82", "47.89"], 0.54, "Commercio ambulante di altri prodotti"),
    (["10", "11"], 0.40, "Industrie alimentari e delle bevande"),
    (["45", "46", "47"], 0.40, "Commercio all'ingrosso e al dettaglio"),
    (["55", "56"], 0.40, "Servizi di alloggio e ristorazione"),
    (["41", "42", "43", "68"], 0.86, "Costruzioni e attività immobiliari"),
    (["64", "65", "66", "69", "70", "71", "72", "73", "74", "75", "85", "86", "87", "88"],
     0.78, "Attività professionali, scientifiche, tecniche, sanitarie, di istruzione, "
           "servizi finanziari e assicurativi"),
]
COEFFICIENTE_RESIDUALE = (0.67, "Altre attività economiche (comprese informatica e "
                                "telecomunicazioni, divisioni 58-63)")

# --- Scadenze fiscali ricorrenti ---
SCADENZE = [
    {"data": "16-02", "tipo": "contributi_inps", "descrizione":
     "4ª rata contributi fissi INPS artigiani/commercianti (anno precedente)",
     "gestioni": ["artigiani", "commercianti"]},
    {"data": "28-02", "tipo": "adempimento", "descrizione":
     "Termine per domanda o rinuncia alla riduzione contributiva del 35% (forfettari)",
     "gestioni": ["artigiani", "commercianti"]},
    {"data": "18-05", "tipo": "contributi_inps", "descrizione":
     "1ª rata contributi fissi INPS artigiani/commercianti",
     "gestioni": ["artigiani", "commercianti"]},
    {"data": "30-06", "tipo": "imposte", "descrizione":
     "Saldo imposta sostitutiva anno precedente + 1° acconto anno in corso; "
     "saldo e 1° acconto contributi INPS eccedenti il minimale",
     "gestioni": ["separata", "artigiani", "commercianti", "cassa"]},
    {"data": "20-08", "tipo": "contributi_inps", "descrizione":
     "2ª rata contributi fissi INPS artigiani/commercianti",
     "gestioni": ["artigiani", "commercianti"]},
    {"data": "30-11", "tipo": "imposte", "descrizione":
     "2° acconto imposta sostitutiva + 2° acconto contributi INPS eccedenti il minimale",
     "gestioni": ["separata", "artigiani", "commercianti", "cassa"]},
    {"data": "16-11", "tipo": "contributi_inps", "descrizione":
     "3ª rata contributi fissi INPS artigiani/commercianti",
     "gestioni": ["artigiani", "commercianti"]},
]

REQUISITI_ACCESSO = [
    "Ricavi o compensi dell'anno precedente non superiori a 85.000 euro",
    "Spese per lavoro dipendente e collaboratori non superiori a 20.000 euro lordi",
    "Redditi da lavoro dipendente o pensione dell'anno precedente non superiori a 35.000 euro "
    "(limite non applicabile se il rapporto di lavoro è cessato)",
    "Nessuna partecipazione in società di persone, associazioni professionali o imprese familiari",
    "Nessun controllo, diretto o indiretto, di SRL che svolgono attività riconducibili a quella "
    "della partita IVA",
    "Attività non prevalentemente rivolta verso l'ex datore di lavoro dei due anni precedenti "
    "(o suoi soggetti collegati)",
    "Residenza fiscale in Italia, oppure in UE/SEE con almeno il 75% del reddito prodotto in Italia",
]

DISCLAIMER = (
    "Stima automatica basata sui parametri 2026, a fini informativi e di pianificazione. "
    "Non sostituisce il parere di un professionista abilitato e non costituisce dichiarazione "
    "fiscale. Il calcolo definitivo dipende da elementi non considerati qui (altri redditi, "
    "detrazioni, acconti già versati, regimi particolari). "
    "Parametri aggiornati al " + ULTIMO_AGGIORNAMENTO + "."
)

CONTATTI = {
    "consulenza_gratuita": "https://calendly.com/ltd24ore?utm_source=taxscan",
    "email": "info@ltd24ore.com",
    "sito": "https://ltd24.co.uk/?utm_source=taxscan",
}


# --- Come ragiona TaxScan sui contributi (lo legge l'assistente IA: aggiornare con le regole dell'anno) ---
RAGIONAMENTO_CONTRIBUTI = (
    "Sui contributi previdenziali ragiona come un commercialista: i contributi spesso pesano piu' dell'imposta, quindi chiediti sempre "
    "se la persona puo' pagarne di meno in modo legale, e se la stima e' giusta per la sua situazione. Le domande da farti: "
    "1) Anno di apertura: per artigiani e commercianti i contributi fissi si pagano solo per i mesi di attivita' (chi apre ad agosto "
    "paga 5 mesi su 12); se non conosci il mese, chiedilo. "
    "2) Artigiani e commercianti forfettari: riduzione del 35% di fissi e percentuali, si chiede una volta all'INPS (entro il 28 febbraio, "
    "o subito dopo l'apertura) e resta finche' non si rinuncia; riduce anche l'accredito per la pensione. "
    "3) Chi si e' iscritto per la prima volta alla gestione artigiani o commercianti nel 2025: 50% in meno sulla quota IVS per 36 mesi "
    "dall'avvio, non cumulabile con il 35% (di solito conviene di piu'). "
    "4) Pensionati INPS con piu' di 65 anni iscritti come artigiani o commercianti: possono chiedere il 50% in meno. "
    "5) Chi ha anche un lavoro dipendente prevalente e apre un'attivita' commerciale: l'iscrizione alla gestione commercianti spesso "
    "non e' dovuta (manca la prevalenza), da verificare con un professionista. "
    "6) Gestione separata: niente minimo, si paga in percentuale; aliquota 26,07%, ma 24% se la persona ha gia' un'altra copertura "
    "obbligatoria (lavoro dipendente, pensione). Si puo' addebitare al cliente una rivalsa INPS del 4% in fattura. "
    "7) I contributi si deducono dal reddito forfettario per cassa, nell'anno in cui si pagano; la parte che supera il reddito "
    "forfettario si deduce dagli altri redditi IRPEF (lavoro dipendente, pensione). "
    "8) Casse professionali: spesso riducono i minimi per i giovani o i nuovi iscritti nei primi anni; il contributo integrativo "
    "si addebita al cliente. "
    "9) Il fondo pensione si deduce solo da altri redditi IRPEF, non dal reddito forfettario. "
    "Collega sempre i dati tra loro (data di apertura, gestione, altri redditi, eta' se nota, incassi) e, se un dato che cambierebbe "
    "il calcolo manca, fai una domanda precisa invece di supporre. Ogni riduzione dei contributi riduce anche la pensione futura: dillo. "
    "Sono stime: le riduzioni vanno sempre verificate con l'INPS o con la propria cassa."
)
