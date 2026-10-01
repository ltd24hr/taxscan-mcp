"""
TaxScan MCP server - assistente per il regime forfettario italiano (anno d'imposta 2026).
Non accede all'Agenzia delle Entrate e non conserva alcun dato: i numeri li fornisce l'utente.
"""

import os
from datetime import date

from fastmcp import FastMCP

import auth
import avvisi
import calcoli
import calendario
import colloquio_web
import db
import fic
import scheda

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")


def _evento(tipo: str, riferimento: str | None = None, dettaglio: dict | None = None) -> None:
    """Traccia l'uso (per capire dove la gente si ferma) senza mai rompere il flusso."""
    try:
        db.registra_evento(tipo, riferimento, dettaglio)
    except Exception:
        pass


def _avvisa_nuovo_iscritto(email: str, scheda_utente: dict) -> None:
    """Una riga di email all'operatore quando un utente salva la scheda per la prima volta."""
    if not ADMIN_EMAIL:
        return
    try:
        s = scheda_utente or {}
        righe = [f"<p>Nuovo iscritto su TaxScan: <b>{email}</b></p>", "<ul>"]
        for etichetta, chiave in (("Codice ATECO", "codice_ateco"), ("Apertura", "data_apertura"),
                                  ("Tipo", "tipo_attivita"), ("Previdenza", "gestione_previdenziale"),
                                  ("Comune", "comune"), ("Ricavi anno scorso", "ricavi_anno_precedente"),
                                  ("Ricavi quest'anno", "ricavi_anno_corrente")):
            if s.get(chiave) not in (None, ""):
                righe.append(f"<li>{etichetta}: {s.get(chiave)}</li>")
        righe.append("</ul>")
        auth.manda_email(ADMIN_EMAIL, f"TaxScan: nuovo iscritto {email}", "".join(righe))
    except Exception as e:
        print(f"avviso nuovo iscritto non mandato: {e}")


