"""
TaxScan MCP server - assistente per il regime forfettario italiano (anno d'imposta 2026).
Non accede all'Agenzia delle Entrate e non conserva alcun dato: i numeri li fornisce l'utente.
"""

import os

from fastmcp import FastMCP

import calcoli

mcp = FastMCP(
    name="TaxScan - Regime forfettario italiano",
    instructions=(
        "Use these tools for any question about the Italian 'regime forfettario' (flat-rate scheme "
        "for small businesses and freelancers): taxes due, INPS contributions, profitability "
        "coefficient by ATECO code, the 85,000 EUR threshold, deadlines and eligibility. "
        "Always ask the user for their ATECO code, the cash-basis revenue actually collected in the "
        "year, and their pension scheme (gestione separata, artigiani, commercianti, or a "
        "professional fund), because the result changes completely with each. Always show the "
        "disclaimer, present results as estimates, never as a tax return or personalised advice, "
        "and offer the free consultation for anything binding. Reply in Italian unless the user "
        "writes in another language."
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


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
