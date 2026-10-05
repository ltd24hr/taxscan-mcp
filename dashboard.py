"""
TaxScan - dashboard: la situazione dell'utente in un colpo d'occhio, in una pagina.

Il connettore (crea_dashboard) calcola quadro e piano dalla scheda, ne salva
un'ISTANTANEA (solo cifre e scadenze: niente nome ne' email) dietro un id casuale
di 12 caratteri, e restituisce il link. La pagina (/d/<id>) legge l'istantanea da
/api/dashboard/<id> e la disegna: prossima scadenza, quanto mettere da parte,
avvicinamento alla soglia degli 85.000 euro, piano mese per mese, avvisi, cose da fare.

E' una fotografia: se i ricavi cambiano, si rigenera (stesso strumento, nuovo link).
Il link e' privato come quello del colloquio: chi lo ha lo vede, quindi non va girato.
"""

import os
import re
import secrets
import string
import time
from datetime import date
from urllib.parse import quote_plus

import assistente
import auth
import agevolazioni
import calendario
import db
import fic
import scheda as S

STRUMENTI_FATTURE = {"fatture_in_cloud": "Fatture in Cloud", "aruba": "Aruba Fatturazione",
                     "facile_fattura": "Facile Fattura", "portale_ade": "Portale gratuito dell'Agenzia delle Entrate",
                     "altro": "Un altro programma", "commercialista": "Se ne occupa il mio commercialista"}

PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://taxscan-mcp.onrender.com").rstrip("/")
_ALFABETO = string.ascii_letters + string.digits


def _nuovo_id() -> str:
    return "".join(secrets.choice(_ALFABETO) for _ in range(12))


def _avviso(a) -> dict:
    if isinstance(a, dict):
        return {"livello": a.get("livello", "informativo"), "titolo": a.get("titolo", ""),
                "testo": a.get("testo", "")}
    return {"livello": "informativo", "titolo": "", "testo": str(a)}


def costruisci(scheda_utente: dict, accantonamento_attuale: float = 0.0) -> dict:
    """Dati della dashboard dalla scheda. Restituisce {'errore': ...} se la scheda e' incompleta."""
    quadro = S.genera_quadro(scheda_utente)
    if "errore" in quadro:
        return quadro
    piano = S.piano_pagamenti(scheda_utente, "", accantonamento_attuale)
    if "errore" in piano:
        return piano

    prof = quadro.get("profilo", {})
    corr = quadro.get("anno_corrente", {})
    stima = corr.get("stima_a_oggi", {}) or {}
    soglia = corr.get("soglia", {}) or {}
    prec = quadro.get("anno_precedente", {}) or {}
    scadenze = piano.get("scadenze", []) or []
    mensile = piano.get("piano_mensile", []) or []

    avvisi = [_avviso(a) for a in (quadro.get("avvisi") or [])]
    avvisi += [_avviso(a) for a in (piano.get("avvisi") or [])]

    if scheda_utente.get("codice_ateco_stimato"):
        avvisi.append({"livello": "attenzione", "titolo": "Settore indicato a grandi linee",
                       "testo": "Non conoscevi il codice ATECO, quindi ho scelto un codice vicino al tuo settore: "
                                "da esso dipende il coefficiente di redditività e quindi le tasse. Controlla il "
                                "codice esatto sul certificato di attribuzione della partita IVA o chiedilo a "
                                "chi ti segue."})

    ordine = {"importante": 0, "attenzione": 1, "informativo": 2}
    avvisi.sort(key=lambda a: ordine.get(a["livello"], 3))

    def _norm_sc(s):
        return {"data": s.get("data"), "etichetta": s.get("etichetta"), "importo": s.get("importo"),
                "dettaglio": s.get("dettaglio", []), "giorni": s.get("giorni_mancanti")}

    cose, link_prof = [], None
    for voce in (quadro.get("cose_da_fare") or []):
        voce = str(voce)
        if voce.startswith("Da ogni fattura incassata") or voce.startswith("Prossima scadenza:"):
            continue  # gia' in evidenza sopra (quota e scadenza)
        m = re.search(r"https?://\S+", voce)
        if m:
            link_prof = link_prof or m.group(0)
            voce = voce.replace(m.group(0), "").rstrip(" :-")
        cose.append(voce)

    rischio_soglia = soglia.get("livello_rischio", "OK") != "OK"
    da_controllare = rischio_soglia or any(a["livello"] in ("importante", "attenzione") for a in avvisi)

    anno_ingresso = prof.get("anno_ingresso_forfettario")
    aliquota = prof.get("aliquota")
    fine_5 = None
    if str(aliquota).startswith("5") and isinstance(anno_ingresso, int):
        fine_5 = anno_ingresso + 5  # dal quale si applica il 15%

    ag = agevolazioni.piano_ricerca(scheda_utente)
    agev = {
        "luogo": ag["luogo"],
        "curati": ag["incentivi_curati"],
        "fonti": ag["fonti_ufficiali"],
        "ricerche": [{"testo": q, "url": "https://www.google.com/search?q=" + quote_plus(q)}
                     for q in ag["ricerche_web"][:5]],
        "regioni": sorted(agevolazioni._PROVINCE),
        "disclaimer": ag["disclaimer"],
    }

    return {
        "_scheda": dict(scheda_utente),
        "nome": S.pulisci_nome(scheda_utente.get("nome")) or None,
        "strumento_fatture": (scheda_utente.get("strumento_fatturazione")
                              if scheda_utente.get("strumento_fatturazione") in STRUMENTI_FATTURE else None),
        "numeri": {"ricavi_anno_corrente": scheda_utente.get("ricavi_anno_corrente"),
                   "ricavi_anno_precedente": scheda_utente.get("ricavi_anno_precedente")},
        "agevolazioni": agev,
        "in_breve": [str(x) for x in (quadro.get("situazione_maturata") or [])],
        "aggiornato_il": date.today().isoformat(),
        "stato": "da_controllare" if da_controllare else "in_ordine",
        "prossima_scadenza": _norm_sc(scadenze[0]) if scadenze else None,
        "quota_per_fattura": piano.get("quota_per_ogni_fattura") or corr.get("quota_da_accantonare"),
        "da_accantonare_questo_mese": (mensile[0].get("da_accantonare") if mensile else None),
        "fondo_a_fine_mese": (mensile[0].get("fondo_a_fine_mese") if mensile else None),
        "totale_da_versare": piano.get("totale_da_versare"),
        "periodo": piano.get("periodo"),
        "anno": stima.get("anno") or prec.get("anno"),
        "anno_corrente": {
            "ricavi_finora": corr.get("ricavi_finora"),
            "imposta": stima.get("imposta_sostitutiva"),
            "contributi": (stima.get("contributi_previdenziali") or {}).get("totale_contributi"),
            "netto": stima.get("netto_stimato"),
            "pressione": stima.get("pressione_fiscale_su_incassato"),
        },
        "soglia": {
            "ricavi": soglia.get("ricavi_ytd"),
            "previsione": soglia.get("previsione_fine_anno"),
            "limite": soglia.get("soglia_85k"),
            "limite_uscita": soglia.get("soglia_uscita_immediata"),
            "margine": soglia.get("margine_residuo"),
            "livello": soglia.get("livello_rischio", "OK"),
            "messaggio": soglia.get("messaggio", ""),
            "mese_superamento": soglia.get("mese_stimato_superamento"),
        },
        "profilo": {
            "aliquota": aliquota,
            "anni_nel_regime": prof.get("anni_nel_regime"),
            "dal_anno_15": fine_5,
            "codice_ateco": prof.get("codice_ateco"),
            "coefficiente": prof.get("coefficiente"),
            "gestione": prof.get("gestione_previdenziale"),
            "nome_cassa": prof.get("nome_cassa"),
        },
        "scadenze": [_norm_sc(s) for s in scadenze],
        "mensile": [{"mese": m.get("mese"), "fondo": m.get("fondo_a_fine_mese"),
                     "da_accantonare": m.get("da_accantonare"), "in_uscita": m.get("in_uscita"),
                     "scoperto": m.get("scoperto")} for m in mensile],
        "avvisi": avvisi,
        "cose_da_fare": cose,
        "link_professionista": link_prof,
        "disclaimer": quadro.get("disclaimer", ""),
    }


