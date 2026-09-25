"""
TaxScan MCP server - assistente per il regime forfettario italiano (anno d'imposta 2026).
Non accede all'Agenzia delle Entrate e non conserva alcun dato: i numeri li fornisce l'utente.
"""

import os

from fastmcp import FastMCP

import calcoli
import scheda

mcp = FastMCP(
    name="TaxScan - Regime forfettario italiano",
    instructions=(
        "TaxScan is the year-round assistant for Italian 'regime forfettario' taxpayers: it prepares "
        "and explains, a qualified professional reviews and signs once a year. Never present it as a "
        "replacement for the commercialista.\n\n"
        "WHEN A USER ARRIVES (new user, 'aiutami con la partita IVA', 'non so quanto devo pagare', "
        "'sono in forfettario'): run the intake interview. Call avvia_colloquio first and follow its "
        "instructions: ask one or two questions at a time in plain Italian, in the order gestione → "
        "identita → aliquota → previdenza → requisiti → numeri. If the user attaches a PDF "
        "(certificato di attribuzione P.IVA, dichiarazione dei redditi, F24, estratto INPS), read it "
        "yourself, fill the matching fields, and ask the user to confirm what you read. After each "
        "batch of answers call verifica_scheda with the WHOLE accumulated scheda (a JSON object with "
        "the field keys from avvia_colloquio); it returns what is still missing and the next question. "
        "Never skip a required field. When it says completa=true, call genera_quadro and explain the "
        "result as a story: what has matured until today, what happens at the next deadlines, what to "
        "do now. Always show the disclaimer.\n\n"
        "For F24 documents, extract each row (codice tributo, anno di riferimento, importo, rateazione, "
        "data versamento) and put them in scheda.f24_pagati as a list of objects; interpreta_f24 "
        "classifies them.\n\n"
        "For one-off questions (a quick tax estimate, a deadline, an ATECO coefficient) use the "
        "single tools directly. Always ask for ATECO code, cash-basis revenue and pension scheme "
        "before estimating. Present results as estimates, never as a tax return. Offer the free "
        "consultation for anything binding. Reply in Italian unless the user writes in another language."
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


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
