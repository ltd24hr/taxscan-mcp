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
import f24
import rate
import bandi_admin
import bandi_auto
import feedback
import approfondimento
import colloquio_web
import dashboard
import agevolazioni
import assistente
import landing
import promemoria
import privacy
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


_COMPITI_DIFFERITI = set()


def _pianifica_bandi(email: str, id_dashboard: str) -> None:
    """Dopo 45 minuti manda una sola email con l'invito al questionario di approfondimento. Se il server si
    riavvia nel frattempo, ci pensa il passaggio giornaliero dei promemoria (db.utenti_approfondimento_da_mandare)."""
    import asyncio

    async def _dopo():
        try:
            await asyncio.sleep(45 * 60)
            await asyncio.to_thread(approfondimento.manda, email, id_dashboard)
        except Exception as e:
            print(f"email di approfondimento non mandata: {e}")

    t = asyncio.get_running_loop().create_task(_dopo())
    _COMPITI_DIFFERITI.add(t)
    t.add_done_callback(_COMPITI_DIFFERITI.discard)


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
        "and explains. Users may manage everything on their own, taking responsibility for what they declare and "
        "pay, or have a professional (commercialista) check the figures whenever they want: that review is "
        "optional, never required. Always say the figures are estimates, never promise results or guarantee "
        "amounts, and offer the free consultation when the situation is specific.\n\n"
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
        "pain, knowing what to set aside and when. Then call crea_dashboard with the same scheda and "
        "give the link_dashboard in one line ('la tua situazione in una pagina, da aprire quando vuoi: "
        "<link>'): it shows next deadline, set-aside share, distance from the 85,000 EUR threshold and "
        "the month-by-month plan at a glance. Always show the disclaimer.\n\n"
        "CHECK DELLE ATTIVITA' (the step that can matter most for tax): in the forfettario every activity has its own "
        "coefficiente di redditivita'; whoever does services falling in different groups applies to each its own coefficient "
        "on its own revenue (kept separate), while the 85,000 EUR threshold counts the SUM of all revenue. Many people do "
        "several small things for clients (e.g. a marketing consultant who also builds sites, sets up tools or handles "
        "paperwork) and are taxed as if everything were the main code. Right after the dashboard, offer once, in plain "
        "words: 'molti fanno più cose di quelle del proprio codice: se me le racconti, calcolo ogni attività con il suo "
        "coefficiente e vediamo quanto cambia'. Then call check_attivita with no servizi to get the plain-language list, "
        "show it as a SHORT numbered list (the user answers with numbers, like '2 e 5'), ask one question at a time: first "
        "which services they really do for clients, then how much each weighs ('poco / un po' / parecchio / circa metà / "
        "quasi tutto'), then roughly the yearly revenue if unknown. Call check_attivita again with the servizi and show the "
        "result as a story: old vs new coefficient, estimated yearly difference in euro, and ALWAYS the avvisi it returns "
        "(only services really performed; separate lines on the invoice; the extra ATECO codes must be on the partita IVA; "
        "a commercial activity can change INPS). Never suggest inventing services or splitting one single job to pay less, "
        "never promise the saving, say the figures are estimates and the codes indicative. To make it count in the "
        "dashboard, send the user to the link_check_attivita page (it has a Save button). If the user has Fatture in Cloud "
        "connected, offer fatture_per_attivita: it reads the invoice LINES (description and amount only) and returns the real "
        "share of revenue per service; ask the user to confirm every line marked sicura=false before using it, pass on its "
        "consigli, then call check_attivita with pesi_percentuali. The user manages this alone "
        "and owns the choice; a professional is optional.\n\n"
        "AGEVOLAZIONI E BANDI: right after the dashboard (and again whenever the user asks about bandi, "
        "contributi, fondo perduto, finanza agevolata), offer once: 'vuoi che cerchi bandi e agevolazioni "
        "per la tua zona e il tuo settore?'. If yes, call cerca_agevolazioni with the scheda: if it says the "
        "location is missing, ask only for the comune, deduce regione and provincia yourself and call it again; "
        "ask the optional age/gender question once. Then follow its istruzioni_per_l_assistente: run a few of "
        "the ricerche_web yourself, open the best official pages, and present at most 4 or 5 items as 'da "
        "verificare' (name, who it is for, deadline, link), never as entitlements, and say to check "
        "requirements on the official notice (and with a professional if unsure) before spending or applying.\n\n"
        "AFTER THE QUADRO, and only then, ask for the email with a reason: 'vuoi che ricordi tutto "
        "questo per la prossima volta e ti avvisi delle scadenze? Dammi la tua email'. If they "
        "agree, do the LOGIN, call salva_scheda_utente, then avvisi_non_letti and incentivi_non_letti "
        "(with their codice_ateco and, if known, regione): if either returns something, mention it briefly, in plain "
        "language - for incentives always add that it's worth double-checking it (or asking a professional) "
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
    to genera_quadro. If it returns link_dashboard, the page already built the user's dashboard: give
    that link (do not call crea_dashboard again). If usa_fatture_in_cloud is 'si', the amounts they typed are approximate:
    offer to connect Fatture in Cloud (needs login) and re-read them."""
    try:
        esito = colloquio_web.stato_colloquio(id_colloquio)
    except Exception as e:
        return {"errore": str(e)}
    if esito is None:
        return {"errore": "id_colloquio non trovato"}
    _evento("chat_letto_web", id_colloquio, {"stato": esito.get("stato")})
    if esito.get("dashboard"):
        # la pagina ha gia' costruito la dashboard di questo colloquio: link assoluto per la chat
        esito["link_dashboard"] = dashboard.PUBLIC_URL + esito["dashboard"]
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
def crea_dashboard(scheda_utente: dict, accantonamento_attuale: float = 0.0) -> dict:
    """Create the user's dashboard: ONE web page that shows their situation at a glance - next
    deadline with amount, share of each invoice to set aside, distance from the 85,000 EUR threshold,
    month-by-month set-aside chart, upcoming deadlines, warnings, to-do list. Built from a completed
    scheda (same input as genera_quadro). Give the user the link_dashboard in one line; it opens on
    their phone, no login. The page is a snapshot: if revenue or other data change, call this again
    for a new link. The link is private: tell the user not to forward it. Use it right after
    piano_pagamenti, or when the user asks 'mostrami la mia situazione', 'una sintesi', 'dashboard'.
    accantonamento_attuale: money already set aside."""
    esito = dashboard.crea_dashboard(scheda_utente, accantonamento_attuale)
    if "errore" not in esito:
        _evento("dashboard_creata", esito.get("id_dashboard"), {"stato": esito.get("stato")})
    return esito


@mcp.tool
def check_attivita(scheda_utente: dict, servizi: list[dict] | None = None, principale: str = "quasi_tutto",
                   ricavi_annui: float = 0.0, id_dashboard: str = "", pesi_percentuali: dict | None = None) -> dict:
    """Check delle attivita': in the forfettario each activity has its own coefficiente di redditivita', applied to
    its own (separately kept) revenue; the 85,000 EUR threshold counts the sum of all revenue. Use it to help the user
    list, in plain words, the services they really do for clients and how much each weighs, then compare the
    'everything on the main ATECO code' calculation with the 'per activity' one.
    1) Call WITHOUT servizi: returns the plain-language catalogue (numbered, grouped) to show as a short list.
    2) Call WITH servizi = [{"id": "sito", "peso": "parecchio"}, ...] (peso: poco | qualche | parecchio | meta |
       quasi_tutto; principale = weight of the main activity of the user's ATECO code; ricavi_annui = yearly revenue,
       or leave 0 to use the scheda). Returns the table, the estimated yearly difference in euro (positive = saving,
       negative = costs more) and avvisi that you MUST always pass on: only services really performed, separate lines on
       invoices, the extra ATECO codes must be on the partita IVA, a commercial activity may change INPS.
    Estimates only: never promise a saving, never suggest inventing services or splitting a single job.
    pesi_percentuali: optional {"principale": 64.2, "sito": 24, ...} (percentages of revenue) - use it when the weights
    come from the user's invoices (see fatture_per_attivita) instead of the peso words.
    Pass id_dashboard if known: link_check_attivita is the page where the user can save the result in their dashboard."""
    import attivita
    link = f"{dashboard.PUBLIC_URL}/d/{id_dashboard}/attivita" if id_dashboard else ""
    if not servizi:
        return {"catalogo": [{"n": i + 1, "id": v["id"], "area": v["area"], "servizio": v["titolo"], "esempio": v["esempio"],
                              "avviso": v["avviso"]} for i, v in enumerate(attivita.CATALOGO)],
                "pesi": attivita.ETICHETTE_PESO, "link_check_attivita": link,
                "istruzioni_per_l_assistente": "Mostra l'elenco breve numerato (solo servizio ed esempio), chiedi quali servizi svolge "
                                               "davvero per i clienti, poi quanto pesa ciascuno. Non mostrare codici o coefficienti prima del risultato."}
    esito = attivita.stima(scheda_utente, servizi, principale, ricavi_annui, pesi_percentuali)
    if "errore" not in esito:
        _evento("chat_check_attivita", id_dashboard or None, {"servizi": len(esito.get("righe", [])) - 1})
        esito["link_check_attivita"] = link
    return esito


@mcp.tool
def fatture_per_attivita(email: str, token_sessione: str, anno: int = 0) -> dict:
    """Read the LINES of the user's issued invoices from the connected Fatture in Cloud account (description and amount
    only - never customer data) and map them to the services of the check delle attività, with the real share of cash-basis
    revenue of each service. Requires a valid token_sessione from conferma_codice and a working Fatture in Cloud link
    (collega_fatture_in_cloud; if there are several aziende, seleziona_azienda_fic first). anno=0: this year, or last year
    if this year has little revenue.
    Then: show the riepilogo in plain words, point out the lines marked sicura=false and ASK the user to confirm or correct
    them (the user decides what each activity really is - never assign silently), pass on the 'consigli' (e.g. write one line
    per service on invoices), and, once confirmed, call check_attivita with servizi built from the confirmed services and
    pesi_percentuali built from the confirmed percentages (key 'principale' for the main activity). Estimates only; the savings
    are real only if the services are really distinct and the ATECO codes are on the partita IVA."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    access_token, company_id, errore = _accesso_fic_pronto(email)
    if errore:
        return errore
    import attivita
    try:
        scheda_salvata = db.carica_scheda(email) or {}
        return attivita.analizza_fatture(access_token, company_id, scheda_salvata, anno or None)
    except Exception as e:
        return {"errore": f"Lettura delle righe delle fatture non riuscita: {e}"}