def crea_dashboard(scheda_utente: dict, accantonamento_attuale: float = 0.0,
                   id_dashboard: str | None = None) -> dict:
    """Crea (o, con id_dashboard, aggiorna) la dashboard. Dal colloquio web l'id e' quello del colloquio."""
    dati = costruisci(scheda_utente, accantonamento_attuale)
    if "errore" in dati:
        return dati
    id_dashboard = id_dashboard or _nuovo_id()
    db.salva_dashboard(id_dashboard, dati)
    return {"id_dashboard": id_dashboard, "link_dashboard": f"{PUBLIC_URL}/d/{id_dashboard}",
            "stato": dati["stato"]}


def dati_dashboard(id_dashboard: str) -> dict | None:
    return db.carica_dashboard(id_dashboard)


def dati_pubblici(id_dashboard: str) -> dict | None:
    """Quello che la pagina puo' vedere: tutto tranne i campi interni (che iniziano con '_')."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return None
    pubblici = {k: v for k, v in dati.items() if not k.startswith("_")}
    pubblici["registrato"] = bool(dati.get("_email"))
    pubblici["fic_collegata"] = False
    if dati.get("_email"):
        try:
            pubblici["fic_collegata"] = bool(db.carica_fic_token(dati["_email"]))
        except Exception:
            pass
    pubblici["chat_attiva"] = assistente.attiva()
    pubblici["chat_limite"] = assistente.LIMITE_UTENTE
    return pubblici


def _ricostruisci(id_dashboard: str, dati_vecchi: dict, scheda_utente: dict) -> dict:
    """Rifa' la dashboard dalla scheda aggiornata, tenendo l'email di chi l'ha gia' salvata."""
    nuovi = costruisci(scheda_utente, 0.0)
    if "errore" in nuovi:
        return nuovi
    if dati_vecchi.get("_email"):
        nuovi["_email"] = dati_vecchi["_email"]
    db.salva_dashboard(id_dashboard, nuovi)
    return nuovi


# ---------------------------------------------------------------- azioni dalla pagina

_ULTIMO_INVIO: dict[str, float] = {}


def manda_codice(id_dashboard: str, email: str) -> dict:
    """Primo passo del 'salva e ricevi avvisi': manda il codice a 6 cifre all'email indicata."""
    if db.carica_dashboard(id_dashboard) is None:
        return {"ok": False, "errore": "Pagina non trovata."}
    ora = time.time()
    if ora - _ULTIMO_INVIO.get(id_dashboard, 0) < 30:
        return {"ok": False, "errore": "Aspetta qualche secondo prima di chiedere un altro codice."}
    _ULTIMO_INVIO[id_dashboard] = ora
    try:
        auth.manda_codice(email)
    except ValueError:
        return {"ok": False, "errore": "Questa email non sembra valida."}
    except Exception:
        return {"ok": False, "errore": "Non riesco a mandare l'email in questo momento. Riprova tra poco."}
    return {"ok": True}


def conferma_codice(id_dashboard: str, email: str, codice: str) -> dict:
    """Secondo passo: verifica il codice e salva la scheda sotto quell'email. Restituisce anche
    'nuovo' (primo salvataggio) e la scheda, perche' chi chiama possa tracciare e avvisare."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return {"ok": False, "errore": "Pagina non trovata."}
    try:
        auth.verifica_codice(email, codice)
    except ValueError:
        return {"ok": False, "errore": "Codice sbagliato o scaduto. Controlla anche lo spam o chiedine uno nuovo."}
    scheda_utente = dati.get("_scheda") or {}
    email = email.strip().lower()
    try:
        nuovo = db.salva_scheda(email, scheda_utente)
        db.imposta_dashboard_utente(email, id_dashboard)
        dati["_email"] = email
        db.salva_dashboard(id_dashboard, dati)
    except Exception:
        return {"ok": False, "errore": "Non riesco a salvare in questo momento. Riprova tra poco."}
    return {"ok": True, "nuovo": bool(nuovo), "scheda": scheda_utente, "email": email}


def aggiorna_luogo(id_dashboard: str, regione: str) -> dict | None:
    """L'utente indica la regione (menu a tendina): si rifa' la dashboard con i bandi di quella zona."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return None
    reg = agevolazioni.regione_da_dati(regione, "")
    if not reg:
        return {"errore": "Regione non riconosciuta."}
    scheda_utente = dict(dati.get("_scheda") or {})
    scheda_utente["regione"] = reg
    nuovi = _ricostruisci(id_dashboard, dati, scheda_utente)
    if "errore" in nuovi:
        return nuovi
    return dati_pubblici(id_dashboard)


def _importo(v) -> float | None:
    try:
        n = float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 10_000_000 else None


def aggiorna_numeri(id_dashboard: str, ricavi_corrente=None, ricavi_precedente=None) -> dict | None:
    """L'utente aggiorna quanto ha incassato: si ricalcola tutto. Se ha gia' salvato l'email,
    si aggiorna anche la scheda salvata."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return None
    scheda_utente = dict(dati.get("_scheda") or {})
    cambiati = 0
    for chiave, valore in (("ricavi_anno_corrente", ricavi_corrente), ("ricavi_anno_precedente", ricavi_precedente)):
        if valore in (None, ""):
            continue
        n = _importo(valore)
        if n is None:
            return {"errore": "Scrivi un importo valido (solo cifre)."}
        scheda_utente[chiave] = int(round(n))
        cambiati += 1
    if not cambiati:
        return {"errore": "Scrivi almeno un importo."}
    nuovi = _ricostruisci(id_dashboard, dati, scheda_utente)
    if "errore" in nuovi:
        return nuovi
    if dati.get("_email"):
        try:
            db.salva_scheda(dati["_email"], scheda_utente)
        except Exception as e:
            print(f"scheda utente non aggiornata: {e}")
    return dati_pubblici(id_dashboard)


# ---------------------------------------------------------------- strumento di fatturazione e Fatture in Cloud

def imposta_strumento(id_dashboard: str, valore: str) -> dict | None:
    """Memorizza quale strumento usa l'utente per fatturare ('' = cancella la scelta)."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return None
    valore = (valore or "").strip()
    if valore and valore not in STRUMENTI_FATTURE:
        return {"errore": "Scelta non riconosciuta."}
    scheda_utente = dict(dati.get("_scheda") or {})
    if valore:
        scheda_utente["strumento_fatturazione"] = valore
    else:
        scheda_utente.pop("strumento_fatturazione", None)
    nuovi = _ricostruisci(id_dashboard, dati, scheda_utente)
    if "errore" in nuovi:
        return nuovi
    if dati.get("_email"):
        try:
            db.salva_scheda(dati["_email"], scheda_utente)
        except Exception as e:
            print(f"scheda utente non aggiornata: {e}")
    return dati_pubblici(id_dashboard)


def fic_link(id_dashboard: str) -> str | None:
    """Link per autorizzare Fatture in Cloud (solo se la pagina ha un'email salvata e verificata)."""
    dati = db.carica_dashboard(id_dashboard)
    email = (dati or {}).get("_email")
    if not email:
        return None
    imposta_strumento(id_dashboard, "fatture_in_cloud")
    return fic.link_autorizzazione(email)


