"""
TaxScan MCP server - assistente per il regime forfettario italiano (anno d'imposta 2026).
Non accede all'Agenzia delle Entrate e non conserva alcun dato: i numeri li fornisce l'utente.
"""

import os
from datetime import date

from fastmcp import FastMCP

import calcoli
import calendario
import db
import fic
import scheda

mcp = FastMCP(
    name="TaxScan - Regime forfettario italiano",
    instructions=(
        "TaxScan is the year-round assistant for Italian 'regime forfettario' taxpayers: it prepares "
        "and explains, a qualified professional reviews and signs once a year. Never present it as a "
        "replacement for the commercialista.\n\n"
        "WHEN A USER ARRIVES (new user, 'aiutami con la partita IVA', 'non so quanto devo pagare', "
        "'sono in forfettario'): first ask for their email (needed to save and retrieve their scheda "
        "between conversations - explain this is not a real login, just a lookup key for now) and call "
        "carica_scheda_salvata. If it finds a saved scheda, summarize what you already know in one or "
        "two lines and ask the user to confirm or correct it, instead of re-running the full interview. "
        "If nothing is found, call avvia_colloquio and follow its instructions: ask one or two questions "
        "at a time in plain Italian, in the order gestione → identita → aliquota → previdenza → "
        "requisiti → numeri. If the user attaches a PDF (certificato di attribuzione P.IVA, "
        "dichiarazione dei redditi, F24, estratto INPS), read it yourself, fill the matching fields, "
        "and ask the user to confirm what you read. After each batch of answers call verifica_scheda "
        "with the WHOLE accumulated scheda (a JSON object with the field keys from avvia_colloquio); "
        "it returns what is still missing and the next question. Never skip a required field. When it "
        "says completa=true, call salva_scheda_utente to persist it, then call genera_quadro and "
        "explain the result as a story: what has matured until today, what happens at the next "
        "deadlines, what to do now. Then call piano_pagamenti and give them the month-by-month plan: "
        "it answers the single most common pain, knowing what to set aside and when. Finally offer "
        "calendario_scadenze so the deadlines and monthly set-aside reminders land in their phone. "
        "Always show the disclaimer. Whenever the user gives new information that changes their saved "
        "scheda (new revenue, a new F24, a changed field), call salva_scheda_utente again with the "
        "updated scheda.\n\n"
        "For F24 documents, extract each row (codice tributo, anno di riferimento, importo, rateazione, "
        "data versamento) and put them in scheda.f24_pagati as a list of objects; interpreta_f24 "
        "classifies them.\n\n"
        "For one-off questions (a quick tax estimate, a deadline, an ATECO coefficient) use the "
        "single tools directly. Always ask for ATECO code, cash-basis revenue and pension scheme "
        "before estimating. Present results as estimates, never as a tax return. Offer the free "
        "consultation for anything binding.\n\n"
        "FATTURE IN CLOUD: if the user asks to connect, import or sync their invoices, or says they "
        "use Fatture in Cloud, call collega_fatture_in_cloud with their email, give them the link, "
        "and ask them to come back after authorizing. When they confirm, call importa_fatture_fic "
        "with their email and the year needed. If it returns multiple aziende to choose from, show "
        "the list and call seleziona_azienda_fic with their choice, then call importa_fatture_fic "
        "again. Once it returns an amount, show it to the user, ask them to confirm it looks right "
        "(it is a first pass, flag it as worth double-checking), and if they confirm, use it to fill "
        "ricavi_anno_precedente or ricavi_anno_corrente in their scheda instead of asking them to "
        "type it, then call salva_scheda_utente. Once Fatture in Cloud is connected, prefer "
        "monitora_soglia_85000_fic over monitora_soglia_85000 for any question about the 85k/100k "
        "threshold or year-end forecast - it reads the current revenue automatically instead of "
        "asking the user for it. Reply in Italian unless the user writes in another "
        "language."
    ),
)


