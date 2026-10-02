"""
TaxScan - ricerca di bandi e finanza agevolata (nazionale, regionale, locale).

Il server NON naviga il web e non pretende di sapere quali bandi sono aperti oggi: cambiano
ogni settimana. Fa il lavoro che sa fare bene:
  1. capisce DOVE si trova l'utente (provincia -> regione) e che profilo ha (settore, anni di
     attivita', eventuale fascia giovani/donne, Sud si/no);
  2. prepara le ricerche giuste (in italiano, per regione, settore, comune, camera di commercio);
  3. indica le fonti ufficiali dove i bandi si pubblicano davvero;
  4. aggiunge la lista curata a mano (incentivi_settore), filtrata per settore, regione e scadenza.
Poi e' l'assistente a fare le ricerche sul web con quelle query e a presentare i risultati come
"cose da verificare", mai come diritti o certezze.
"""

from datetime import date

import db
import scheda as S

# ---------------------------------------------------------------- province -> regione
_PROVINCE = {
    "Piemonte": "AL AT BI CN NO TO VB VC",
    "Valle d'Aosta": "AO",
    "Lombardia": "BG BS CO CR LC LO MB MI MN PV SO VA",
    "Trentino-Alto Adige": "BZ TN",
    "Veneto": "BL PD RO TV VE VI VR",
    "Friuli-Venezia Giulia": "GO PN TS UD",
    "Liguria": "GE IM SP SV",
    "Emilia-Romagna": "BO FC FE MO PC PR RA RE RN",
    "Toscana": "AR FI GR LI LU MS PI PO PT SI",
    "Umbria": "PG TR",
    "Marche": "AN AP FM MC PU",
    "Lazio": "FR LT RI RM VT",
    "Abruzzo": "AQ CH PE TE",
    "Molise": "CB IS",
    "Campania": "AV BN CE NA SA",
    "Puglia": "BA BR BT FG LE TA",
    "Basilicata": "MT PZ",
    "Calabria": "CS CZ KR RC VV",
    "Sicilia": "AG CL CT EN ME PA RG SR TP",
    "Sardegna": "CA NU OR SS SU",
}
PROVINCIA_A_REGIONE = {p: r for r, elenco in _PROVINCE.items() for p in elenco.split()}
REGIONI_SUD = {"Abruzzo", "Molise", "Campania", "Puglia", "Basilicata", "Calabria", "Sicilia", "Sardegna"}


def _norm(txt: str) -> str:
    return "".join(c for c in (txt or "").lower() if c.isalnum())


_REGIONE_DA_NOME = {_norm(r): r for r in _PROVINCE}
_REGIONE_DA_NOME.update({
    _norm("Trentino"): "Trentino-Alto Adige", _norm("Alto Adige"): "Trentino-Alto Adige",
    _norm("Friuli"): "Friuli-Venezia Giulia", _norm("Friuli Venezia Giulia"): "Friuli-Venezia Giulia",
    _norm("Valle d Aosta"): "Valle d'Aosta", _norm("Emilia Romagna"): "Emilia-Romagna",
})


def regione_da_dati(regione: str = "", provincia: str = "") -> str | None:
    """Regione normalizzata dal nome (anche scritto male) o, in mancanza, dalla sigla di provincia."""
    r = _REGIONE_DA_NOME.get(_norm(regione))
    if r:
        return r
    sigla = (provincia or "").strip().upper()
    return PROVINCIA_A_REGIONE.get(sigla)


# ---------------------------------------------------------------- profilo facoltativo
OPZIONI_PROFILO = [
    (1, "giovane", "Ho meno di 36 anni"),
    (2, "donna", "Sono una donna"),
    (3, "giovane_donna", "Entrambe le cose"),
    (4, "nessuno", "Nessuna delle due / preferisco non dirlo"),
]

DOMANDA_LUOGO = ("In che comune hai la sede dell'attività? Basta il nome del comune: i bandi cambiano molto "
                 "da regione a regione e da comune a comune.")
DOMANDA_PROFILO = ("Alcuni bandi sono riservati a giovani o a imprese femminili. Vuoi dirmelo? (facoltativo)\n"
                   + "\n".join(f"{n}) {e}" for n, _, e in OPZIONI_PROFILO))

FONTI_UFFICIALI = [
    {"nome": "Incentivi.gov.it", "url": "https://www.incentivi.gov.it",
     "cosa": "Portale nazionale degli incentivi alle imprese, con filtri per settore, regione e dimensione"},
    {"nome": "Invitalia", "url": "https://www.invitalia.it",
     "cosa": "Agevolazioni per nuove attività, autoimpiego, giovani, donne e imprese del Sud"},
    {"nome": "MIMIT - incentivi", "url": "https://www.mimit.gov.it/it/incentivi",
     "cosa": "Elenco ufficiale degli incentivi del Ministero delle Imprese e del Made in Italy"},
]