def fic_importa(id_dashboard: str, company_id=None) -> dict:
    """Legge gli incassi di quest'anno e dell'anno scorso da Fatture in Cloud e li restituisce SENZA
    salvarli: l'utente li controlla e conferma con 'Aggiorna' (mai sovrascrivere in silenzio)."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return {"ok": False, "errore": "Pagina non trovata."}
    email = dati.get("_email")
    if not email:
        return {"ok": False, "errore": "Salva prima la tua email."}
    try:
        token = fic.token_valido(email)
        if not token:
            return {"ok": False, "errore": "Collegamento a Fatture in Cloud non trovato: collegalo di nuovo."}
        if company_id:
            db.imposta_azienda_fic(email, int(company_id), "")
        coll = db.carica_fic_token(email) or {}
        if not coll.get("company_id"):
            aziende = fic.lista_aziende(token)
            if len(aziende) == 1:
                db.imposta_azienda_fic(email, aziende[0]["id"], aziende[0].get("name", ""))
            elif len(aziende) > 1:
                return {"ok": False, "scegli_azienda": [{"id": a["id"], "nome": a.get("name", "")} for a in aziende]}
            else:
                return {"ok": False, "errore": "Nessuna azienda trovata su questo account Fatture in Cloud."}
            coll = db.carica_fic_token(email) or {}
        anno = date.today().year
        cur = fic.fatture_incassate_anno(token, coll["company_id"], anno)
        prec = fic.fatture_incassate_anno(token, coll["company_id"], anno - 1)
    except Exception as e:
        print(f"fic_importa fallito: {e}")
        return {"ok": False, "errore": "Non riesco a leggere le fatture in questo momento. Riprova tra poco."}
    return {"ok": True, "anno": anno, "corrente": round(cur["ricavi_incassati_stimati"]),
            "precedente": round(prec["ricavi_incassati_stimati"]),
            "fatture": cur.get("fatture_esaminate", 0) + prec.get("fatture_esaminate", 0)}


# ---------------------------------------------------------------- cancellazione dei dati

_ULTIMA_CANCELLAZIONE: dict[str, float] = {}


def _maschera(email: str) -> str:
    nome, _, dominio = email.partition("@")
    return (nome[:1] + "***@" + dominio) if nome else email


def cancella_richiedi(id_dashboard: str) -> dict:
    """Primo passo. Se la pagina ha un'email salvata, manda un codice a quell'email (solo il suo
    proprietario puo' cancellare); se non ha email, basta la conferma sulla pagina."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return {"ok": False, "errore": "Pagina non trovata."}
    email = dati.get("_email")
    if not email:
        return {"ok": True, "serve_codice": False}
    ora = time.time()
    if ora - _ULTIMA_CANCELLAZIONE.get(id_dashboard, 0) < 30:
        return {"ok": False, "errore": "Aspetta qualche secondo prima di chiedere un altro codice."}
    _ULTIMA_CANCELLAZIONE[id_dashboard] = ora
    try:
        auth.manda_codice(email)
    except Exception:
        return {"ok": False, "errore": "Non riesco a mandare l'email in questo momento. Riprova tra poco."}
    return {"ok": True, "serve_codice": True, "email": _maschera(email)}


def cancella_conferma(id_dashboard: str, codice: str = "") -> dict:
    """Secondo passo: cancella davvero tutto (dashboard, scheda, email, chat, collegamenti)."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return {"ok": False, "errore": "Pagina non trovata."}
    email = dati.get("_email")
    if email:
        try:
            auth.verifica_codice(email, codice)
        except ValueError:
            return {"ok": False, "errore": "Codice sbagliato o scaduto. Controlla anche lo spam o chiedine uno nuovo."}
    try:
        db.cancella_dati(email, id_dashboard)
    except Exception as e:
        print(f"cancellazione fallita: {e}")
        return {"ok": False, "errore": "Non riesco a cancellare in questo momento. Riprova tra poco."}
    return {"ok": True}


# ---------------------------------------------------------------- rientro con l'email ("Accedi")

_ULTIMO_ACCESSO: dict[str, float] = {}


def accedi_manda_codice(email: str) -> dict:
    """Manda il codice solo se esiste un profilo con questa email, ma risponde sempre allo stesso
    modo: la pagina non deve rivelare chi e' registrato."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "errore": "Questa email non sembra valida."}
    ora = time.time()
    if ora - _ULTIMO_ACCESSO.get(email, 0) < 30:
        return {"ok": False, "errore": "Aspetta qualche secondo prima di chiedere un altro codice."}
    _ULTIMO_ACCESSO[email] = ora
    try:
        if db.carica_scheda(email) is not None:
            auth.manda_codice(email)
    except Exception:
        return {"ok": False, "errore": "Non riesco a mandare l'email in questo momento. Riprova tra poco."}
    return {"ok": True}


def accedi_conferma(email: str, codice: str) -> dict:
    """Verifica il codice e restituisce il percorso della dashboard dell'utente, aggiornata ad oggi
    (stessa pagina di prima se esiste, altrimenti nuova, ad esempio per chi si e' registrato dalla chat)."""
    email = (email or "").strip().lower()
    try:
        auth.verifica_codice(email, codice)
    except ValueError:
        return {"ok": False, "errore": "Codice sbagliato o scaduto. Controlla anche lo spam o chiedine uno nuovo."}
    try:
        scheda_utente = db.carica_scheda(email)
        if scheda_utente is None:
            return {"ok": False, "errore": "Non trovo un profilo con questa email: inizia da capo, ci vogliono 2 minuti."}
        id_dashboard = db.dashboard_di_utente(email) or _nuovo_id()
        nuovi = costruisci(scheda_utente, 0.0)
        if "errore" in nuovi:
            return {"ok": False, "errore": "Il profilo salvato e' incompleto: rifai il colloquio per aggiornarlo."}
        nuovi["_email"] = email
        db.salva_dashboard(id_dashboard, nuovi)
        db.imposta_dashboard_utente(email, id_dashboard)
    except Exception:
        return {"ok": False, "errore": "Non riesco ad aprire il tuo profilo in questo momento. Riprova tra poco."}
    return {"ok": True, "dashboard": f"/d/{id_dashboard}"}


def link_calendario(id_dashboard: str) -> str | None:
    """Genera al volo il file calendario (.ics) con le scadenze e restituisce il suo link breve."""
    dati = db.carica_dashboard(id_dashboard)
    if dati is None:
        return None
    piano = S.piano_pagamenti(dati.get("_scheda") or {}, "", 0.0)
    if "errore" in piano:
        return None
    eventi = calendario.eventi_dal_piano(piano, True)
    if not eventi:
        return None
    return calendario.link_calendario(eventi)["link_calendario"]


PAGINA_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>La tua situazione - TaxScan</title>
<style>
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{
  color-scheme:light;
  --bg:#eef2f8; --surface:#ffffff; --line:#d8e2ed; --track:#d8e2ed;
  --ink:#122452; --ink2:#3d4a73; --ink3:#6b7599;
  --accent:#4355cc; --accent-ink:#4355cc; --accent-soft:#e8ebfa;
  --good:#0ca30c; --good-ink:#087308; --warn:#efac35; --warn-ink:#8a5a00; --serious:#ec835a; --crit:#d03b3b;
  --hl-bg:#122452; --hl-ink:#ffffff; --hl-ink2:#c9d3ec; --hl-btn:#05d5c8; --hl-btn-ink:#122452; --hl-line:#2c3f77;
  --f-tit:"Rethink Sans","Poppins",system-ui,sans-serif; --f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --bg:#0a1330; --surface:#122452; --line:#25397a; --track:#25397a;
    --ink:#ffffff; --ink2:#c9d3ec; --ink3:#93a1cc;
    --accent:#5566dd; --accent-ink:#a6b4ff; --accent-soft:#1c3070;
    --good-ink:#5bd65b; --warn-ink:#efac35;
    --hl-bg:#05d5c8; --hl-ink:#122452; --hl-ink2:#1d3a5c; --hl-btn:#122452; --hl-btn-ink:#ffffff; --hl-line:#0aa89e;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#0a1330; --surface:#122452; --line:#25397a; --track:#25397a;
  --ink:#ffffff; --ink2:#c9d3ec; --ink3:#93a1cc;
  --accent:#5566dd; --accent-ink:#a6b4ff; --accent-soft:#1c3070;
  --good-ink:#5bd65b; --warn-ink:#efac35;
  --hl-bg:#05d5c8; --hl-ink:#122452; --hl-ink2:#1d3a5c; --hl-btn:#122452; --hl-btn-ink:#ffffff; --hl-line:#0aa89e;
}
*{box-sizing:border-box;margin:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-txt);
  padding:16px 16px 40px;max-width:640px;margin:0 auto}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin:4px 0 16px}
header>div{min-width:0}
h1{font-family:var(--f-tit);font-size:21px;white-space:nowrap;line-height:1.2;font-weight:700}
.sub{color:var(--ink2);font-size:14px;margin-top:2px}
.chip{flex:none;display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:600;padding:6px 10px;border-radius:999px;
  border:1px solid var(--line);background:var(--surface);white-space:nowrap}