@mcp.tool
def coefficiente_ateco(codice_ateco: str) -> dict:
    """Profitability coefficient (coefficiente di redditività) for a given Italian ATECO code.
    Accepts full or partial codes (e.g. '62.01.00', '4791', '69')."""
    return calcoli.coefficiente_da_ateco(codice_ateco)


@mcp.tool
def calcola_tasse_forfettario(
    ricavi_incassati: float,
    codice_ateco: str = "",
    coefficiente: float | None = None,
    gestione: str = "separata",
    nuova_attivita: bool = False,
    riduzione_35: bool = False,
    altra_copertura_previdenziale: bool = False,
    aliquota_cassa: float = 0.0,
    iscritto_ante_1996: bool = False,
    contributi_versati_nell_anno: float | None = None,
) -> dict:
    """Estimate income, INPS contributions and flat tax for an Italian forfettario taxpayer.
    ricavi_incassati: revenue actually collected in the year (cash basis).
    gestione: 'separata' (freelancers without a professional fund), 'artigiani', 'commercianti'
    or 'cassa' (professional fund - then pass aliquota_cassa, e.g. 0.16).
    nuova_attivita: true for the 5% rate in the first five years.
    riduzione_35: true if the 35% INPS discount for forfettari was granted (artigiani/commercianti).
    contributi_versati_nell_anno: contributions actually paid during the year, if known."""
    return calcoli.calcola_forfettario(
        ricavi_incassati, codice_ateco, coefficiente, gestione, None, nuova_attivita,
        riduzione_35, altra_copertura_previdenziale, aliquota_cassa, iscritto_ante_1996,
        contributi_versati_nell_anno)


@mcp.tool
def monitora_soglia_85000(ricavi_incassati_ytd: float, mese_di_riferimento: int | None = None,
                          crescita_mensile_attesa: float = 0.0) -> dict:
    """Forecast year-end revenue and assess the risk of crossing the 85,000 / 100,000 EUR
    thresholds of the Italian flat-rate scheme. crescita_mensile_attesa: expected monthly growth
    as a decimal (0.05 = +5% per month)."""
    return calcoli.monitora_soglia(ricavi_incassati_ytd, mese_di_riferimento,
                                   crescita_mensile_attesa)


@mcp.tool
def scadenze_fiscali(gestione: str = "separata", giorni: int = 120) -> dict:
    """Upcoming Italian tax and INPS deadlines for a forfettario taxpayer within the next N days.
    gestione: 'separata', 'artigiani', 'commercianti' or 'cassa'."""
    return calcoli.prossime_scadenze(gestione, giorni)


@mcp.tool
def verifica_requisiti_forfettario(
    ricavi_anno_precedente: float | None = None,
    spese_personale: float | None = None,
    redditi_dipendente_o_pensione: float | None = None,
    partecipazioni_societarie: bool = False,
    controllo_srl_stessa_attivita: bool = False,
    attivita_prevalente_verso_ex_datore: bool = False,
) -> dict:
    """Check the main eligibility requirements for the Italian flat-rate scheme (access and
    permanence), based on figures declared by the user."""
    return calcoli.verifica_requisiti(ricavi_anno_precedente, spese_personale,
                                      redditi_dipendente_o_pensione, partecipazioni_societarie,
                                      controllo_srl_stessa_attivita,
                                      attivita_prevalente_verso_ex_datore)


@mcp.tool
def prenota_consulenza(argomento: str = "") -> dict:
    """Link to book a free consultation with a qualified professional. Use it whenever the user
    needs binding advice, a tax return, or help with a threshold or eligibility problem."""
    return calcoli.richiedi_consulenza(argomento)


# ---------------------------------------------------------------- memoria (email come chiave)

@mcp.tool
def carica_scheda_salvata(email: str) -> dict:
    """Retrieve a previously saved scheda for this email, if any exists. Call this right after
    getting the user's email, before avvia_colloquio, so a returning user is not asked everything
    again. Not a real login: the email is only a lookup key for now."""
    try:
        trovata = db.carica_scheda(email)
    except Exception as e:
        return {"trovata": False, "errore": str(e)}
    if not trovata:
        return {"trovata": False}
    return {"trovata": True, "scheda": trovata}