_ISTRUZIONI = [
    "Fai le ricerche web TU, con le query di ricerche_web (da 3 a 5 ricerche, non tutte), poi apri le pagine "
    "più promettenti (di preferenza le fonti ufficiali: enti pubblici, regione, camera di commercio, Invitalia, "
    "incentivi.gov.it) per leggere scadenza e requisiti. Non fidarti di siti che vendono consulenze o "
    "'trova bando' senza fonte ufficiale.",
    "Presenta al massimo 4 o 5 voci, le più pertinenti e ancora aperte o in apertura, ognuna in 3 righe: nome ed "
    "ente, cosa finanzia e chi può chiederlo, scadenza e link. Scarta ciò che è chiuso, scaduto o riservato a chi "
    "l'utente non è (grandi imprese, società, fasce di età diverse). Se non sei sicuro che un bando sia ancora "
    "aperto, dillo.",
    "Mai scrivere 'ti spetta' o 'puoi ottenere': scrivi 'da verificare'. L'ammissibilità dipende da requisiti che "
    "TaxScan non conosce del tutto (regole de minimis, ISEE, ATECO ammessi, spese da sostenere). Ricorda in una "
    "riga che con la partita IVA forfettaria alcune agevolazioni hanno limiti (es. crediti d'imposta inutili se "
    "non si pagano imposte ordinarie) e che prima di spendere soldi o presentare domanda conviene sentire il "
    "commercialista; offri la consulenza gratuita se la situazione è specifica.",
    "Le voci di incentivi_curati vengono da una lista verificata a mano: mettile per prime, con la stessa cautela.",
    "Se la ricerca web non è disponibile o non trova nulla di affidabile, dillo e dai le fonti_ufficiali con "
    "i filtri da usare (regione, settore): è meglio un 'non ho trovato nulla di sicuro' che un bando inventato.",
    "Finito, offri di ricordarlo: se l'utente ha già l'email registrata, i bandi curati nuovi gli arrivano "
    "con incentivi_non_letti alla prossima visita.",
]


def piano_ricerca(scheda_utente: dict, regione: str = "", provincia: str = "", comune: str = "",
                  profilo: str = "") -> dict:
    """Prepara la ricerca di agevolazioni: luogo, query, fonti, lista curata e istruzioni per l'assistente."""
    s = scheda_utente or {}
    comune = (comune or s.get("comune") or "").strip()
    provincia = (provincia or s.get("provincia") or "").strip().upper()
    regione_in = (regione or s.get("regione") or "").strip()
    profilo = (profilo or s.get("profilo_agevolazioni") or "").strip()
    reg = regione_da_dati(regione_in, provincia)

    codice = (s.get("codice_ateco") or "").strip()
    deduzione = S.deduci_da_ateco(codice) if codice else {}
    settore = (s.get("descrizione_attivita") or s.get("descrizione_attivita_certificato")
               or deduzione.get("descrizione") or "").strip().lower().replace("'", "")
    anno = date.today().year

    luogo = {"comune": comune or None, "provincia": provincia or None, "regione": reg,
             "area_sud": bool(reg and reg in REGIONI_SUD)}

    mancano = []
    if not reg:
        mancano.append({"campo": "luogo", "domanda": DOMANDA_LUOGO,
                        "come_usarla": "Deduci tu regione e sigla di provincia dal comune che risponde e richiama "
                                       "cerca_agevolazioni con regione, provincia e comune compilati."})
    if profilo not in {v for _, v, _ in OPZIONI_PROFILO}:
        mancano.append({"campo": "profilo_agevolazioni", "facoltativa": True, "domanda": DOMANDA_PROFILO,
                        "opzioni": [{"numero": n, "valore": v, "etichetta": e} for n, v, e in OPZIONI_PROFILO],
                        "come_usarla": "Chiedila una volta sola; se l'utente non vuole rispondere, vai avanti."})

    try:
        nuova = anno - int(s.get("anno_ingresso_forfettario")) <= 3
    except (TypeError, ValueError):
        nuova = False

    q = []
    q.append(f"agevolazioni contributi fondo perduto nuove partite IVA lavoratori autonomi {anno}")
    if reg:
        q.append(f"bandi Regione {reg} contributi microimprese lavoratori autonomi {anno}")
        if settore:
            q.append(f"bandi {reg} {settore} contributi {anno}")
    if settore and not reg:
        q.append(f"bandi contributi {settore} {anno}")
    if comune or provincia:
        luogo_txt = comune or provincia
        q.append(f"camera di commercio {luogo_txt} bandi contributi imprese {anno}")
        if comune:
            q.append(f"comune di {comune} bando contributi nuove attività autonomi {anno}")
    if luogo["area_sud"]:
        q.append(f"Resto al Sud autoimpiego requisiti {anno} Invitalia")
    if profilo in ("giovane", "giovane_donna"):
        q.append(f"agevolazioni giovani under 36 autoimpiego nuove imprese Invitalia {anno}")
    if profilo in ("donna", "giovane_donna"):
        q.append(f"incentivi imprenditoria femminile lavoratrici autonome {anno}")
    q.append(f"contributo acquisto attrezzature beni strumentali piccole imprese {anno} Nuova Sabatini")
    if nuova:
        q.append(f"bonus nuove attività autonome primi anni partita IVA contributi {anno}")

    curati = []
    try:
        curati = db.incentivi_per_profilo(codice, reg or "")
    except Exception:
        curati = []

    return {
        "luogo": luogo,
        "settore": settore or None,
        "mancano": mancano,
        "ricerche_web": q,
        "fonti_ufficiali": FONTI_UFFICIALI,
        "incentivi_curati": curati,
        "istruzioni_per_l_assistente": _ISTRUZIONI,
        "disclaimer": ("Elenco indicativo e non esaustivo: i bandi cambiano spesso e i requisiti vanno verificati "
                       "sul testo ufficiale. TaxScan non presenta domande e non garantisce l'ammissibilità; "
                       "prima di decidere, confronto con il tuo commercialista."),
    }