.chip svg{width:14px;height:14px;flex:none}
.chip.ok{color:var(--good-ink)} .chip.ok svg{color:var(--good)}
.chip.chk{color:var(--warn-ink)} .chip.chk svg{color:var(--warn)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:12px}
.eyebrow{font-size:13px;color:var(--ink2);font-weight:600}
.hero .valore{font-family:var(--f-tit);font-size:52px;line-height:1.05;font-weight:700;letter-spacing:-.02em;margin:6px 0 2px}
.hero .quando{font-size:16px;color:var(--ink)}
.hero .quando b{font-weight:700}
.hero .det{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;color:var(--ink2);font-size:14px}
.hero .det div{display:flex;justify-content:space-between;gap:12px;padding:2px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.grid .card{margin:0;padding:16px}
.tile .valore{font-family:var(--f-tit);font-size:28px;font-weight:700;line-height:1.1;margin:6px 0 2px;letter-spacing:-.01em}
.tile .nota{font-size:13px;color:var(--ink2)}
h2{font-family:var(--f-tit);font-size:17px;font-weight:700;margin-bottom:2px}
.lead{font-size:14px;color:var(--ink2);margin-bottom:14px}
/* misuratore soglia */
.meter{position:relative;height:14px;border-radius:7px;background:var(--track);margin:30px 0 30px}
.meter .fill{position:absolute;left:0;top:0;bottom:0;border-radius:7px;background:var(--accent);min-width:4px}
.meter .fill.warn{background:var(--warn)} .meter .fill.crit{background:var(--crit)}
.tick{position:absolute;top:-6px;bottom:-6px;width:2px;background:var(--ink)}
.tick span{position:absolute;white-space:nowrap;font-size:12px;color:var(--ink2);left:50%;transform:translateX(-50%)}
.tick.top span{bottom:100%;margin-bottom:3px} .tick.bot span{top:100%;margin-top:3px}
.tick.right span{left:auto;right:0;transform:none}
.tick.fc{background:var(--ink3);width:0;border-left:2px dashed var(--ink3)}
.stato{display:flex;gap:8px;align-items:flex-start;font-size:14px;margin-top:4px}
.stato svg{width:18px;height:18px;flex:none;margin-top:1px}
.stato.ok svg{color:var(--good)} .stato.warn svg{color:var(--warn)} .stato.crit svg{color:var(--crit)}
.kv{display:flex;justify-content:space-between;gap:12px;font-size:14px;color:var(--ink2);padding-top:10px;margin-top:10px;border-top:1px solid var(--line)}
.kv b{color:var(--ink);font-weight:600}
/* barre mensili */
.bars{display:flex;align-items:flex-end;gap:4px;height:150px;margin:8px 0 0}
.bar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:stretch;height:100%;cursor:pointer;
  background:none;border:0;padding:0;font:inherit;color:inherit;-webkit-tap-highlight-color:transparent}