@mcp.tool
def salva_scheda_utente(email: str, scheda_utente: dict) -> dict:
    """Save (or update) this user's scheda under their email, so a future conversation can retrieve
    it with carica_scheda_salvata. Call it once verifica_scheda says completa=true, and again
    whenever the user gives new information that changes the scheda."""
    try:
        db.salva_scheda(email, scheda_utente)
    except Exception as e:
        return {"salvata": False, "errore": str(e)}
    return {"salvata": True}


# ---------------------------------------------------------------- Fatture in Cloud

@mcp.tool
def collega_fatture_in_cloud(email: str) -> dict:
    """Generate a link to authorize TaxScan on the user's Fatture in Cloud account (read-only
    access to issued invoices). Give the user the link and ask them to come back once done."""
    try:
        link = fic.link_autorizzazione(email)
    except Exception as e:
        return {"errore": str(e)}
    return {
        "link": link,
        "istruzioni": "Apri il link, accedi a Fatture in Cloud se richiesto, e autorizza "
                      "l'accesso in sola lettura alle fatture emesse. Poi torna qui e dimmelo.",
    }


def _accesso_fic_pronto(email: str):
    """Prepara token e company_id per leggere Fatture in Cloud. Restituisce (access_token,
    company_id, None) se tutto pronto, oppure (None, None, dict) con l'errore o la scelta
    azienda da mostrare all'utente."""
    try:
        access_token = fic.token_valido(email)
    except Exception as e:
        return None, None, {"errore": str(e)}
    if not access_token:
        return None, None, {"errore": "Nessun collegamento Fatture in Cloud trovato per questa "
                                       "email. Usa prima collega_fatture_in_cloud."}
    collegamento = db.carica_fic_token(email)
    if not collegamento.get("company_id"):
        try:
            aziende = fic.lista_aziende(access_token)
        except Exception as e:
            return None, None, {"errore": f"Non sono riuscito a leggere le aziende collegate: {e}"}
        if len(aziende) == 1:
            azienda = aziende[0]
            db.imposta_azienda_fic(email, azienda["id"], azienda.get("name", ""))
        elif len(aziende) > 1:
            return None, None, {"scegli_azienda": [{"id": a["id"], "nome": a.get("name", "")}
                                                     for a in aziende]}
        else:
            return None, None, {"errore": "Nessuna azienda trovata su questo account Fatture in Cloud."}
        collegamento = db.carica_fic_token(email)
    return access_token, collegamento["company_id"], None


@mcp.tool
def importa_fatture_fic(email: str, anno: int) -> dict:
    """Read invoices from the user's connected Fatture in Cloud account and estimate cash-basis
    revenue (ricavi incassati) for the given year. Call it after the user confirms they authorized
    the link from collega_fatture_in_cloud. If the account has more than one azienda, this returns
    the list instead of an amount - show it and call seleziona_azienda_fic with their choice, then
    call this again."""
    access_token, company_id, errore = _accesso_fic_pronto(email)
    if errore:
        return errore
    try:
        return fic.fatture_incassate_anno(access_token, company_id, anno)
    except Exception as e:
        return {"errore": f"Lettura fatture non riuscita: {e}"}