@mcp.tool
def righe_da_fatture_allegate(scheda_utente: dict, righe: list[dict], anno: int = 0) -> dict:
    """For users WITHOUT Fatture in Cloud who attach invoices (PDF, photo, XML) in the chat. YOU read the attached invoices
    and pass ONLY the service lines: righe = [{"testo": "<description of the service>", "importo": <net amount in euro>}].
    NEVER pass customer names, VAT numbers, tax codes, addresses, IBANs or invoice numbers (replace a customer name inside a
    description with «[cliente]»). Returns the same as fatture_per_attivita: riepilogo per service, lines with sicura=false
    to confirm, 'generiche' (the vague descriptions, e.g. one line 'consulenza marketing'), consigli. No login needed; nothing
    is stored. Then: (1) show the riepilogo in plain words and ask the user to confirm the doubtful lines; (2) for each entry
    in 'generiche' ask ONE short question at a time about what is inside that line (e.g. 'dentro quella consulenza hai anche
    configurato un CRM, creato un sito o una landing page, fatto formazione?' - concrete examples, never inventing services or
    suggesting to split one job just to pay less); (3) when distinct services emerge, explain that each can have its own ATECO
    code and coefficient, that the code must be ADDED to the partita IVA (variazione dati, modello AA9/12, within 30 days, free),
    and call check_attivita with servizi + pesi_percentuali; (4) offer to guide the user step by step through the variazione
    (the dashboard page /d/<id>/attivita also shows the steps). Figures are estimates; the user decides what is true."""
    import attivita
    try:
        esito = attivita.analizza_righe_allegate(righe, scheda_utente, anno or None)
    except Exception as e:
        return {"errore": f"Lettura delle righe non riuscita: {e}"}
    if "errore" not in esito:
        _evento("attivita_da_allegati", None, {"righe": len(esito.get("righe", [])), "da_controllare": esito.get("da_controllare")})
    return esito