mcp = FastMCP(
    name="TaxScan - Regime forfettario italiano",
    instructions=(
        "TaxScan is the year-round assistant for Italian 'regime forfettario' taxpayers: it prepares "
        "and explains, a qualified professional reviews and signs once a year. Never present it as a "
        "replacement for the commercialista.\n\n"
        "STYLE: TaxScan does, it does not interrogate. Most users know almost nothing about taxes and "
        "get annoyed by questions. So: read from documents first, deduce what can be deduced and ask "
        "to confirm it, ask the rest as NUMBERED OPTIONS (the user answers '2'), and use free text "
        "only for amounts or 'altro'. One question per message, short messages, no jargon. Never ask "
        "for something you could read from an attached document or deduce from what you already "
        "have.\n\n"
        "WHEN A USER ARRIVES (new user, 'aiutami con la partita IVA', 'non so quanto devo pagare', "
        "'sono in forfettario'): do NOT ask for the email. Call avvia_colloquio first and show, in one "
        "short message, its testo_pronto (three numbered options: attach the certificato / answer a "
        "couple of questions / resume a previous session) AND its link_colloquio_web: 'oppure "
        "rispondi da questa pagina con i pulsanti, più comoda da telefono: <link>'. If the user goes "
        "to the page and comes back ('ho finito', 'fatto', 'compilato'), call leggi_colloquio_web "
        "with the id_colloquio_web and continue from what it returns: if completa, go straight to "
        "genera_quadro; if stato is da_completare_in_chat, propose the ATECO code from "
        "descrizione_attivita, confirm it, and go on with verifica_scheda. Otherwise follow "
        "avvia_colloquio's istruzioni_per_l_assistente exactly: after "
        "every answer call verifica_scheda with the WHOLE accumulated scheda, and show the "
        "testo_pronto it returns (the next question already written with its numbered options). "
        "Store the option's 'valore' in the scheda, never the number. When it returns "
        "proposta_deduzioni, that is the one confirmation step ('Ho capito così... Giusto?'). If the "
        "user picks 'riprendo' (resume), do the LOGIN below, then call carica_scheda_salvata, "
        "avvisi_non_letti and incentivi_non_letti, summarize in two lines what you already know and "
        "ask the user to confirm or correct, instead of re-running the interview. When "
        "verifica_scheda says completa=true, call genera_quadro and explain the result as a story: "
        "what has matured until today, what happens at the next deadlines, what to do now. Then "
        "call piano_pagamenti and give the month-by-month plan: it answers the single most common "
        "pain, knowing what to set aside and when. Always show the disclaimer.\n\n"
        "AFTER THE QUADRO, and only then, ask for the email with a reason: 'vuoi che ricordi tutto "
        "questo per la prossima volta e ti avvisi delle scadenze? Dammi la tua email'. If they "
        "agree, do the LOGIN, call salva_scheda_utente, then avvisi_non_letti and incentivi_non_letti "
        "(with their codice_ateco): if either returns something, mention it briefly, in plain "
        "language - for incentives always add that it's worth confirming with their commercialista "
        "before relying on it (the list is curated, not official guidance); mention once that they "
        "can ask to stop receiving avvisi (disattiva_avvisi_normativi). Then offer "
        "calendario_scadenze so deadlines and monthly set-aside reminders land in their phone, and, "
        "if they feel like it, the optional 'gestione_attuale' question (once). Whenever the user "
        "later gives new information that changes a saved scheda (new revenue, a new F24, a changed "
        "field), call salva_scheda_utente again with the updated scheda.\n\n"
        "LOGIN: tools marked (richiede token_sessione) need a valid session. Ask for the email, call "
        "verifica_email(email): it sends a 6-digit code. Ask the user for the code (tell them to "
        "check spam too), then call conferma_codice(email, codice); on success it returns a "
        "token_sessione valid 24 hours. Keep it in this conversation and pass it to every tool that "
        "needs it. If a tool returns a session error (expired or never verified), repeat this flow "
        "once and retry. Never call a token_sessione-gated tool with a made-up or "
        "remembered-from-elsewhere token. Login is needed only to: resume a saved scheda, save one, "
        "connect Fatture in Cloud, read avvisi/incentivi. If the user chooses Fatture in Cloud during "
        "the interview, explain in one line that connecting it needs the email verified, and do the "
        "login then.\n\n"
        "For F24 documents, extract each row (codice tributo, anno di riferimento, importo, rateazione, "
        "data versamento) and put them in scheda.f24_pagati as a list of objects; interpreta_f24 "
        "classifies them.\n\n"
        "For one-off questions (a quick tax estimate, a deadline, an ATECO coefficient) use the "
        "single tools directly. Always ask for ATECO code, cash-basis revenue and pension scheme "
        "before estimating. Present results as estimates, never as a tax return. Offer the free "
        "consultation for anything binding.\n\n"
        "FATTURE IN CLOUD (needs a valid token_sessione, see LOGIN above): if the user asks to "
        "connect, import or sync their invoices, or says they "
        "use Fatture in Cloud, call collega_fatture_in_cloud with their email, give them the link, "
        "and ask them to come back after authorizing. When they confirm, call importa_fatture_fic "
        "with their email and the year needed - and if the scheda already has a value for that year "
        "(ricavi_anno_precedente or ricavi_anno_corrente, from a manual answer, an F24 or an earlier "
        "import), pass it as ricavo_gia_in_scheda so you get a 'confronto' back instead of a bare "
        "number. If it returns multiple aziende to choose from, show the list and call "
        "seleziona_azienda_fic with their choice, then call importa_fatture_fic again. If the result "
        "has no 'confronto' (nothing was in the scheda yet) or confronto.corrispondono is true, show "
        "the amount, ask the user to confirm it looks right (it is a first pass, flag it as worth "
        "double-checking), and if they confirm, fill ricavi_anno_precedente or ricavi_anno_corrente "
        "with it. If confronto.corrispondono is false, do NOT silently overwrite either value: show "
        "both numbers and the confronto.messaggio, and ask the user which one is right (or whether "
        "something is missing on one side) before touching the scheda. Either way, once the user has "
        "settled on a value, call salva_scheda_utente. Once Fatture in Cloud is connected, prefer "
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


# ---------------------------------------------------------------- login (codice via email)

@mcp.tool
def verifica_email(email: str) -> dict:
    """Send a 6-digit verification code to this email via Resend. Call it whenever the user gives
    an email and there is no valid session yet (start of conversation, or after a session-expired
    error from another tool). Tell the user to check their inbox (including spam) and give you the
    code, then call conferma_codice with it."""
    try:
        return auth.manda_codice(email)
    except Exception as e:
        return {"inviato": False, "errore": str(e)}


@mcp.tool
def conferma_codice(email: str, codice: str) -> dict:
    """Verify the 6-digit code the user received by email. On success, returns a token_sessione
    valid for 24 hours: keep it in this conversation and pass it as token_sessione to every other
    tool that requires one, for the rest of the conversation - the user does not need to verify
    again until it expires."""
    try:
        token = auth.verifica_codice(email, codice)
    except ValueError as e:
        return {"autenticato": False, "errore": str(e)}
    except Exception as e:
        return {"autenticato": False, "errore": str(e)}
    return {"autenticato": True, "token_sessione": token, "valido_ore": 24}


def _sessione_richiesta(email: str, token_sessione: str) -> dict | None:
    """None se la sessione è valida, altrimenti il dict di errore da restituire subito."""
    if not auth.email_autenticata(email, token_sessione):
        return {"errore": "Sessione non valida o scaduta. Chiedi all'utente l'email (se non ce "
                           "l'hai già), chiama verifica_email, fatti dare il codice ricevuto via "
                           "email e chiama conferma_codice per ottenere un nuovo token_sessione."}
    return None


# ---------------------------------------------------------------- memoria (email come chiave)

@mcp.tool
def carica_scheda_salvata(email: str, token_sessione: str) -> dict:
    """Retrieve a previously saved scheda for this email, if any exists. Requires a valid
    token_sessione from conferma_codice. Call it when the user chooses 'riprendo' at the start (or
    says they already used TaxScan), right after login, so they are not asked everything again."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    try:
        trovata = db.carica_scheda(email)
    except Exception as e:
        return {"trovata": False, "errore": str(e)}
    if not trovata:
        return {"trovata": False}
    return {"trovata": True, "scheda": trovata}


@mcp.tool
def salva_scheda_utente(email: str, scheda_utente: dict, token_sessione: str) -> dict:
    """Save (or update) this user's scheda under their email, so a future conversation can retrieve
    it with carica_scheda_salvata. Requires a valid token_sessione from conferma_codice. Call it
    once verifica_scheda says completa=true, and again whenever the user gives new information
    that changes the scheda."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    try:
        nuovo = db.salva_scheda(email, scheda_utente)
    except Exception as e:
        return {"salvata": False, "errore": str(e)}
    if nuovo:
        _evento("utente_registrato", email.strip().lower())
        _avvisa_nuovo_iscritto(email.strip().lower(), scheda_utente)
    return {"salvata": True}


# ---------------------------------------------------------------- Fatture in Cloud

@mcp.tool
def collega_fatture_in_cloud(email: str, token_sessione: str) -> dict:
    """Generate a link to authorize TaxScan on the user's Fatture in Cloud account (read-only
    access to issued invoices). Requires a valid token_sessione from conferma_codice. Give the
    user the link and ask them to come back once done."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
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
def importa_fatture_fic(email: str, anno: int, token_sessione: str,
                        ricavo_gia_in_scheda: float | None = None) -> dict:
    """Read invoices from the user's connected Fatture in Cloud account and estimate cash-basis
    revenue (ricavi incassati) for the given year. Requires a valid token_sessione from
    conferma_codice. Call it after the user confirms they authorized the link from
    collega_fatture_in_cloud. If the account has more than one azienda, this returns the list
    instead of an amount - show it and call seleziona_azienda_fic with their choice, then call
    this again.
    ricavo_gia_in_scheda: pass the current ricavi_anno_precedente or ricavi_anno_corrente value
    from the user's scheda, if one is already there (from a manual answer, an earlier import, or
    an F24). When given, the result includes a 'confronto' with the two values instead of just
    handing you a number to silently overwrite - a mismatch usually means a missing invoice or
    payment on one side, worth asking the user about rather than trusting either figure blindly."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    access_token, company_id, errore = _accesso_fic_pronto(email)
    if errore:
        return errore
    try:
        esito = fic.fatture_incassate_anno(access_token, company_id, anno)
    except Exception as e:
        return {"errore": f"Lettura fatture non riuscita: {e}"}
    if ricavo_gia_in_scheda is not None and "ricavi_incassati_stimati" in esito:
        esito["confronto"] = calcoli.confronta_ricavi(
            esito["ricavi_incassati_stimati"], ricavo_gia_in_scheda)
    return esito


@mcp.tool
def monitora_soglia_85000_fic(email: str, token_sessione: str,
                              crescita_mensile_attesa: float = 0.0) -> dict:
    """Same as monitora_soglia_85000, but reads current-year cash-basis revenue automatically
    from the user's connected Fatture in Cloud account instead of asking them for the figure.
    Requires a valid token_sessione from conferma_codice, and a working collega_fatture_in_cloud
    connection. Use this whenever the user has Fatture in Cloud connected and asks about the
    85k/100k threshold, or when checking in on their situation proactively."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
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
def seleziona_azienda_fic(email: str, company_id: int, token_sessione: str,
                          nome_azienda: str = "") -> dict:
    """Set which Fatture in Cloud azienda to use for this email, after importa_fatture_fic
    returned a choice between multiple aziende. Requires a valid token_sessione from
    conferma_codice."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    try:
        db.imposta_azienda_fic(email, company_id, nome_azienda)
    except Exception as e:
        return {"impostata": False, "errore": str(e)}
    return {"impostata": True}


# ---------------------------------------------------------------- colloquio iniziale

@mcp.tool
def avvia_colloquio() -> dict:
    """START HERE for any user, before any login. Returns the interview instructions, the empty
    'scheda' (profile) with all field keys, the opening question already written with its three
    numbered options (testo_pronto): attach the certificato / answer a couple of questions / resume
    a previous session - AND a link_colloquio_web: a web page where the user answers the same
    questions by tapping buttons and can upload the certificato. Offer both in the first message:
    'puoi rispondere qui, oppure da questa pagina con i pulsanti (più comodo da telefono): <link>'.
    If the user goes to the page and comes back ('ho finito', 'fatto'), call leggi_colloquio_web
    with the id_colloquio_web returned here. Call this tool once at the beginning."""
    esito = scheda.avvia_colloquio()
    try:
        web = colloquio_web.crea_colloquio()
        esito["link_colloquio_web"] = web["link"]
        esito["id_colloquio_web"] = web["id_colloquio"]
        _evento("chat_avvio", web["id_colloquio"])
    except Exception as e:
        esito["link_colloquio_web"] = None
        esito["nota_web"] = f"Pagina web non disponibile al momento ({e}): prosegui in chat."
    return esito


@mcp.tool
def leggi_colloquio_web(id_colloquio: str) -> dict:
    """Read the answers the user gave on the web page (link from avvia_colloquio) when they come
    back to the chat. Returns stato ('aperto' = not finished yet, 'completato', or
    'da_completare_in_chat' = they described their activity but don't know the ATECO code: propose
    the code yourself from descrizione_attivita and confirm it), the scheda, and the same output as
    verifica_scheda (completa, testo_pronto for anything still missing). If completa, go straight
    to genera_quadro. If usa_fatture_in_cloud is 'si', the amounts they typed are approximate:
    offer to connect Fatture in Cloud (needs login) and re-read them."""
    try:
        esito = colloquio_web.stato_colloquio(id_colloquio)
    except Exception as e:
        return {"errore": str(e)}
    if esito is None:
        return {"errore": "id_colloquio non trovato"}
    _evento("chat_letto_web", id_colloquio, {"stato": esito.get("stato")})
    return esito


@mcp.tool
def verifica_scheda(scheda_utente: dict) -> dict:
    """Validate the accumulated interview profile and get the NEXT question ready to show. Pass the
    WHOLE scheda (all fields collected so far, keys from avvia_colloquio; for option questions store
    the option's 'valore', for situazioni_particolari a list of valori). Returns the normalized scheda
    (pass this one back next time: it also contains what was deduced), completa, campi_mancanti,
    and testo_pronto - the next question with its numbered options, to show verbatim. When it
    returns proposta_deduzioni it is the confirmation step: on 'sì' set conferma_deduzioni=true; on
    'no' show opzioni_correzione for the field to fix, set the chosen valore, then
    conferma_deduzioni=true. Reads from documents always beat questions: fill what you read, then
    call this."""
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
    esito = scheda.genera_quadro(scheda_utente)
    if "errore" not in esito:
        _evento("chat_quadro", None, {"codice_ateco": (scheda_utente or {}).get("codice_ateco")})
    return esito


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


# ---------------------------------------------------------------- avvisi normativi

@mcp.tool
def avvisi_non_letti(email: str, token_sessione: str) -> dict:
    """Check for regulatory-change avvisi already emailed to this user but not yet mentioned in
    a conversation. Requires a valid token_sessione. Call it right after carica_scheda_salvata,
    every time a user arrives - if it returns any, tell the user briefly before anything else."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    lista = db.avvisi_da_menzionare(email)
    if lista:
        db.segna_avvisi_menzionati(email)
    return {"avvisi": lista}


@mcp.tool
def disattiva_avvisi_normativi(email: str, token_sessione: str) -> dict:
    """Opt this user out of future regulatory-change emails. Requires a valid token_sessione.
    Call it when the user asks to stop receiving these."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    db.disattiva_avvisi(email)
    return {"disattivato": True}


# ---------------------------------------------------------------- incentivi di settore

@mcp.tool
def incentivi_non_letti(email: str, token_sessione: str, codice_ateco: str) -> dict:
    """Check for sector-specific tax incentives/detrazioni the user hasn't been told about yet,
    matching their ATECO code (e.g. a tax credit on machinery for a given trade). This is a
    curated list (no automatic scraping), so matches are deliberately conservative. Requires a
    valid token_sessione. Call it right after carica_scheda_salvata/avvisi_non_letti whenever you
    know the user's codice_ateco (from their saved scheda or the current conversation) - if it
    returns any, mention them briefly, in plain language, and always add that the user should
    confirm applicability with their commercialista before acting on it. Never present these as
    guaranteed or automatic entitlements."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    lista = db.incentivi_non_mostrati(email, codice_ateco)
    for incentivo in lista:
        db.segna_incentivo_mostrato(incentivo["id"], email)
    return {"incentivi": lista}


@mcp.tool
def aggiungi_incentivo_settore(admin_token: str, titolo: str, descrizione: str, requisiti: str,
                               codici_ateco: str, url_fonte: str = "") -> dict:
    """ADMIN ONLY. Add a sector-specific incentive/detrazione to the curated list. codici_ateco:
    comma-separated ATECO prefixes this applies to (e.g. "43" for all of edilizia/installazione,
    or "47.78.91,32.50" for narrower matches) - a user whose codice_ateco starts with one of
    these prefixes will see it in incentivi_non_letti. descrizione and requisiti must be in
    plain Italian: descrizione explains what it is and who it is for, requisiti what conditions
    apply. This list is written by hand, deliberately - do not create an entry unless you (or the
    operator) have actually verified the source, since a wrong or outdated entry here is shown
    directly to users as a suggestion to act on."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    id_nuovo = db.aggiungi_incentivo(titolo, descrizione, requisiti, codici_ateco, url_fonte)
    return {"creato": True, "id": id_nuovo}


@mcp.tool
def lista_incentivi_settore(admin_token: str) -> dict:
    """ADMIN ONLY. List all curated sector incentives (active and not), for review."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    return {"incentivi": db.lista_incentivi()}


@mcp.tool
def disattiva_incentivo_settore(admin_token: str, id_incentivo: int) -> dict:
    """ADMIN ONLY. Deactivate a curated incentive (expired, superseded, or added by mistake): it
    will stop being shown to anyone, even users who hadn't seen it yet."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    db.disattiva_incentivo(id_incentivo)
    return {"disattivato": True}


@mcp.tool
def avvisi_diagnostica(admin_token: str) -> dict:
    """ADMIN ONLY. How many source items have been examined so far, grouped by stato (nuovo /
    irrilevante / approvato / scartato). Use it to check whether the background job actually
    ran, when avvisi_da_rivedere keeps coming back empty."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    return db.conteggio_candidati()


@mcp.tool
def statistiche_uso(admin_token: str, giorni: int = 30) -> dict:
    """ADMIN ONLY. How TaxScan is being used in the last N days: counts per event (chat_avvio,
    web_aperto, web_domanda, web_certificato, web_completato, chat_letto_web, chat_quadro,
    utente_registrato) and, for web interviews that were never completed, the last question seen -
    i.e. where people drop off. Use it to decide which question to cut or simplify next."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    try:
        return db.statistiche_eventi(giorni)
    except Exception as e:
        return {"errore": str(e)}


@mcp.tool
def avvisi_da_rivedere(admin_token: str) -> dict:
    """ADMIN ONLY (requires the operator's ADMIN_TOKEN, set on Render - not a normal user
    credential). Lists regulatory-change candidates found by the periodic job, not yet approved
    or discarded. For each, open its url yourself, judge whether it actually matters for
    regime forfettario taxpayers, then call approva_avviso (with a plain-language titolo_utente
    and riassunto) or scarta_avviso."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    return {"candidati": db.candidati_nuovi()}




@mcp.tool
def approva_avviso(admin_token: str, id_candidato: int, titolo_utente: str, riassunto: str) -> dict:
    """ADMIN ONLY. Approve a candidate from avvisi_da_rivedere and immediately email it to every
    subscribed user. titolo_utente and riassunto must be in plain Italian, written for someone
    with no tax background - this is what the user actually receives."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    candidato = db.dettaglio_candidato(id_candidato)
    if not candidato:
        return {"errore": "candidato non trovato"}
    db.approva_candidato(id_candidato, titolo_utente, riassunto)
    esito_invio = avvisi.manda_avviso_a_tutti(id_candidato, titolo_utente, riassunto,
                                              candidato["url"])
    return {"approvato": True, "invio": esito_invio}


@mcp.tool
def scarta_avviso(admin_token: str, id_candidato: int) -> dict:
    """ADMIN ONLY. Discard a candidate from avvisi_da_rivedere without sending anything."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    db.scarta_candidato(id_candidato)
    return {"scartato": True}


@mcp.custom_route("/cron/controlla_avvisi", methods=["GET"])
async def cron_controlla_avvisi(request):
    """Chiamata da un cron esterno (es. cron-job.org) a orari fissi, con ?chiave=ADMIN_TOKEN.
    Legge le fonti e mette in tabella le voci nuove da rivedere - non manda email. Risponde
    subito e fa il lavoro vero e proprio in background, perché leggere per intero decine di
    pagine una alla volta può superare i tempi di risposta massimi di un cron esterno."""
    from starlette.background import BackgroundTask
    from starlette.responses import JSONResponse
    chiave = request.query_params.get("chiave", "")
    if not avvisi._ammin_ok(chiave):
        return JSONResponse({"errore": "non autorizzato"}, status_code=403)

    def esegui():
        try:
            avvisi.controlla_fonti()
        except Exception as e:
            print(f"controlla_avvisi in background fallito: {e}")

    return JSONResponse({"avviato": True, "nota": "Il controllo gira in background: ricontrolla "
                                                   "tra un minuto con avvisi_da_rivedere."},
                        background=BackgroundTask(esegui))


# ---------------------------------------------------------------- colloquio web (pagina + API)

@mcp.custom_route("/colloquio/nuovo", methods=["GET"])
async def colloquio_nuovo(request):
    """Crea un colloquio e rimanda alla sua pagina (per chi arriva senza passare dalla chat)."""
    from starlette.responses import RedirectResponse, PlainTextResponse
    try:
        web = colloquio_web.crea_colloquio()
    except Exception as e:
        return PlainTextResponse(f"Servizio momentaneamente non disponibile: {e}", status_code=503)
    return RedirectResponse(url=f"/colloquio/{web['id_colloquio']}", status_code=302)


@mcp.custom_route("/colloquio/{id_colloquio}", methods=["GET"])
async def colloquio_pagina(request):
    from starlette.responses import HTMLResponse
    id_colloquio = request.path_params.get("id_colloquio", "")
    return HTMLResponse(colloquio_web.pagina(id_colloquio),
                        headers={"Cache-Control": "no-store"})


@mcp.custom_route("/api/colloquio/{id_colloquio}", methods=["GET", "POST"])
async def colloquio_api(request):
    from starlette.responses import JSONResponse
    id_colloquio = request.path_params.get("id_colloquio", "")
    try:
        if request.method == "GET":
            esito = colloquio_web.stato_colloquio(id_colloquio)
        else:
            corpo = await request.json()
            esito = colloquio_web.registra_risposte(id_colloquio, (corpo or {}).get("scheda") or {})
    except Exception as e:
        return JSONResponse({"errore": str(e)}, status_code=500)
    if esito is None:
        return JSONResponse({"errore": "colloquio non trovato"}, status_code=404)
    return JSONResponse(esito)


@mcp.custom_route("/api/colloquio/{id_colloquio}/certificato", methods=["POST"])
async def colloquio_certificato(request):
    """Riceve il certificato di attribuzione in base64 e restituisce i dati letti (best-effort)."""
    import base64
    from starlette.responses import JSONResponse
    id_colloquio = request.path_params.get("id_colloquio", "")
    if db.carica_colloquio_web(id_colloquio) is None:
        return JSONResponse({"errore": "colloquio non trovato"}, status_code=404)
    try:
        corpo = await request.json()
        pdf = base64.b64decode((corpo or {}).get("pdf_base64") or "")
    except Exception:
        return JSONResponse({"trovati": {}, "errore": "file non valido"}, status_code=400)
    if len(pdf) > 5_000_000:
        return JSONResponse({"trovati": {}, "errore": "file troppo grande (max 5 MB)"}, status_code=400)
    esito = colloquio_web.leggi_certificato(pdf)
    _evento("web_certificato", id_colloquio, {"letto": bool(esito.get("trovati")),
                                                "campi": sorted(esito.get("trovati", {}).keys())})
    return JSONResponse(esito)


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