@mcp.tool
def monitora_soglia_85000_fic(email: str, crescita_mensile_attesa: float = 0.0) -> dict:
    """Same as monitora_soglia_85000, but reads current-year cash-basis revenue automatically
    from the user's connected Fatture in Cloud account instead of asking them for the figure.
    Requires a working collega_fatture_in_cloud connection. Use this whenever the user has
    Fatture in Cloud connected and asks about the 85k/100k threshold, or when checking in on
    their situation proactively."""
    access_token, company_id, errore = _accesso_fic_pronto(email)
    if errore:
        return errore
    anno_corrente = date.today().year
    try:
        lettura = fic.fatture_incassate_anno(access_token, company_id, anno_corrente)
    except Exception as e:
        return {"errore": f"Lettura fatture non riuscita: {e}"}
    esito = calcoli.monitora_soglia(lettura["ricavi_incassati_stimati"], None,
                                     crescita_mensile_attesa)
    esito["ricavi_incassati_letti_da_fic"] = lettura["ricavi_incassati_stimati"]
    esito["fatture_esaminate"] = lettura["fatture_esaminate"]
    esito["anno"] = anno_corrente
    return esito


@mcp.tool
def seleziona_azienda_fic(email: str, company_id: int, nome_azienda: str = "") -> dict:
    """Set which Fatture in Cloud azienda to use for this email, after importa_fatture_fic
    returned a choice between multiple aziende."""
    try:
        db.imposta_azienda_fic(email, company_id, nome_azienda)
    except Exception as e:
        return {"impostata": False, "errore": str(e)}
    return {"impostata": True}


# ---------------------------------------------------------------- colloquio iniziale

@mcp.tool
def avvia_colloquio() -> dict:
    """START HERE for any new user. Returns the interview instructions, the empty 'scheda' (profile)
    with all field keys, and the first question to ask. Call it once at the beginning."""
    return scheda.avvia_colloquio()


@mcp.tool
def verifica_scheda(scheda_utente: dict) -> dict:
    """Validate the accumulated interview profile. Pass the WHOLE scheda (all fields collected so far,
    keys from avvia_colloquio). Returns the normalized scheda, whether it is complete, the list of
    missing required fields, the next question to ask and where the user can find that information."""
    return scheda.verifica_scheda(scheda_utente)


@mcp.tool
def interpreta_f24(righe: list[dict], data_versamento: str = "") -> dict:
    """Classify F24 rows by 'codice tributo' (1790/1791/1792 imposta sostitutiva, AF/AP artigiani,
    CF/CP commercianti, PXX/P10/P11 gestione separata, 1668/1944/8944 interessi e sanzioni...).
    righe: [{"codice_tributo": "1792", "anno_riferimento": 2025, "importo": 1234.56,
             "rateazione": "0101", "data_versamento": "2026-06-30"}].
    Returns what each payment was for, totals by category, and a plain-language explanation."""
    return scheda.interpreta_f24(righe, data_versamento)


@mcp.tool
def genera_quadro(scheda_utente: dict) -> dict:
    """Generate the full picture once verifica_scheda says the profile is complete: what has matured
    until today (saldo/acconti explained year by year, first-year and second-year traps), estimates
    for last year and this year, share of each invoice to set aside, comparison with F24 already
    paid, warnings (5% eligibility, cause ostative, 35,000 EUR employee-income limit, INPS 35%
    discount), upcoming deadlines and a to-do list. Always show its disclaimer."""
    return scheda.genera_quadro(scheda_utente)


@mcp.tool
def piano_pagamenti(scheda_utente: dict, accantonamento_attuale: float = 0.0) -> dict:
    """Month-by-month payment plan built from a completed scheda: which deadlines are coming with their
    estimated amounts and codici tributo, how much to set aside each month to arrive covered, the share of
    each invoice to put away, whether the user would end up short, and any credit arising from overpaid
    acconti. Use it right after genera_quadro, or whenever the user asks 'quanto devo mettere da parte',
    'quando pago', 'come mi organizzo con le scadenze'. accantonamento_attuale: money already set aside."""
    return scheda.piano_pagamenti(scheda_utente, "", accantonamento_attuale)