@mcp.tool
def cerca_agevolazioni(scheda_utente: dict, regione: str = "", provincia: str = "", comune: str = "",
                       profilo_agevolazioni: str = "") -> dict:
    """Prepare the search for bandi and finanza agevolata (national, regional, local) that could be
    relevant to this user. TaxScan does NOT know which bandi are open today: this tool works out
    WHERE the user is (province -> region; comune and provincia are already in the scheda when they
    uploaded the certificato), their sector and profile, and returns: ricerche_web (ready-made
    Italian search queries), fonti_ufficiali (incentivi.gov.it, Invitalia, MIMIT), incentivi_curati
    (hand-verified list, by sector and region), 'mancano' (what to ask: the comune if the location
    is unknown - then call this tool again with regione/provincia/comune filled in - and one optional
    numbered question about age/gender, ask it once) and istruzioni_per_l_assistente. YOU then run the
    web searches and open the best pages, and present at most 4-5 items as 'da verificare' with
    deadline and link, never as entitlements. Use it after the quadro/piano/dashboard when the user
    says yes to 'vuoi che cerchi bandi e agevolazioni per la tua zona?', or asks about bandi,
    contributi, finanza agevolata, fondo perduto, incentivi. No login needed. profilo_agevolazioni:
    'giovane', 'donna', 'giovane_donna' or 'nessuno' (the value of the optional question)."""
    esito = agevolazioni.piano_ricerca(scheda_utente, regione, provincia, comune, profilo_agevolazioni)
    _evento("bandi_cercati", None, {"regione": esito["luogo"]["regione"],
                                    "curati": len(esito["incentivi_curati"])})
    return esito


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
def incentivi_non_letti(email: str, token_sessione: str, codice_ateco: str, regione: str = "") -> dict:
    """Check for sector-specific tax incentives/detrazioni the user hasn't been told about yet,
    matching their ATECO code (e.g. a tax credit on machinery for a given trade). This is a
    curated list (no automatic scraping), so matches are deliberately conservative. Requires a
    valid token_sessione. Call it right after carica_scheda_salvata/avvisi_non_letti whenever you
    know the user's codice_ateco (from their saved scheda or the current conversation) - if it
    returns any, mention them briefly, in plain language, and always add that the user should
    double-check applicability (or ask a professional) before acting on it. Never present these as
    guaranteed or automatic entitlements. regione (optional): the user's region, so regional
    entries are included."""
    errore = _sessione_richiesta(email, token_sessione)
    if errore:
        return errore
    lista = db.incentivi_non_mostrati(email, codice_ateco, regione)
    for incentivo in lista:
        db.segna_incentivo_mostrato(incentivo["id"], email)
    return {"incentivi": lista}


@mcp.tool
def aggiungi_incentivo_settore(admin_token: str, titolo: str, descrizione: str, requisiti: str,
                               codici_ateco: str, url_fonte: str = "", ambito: str = "nazionale",
                               regioni: str = "", scadenza: str = "") -> dict:
    """ADMIN ONLY. Add a sector-specific incentive/detrazione to the curated list. codici_ateco:
    comma-separated ATECO prefixes this applies to (e.g. "43" for all of edilizia/installazione,
    or "47.78.91,32.50" for narrower matches) - a user whose codice_ateco starts with one of
    these prefixes will see it in incentivi_non_letti. descrizione and requisiti must be in
    plain Italian: descrizione explains what it is and who it is for, requisiti what conditions
    apply. This list is written by hand, deliberately - do not create an entry unless you (or the
    operator) have actually verified the source, since a wrong or outdated entry here is shown
    directly to users as a suggestion to act on. ambito: 'nazionale', 'regionale' or 'locale'.
    regioni: comma-separated region names the entry is limited to (empty = everywhere), e.g.
    "Lombardia,Veneto". scadenza: ISO date (YYYY-MM-DD) after which it stops being shown (empty =
    none). codici_ateco may be empty to apply to every sector."""
    if not avvisi._ammin_ok(admin_token):
        return {"errore": "token amministratore non valido"}
    id_nuovo = db.aggiungi_incentivo(titolo, descrizione, requisiti, codici_ateco, url_fonte,
                                     ambito, regioni, scadenza or None)
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