.bar i{display:block;background:var(--accent);border-radius:4px 4px 0 0;min-height:2px}
.bar.sel i{outline:2px solid var(--ink);outline-offset:1px}
.bar.out i{background:var(--accent-ink)}
.bar em{font-style:normal;font-size:10px;color:var(--ink2);text-align:center;margin-top:4px;height:12px;overflow:hidden}
.legenda{display:flex;gap:14px;font-size:12px;color:var(--ink2);margin-top:8px;flex-wrap:wrap}
.legenda span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.legenda .a::before{background:var(--accent)} .legenda .b::before{background:var(--accent-ink)}
.dettaglio{margin-top:12px;padding:12px;border-radius:12px;background:var(--accent-soft);font-size:14px;min-height:64px}
.dettaglio b{font-weight:700}
details{margin-top:10px;font-size:14px;color:var(--ink2)}
details summary{cursor:pointer;color:var(--accent-ink);font-weight:600}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
th,td{padding:6px 4px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left}
/* scadenze */
.sc{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line)}
.sc:first-of-type{border-top:0;padding-top:4px}
.data{flex:none;width:52px;text-align:center;border-radius:10px;background:var(--accent-soft);padding:6px 0;color:var(--accent-ink)}
.data b{display:block;font-size:20px;line-height:1.1}
.data span{font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.sc .t{font-weight:600}
.sc .imp{margin-left:auto;font-weight:700;white-space:nowrap}
.sc .d{font-size:13px;color:var(--ink2)}
.sc .g{font-size:13px;color:var(--ink3)}
/* avvisi e cose da fare */
.av{display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--line);font-size:14px}
.av:first-of-type{border-top:0;padding-top:2px}
.av svg{width:18px;height:18px;flex:none;margin-top:2px}
.av .l{font-size:12px;font-weight:700}
.av.importante svg,.av.importante .l{color:var(--crit)}
.av.attenzione svg,.av.attenzione .l{color:var(--warn-ink)}
.av.informativo svg,.av.informativo .l{color:var(--accent-ink)}
.av .tt{font-weight:600}
.av .tx{color:var(--ink2)}
ul.todo{list-style:none;padding:0}
ul.todo li{display:flex;gap:10px;padding:8px 0;border-top:1px solid var(--line);font-size:14px}
ul.todo li:first-child{border-top:0}
ul.todo li::before{content:"";flex:none;width:18px;height:18px;border:2px solid var(--ink3);border-radius:5px;margin-top:1px}
.btn{display:block;text-align:center;margin-top:12px;padding:12px;border-radius:12px;background:var(--accent);color:#fff;font-weight:600;text-decoration:none}
.campo{width:100%;padding:12px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;margin-bottom:8px}
.btn.sec{background:var(--accent-soft);color:var(--accent-ink)}
.card.hl{background:var(--hl-bg);color:var(--hl-ink);border-color:var(--hl-bg);border-radius:0;padding:22px 20px;
  clip-path:polygon(0 0,calc(100% - 34px) 0,100% 34px,100% 100%,0 100%)}
.card.hl h2{color:var(--hl-ink);font-size:20px}
.card.hl .lead,.card.hl .stato,.card.hl p{color:var(--hl-ink2)}
.card.hl b{color:var(--hl-ink)}
.card.hl a{color:var(--hl-ink);text-decoration:underline}
.card.hl .campo{background:#fff;color:#122452;border-color:transparent}
.card.hl .btn{background:var(--hl-btn);color:var(--hl-btn-ink)}
.card.hl .stato.ok svg{color:var(--hl-btn)}
.card.hl .msg{color:var(--hl-ink)}
.card.hl .lbl{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 8px;background:var(--hl-btn);color:var(--hl-btn-ink);margin-bottom:8px}
button.btn{width:100%;border:0;font:inherit;font-weight:600;cursor:pointer}
.msg{font-size:13px;color:var(--ink2);margin-top:8px;min-height:18px}
.msg.err{color:var(--crit)}
.lk{display:block;padding:10px 0;border-top:1px solid var(--line);font-size:14px;color:var(--accent-ink);text-decoration:none;font-weight:600}
.lk small{display:block;color:var(--ink2);font-weight:400;font-size:12px}
.sub2{font-size:13px;font-weight:700;color:var(--ink2);margin:14px 0 2px}
.cur{padding:10px 0;border-top:1px solid var(--line);font-size:14px}
.cur b{display:block}
.by{font-size:12px;color:var(--ink3);margin-top:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.by a{display:inline-flex;align-items:center;color:var(--ink2);font-weight:700;text-decoration:none}
.by img{height:20px;width:auto}
.by{padding-bottom:84px}
.board{display:flex;flex-direction:column}
.colL,.colR{display:contents}
@media (min-width:900px){
  body{max-width:1120px;padding:24px 28px 56px}
  .board{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:0 20px;align-items:start}
  .colL,.colR{display:block;min-width:0}
  h1{font-size:26px}
  .hero .valore{font-size:64px}
}
.fab{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:20;border:0;border-radius:999px;padding:14px 18px;background:var(--accent);color:#fff;font:inherit;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,.25);cursor:pointer;display:flex;gap:8px;align-items:center}
.fab svg{width:18px;height:18px}
.chat{position:fixed;left:0;right:0;bottom:0;z-index:30;margin:0 auto;max-width:640px;height:min(82vh,640px);background:var(--surface);border:1px solid var(--line);border-bottom:0;border-radius:18px 18px 0 0;box-shadow:0 -8px 30px rgba(0,0,0,.25);display:flex;flex-direction:column}
.chat.nascosto{display:none}
.chat header{display:flex;justify-content:space-between;align-items:center;margin:0;padding:14px 16px;border-bottom:1px solid var(--line)}
.chat header b{font-size:16px}.chat header small{display:block;color:var(--ink2);font-size:12px;font-weight:400}
.chat header button{border:0;background:none;color:var(--ink2);font-size:26px;line-height:1;cursor:pointer;padding:0 4px}
.msgs{flex:1;overflow-y:auto;padding:14px 16px;display:flex;flex-direction:column;gap:10px}
.m{max-width:88%;padding:10px 13px;border-radius:14px;font-size:15px;line-height:1.45;word-wrap:break-word}
.m.u{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:4px}
.m.a{align-self:flex-start;background:var(--accent-soft);border-bottom-left-radius:4px}
.m.a a{color:var(--accent-ink);word-break:break-all}
.m.a .fonti{margin-top:8px;font-size:12px;color:var(--ink2)}
.m.pensa{color:var(--ink2);font-style:italic}
.chips{display:flex;flex-wrap:wrap;gap:8px;padding:0 16px 8px}
.chips button{border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:999px;padding:8px 12px;font:inherit;font-size:13px;cursor:pointer}
.chat form{display:flex;gap:8px;padding:10px 16px 6px}
.chat form input{flex:1;padding:12px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;min-width:0}
.chat form button{border:0;border-radius:12px;padding:0 16px;background:var(--accent);color:#fff;font:inherit;font-weight:700;cursor:pointer}
.chat .nota{font-size:11px;color:var(--ink3);padding:0 16px calc(10px + env(safe-area-inset-bottom));line-height:1.4}
.foot{font-size:12px;color:var(--ink3);margin-top:18px;line-height:1.5}
.foot b{color:var(--ink2)}
.err{padding:40px 8px;text-align:center;color:var(--ink2)}
@media (max-width:360px){.hero .valore{font-size:44px}.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div id="app"><div class="err">Carico la tua situazione…</div></div>
<script>
const ID = "{{ID}}";
const MESI = ["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"];
const MESI_LUNGHI = ["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
const ICONE = {
  ok:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="10" cy="10" r="8"/><path d="M6.5 10.5l2.4 2.4 4.6-5"/></svg>',
  warn:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 2.5l8 14H2z"/><path d="M10 8v4M10 14.3v.2"/></svg>',
  info:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="10" cy="10" r="8"/><path d="M10 9v5M10 6.2v.2"/></svg>',
  crit:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="10" cy="10" r="8"/><path d="M7 7l6 6M13 7l-6 6"/></svg>'
};
function h(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function eur(n,dec){if(n==null||isNaN(n))return "–";const t=Number(n).toFixed(dec||0).split(".");return t[0].replace(/\B(?=(\d{3})+(?!\d))/g,".")+(t[1]?","+t[1]:"")+"\u00a0€"}
function dataIt(iso){const [y,m,d]=iso.split("-").map(Number);return {g:d,m:MESI[m-1],mm:MESI_LUNGHI[m-1],a:y}}
function giorni(n){if(n==null)return "";if(n<=0)return "oggi";if(n===1)return "domani";if(n<45)return "tra "+n+" giorni";const m=Math.round(n/30);return "tra circa "+m+" mesi"}

function render(d){
  const app=document.getElementById("app");
  const ok=d.stato==="in_ordine";
  const agg=dataIt(d.aggiornato_il);
  let html='';
  const parts=[]; let colo='h';
  const begin=c=>{if(html)parts.push([colo,html]);html='';colo=c};
  html+='<header><div><h1>'+(d.nome?'Ciao '+h(d.nome):'La tua situazione')+'</h1><div class="sub">'+(d.nome?'Ecco la tua situazione · ':'')+agg.g+' '+agg.mm+' '+agg.a+' · stime</div></div>'
    +'<span class="chip '+(ok?'ok':'chk')+'">'+(ok?ICONE.ok:ICONE.warn)+(ok?'Tutto in ordine':'Da controllare')+'</span></header>';

  begin('l');
  // eroe: prossima scadenza
  const p=d.prossima_scadenza;
  if(p){
    const dt=dataIt(p.data);
    html+='<section class="card hero"><div class="eyebrow">Prossima scadenza</div>'
      +'<div class="valore">'+eur(p.importo,0)+'</div>'
      +'<div class="quando"><b>'+dt.g+' '+dt.mm+' '+dt.a+'</b> · '+giorni(p.giorni)+' — '+h(p.etichetta)+'</div>';
    if(p.dettaglio&&p.dettaglio.length){html+='<div class="det">'+p.dettaglio.map(x=>'<div><span>'+h(x)+'</span></div>').join('')+'</div>'}
    html+='</section>';
  } else {
    html+='<section class="card hero"><div class="eyebrow">Prossima scadenza</div><div class="valore" style="font-size:30px">Nessuna a breve</div></section>';
  }

  // due tessere
  const ac=d.anno_corrente||{};
  html+='<div class="grid">'
    +'<div class="card tile"><div class="eyebrow">Da ogni fattura incassata</div><div class="valore">'+h(d.quota_per_fattura||"–")+'</div><div class="nota">metti da parte questa quota</div></div>'
    +'<div class="card tile"><div class="eyebrow">Netto stimato '+h(d.anno||"")+'</div><div class="valore">'+eur(ac.netto,0)+'</div><div class="nota">su '+eur(ac.ricavi_finora,0)+' incassati finora</div></div>'
    +'</div>';

  // in parole semplici
  if((d.in_breve||[]).length){
    html+='<section class="card"><h2>In parole semplici</h2>'+d.in_breve.map(x=>'<p style="font-size:14px;color:var(--ink2);margin-top:8px">'+h(x)+'</p>').join('')+'</section>';
  }

  // soglia
  const s=d.soglia||{};
  const lim=s.limite||85000, max=(s.limite_uscita||100000);
  const pct=v=>Math.max(0,Math.min(100,(v/max)*100));
  let sev='ok', ico=ICONE.ok, lab='In regola';
  if(s.livello==="RISCHIO_MEDIO"){sev='warn';ico=ICONE.warn;lab='Attenzione'}
  else if(s.livello==="RISCHIO_ALTO"||s.livello==="SUPERATA_85K"||s.livello==="SUPERATA_USCITA_IMMEDIATA"){sev='crit';ico=ICONE.crit;lab='Rischio'}
  const fillCls=sev==='warn'?'warn':(sev==='crit'?'crit':'');
  html+='<section class="card"><h2>Quanto sei lontano dagli '+eur(lim,0)+'</h2>'
    +'<div class="lead">Oltre questa soglia di ricavi si esce dal forfettario.</div>'
    +'<div class="meter" role="img" aria-label="Ricavi '+eur(s.ricavi,0)+' su '+eur(lim,0)+'">'
    +'<div class="fill '+fillCls+'" style="width:'+pct(s.ricavi||0)+'%"></div>'
    +'<div class="tick top'+(pct(lim)>70?' right':'')+'" style="left:'+pct(lim)+'%"><span>'+eur(lim,0)+'</span></div>'
    +((s.previsione!=null&&s.previsione>0)?'<div class="tick fc bot'+(pct(s.previsione)>70?' right':'')+'" style="left:'+pct(s.previsione)+'%"><span>previsione '+eur(s.previsione,0)+'</span></div>':'')
    +'</div>'
    +'<div class="stato '+sev+'">'+ico+'<div><b>'+lab+'.</b> '+h(s.messaggio)+'</div></div>'
    +'<div class="kv"><span>Incassato finora</span><b>'+eur(s.ricavi,0)+'</b></div>'
    +'<div class="kv" style="border:0;margin-top:0;padding-top:4px"><span>Margine residuo</span><b>'+eur(s.margine,0)+'</b></div>'
    +'</section>';

  // piano mensile
  const mm=d.mensile||[];
  if(mm.length){
    const mx=Math.max(...mm.map(m=>m.fondo||0),1);
    html+='<section class="card"><h2>Quanto mettere da parte, mese per mese</h2>'
      +'<div class="lead">L\'altezza è il fondo che avrai accumulato a fine mese. Tocca una barra per il dettaglio.</div>'
      +'<div class="bars" id="bars">'+mm.map((m,i)=>{
        const nome=(m.mese||"").split(" ")[0].slice(0,3);
        const usc=(m.in_uscita||0)>0;
        return '<button class="bar'+(usc?' out':'')+'" data-i="'+i+'" aria-label="'+h(m.mese)+': fondo '+eur(m.fondo,0)+'">'
          +'<i style="height:'+Math.max(2,((m.fondo||0)/mx)*118)+'px"></i><em>'+h(nome)+'</em></button>'}).join('')+'</div>'
      +'<div class="legenda"><span class="a">Mese di accantonamento</span><span class="b">Mese con un pagamento</span></div>'
      +'<div class="dettaglio" id="dett"></div>'
      +'<details><summary>Vedi come tabella</summary><table><thead><tr><th>Mese</th><th>Da mettere da parte</th><th>Da pagare</th><th>Fondo</th></tr></thead><tbody>'
      +mm.map(m=>'<tr><td>'+h(m.mese)+'</td><td>'+eur(m.da_accantonare,0)+'</td><td>'+eur(m.in_uscita,0)+'</td><td>'+eur(m.fondo,0)+'</td></tr>').join('')
      +'</tbody></table></details></section>';
  }

  begin('r');
  // scadenze
  const sc=d.scadenze||[];
  if(sc.length){
    html+='<section class="card"><h2>Le prossime scadenze</h2><div class="lead">Totale da versare: '+eur(d.totale_da_versare,0)+(d.periodo?' · '+h(d.periodo):'')+'</div>'
      +sc.map(x=>{const dt=dataIt(x.data);
        return '<div class="sc"><div class="data"><b>'+dt.g+'</b><span>'+dt.m+'</span></div><div style="flex:1"><div style="display:flex;gap:8px"><div class="t">'+h(x.etichetta)+'</div><div class="imp">'+eur(x.importo,0)+'</div></div>'
          +(x.dettaglio||[]).map(r=>'<div class="d">'+h(r)+'</div>').join('')+'<div class="g">'+giorni(x.giorni)+'</div></div></div>'}).join('')
      +'<a class="btn sec" href="/d/'+encodeURIComponent(ID)+'/calendario">Metti le scadenze nel calendario del telefono</a></section>';
  }

  begin('r');
  // salva
  const rientro='Per rientrare quando vuoi vai su <b>'+h(location.host)+'</b>, tocca <b>Accedi</b> e scrivi la tua email: ti arriva un codice, niente password da ricordare. Puoi anche salvare questa pagina tra i preferiti.';
  html+='<section class="card hl" id="salva"><span class="lbl">Importante</span><h2>Ritrova tutto quando vuoi</h2>'
    +(d.registrato
      ? '<div class="stato ok">'+ICONE.ok+'<div><b>La tua situazione è salvata.</b> '+rientro+'</div></div>'
      : '<div class="lead">Salva la tua situazione con la tua email: la ritrovi quando vuoi, aggiorni i numeri e ti scriviamo se cambia una norma che ti riguarda. Niente password: ti mandiamo un codice.</div>'
        +'<p class="lead" style="font-size:13px;margin-top:0">Ti scriveremo solo promemoria sulle tue scadenze e un riepilogo al mese, e puoi disiscriverti con un clic. Scrivendo la tua email accetti l\'<a href="/privacy" target="_blank" rel="noopener">informativa privacy</a>.</p>'
        +'<div id="salva-box"><input class="campo" id="em" type="email" inputmode="email" autocomplete="email" placeholder="La tua email"><button class="btn" id="em-ok" style="margin-top:0">Ricevi il codice</button><p class="msg" id="em-msg"></p></div>')
    +'</section>';

  begin('r');
  // aggiorna i numeri
  const nu=d.numeri||{};
  html+='<section class="card"><h2>Aggiorna i tuoi numeri</h2><div class="lead">Hai incassato altro dall\'ultima volta? Aggiorna e rifaccio i conti.</div>'
    +'<div class="sub2" style="margin-top:0">Incassato quest\'anno (€)</div><input class="campo" id="n-corr" inputmode="numeric" value="'+h(nu.ricavi_anno_corrente==null?'':nu.ricavi_anno_corrente)+'">'
    +'<div class="sub2" style="margin-top:0">Incassato l\'anno scorso (€)</div><input class="campo" id="n-prec" inputmode="numeric" value="'+h(nu.ricavi_anno_precedente==null?'':nu.ricavi_anno_precedente)+'">'
    +'<button class="btn sec" id="n-ok" style="margin-top:0">Aggiorna</button><p class="msg" id="n-msg"></p></section>';

  // come emetti le fatture
  begin('r');
  const SF=[['fatture_in_cloud','Fatture in Cloud'],['aruba','Aruba Fatturazione'],['facile_fattura','Facile Fattura'],['portale_ade','Portale gratuito dell\'Agenzia delle Entrate'],['altro','Un altro programma'],['commercialista','Se ne occupa il mio commercialista']];
  const sf=d.strumento_fatture, sfNome=(SF.find(x=>x[0]===sf)||[])[1];
  html+='<section class="card" id="fatture"><h2>Come emetti le fatture?</h2>';
  if(!sf){
    html+='<div class="lead">Dimmi che strumento usi: se posso, lo collego e leggo gli incassi da solo. Altrimenti ti avviso quando sarà pronto.</div>'
      +SF.map(x=>'<button class="btn sec sf" data-v="'+x[0]+'" style="margin-top:8px">'+h(x[1])+'</button>').join('')+'<p class="msg" id="sf-msg"></p>';
  } else if(sf==='fatture_in_cloud'){
    if(!d.registrato){
      html+='<div class="lead">Hai scelto <b>Fatture in Cloud</b>. Per collegarlo salva prima la tua email, più sotto in «Ritrova tutto quando vuoi».</div><a class="btn sec" href="#salva">Salva la mia email</a>';
    } else if(!d.fic_collegata){
      html+='<div class="lead">Autorizzi TaxScan a <b>leggere</b> le tue fatture emesse. Niente password: lo fai direttamente su Fatture in Cloud.</div><a class="btn" href="/d/'+encodeURIComponent(ID)+'/fic/collega">Collega Fatture in Cloud</a>';
    } else {
      html+='<div class="stato ok">'+ICONE.ok+'<div><b>Fatture in Cloud è collegato.</b> Posso leggere gli incassi al posto tuo.</div></div>'
        +'<button class="btn" id="fic-leggi" style="margin-top:12px">Leggi i miei incassi</button><div id="fic-az"></div><p class="msg" id="fic-msg"></p>';
    }
  } else {
    html+='<div class="lead">Hai scelto: <b>'+h(sfNome||'')+'</b>. Per ora non posso collegarlo: aggiorna i numeri a mano qui sopra. Ti avvisiamo quando sarà pronto.</div>';
  }
  if(sf)html+='<p class="foot" style="margin-top:12px"><a href="#" id="sf-cambia">Cambia scelta</a></p>';
  html+='</section>';

  begin('l');
  // profilo
  const pr=d.profilo||{};
  html+='<section class="card"><h2>Il tuo regime</h2>'
    +'<div class="kv" style="border:0;margin-top:6px;padding-top:0"><span>Aliquota imposta</span><b>'+h(pr.aliquota||"–")+'</b></div>'
    +(pr.dal_anno_15?'<div class="kv" style="border:0;margin-top:0;padding-top:4px"><span>Il 5% vale fino al</span><b>'+(pr.dal_anno_15-1)+'</b></div>':'')
    +'<div class="kv" style="border:0;margin-top:0;padding-top:4px"><span>Coefficiente di redditività</span><b>'+h(pr.coefficiente||"–")+'</b></div>'
    +'<div class="kv" style="border:0;margin-top:0;padding-top:4px"><span>Codice ATECO</span><b>'+h(pr.codice_ateco||"–")+'</b></div>'
    +'</section>';

  // (avvisi restano a sinistra)
  // avvisi
  const av=d.avvisi||[];
  if(av.length){
    const L={importante:["Importante",ICONE.crit],attenzione:["Attenzione",ICONE.warn],informativo:["Da sapere",ICONE.info]};
    html+='<section class="card"><h2>Da tenere d\'occhio</h2>'
      +av.map(a=>{const l=L[a.livello]||L.informativo;
        return '<div class="av '+h(a.livello)+'">'+l[1]+'<div><div class="l">'+l[0]+'</div>'+(a.titolo?'<div class="tt">'+h(a.titolo)+'</div>':'')+'<div class="tx">'+h(a.testo)+'</div></div></div>'}).join('')
      +'</section>';
  }

  begin('r');
  // cose da fare
  const td=d.cose_da_fare||[];
  if(td.length){
    html+='<section class="card"><h2>Cosa fare adesso</h2><ul class="todo">'+td.map(x=>'<li><span>'+h(x)+'</span></li>').join('')+'</ul>'
      +(/^https:\/\//.test(d.link_professionista||'')?'<a class="btn" href="'+h(d.link_professionista)+'" target="_blank" rel="noopener">Parla con un professionista</a>':'')+'</section>';
  }

  begin('l');
  // bandi
  const ag=d.agevolazioni||{}, lg=ag.luogo||{};
  html+='<section class="card" id="bandi"><h2>Bandi e agevolazioni da verificare</h2><div class="lead">'
    +(lg.regione?'Per '+h(lg.regione)+' e il tuo settore. ':'')
    +'Sono spunti, non diritti: requisiti e scadenze vanno controllati sul testo ufficiale e con il commercialista.</div>';
  if(!lg.regione){
    html+='<div class="sub2">In che regione hai la sede?</div><select class="campo" id="reg"><option value="">Scegli la regione</option>'
      +(ag.regioni||[]).map(r=>'<option>'+h(r)+'</option>').join('')+'</select><button class="btn sec" id="reg-ok" style="margin-top:0">Cerca per la mia zona</button><p class="msg" id="reg-msg"></p>';
  }
  if((ag.curati||[]).length){
    html+='<div class="sub2">Selezionati da TaxScan</div>'+ag.curati.map(c=>'<div class="cur"><b>'+h(c.titolo)+'</b>'+h(c.descrizione)
      +(c.scadenza?'<br><small>Scadenza: '+h(c.scadenza)+'</small>':'')
      +(/^https:\/\//.test(c.url_fonte||'')?'<br><a href="'+h(c.url_fonte)+'" target="_blank" rel="noopener" style="color:var(--accent-ink)">Fonte ufficiale</a>':'')+'</div>').join('');
  }
  if((ag.ricerche||[]).length){
    html+='<div class="sub2">Ricerche già pronte per te</div>'+ag.ricerche.map(r=>'<a class="lk" href="'+h(r.url)+'" target="_blank" rel="noopener">'+h(r.testo)+'</a>').join('');
  }
  if((ag.fonti||[]).length){
    html+='<div class="sub2">Dove si pubblicano i bandi ufficiali</div>'+ag.fonti.map(f=>'<a class="lk" href="'+h(f.url)+'" target="_blank" rel="noopener">'+h(f.nome)+'<small>'+h(f.cosa)+'</small></a>').join('');
  }
  html+='</section>';

  begin('r');
  html+='<section class="card" id="dati"><h2>I tuoi dati</h2><div class="lead">Se vuoi, puoi far dimenticare tutto a TaxScan: cancelliamo i tuoi numeri, la tua email e le conversazioni con l\'assistente. Dopo non si può più tornare indietro.</div><p class="lead" style="font-size:13px;margin:0 0 4px"><a href="/privacy">Leggi come trattiamo i tuoi dati</a></p>'
    +'<div id="canc-box"><button class="btn" id="canc-ok" style="margin-top:0;background:transparent;color:var(--ink2);border:1px solid var(--line)">Cancella i miei dati</button><p class="msg" id="canc-msg"></p></div></section>';

  begin('f');
  html+='<p class="foot"><b>Sono stime, non una dichiarazione.</b> TaxScan prepara e spiega; il tuo commercialista controlla e firma. '
    +h(d.disclaimer||"")+'</p>'
    +'<p class="by">TaxScan è un servizio offerto da <a href="https://ltd24.co.uk" target="_blank" rel="noopener"><picture><source srcset="/logo-ltd24-scuro.png" media="(prefers-color-scheme: dark)"><img src="/logo-ltd24.png" alt="LTD24" onerror="this.replaceWith(document.createTextNode(\'LTD24\'))"></picture></a> · <a href="/privacy">Privacy</a></p>';
  begin('x');
  let hh='',LL='',RR='',FF='';
  parts.forEach(([c,t],i)=>{const w='<div class="pt" style="order:'+i+'">'+t+'</div>';
    if(c==='h')hh+=t;else if(c==='l')LL+=w;else if(c==='r')RR+=w;else FF+=t});
  app.innerHTML=hh+'<div class="board"><div class="colL">'+LL+'</div><div class="colR">'+RR+'</div></div>'+FF;
  const post=async(p,b)=>{const r=await fetch('/api/dashboard/'+encodeURIComponent(ID)+p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});let j={};try{j=await r.json()}catch(e){}return j};
  const msg=(id,t,err)=>{const e=document.getElementById(id);if(e){e.textContent=t;e.className='msg'+(err?' err':'')}};
  iniziaChat(d);
  const nOk=document.getElementById('n-ok');
  if(nOk)nOk.onclick=async()=>{const c=document.getElementById('n-corr').value.trim(),pr=document.getElementById('n-prec').value.trim();
    msg('n-msg','Rifaccio i conti…');const j=await post('/numeri',{ricavi_corrente:c,ricavi_precedente:pr});
    if(j&&j.agevolazioni){render(j);window.scrollTo({top:0})}else msg('n-msg',(j&&j.errore)||'Non ci sono riuscito, riprova.',true)};
  const regOk=document.getElementById('reg-ok');
  if(regOk)regOk.onclick=async()=>{const v=document.getElementById('reg').value;if(!v)return msg('reg-msg','Scegli una regione.',true);
    msg('reg-msg','Cerco…');const j=await post('/luogo',{regione:v});if(j&&j.agevolazioni){render(j);const bb=document.getElementById('bandi');if(bb)bb.scrollIntoView()}else msg('reg-msg',(j&&j.errore)||'Non ci sono riuscito, riprova.',true)};
  const emOk=document.getElementById('em-ok');
  if(emOk)emOk.onclick=async()=>{const email=document.getElementById('em').value.trim();
    if(!/^\S+@\S+\.\S+$/.test(email))return msg('em-msg','Scrivi un\'email valida.',true);
    msg('em-msg','Ti mando il codice…');const j=await post('/email',{email});
    if(!j.ok)return msg('em-msg',j.errore||'Non ci sono riuscito.',true);
    document.getElementById('salva-box').innerHTML='<p class="lead" style="margin-bottom:8px">Ti ho scritto a <b>'+h(email)+'</b>. Inserisci il codice di 6 cifre (guarda anche nello spam).</p>'
      +'<input class="campo" id="cod" inputmode="numeric" maxlength="6" placeholder="Codice" autocomplete="one-time-code"><button class="btn" id="cod-ok" style="margin-top:0">Conferma</button><p class="msg" id="cod-msg"></p>';
    document.getElementById('cod-ok').onclick=async()=>{const codice=document.getElementById('cod').value.trim();
      msg('cod-msg','Controllo…');const r=await post('/codice',{email,codice});
      if(r.ok)document.getElementById('salva-box').innerHTML='<div class="stato ok">'+ICONE.ok+'<div><b>Fatto.</b> La tua situazione è salvata con '+h(email)+'. '+rientro+'</div></div>';
      else msg('cod-msg',r.errore||'Codice non valido.',true)}};

  const cancOk=document.getElementById('canc-ok');
  if(cancOk)cancOk.onclick=()=>{
    document.getElementById('canc-box').innerHTML='<p class="lead" style="margin-bottom:8px"><b>Sei sicuro?</b> Cancelliamo la tua situazione, l\'email, le conversazioni con l\'assistente e i promemoria. Non si può annullare.</p>'
      +'<button class="btn" id="canc-si" style="margin-top:0;background:var(--crit)">Sì, cancella tutto</button><button class="btn" id="canc-no" style="background:transparent;color:var(--ink2);border:1px solid var(--line)">Annulla</button><p class="msg" id="canc-msg"></p>';
    document.getElementById('canc-no').onclick=()=>render(d);
    document.getElementById('canc-si').onclick=async()=>{
      msg('canc-msg','Un attimo…');const j=await post('/cancella/richiedi',{});
      if(!j.ok)return msg('canc-msg',j.errore||'Non ci sono riuscito, riprova.',true);
      const fine=()=>{app.innerHTML='<section class="card" style="margin-top:24px"><h2>Fatto</h2><div class="lead">Abbiamo cancellato i tuoi dati. Se vuoi ricominciare, <a href="/">torna alla home</a>.</div></section>';window.scrollTo({top:0})};
      if(!j.serve_codice){const r=await post('/cancella/conferma',{});return r.ok?fine():msg('canc-msg',r.errore||'Non ci sono riuscito.',true)}
      document.getElementById('canc-box').innerHTML='<p class="lead" style="margin-bottom:8px">Per sicurezza ti ho scritto un codice a <b>'+h(j.email)+'</b>. Inseriscilo per confermare la cancellazione.</p>'
        +'<input class="campo" id="canc-cod" inputmode="numeric" maxlength="6" placeholder="Codice" autocomplete="one-time-code"><button class="btn" id="canc-cod-ok" style="margin-top:0;background:var(--crit)">Cancella tutto</button><p class="msg" id="canc-msg"></p>';
      document.getElementById('canc-cod-ok').onclick=async()=>{msg('canc-msg','Controllo…');
        const r=await post('/cancella/conferma',{codice:document.getElementById('canc-cod').value.trim()});
        r.ok?fine():msg('canc-msg',r.errore||'Codice non valido.',true)}}};

  document.querySelectorAll('.sf').forEach(b=>b.onclick=async()=>{msg('sf-msg','Un attimo…');const j=await post('/strumento',{valore:b.dataset.v});
    if(j&&j.agevolazioni){render(j);const f=document.getElementById('fatture');if(f)f.scrollIntoView({block:'center'})}else msg('sf-msg',(j&&j.errore)||'Non ci sono riuscito, riprova.',true)});
  const sfc=document.getElementById('sf-cambia');
  if(sfc)sfc.onclick=async e=>{e.preventDefault();const j=await post('/strumento',{valore:''});if(j&&j.agevolazioni)render(j)};
  async function leggiFic(az){
    msg('fic-msg','Leggo le tue fatture…');
    const j=await post('/fic/importa',az?{company_id:az}:{});
    if(j.scegli_azienda){document.getElementById('fic-az').innerHTML='<div class="lead" style="margin-top:10px">Quale azienda?</div>'+j.scegli_azienda.map(a=>'<button class="btn sec az" data-id="'+h(a.id)+'" style="margin-top:6px">'+h(a.nome||('Azienda '+a.id))+'</button>').join('');
      document.querySelectorAll('.az').forEach(b=>b.onclick=()=>leggiFic(b.dataset.id));return msg('fic-msg','')}
    if(!j.ok)return msg('fic-msg',j.errore||'Non ci sono riuscito, riprova.',true);
    document.getElementById('fic-az').innerHTML='';
    document.getElementById('n-corr').value=j.corrente;document.getElementById('n-prec').value=j.precedente;
    msg('fic-msg','Letti da Fatture in Cloud ('+j.fatture+' fatture): '+j.corrente.toLocaleString('it-IT')+' € nel '+j.anno+' e '+j.precedente.toLocaleString('it-IT')+' € l\'anno prima.');
    msg('n-msg','Cifre lette da Fatture in Cloud: controllale e premi «Aggiorna» per confermare.');
    document.getElementById('n-corr').scrollIntoView({block:'center'})}
  const fl=document.getElementById('fic-leggi');if(fl)fl.onclick=()=>leggiFic();
  if(location.search.indexOf('fic=collegato')>=0){history.replaceState(null,'',location.pathname);if(fl)leggiFic()}

  // interazione barre
  const bars=[...document.querySelectorAll(".bar")];
  function sel(i){
    bars.forEach((b,k)=>b.classList.toggle("sel",k===i));
    const m=mm[i]; if(!m)return;
    let t='<b>'+h(m.mese)+'</b><br>Metti da parte <b>'+eur(m.da_accantonare,0)+'</b>';
    if(m.in_uscita>0)t+=' · si paga <b>'+eur(m.in_uscita,0)+'</b>';
    t+='<br>Fondo a fine mese: <b>'+eur(m.fondo,0)+'</b>';
    if(m.scoperto>0)t+='<br>Mancano <b>'+eur(m.scoperto,0)+'</b> per coprire i pagamenti.';
    document.getElementById("dett").innerHTML=t;
  }
  bars.forEach((b,i)=>b.addEventListener("click",()=>sel(i)));
  if(bars.length)sel(0);
}

let chatPronta=false, storia=[], rimaste=null;
function iniziaChat(d){
  if(chatPronta||!d.chat_attiva)return; chatPronta=true; rimaste=d.chat_limite;
  const w=document.createElement('div');
  w.innerHTML='<button class="fab" id="fab" aria-label="Fai una domanda a TaxScan"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4h14v9H8l-4 3.5V13H3z"/></svg>Chiedi a TaxScan</button>'
   +'<div class="chat nascosto" id="chat" role="dialog" aria-label="Assistente TaxScan"><header><div><b>Assistente TaxScan</b><small>Assistente virtuale basato su intelligenza artificiale</small></div><button id="chiudi" aria-label="Chiudi">×</button></header>'
   +'<div class="msgs" id="msgs"></div><div class="chips" id="chips"></div>'
   +'<form id="cf"><input id="ci" maxlength="600" placeholder="Scrivi la tua domanda" autocomplete="off"><button type="submit">Invia</button></form>'
   +'<p class="nota" id="cnota"></p></div>';
  document.body.appendChild(w);
  const $=i=>document.getElementById(i);
  const nota=()=>{$('cnota').textContent='Risposte indicative, non sostituiscono il commercialista. Le domande vengono salvate per migliorare il servizio.'+(rimaste!=null?' Domande rimaste oggi: '+rimaste+'.':'')};
  const lk=t=>h(t).replace(/(https?:\/\/[^\s<)]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>').replace(/\n/g,'<br>');
  const agg=(cl,html)=>{const m=document.createElement('div');m.className='m '+cl;m.innerHTML=html;$('msgs').appendChild(m);$('msgs').scrollTop=$('msgs').scrollHeight;return m};
  const apri=()=>{$('chat').classList.remove('nascosto');$('fab').style.display='none';
    if(!$('msgs').children.length){agg('a','Ciao! Sono l\'assistente virtuale di TaxScan. Posso spiegarti le tue scadenze, quanto mettere da parte e cercare bandi per la tua zona. Cosa vuoi sapere? (Non scrivere dati personali o sensibili: le conversazioni vengono salvate. Informativa su /privacy)');
      $('chips').innerHTML=['Cosa pago a novembre?','Quanto metto da parte?','Rischio di superare gli 85.000 €?','Che bandi ci sono per me?'].map(x=>'<button type="button">'+h(x)+'</button>').join('');
      $('chips').querySelectorAll('button').forEach(b=>b.onclick=()=>invia(b.textContent))}
    nota();$('ci').focus()};
  const chiudi=()=>{$('chat').classList.add('nascosto');$('fab').style.display=''};
  $('fab').onclick=apri;$('chiudi').onclick=chiudi;
  let occupato=false;
  async function invia(testo){
    testo=(testo||'').trim();if(!testo||occupato)return;occupato=true;$('chips').innerHTML='';$('ci').value='';
    agg('u',h(testo));const att=agg('a pensa','Ci penso…');
    try{
      const r=await fetch('/api/dashboard/'+encodeURIComponent(ID)+'/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domanda:testo,storia:storia})});
      const j=await r.json(); att.remove();
      if(j.ok){storia.push({ruolo:'utente',testo:testo},{ruolo:'assistente',testo:j.risposta});storia=storia.slice(-6);rimaste=j.rimaste;
        agg('a',lk(j.risposta)+((j.fonti||[]).length?'<div class="fonti">Fonti: '+j.fonti.map(f=>'<a href="'+h(f.url)+'" target="_blank" rel="noopener">'+h(f.titolo)+'</a>').join(' · ')+'</div>':''))}
      else{if(j.limite)rimaste=0;agg('a',h(j.errore||'Non riesco a rispondere ora.'))}
    }catch(e){att.remove();agg('a','Connessione persa: riprova tra un momento.')}
    nota();occupato=false;
  }
  $('cf').onsubmit=e=>{e.preventDefault();invia($('ci').value)};
}

fetch("/api/dashboard/"+encodeURIComponent(ID)).then(r=>{
  if(!r.ok)throw new Error("nf");return r.json()
}).then(render).catch(()=>{
  document.getElementById("app").innerHTML='<div class="err"><b>Questa pagina non c\'è più.</b><br>Torna su TaxScan e chiedi di nuovo "la mia situazione": ne genero una aggiornata.</div>';
});
</script>
</body>
</html>
"""


def pagina(id_dashboard: str) -> str:
    id_pulito = "".join(c for c in id_dashboard if c.isalnum())[:32]  # l'id finisce dentro uno script
    return PAGINA_HTML.replace("{{ID}}", id_pulito)