@mcp.tool
def calendario_scadenze(scheda_utente: dict, accantonamento_attuale: float = 0.0,
                        includi_accantonamento_mensile: bool = True) -> dict:
    """Give the user a link that adds all their tax deadlines to the phone calendar (.ics): each
    payment with amount and codici tributo, reminders 30/7/1 days before, plus a monthly 'set aside
    X EUR' reminder on the 1st. Built from a completed scheda. Use it after piano_pagamenti, or when
    the user asks for reminders, 'avvisami', 'mettimelo in calendario'. Show the link and the
    one-line instructions for their device."""
    piano = scheda.piano_pagamenti(scheda_utente, "", accantonamento_attuale)
    if "errore" in piano:
        return piano
    eventi = calendario.eventi_dal_piano(piano, includi_accantonamento_mensile)
    if not eventi:
        return {"errore": "Nessuna scadenza da mettere in calendario con i dati forniti."}
    return calendario.link_calendario(eventi)


@mcp.custom_route("/c/{id_breve}", methods=["GET"])
async def calendario_ics(request):
    """Serve il file .ics per l'id breve generato da calendario_scadenze."""
    from starlette.responses import PlainTextResponse
    id_breve = request.path_params.get("id_breve", "")
    try:
        eventi = calendario.eventi_da_id(id_breve)
    except Exception:
        return PlainTextResponse(
            "Link scaduto o non valido: torna su TaxScan e chiedi di nuovo il calendario.",
            status_code=400)
    ics = calendario.genera_ics(eventi)
    # application/octet-stream (non text/calendar) fa scaricare il file invece di farlo aprire
    # da Safari come "abbonamento calendario": l'utente lo apre poi dai download per l'aggiunta
    # una tantum degli eventi, invece dell'iscrizione live che su iOS spesso fallisce la verifica.
    return PlainTextResponse(ics, media_type="application/octet-stream",
                             headers={"Content-Disposition": 'attachment; filename="taxscan-scadenze.ics"',
                                      "Cache-Control": "no-store"})


@mcp.custom_route("/oauth/fic/callback", methods=["GET"])
async def fic_callback(request):
    """Riceve l'utente dopo l'autorizzazione su Fatture in Cloud, scambia il codice con i token
    e li salva. Pagina semplice: l'utente poi torna nella conversazione con Claude."""
    from starlette.responses import HTMLResponse

    def pagina(titolo, messaggio, ok=True):
        colore = "#0f4c3a" if ok else "#8a1f1f"
        return HTMLResponse(
            f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{titolo}</title></head>"
            f"<body style='font-family:sans-serif;max-width:480px;margin:60px auto;padding:0 20px;"
            f"color:#1a1a1a'><h2 style='color:{colore}'>{titolo}</h2><p>{messaggio}</p></body></html>",
            status_code=200 if ok else 400,
        )

    errore = request.query_params.get("error")
    if errore:
        return pagina("Autorizzazione annullata",
                       "Non hai completato l'autorizzazione su Fatture in Cloud. Torna su TaxScan "
                       "e chiedi di nuovo il link se vuoi riprovare.", ok=False)

    state = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    email = fic.email_da_state(state)
    if not email or not code:
        return pagina("Link scaduto o non valido",
                       "Torna su TaxScan e chiedi di nuovo il collegamento a Fatture in Cloud.", ok=False)
    try:
        fic.scambia_codice(email, code)
    except Exception as e:
        return pagina("Collegamento non riuscito", f"Errore: {e}. Riprova tra poco.", ok=False)
    return pagina("Fatture in Cloud collegato",
                  "Ora puoi tornare nella conversazione con TaxScan e dire che hai completato "
                  "l'autorizzazione.")


@mcp.custom_route("/", methods=["GET", "HEAD"])
async def home(request):
    from starlette.responses import PlainTextResponse
    return PlainTextResponse("TaxScan MCP server attivo. Endpoint MCP: /mcp")


if __name__ == "__main__":
    try:
        db.inizializza()
    except Exception as e:
        # Non blocca l'avvio: senza database il server funziona lo stesso, solo senza
        # salvare/ritrovare le schede (carica_scheda_salvata e salva_scheda_utente lo
        # segnaleranno riga per riga quando chiamati).
        print(f"Attenzione: inizializzazione database fallita ({e}). Il server parte comunque.")
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