@mcp.custom_route("/privacy", methods=["GET"])
async def pagina_privacy(request):
    from starlette.responses import HTMLResponse
    return HTMLResponse(privacy.pagina())


@mcp.custom_route("/cron/promemoria", methods=["GET"])
async def cron_promemoria(request):
    """Cron esterno una volta al giorno, con ?chiave=ADMIN_TOKEN. Manda i promemoria (scadenze, dati
    mancanti, riepilogo mensile). Con &prova=1 non manda nulla e dice solo cosa manderebbe."""
    from starlette.background import BackgroundTask
    from starlette.responses import JSONResponse
    import asyncio
    if not avvisi._ammin_ok(request.query_params.get("chiave", "")):
        return JSONResponse({"errore": "non autorizzato"}, status_code=403)
    if request.query_params.get("prova"):
        esito = await asyncio.to_thread(promemoria.esegui, True)
        return JSONResponse(esito)

    def esegui():
        try:
            print(f"promemoria: {promemoria.esegui(False)}")
        except Exception as e:
            print(f"promemoria fallito: {e}")

    return JSONResponse({"avviato": True}, background=BackgroundTask(esegui))


@mcp.custom_route("/cron/cerca_bandi", methods=["GET"])
async def cron_cerca_bandi(request):
    """Cron esterno una volta a settimana, con ?chiave=ADMIN_TOKEN. Cerca bandi aperti (Italia + regioni degli iscritti),
    li controlla e li pubblica; l'email parte con il passaggio delle 8:55. Con &prova=1 mostra solo le zone."""
    from starlette.background import BackgroundTask
    from starlette.responses import JSONResponse
    import asyncio
    if not avvisi._ammin_ok(request.query_params.get("chiave", "")):
        return JSONResponse({"errore": "non autorizzato"}, status_code=403)
    if request.query_params.get("prova"):
        return JSONResponse(await asyncio.to_thread(bandi_auto.esegui, True))

    def esegui():
        try:
            print(f"bandi automatici: {bandi_auto.esegui(False)}")
        except Exception as e:
            print(f"ricerca bandi fallita: {e}")
            bandi_auto.salva({"zone": [], "trovati": 0, "nuovi": [], "scartati": [], "errori": [f"errore generale: {bandi_auto._pulisci_errore(e)}"]})

    return JSONResponse({"avviato": True}, background=BackgroundTask(esegui))


@mcp.custom_route("/approfondisci", methods=["GET"])
async def approfondisci_pagina(request):
    """Questionario di approfondimento (link firmato nell'email): una domanda alla volta, poi gli spunti."""
    from starlette.responses import HTMLResponse
    import asyncio
    q = request.query_params
    try:
        pagina = await asyncio.to_thread(approfondimento.pagina, q.get("e", ""), q.get("t", ""))
    except Exception as e:
        return HTMLResponse(f"<p>Servizio momentaneamente non disponibile: {e}</p>", status_code=503)
    return HTMLResponse(pagina, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/api/approfondisci", methods=["POST"])
async def approfondisci_salva(request):
    from starlette.responses import JSONResponse
    import asyncio
    try:
        c = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "errore": "Richiesta non valida."}, status_code=400)
    try:
        esito = await asyncio.to_thread(approfondimento.salva, str(c.get("e", "")), str(c.get("t", "")),
                                        c.get("risposte") if isinstance(c.get("risposte"), dict) else {})
    except Exception as e:
        return JSONResponse({"ok": False, "errore": f"Non sono riuscito a salvare: {e}"}, status_code=500)
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/feedback", methods=["GET"])
async def feedback_pagina(request):
    """Pagina del sondaggio (link firmato nell'email). Aprirla NON registra nulla: si salva solo con Invia."""
    from starlette.responses import HTMLResponse
    q = request.query_params
    try:
        pagina = feedback.pagina(q.get("e", ""), q.get("t", ""), q.get("r", ""))
    except Exception as e:
        return HTMLResponse(f"<p>Servizio momentaneamente non disponibile: {e}</p>", status_code=503)
    return HTMLResponse(pagina, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/api/feedback", methods=["POST"])
async def feedback_salva(request):
    from starlette.responses import JSONResponse
    import asyncio
    try:
        c = await request.json()
        esito = await asyncio.to_thread(feedback.salva, c.get("e", ""), c.get("t", ""), c.get("r", ""),
                                        c.get("risposte") or {}, c.get("commento", ""), bool(c.get("ricontatto")))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": f"Non sono riuscito a salvare: {e}"}, status_code=500)
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/admin/feedback", methods=["GET"])
async def feedback_admin(request):
    """Pagina privata (?chiave=ADMIN_TOKEN): risposte, medie e persone da contattare di persona."""
    from starlette.responses import HTMLResponse, JSONResponse
    import asyncio
    if not avvisi._ammin_ok(request.query_params.get("chiave", "")):
        return JSONResponse({"errore": "non autorizzato"}, status_code=403)
    riep = await asyncio.to_thread(db.feedback_riepilogo)
    return HTMLResponse(feedback.pagina_admin(riep), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@mcp.custom_route("/admin/bandi", methods=["GET", "POST"])
async def bandi_admin_pagina(request):
    """Pagina privata (?chiave=ADMIN_TOKEN): inserisci, attiva per email o disattiva i bandi approvati."""
    from starlette.responses import HTMLResponse, JSONResponse
    from urllib.parse import parse_qs
    import asyncio
    messaggio = ""
    if request.method == "POST":
        corpo = parse_qs((await request.body()).decode("utf-8", "ignore"))
        chiave = (corpo.get("chiave") or [""])[0]
        if not avvisi._ammin_ok(chiave):
            return JSONResponse({"errore": "non autorizzato"}, status_code=403)
        azione = (corpo.get("azione") or [""])[0]
        try:
            if azione == "nuovo":
                campi = {k: (v[0] if v else "") for k, v in corpo.items()}
                campi["regioni_lista"] = corpo.get("regione", [])
                ok, errore = bandi_admin.valida(campi)
                if not ok:
                    messaggio = errore
                else:
                    id_nuovo = await asyncio.to_thread(
                        db.aggiungi_incentivo, ok["titolo"], ok["descrizione"], ok["requisiti"], ok["codici_ateco"],
                        ok["url_fonte"], ok["ambito"], ok["regioni"], ok["scadenza"])
                    if (corpo.get("mail") or [""])[0] == "1":
                        await asyncio.to_thread(db.attiva_notifica_incentivo, id_nuovo)
                    messaggio = "Bando salvato." + (" Partirà per email alle 8:55." if (corpo.get("mail") or [""])[0] == "1" else "")
            elif azione.startswith("mail:") and azione[5:].isdigit():
                await asyncio.to_thread(db.attiva_notifica_incentivo, int(azione[5:]))
                messaggio = "Fatto: partirà per email alle 8:55."
            elif azione.startswith("off:") and azione[4:].isdigit():
                await asyncio.to_thread(db.disattiva_incentivo, int(azione[4:]))
                messaggio = "Bando disattivato."
        except Exception as e:
            messaggio = f"Non sono riuscito a salvare: {e}"
    else:
        chiave = request.query_params.get("chiave", "")
        if not avvisi._ammin_ok(chiave):
            return JSONResponse({"errore": "non autorizzato"}, status_code=403)
    pagina_html = await asyncio.to_thread(bandi_admin.pagina, chiave, messaggio)
    return HTMLResponse(pagina_html, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@mcp.custom_route("/disiscriviti", methods=["GET", "POST"])
async def disiscriviti(request):
    from starlette.responses import HTMLResponse
    from urllib.parse import parse_qs
    if request.method == "POST":
        corpo = parse_qs((await request.body()).decode("utf-8", "ignore"))
        email = (corpo.get("e") or [""])[0].strip().lower()
        token = (corpo.get("t") or [""])[0]
        azione = (corpo.get("azione") or ["disattiva"])[0]
        if promemoria.firma_valida(email, token):
            try:
                if azione == "riattiva":
                    db.riattiva_email(email)
                    return HTMLResponse(promemoria.pagina_disiscrizione(email, token, riattivato=True))
                db.disattiva_email(email)
                db.disattiva_avvisi(email)
                _evento("email_disattivate", None)
                return HTMLResponse(promemoria.pagina_disiscrizione(email, token, fatto=True))
            except Exception as e:
                print(f"disiscrizione fallita: {e}")
        return HTMLResponse(promemoria.pagina_disiscrizione(email, token), status_code=400)
    email = request.query_params.get("e", "").strip().lower()
    return HTMLResponse(promemoria.pagina_disiscrizione(email, request.query_params.get("t", "")))


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


@mcp.custom_route("/d/{id_dashboard}", methods=["GET"])
async def dashboard_pagina(request):
    from starlette.responses import HTMLResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    return HTMLResponse(dashboard.pagina(id_dashboard),
                        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@mcp.custom_route("/api/dashboard/{id_dashboard}", methods=["GET"])
async def dashboard_api(request):
    from starlette.responses import JSONResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        dati = dashboard.dati_pubblici(id_dashboard)
    except Exception as e:
        return JSONResponse({"errore": str(e)}, status_code=500)
    if dati is None:
        return JSONResponse({"errore": "dashboard non trovata"}, status_code=404)
    _evento("dashboard_aperta", id_dashboard)
    return JSONResponse(dati, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/d/{id_dashboard}/calendario", methods=["GET"])
async def dashboard_calendario(request):
    """Genera il calendario (.ics) con le scadenze della dashboard e rimanda al file."""
    from starlette.responses import RedirectResponse, PlainTextResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        link = dashboard.link_calendario(id_dashboard)
    except Exception as e:
        return PlainTextResponse(f"Servizio momentaneamente non disponibile: {e}", status_code=503)
    if not link:
        return PlainTextResponse("Nessuna scadenza da mettere in calendario.", status_code=404)
    _evento("calendario_scaricato", id_dashboard)
    return RedirectResponse(url=link, status_code=302)


@mcp.custom_route("/d/{id_dashboard}/f24", methods=["GET"])
async def dashboard_f24(request):
    """Bozza dell'F24 per una scadenza della dashboard (pagina stampabile, NON valida per il pagamento)."""
    from starlette.responses import HTMLResponse, PlainTextResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    data_iso = request.query_params.get("data", "")
    try:
        from datetime import date as _d
        _d.fromisoformat(data_iso)
        v = f24.trova(id_dashboard, data_iso)
    except ValueError:
        return PlainTextResponse("Data non valida.", status_code=400)
    except Exception as e:
        return PlainTextResponse(f"Servizio momentaneamente non disponibile: {e}", status_code=503)
    if not v:
        return PlainTextResponse("Nessuna bozza disponibile per questa scadenza: torna sulla tua situazione e riprova.",
                                 status_code=404)
    _evento("f24_bozza", id_dashboard)
    return HTMLResponse(f24.pagina(v, id_dashboard), headers={"Cache-Control": "no-store"})


@mcp.custom_route("/d/{id_dashboard}/situazione", methods=["GET"])
async def dashboard_situazione(request):
    """Dalla sezione "Ottimizzazione fiscale": porta al questionario firmato di chi ha salvato l'email."""
    from starlette.responses import PlainTextResponse, RedirectResponse
    import asyncio
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        dati = await asyncio.to_thread(dashboard.dati_dashboard, id_dashboard)
    except Exception as e:
        return PlainTextResponse(f"Servizio momentaneamente non disponibile: {e}", status_code=503)
    email = (dati or {}).get("_email")
    if not email:
        return PlainTextResponse("Salva prima la tua email dalla tua pagina: ti mandiamo il questionario.", status_code=404)
    return RedirectResponse(approfondimento._link(email), status_code=302, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/d/{id_dashboard}/rate", methods=["GET"])
async def dashboard_rate(request):
    """Pagina "Voglio rateizzare" per una scadenza (saldo / primo acconto)."""
    from starlette.responses import HTMLResponse, PlainTextResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    data_iso = request.query_params.get("data", "")
    try:
        n = int(request.query_params.get("rate", "6"))
    except ValueError:
        n = 6
    try:
        from datetime import date as _d
        _d.fromisoformat(data_iso)
        v = f24.trova(id_dashboard, data_iso)
    except ValueError:
        return PlainTextResponse("Data non valida.", status_code=400)
    except Exception as e:
        return PlainTextResponse(f"Servizio momentaneamente non disponibile: {e}", status_code=503)
    if not v:
        return PlainTextResponse("Nessuna scadenza disponibile: torna sulla tua situazione e riprova.", status_code=404)
    _evento("rate_pagina", id_dashboard)
    return HTMLResponse(rate.pagina(v, id_dashboard, n), headers={"Cache-Control": "no-store"})


@mcp.custom_route("/d/{id_dashboard}/attivita", methods=["GET"])
async def dashboard_attivita(request):
    """Check delle attivita': quali servizi svolge l'utente e quanto pesano, per applicare a ognuno il suo coefficiente."""
    from starlette.responses import HTMLResponse, PlainTextResponse
    import asyncio
    import attivita
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        dati = await asyncio.to_thread(dashboard.dati_dashboard, id_dashboard)
    except Exception as e:
        return PlainTextResponse(f"Servizio momentaneamente non disponibile: {e}", status_code=503)
    if not dati:
        return PlainTextResponse("Pagina non trovata.", status_code=404)
    _evento("attivita_pagina", id_dashboard)
    fic_stato = {"registrato": bool(dati.get("_email")), "collegata": False}
    if dati.get("_email"):
        try:
            fic_stato["collegata"] = bool(await asyncio.to_thread(db.carica_fic_token, dati["_email"]))
        except Exception:
            pass
    return HTMLResponse(attivita.pagina(id_dashboard, dati.get("_scheda") or {}, fic_stato),
                        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@mcp.custom_route("/api/dashboard/{id_dashboard}/attivita/stima", methods=["POST"])
async def dashboard_attivita_stima(request):
    from starlette.responses import JSONResponse
    import asyncio
    import attivita
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        dati = await asyncio.to_thread(dashboard.dati_dashboard, id_dashboard)
        if not dati:
            return JSONResponse({"errore": "pagina non trovata"}, status_code=404)
        esito = await asyncio.to_thread(attivita.stima, dati.get("_scheda") or {}, corpo.get("voci"),
                                        corpo.get("principale"), corpo.get("ricavi"), corpo.get("pct"))
    except Exception as e:
        return JSONResponse({"errore": str(e)}, status_code=500)
    if "errore" not in esito:
        _evento("attivita_stima", id_dashboard, {"servizi": len(esito.get("righe", [])) - 1})
    return JSONResponse(esito, status_code=400 if "errore" in esito else 200)


@mcp.custom_route("/api/dashboard/{id_dashboard}/attivita/fatture", methods=["POST"])
async def dashboard_attivita_fatture(request):
    """Legge le righe delle fatture da Fatture in Cloud e le riconduce ai servizi (senza salvare nulla)."""
    from starlette.responses import JSONResponse
    import asyncio
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        esito = await asyncio.to_thread(dashboard.fic_righe, id_dashboard, corpo.get("company_id"))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    if esito.get("ok"):
        _evento("attivita_da_fatture", id_dashboard, {"righe": len(esito.get("righe", [])), "da_controllare": esito.get("da_controllare")})
    return JSONResponse(esito, status_code=200 if esito.get("ok") or esito.get("scegli_azienda") else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/attivita/file", methods=["POST"])
async def dashboard_attivita_file(request):
    """Analizza le fatture caricate dall'utente (XML, PDF, foto). Nulla viene salvato."""
    from starlette.responses import JSONResponse
    import asyncio
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        esito = await asyncio.to_thread(dashboard.fatture_caricate, id_dashboard, corpo.get("files"), bool(corpo.get("consenso")))
    except Exception as e:
        print(f"attivita/file: {e}")
        return JSONResponse({"ok": False, "errore": "Non riesco a leggere le fatture in questo momento."}, status_code=500)
    if esito.get("ok"):
        _evento("attivita_da_file", id_dashboard, {"righe": len(esito.get("righe", [])), "da_controllare": esito.get("da_controllare")})
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/attivita/salva", methods=["POST"])
async def dashboard_attivita_salva(request):
    from starlette.responses import JSONResponse
    import asyncio
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        esito = await asyncio.to_thread(dashboard.imposta_attivita, id_dashboard, corpo.get("voci"),
                                        corpo.get("principale"), corpo.get("altro", ""), corpo.get("pct"), corpo.get("anno"))
    except Exception as e:
        return JSONResponse({"errore": str(e)}, status_code=500)
    if esito is None:
        return JSONResponse({"errore": "pagina non trovata"}, status_code=404)
    if "errore" not in esito:
        _evento("attivita_salvata", id_dashboard)
    return JSONResponse(esito, status_code=400 if "errore" in esito else 200)


@mcp.custom_route("/api/dashboard/{id_dashboard}/email", methods=["POST"])
async def dashboard_email(request):
    from starlette.responses import JSONResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json()
        esito = dashboard.manda_codice(id_dashboard, (corpo or {}).get("email", ""))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/codice", methods=["POST"])
async def dashboard_codice(request):
    from starlette.responses import JSONResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json()
        esito = dashboard.conferma_codice(id_dashboard, (corpo or {}).get("email", ""),
                                          (corpo or {}).get("codice", ""))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    if esito.get("ok"):
        try:  # scelta sulle email con spunti su bandi, agevolazioni, finanziamenti e previdenza (casella non spuntata)
            db.imposta_novita(esito["email"], bool((corpo or {}).get("novita")))
        except Exception as e:
            print(f"scelta novita non salvata: {e}")
    if esito.get("ok") and esito.get("nuovo"):
        _evento("utente_registrato", esito["email"], {"da": "web"})
        _avvisa_nuovo_iscritto(esito["email"], esito.get("scheda") or {})
        try:
            import asyncio
            await asyncio.to_thread(promemoria.manda_benvenuto, esito["email"], id_dashboard,
                                      (esito.get("scheda") or {}).get("nome", ""),
                                      db.novita_consentite(esito["email"]))
            oggi = date.today()
            db.prenota_promemoria(esito["email"], "benvenuto", "1")
            db.prenota_promemoria(esito["email"], "mensile", f"{oggi.year}-{oggi.month:02d}")
            _evento("benvenuto_mandato", id_dashboard)
            _pianifica_bandi(esito["email"], id_dashboard)
        except Exception as e:
            print(f"email di benvenuto non mandata: {e}")
    return JSONResponse({"ok": bool(esito.get("ok")), "errore": esito.get("errore")},
                        status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/numeri", methods=["POST"])
async def dashboard_numeri(request):
    from starlette.responses import JSONResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        esito = dashboard.aggiorna_numeri(id_dashboard, corpo.get("ricavi_corrente"), corpo.get("ricavi_precedente"))
    except Exception as e:
        return JSONResponse({"errore": str(e)}, status_code=500)
    if esito is None:
        return JSONResponse({"errore": "pagina non trovata"}, status_code=404)
    if "errore" not in esito:
        _evento("dashboard_aggiornata", id_dashboard)
    return JSONResponse(esito, status_code=400 if "errore" in esito else 200)


@mcp.custom_route("/api/dashboard/{id_dashboard}/cancella/richiedi", methods=["POST"])
async def dashboard_cancella_richiedi(request):
    from starlette.responses import JSONResponse
    import asyncio
    try:
        esito = await asyncio.to_thread(dashboard.cancella_richiedi, request.path_params.get("id_dashboard", ""))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/cancella/conferma", methods=["POST"])
async def dashboard_cancella_conferma(request):
    from starlette.responses import JSONResponse
    import asyncio
    try:
        corpo = await request.json() or {}
        esito = await asyncio.to_thread(dashboard.cancella_conferma, request.path_params.get("id_dashboard", ""),
                                        corpo.get("codice", ""))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    if esito.get("ok"):
        _evento("dati_cancellati")  # senza riferimenti: non resta traccia di chi
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/strumento", methods=["POST"])
async def dashboard_strumento(request):
    from starlette.responses import JSONResponse
    import asyncio
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        valore = corpo.get("valore", "")
        esito = await asyncio.to_thread(dashboard.imposta_strumento, id_dashboard, valore)
    except Exception as e:
        return JSONResponse({"errore": str(e)}, status_code=500)
    if esito is None:
        return JSONResponse({"errore": "pagina non trovata"}, status_code=404)
    if "errore" not in esito and valore:
        _evento(f"strumento_{valore}", id_dashboard)
    return JSONResponse(esito, status_code=400 if "errore" in esito else 200)


@mcp.custom_route("/d/{id_dashboard}/fic/collega", methods=["GET"])
async def dashboard_fic_collega(request):
    from starlette.responses import RedirectResponse, PlainTextResponse
    id_dashboard = "".join(c for c in request.path_params.get("id_dashboard", "") if c.isalnum())
    try:
        link = dashboard.fic_link(id_dashboard)
    except Exception as e:
        return PlainTextResponse(f"Servizio momentaneamente non disponibile: {e}", status_code=503)
    if not link:
        return RedirectResponse(url=f"/d/{id_dashboard}", status_code=302)
    _evento("fic_collegamento_avviato", id_dashboard)
    return RedirectResponse(url=link, status_code=302)


@mcp.custom_route("/api/dashboard/{id_dashboard}/fic/importa", methods=["POST"])
async def dashboard_fic_importa(request):
    from starlette.responses import JSONResponse
    import asyncio
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        esito = await asyncio.to_thread(dashboard.fic_importa, id_dashboard, corpo.get("company_id"))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    if esito.get("ok"):
        _evento("fic_incassi_letti", id_dashboard)
    return JSONResponse(esito, status_code=200 if (esito.get("ok") or esito.get("scegli_azienda")) else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/chat", methods=["POST"])
async def dashboard_chat(request):
    from starlette.responses import JSONResponse
    import asyncio
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json() or {}
        esito = await asyncio.to_thread(assistente.rispondi, id_dashboard, corpo.get("domanda", ""),
                                        corpo.get("storia"), "attivita" if corpo.get("contesto") == "attivita" else "")
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    if esito.get("ok"):
        _evento("chat_attivita" if corpo.get("contesto") == "attivita" else "chat_domanda", id_dashboard,
                {"risposta_caratteri": len(esito.get("risposta", "")), "fonti": len(esito.get("fonti", []))})
    elif esito.get("limite"):
        _evento("chat_limite", id_dashboard)
    return JSONResponse(esito, status_code=200 if esito.get("ok") or esito.get("limite") else 400)


@mcp.custom_route("/logo-ltd24.png", methods=["GET"])
async def logo_ltd24(request):
    """Logo LTD24 per il pie' di pagina (file static/ltd24-logo.png nel repository)."""
    return _logo("ltd24-logo.png")


@mcp.custom_route("/logo-ltd24-scuro.png", methods=["GET"])
async def logo_ltd24_scuro(request):
    """Variante chiara del logo, per il tema scuro."""
    return _logo("ltd24-logo-scuro.png")


@mcp.custom_route("/font/{nome}", methods=["GET"])
async def font_file(request):
    """Font del marchio (Poppins, Rethink Sans) serviti dal nostro sito, senza chiamare servizi esterni."""
    from starlette.responses import Response
    nome = request.path_params.get("nome", "")
    if nome not in ("Poppins-Regular.ttf", "Poppins-Medium.ttf", "Poppins-Bold.ttf", "RethinkSans-VariableFont_wght.ttf"):
        return Response("non trovato", status_code=404)
    percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fonts", nome)
    try:
        with open(percorso, "rb") as f:
            return Response(f.read(), media_type="font/ttf", headers={"Cache-Control": "public, max-age=604800"})
    except OSError:
        return Response("font non presente", status_code=404)


def _logo(nome_file: str):
    from starlette.responses import Response
    percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", nome_file)
    try:
        with open(percorso, "rb") as f:
            return Response(f.read(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
    except OSError:
        return Response("logo non presente", status_code=404)


@mcp.custom_route("/accedi", methods=["GET"])
async def accedi_pagina(request):
    from starlette.responses import HTMLResponse
    return HTMLResponse(landing.ACCEDI_HTML, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/api/accedi/email", methods=["POST"])
async def accedi_email(request):
    from starlette.responses import JSONResponse
    try:
        corpo = await request.json() or {}
        esito = dashboard.accedi_manda_codice(corpo.get("email", ""))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/api/accedi/codice", methods=["POST"])
async def accedi_codice(request):
    from starlette.responses import JSONResponse
    try:
        corpo = await request.json() or {}
        esito = dashboard.accedi_conferma(corpo.get("email", ""), corpo.get("codice", ""))
    except Exception as e:
        return JSONResponse({"ok": False, "errore": str(e)}, status_code=500)
    if esito.get("ok"):
        _evento("accesso_web", None, None)
    return JSONResponse(esito, status_code=200 if esito.get("ok") else 400)


@mcp.custom_route("/api/dashboard/{id_dashboard}/luogo", methods=["POST"])
async def dashboard_luogo(request):
    from starlette.responses import JSONResponse
    id_dashboard = request.path_params.get("id_dashboard", "")
    try:
        corpo = await request.json()
        esito = dashboard.aggiorna_luogo(id_dashboard, (corpo or {}).get("regione", ""))
    except Exception as e:
        return JSONResponse({"errore": str(e)}, status_code=500)
    if esito is None:
        return JSONResponse({"errore": "pagina non trovata"}, status_code=404)
    return JSONResponse(esito, status_code=400 if "errore" in esito else 200)


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
    try:
        id_dash = db.dashboard_di_utente(email)
    except Exception:
        id_dash = None
    if id_dash:
        from starlette.responses import RedirectResponse
        _evento("fic_collegato", id_dash)
        return RedirectResponse(url=f"/d/{id_dash}?fic=collegato", status_code=302)
    return pagina("Fatture in Cloud collegato",
                  "Ora puoi tornare nella conversazione con TaxScan e dire che hai completato "
                  "l'autorizzazione.")


@mcp.custom_route("/", methods=["GET", "HEAD"])
async def home(request):
    from starlette.responses import HTMLResponse
    return HTMLResponse(landing.PAGINA_HTML)


if __name__ == "__main__":
    try:
        db.inizializza()
    except Exception as e:
        # Non blocca l'avvio: senza database il server funziona lo stesso, solo senza
        # salvare/ritrovare le schede (carica_scheda_salvata e salva_scheda_utente lo
        # segnaleranno riga per riga quando chiamati).
        print(f"Attenzione: inizializzazione database fallita ({e}). Il server parte comunque.")
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
