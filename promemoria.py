"""
TaxScan - email all'utente: benvenuto e promemoria.

Obiettivo: l'utente si ricorda di TaxScan al momento giusto, senza essere sommerso.
  - benvenuto: subito dopo il primo salvataggio dell'email (cosa fa TaxScan, cosa riceverai)
  - scadenza: una scadenza fiscale e' vicinissima (2 giorni prima, una volta sola per scadenza)
  - settimanale: UNA email a settimana con tutte le prossime scadenze (e, in fondo, se manca un dato o i
    numeri sono fermi da tempo). Sostituisce il vecchio riepilogo mensile e i promemoria "in sospeso".
  - pensione: una email educativa, una volta sola, sulla previdenza per chi e' in forfettario (vedi pensione.py)

Regole per non dare fastidio: al massimo UNA email per utente per ogni passaggio del cron, il riepilogo
settimanale solo se sono passati almeno 6 giorni dal precedente e 3 dall'ultima altra email (tranne la scadenza
a 2 giorni), ogni email ha il link per disiscriversi con un clic, e ogni email si manda una sola volta
(tabella promemoria_inviati).
Non sono consigli fiscali: sono promemoria e riepiloghi delle stime della dashboard.
"""

import hashlib
import hmac
import html as _html
import os
from datetime import date

import auth
import dashboard
import scheda as S
import dati_fisco as D
import db
import emailtpl
import agevolazioni

PUBLIC_URL = dashboard.PUBLIC_URL
_SEGRETO = (os.environ.get("ADMIN_TOKEN") or os.environ.get("RESEND_API_KEY") or "taxscan").encode()
DISTANZA_MINIMA_GIORNI = 3        # tra il riepilogo settimanale e un'altra email
GIORNI_TRA_RIEPILOGHI = 6        # il riepilogo e' settimanale: almeno 6 giorni dal precedente
PRIMO_RIEPILOGO_DOPO_GIORNI = 7  # il primo arriva una settimana dopo l'iscrizione (prima ci sono benvenuto, bandi, feedback)
ORIZZONTE_SCADENZE_GIORNI = 120  # nel riepilogo si elencano le scadenze dei prossimi 4 mesi
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]


# ---------------------------------------------------------------- disiscrizione

def firma(email: str) -> str:
    return hmac.new(_SEGRETO, (email or "").strip().lower().encode(), hashlib.sha256).hexdigest()[:32]


def firma_valida(email: str, token: str) -> bool:
    return bool(email) and bool(token) and hmac.compare_digest(firma(email), token)


def _link_disiscrizione(email: str) -> str:
    from urllib.parse import quote
    return f"{PUBLIC_URL}/disiscriviti?e={quote(email)}&t={firma(email)}"


# ---------------------------------------------------------------- aspetto dell'email

def _e(x) -> str:
    return _html.escape(str(x if x is not None else ""))


def eur(n) -> str:
    try:
        t = f"{float(n):.0f}"
    except (TypeError, ValueError):
        return "–"
    neg = t.startswith("-")
    t = t.lstrip("-")
    gruppi = []
    while len(t) > 3:
        gruppi.insert(0, t[-3:])
        t = t[:-3]
    gruppi.insert(0, t)
    return ("-" if neg else "") + ".".join(gruppi) + " €"


def _data_it(iso: str) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{d.day} {MESI[d.month - 1]} {d.year}"
    except ValueError:
        return str(iso or "")


def _cornice(email: str, titolo: str, corpo: str, pulsante: tuple[str, str] | None = None) -> str:
    piede = (
        "<p style='font-size:13px;color:#3d4a73;border-top:1px solid #d8e2ed;padding-top:14px;margin-top:26px'>"
        "Le cifre sono stime a scopo informativo, non una consulenza: la responsabilità di ciò che dichiari e paghi è tua. "
        f"Se vuoi farle controllare da un professionista c'è la <a href='{_e(D.CONTATTI['consulenza_gratuita'])}' "
        "style='color:#4355cc'>consulenza gratuita</a>.</p>"
        "<p style='font-size:12px;color:#6b7599'>TaxScan è un servizio offerto da "
        f"<a href='{_e(D.CONTATTI['sito'])}' style='color:#6b7599'>LTD24</a>. "
        f"Non vuoi più ricevere queste email? <a href='{_e(_link_disiscrizione(email))}' "
        f"style='color:#6b7599'>Disiscriviti</a>. <a href='{_e(PUBLIC_URL)}/privacy' style='color:#6b7599'>Privacy</a>.</p>"
    )
    return emailtpl.cornice(titolo, corpo, pulsante, piede)


# ---------------------------------------------------------------- benvenuto

def manda_benvenuto(email: str, id_dashboard: str, nome: str = "", novita: bool = True) -> None:
    nome = S.pulisci_nome(nome)
    link = f"{PUBLIC_URL}/d/{id_dashboard}"
    corpo = (
        (f"<p>Ciao {_e(nome)},</p>" if nome else "") +
        "<p>Grazie per esserti iscritto. D'ora in poi hai un posto dove tenere sotto controllo la tua partita IVA "
        "forfettaria, senza dover capire tutto da solo.</p>"
        "<p><b>Cosa fa TaxScan per te</b></p>"
        "<ul style='padding-left:20px'>"
        "<li>Ti dice <b>quanto mettere da parte</b> da ogni fattura per imposte e contributi.</li>"
        "<li>Ti mostra le <b>prossime scadenze</b> e quanto pagare, e le puoi mettere nel calendario.</li>"
        "<li>Controlla la <b>soglia degli 85.000 €</b> e ti avvisa se ti stai avvicinando.</li>"
        "<li>Cerca <b>bandi e agevolazioni</b> per la tua zona e il tuo settore (da verificare sempre).</li>"
        "<li>Risponde alle tue domande con l'<b>assistente virtuale</b>, basato su intelligenza artificiale.</li>"
        "</ul>"
        "<p><b>Cosa riceverai da noi</b></p>"
        "<ul style='padding-left:20px'>"
        "<li>Un riepilogo <b>una volta a settimana</b> con tutte le prossime scadenze e quanto mettere da parte.</li>"
        "<li>Un avviso in più quando una scadenza è a <b>due giorni</b>.</li>"
        "<li>Un messaggio se cambia una regola importante che ti riguarda.</li>"
        + ("<li>Tra poco, <b>una email</b> con un questionario di 5 minuti per completare la tua situazione (immobili, "
           "altri redditi, pensione) e vedere spunti su misura; più avanti i <b>bandi</b> adatti a te e una email sulla "
           "previdenza.</li>" if novita else "") +
        "<li>Domani, <b>una domanda veloce</b> per sapere com'è andata.</li>"
        "</ul>"
        "<p>Poche email, solo quando servono. Puoi smettere di riceverle quando vuoi dal link in fondo.</p>"
        "<p><b>Per tornare</b> basta il pulsante qui sotto, oppure scrivi la tua email nella pagina "
        f"<a href='{_e(PUBLIC_URL)}/accedi' style='color:#4355cc'>Accedi</a> e ti mandiamo un codice.</p>"
        "<p>Più i tuoi numeri sono aggiornati, più le stime sono precise: ogni tanto aggiorna quanto hai incassato.</p>"
        "<p style='background:#e8ebfa;border-radius:10px;padding:12px 14px;font-size:15px'>TaxScan prepara e spiega: le cifre sono "
        "stime e la responsabilità di ciò che dichiari e paghi è tua. Se hai un dubbio importante o vuoi un controllo, "
        f"<a href='{_e(D.CONTATTI['consulenza_gratuita'])}' style='color:#4355cc'>prenota una consulenza gratuita</a> "
        "con un professionista di LTD24.</p>"
    )
    auth.manda_email(email, (f"Benvenuto {nome} su TaxScan" if nome else "Benvenuto su TaxScan"), _cornice(
        email, (f"Benvenuto {nome} su TaxScan" if nome else "Benvenuto su TaxScan"), corpo, ("Apri la tua situazione", link)))


# ---------------------------------------------------------------- bandi (una volta, dopo l'iscrizione)

def manda_bandi(email: str, id_dashboard: str) -> bool:
    """Una sola email, poco dopo l'iscrizione, con spunti su bandi e finanza agevolata.
    Non promette nulla di specifico: indica dove si pubblicano i bandi ufficiali e come cercarli in TaxScan.
    Restituisce True se l'ha mandata (False se disiscritto o gia' mandata)."""
    email = (email or "").strip().lower()
    if not email or db.email_disattivate(email) or not db.novita_consentite(email):
        return False
    if not db.prenota_promemoria(email, "bandi_intro", "1"):
        return False
    try:
        dati = db.carica_dashboard(id_dashboard) or {}
        scheda = dati.get("_scheda") or {}
        nome = S.pulisci_nome(scheda.get("nome"))
        regione = (scheda.get("regione") or "").strip()
        fonti = "".join(
            f"<li><a href='{_e(f['url'])}' style='color:#4355cc;font-weight:700'>{_e(f['nome'])}</a>: {_e(f['cosa'])}.</li>"
            for f in agevolazioni.FONTI_UFFICIALI)
        corpo = (
            (f"<p>Ciao {_e(nome)},</p>" if nome else "") +
            "<p>Un'ultima cosa utile per chi ha da poco la partita IVA: esistono <b>bandi, contributi e agevolazioni</b> "
            "per nuove attività e lavoratori autonomi, e spesso si scoprono tardi. Non sono diritti automatici: "
            "ognuno ha <b>requisiti e scadenze</b> da controllare.</p>"
            + (f"<p>Hai indicato <b>{_e(regione)}</b>: in TaxScan trovi ricerche già pronte per la tua zona e il tuo settore.</p>"
               if regione else
               "<p>In TaxScan scegli la <b>regione</b> in cui hai la sede e trovi ricerche già pronte per la tua zona e il tuo settore.</p>")
            + "<p><b>Dove si pubblicano i bandi ufficiali</b></p>"
              f"<ul style='padding-left:20px'>{fonti}</ul>"
              "<p style='background:#e8ebfa;padding:12px 14px;font-size:14px'>Sono spunti da verificare, non promesse: prima di "
              "spendere o fare domanda, controlla requisiti e scadenze sul testo ufficiale del bando (o con un professionista).</p>")
        auth.manda_email(email, "TaxScan: bandi e agevolazioni da guardare", _cornice(
            email, "Bandi e agevolazioni da guardare", corpo,
            ("Cerca i bandi per la mia zona", f"{PUBLIC_URL}/d/{id_dashboard}#bandi")))
        try:
            db.registra_evento("bandi_intro_mandato", id_dashboard, {})
        except Exception:
            pass
        return True
    except Exception:
        db.annulla_promemoria(email, "bandi_intro", "1")
        raise


# ---------------------------------------------------------------- nuovi bandi approvati

def bandi_per_utente(scheda: dict, emailgia: set, bandi: list[dict]) -> list[dict]:
    """I bandi pertinenti (settore e regione) per questa scheda, non ancora mandati."""
    scheda = scheda or {}
    codice = str(scheda.get("codice_ateco") or "")
    regione = str(scheda.get("regione") or "")
    return [b for b in bandi if b["id"] not in emailgia
            and db._incentivo_pertinente(b["codici_ateco"], b["regioni"], codice, regione)]


def manda_bandi_nuovi(email: str, id_dashboard: str, scheda: dict, bandi: list[dict]) -> bool:
    """Una email con i bandi nuovi approvati e pertinenti. Segna ogni bando come mostrato a quell'utente."""
    email = (email or "").strip().lower()
    if not bandi or not email or db.email_disattivate(email) or not db.novita_consentite(email):
        return False
    iso = date.today().isocalendar()
    chiave = f"{iso[0]}-W{iso[1]}"
    if not db.prenota_promemoria(email, "bandi_nuovi", chiave):  # al massimo una email sui bandi a settimana
        return False
    nome = S.pulisci_nome((scheda or {}).get("nome"))
    voci = ""
    for b in bandi:
        url = b.get("url_fonte") or ""
        voci += (f"<div style='border-left:4px solid #4355cc;padding:4px 0 4px 12px;margin:14px 0'>"
                 f"<b>{_e(b['titolo'])}</b><br>{_e(b['descrizione'])}"
                 + (f"<br><small>Per chi: {_e(b['requisiti'])}</small>" if b.get("requisiti") else "")
                 + (f"<br><small>Scadenza: {_e(b['scadenza'])}</small>" if b.get("scadenza") else "")
                 + (f"<br><a href='{_e(url)}' style='color:#4355cc;font-weight:700'>Leggi il testo ufficiale</a>"
                    if url.startswith("https://") else "") + "</div>")
    n = len(bandi)
    corpo = ((f"<p>Ciao {_e(nome)},</p>" if nome else "")
             + f"<p>{'Ti segnaliamo un possibile bando' if n == 1 else 'Ti segnaliamo ' + str(n) + ' possibili bandi'} "
               "per il tuo settore e la tua zona.</p>" + voci
             + "<p style='background:#e8ebfa;padding:12px 14px;font-size:14px'>Sono spunti, non diritti: prima di fare "
               "domanda controlla requisiti, importi e scadenze sul testo ufficiale (o con un professionista).</p>")
    try:
        auth.manda_email(email, "TaxScan: " + ("un nuovo bando per te" if n == 1 else f"{n} nuovi bandi per te"),
                         _cornice(email, "Bandi e agevolazioni per te", corpo,
                                  ("Vedi tutti i tuoi bandi", f"{PUBLIC_URL}/d/{id_dashboard}#bandi")))
    except Exception:
        db.annulla_promemoria(email, "bandi_nuovi", chiave)
        raise
    for b in bandi:
        db.segna_incentivo_mostrato(b["id"], email)
    try:
        db.registra_evento("bandi_nuovi_mandati", id_dashboard, {"n": n})
    except Exception:
        pass
    return True


# ---------------------------------------------------------------- previdenza (una volta, informativa)

FONTI_PENSIONE = {
    "covip_costi": "https://www.covip.it/isc_dinamico/",
    "covip_guida": "https://www.covip.it/sites/default/files/guida_introduttiva_alla_previdenza_complementare_0.pdf",
    "forfettari": "https://www.informazionefiscale.it/fondo-pensione-deducibile-regime-forfettario",
}


def _ha_altri_redditi(scheda: dict) -> bool:
    """Lavoro dipendente o pensione: redditi tassati con IRPEF, da cui si possono dedurre i versamenti a un fondo."""
    sit = (scheda or {}).get("situazioni_particolari") or []
    return "dipendente_o_pensione" in sit or ((scheda or {}).get("redditi_dipendente_pensione") or 0) > 0


def corpo_pensione(altri_redditi: bool, nome: str = "") -> str:
    """Testo dell'email sulla previdenza. Informativo e neutro: nessun prodotto, nessun invito a comprare.
    Dati verificati su documenti sul regime fiscale dei fondi pensione (luglio 2026): limite di deduzione 5.300 euro
    dal 2026, rendimenti tassati al 20% (12,5% sui titoli di Stato), prestazioni al 15% fino al 9% dopo 35 anni,
    contributi non dedotti da comunicare al fondo entro il 31 dicembre dell'anno successivo."""
    link = lambda u, t: f"<a href='{_e(u)}' style='color:#4355cc;font-weight:700'>{_e(t)}</a>"
    if altri_redditi:
        deduzione = (
            "<p><b>Nel tuo caso c'è un vantaggio fiscale.</b> Hai indicato anche un lavoro dipendente o una pensione: su quei "
            "redditi paghi l'IRPEF ordinaria, e i versamenti a un fondo pensione si possono <b>dedurre</b> da lì, fino a "
            "<b>5.300 € l'anno</b> (limite in vigore dal 2026). Il risparmio dipende dalla tua aliquota IRPEF: non è un regalo "
            "dello Stato, è un'imposta che si sposta in avanti, perché quando incassi la prestazione paghi una tassa agevolata.</p>")
    else:
        deduzione = (
            "<p><b>La cosa da sapere subito:</b> con la partita IVA forfettaria i versamenti a un fondo pensione "
            "<b>non si deducono</b> dal tuo reddito. Dal reddito forfettario si sottraggono solo i contributi previdenziali "
            f"<i>obbligatori</i> (INPS o cassa). Quindi il risparmio fiscale di cui si parla spesso, per te, in genere non c'è "
            f"({link(FONTI_PENSIONE['forfettari'], 'spiegazione')}). Se in dichiarazione hai anche un lavoro dipendente o una "
            "pensione, invece, la deduzione c'è (fino a 5.300 € l'anno dal 2026), perché quei redditi pagano l'IRPEF ordinaria.</p>")
    return (
        (f"<p>Ciao {_e(nome)},</p>" if nome else "") +
        "<p>Con la partita IVA la pensione dipende da <b>quanti contributi versi all'INPS</b>, e nel regime forfettario "
        "i contributi si calcolano su un reddito ridotto: per questo l'assegno futuro può essere basso. Molti guardano "
        "alla <b>previdenza complementare</b> (i fondi pensione). Ecco cosa c'è di vero, senza titoli gonfiati.</p>"
        + deduzione +
        "<p><b>Cosa resta, anche senza deduzione</b></p>"
        "<ul style='padding-left:20px'>"
        "<li>I <b>rendimenti</b> del fondo sono tassati al <b>20%</b> (12,5% sulla parte in titoli di Stato), invece del 26% "
        "che di solito si paga sui guadagni di fondi comuni ed ETF.</li>"
        "<li>Se versi <b>senza dedurre</b>, devi <b>comunicarlo al fondo entro il 31 dicembre dell'anno dopo</b> il versamento: "
        "quella parte, quando incassi, non viene tassata una seconda volta.</li>"
        "<li>La parte che viene tassata all'uscita paga il <b>15%</b>, che scende fino al <b>9%</b> dopo 35 anni di iscrizione.</li>"
        "</ul>"
        "<p><b>Cosa tenere presente</b></p>"
        "<ul style='padding-left:20px'>"
        "<li>I soldi restano <b>vincolati fino alla pensione</b>. Gli anticipi sono possibili solo in casi precisi "
        "(spese sanitarie gravi, prima casa, altre esigenze) e hanno una tassazione propria.</li>"
        "<li>I rendimenti <b>non sono garantiti</b>: dipendono dai mercati, e col tempo l'inflazione riduce il valore dei soldi.</li>"
        "<li>I <b>costi</b> cambiano molto da un fondo all'altro. Si confrontano con l'indicatore ISC, nel "
        f"{link(FONTI_PENSIONE['covip_costi'], 'comparatore ufficiale della COVIP')}. In genere i fondi negoziali (di categoria) "
        "costano meno dei prodotti venduti da banche e assicurazioni.</li>"
        "<li>Se non vuoi bloccare i soldi, ci sono alternative (fondi, ETF, polizze) più flessibili ma senza questi vantaggi fiscali: "
        "ognuna ha pregi e difetti.</li>"
        "</ul>"
        "<p style='background:#e8ebfa;padding:12px 14px;font-size:14px'>Informazioni generali aggiornate a luglio 2026, non una "
        "consulenza e non un'offerta di prodotti. Prima di scegliere leggi la Nota informativa del fondo "
        f"({link(FONTI_PENSIONE['covip_guida'], 'guida della COVIP')}) o fatti aiutare da un professionista abilitato.</p>")


def manda_pensione(email: str, id_dashboard: str, scheda: dict | None = None) -> bool:
    """Una sola email informativa sulla previdenza. True se mandata (False se disiscritto, senza consenso o gia' mandata)."""
    email = (email or "").strip().lower()
    if not email or db.email_disattivate(email) or not db.novita_consentite(email):
        return False
    if not db.prenota_promemoria(email, "pensione", "1"):
        return False
    try:
        if scheda is None:
            scheda = (db.carica_dashboard(id_dashboard) or {}).get("_scheda") or {}
        nome = S.pulisci_nome((scheda or {}).get("nome"))
        corpo = corpo_pensione(_ha_altri_redditi(scheda), nome)
        auth.manda_email(email, "TaxScan: pensione e partita IVA forfettaria, cosa c'è da sapere", _cornice(
            email, "Pensione: cosa conviene sapere", corpo, ("Torna alla tua situazione", f"{PUBLIC_URL}/d/{id_dashboard}")))
        try:
            db.registra_evento("pensione_mandata", id_dashboard, {})
        except Exception:
            pass
        return True
    except Exception:
        db.annulla_promemoria(email, "pensione", "1")
        raise


# ---------------------------------------------------------------- promemoria periodici

def _scadenza_prossima(dati: dict) -> dict | None:
    sc = dati.get("prossima_scadenza")
    return sc if sc and sc.get("giorni") is not None else None


def _riepilogo_settimanale(email: str, scheda: dict, dati: dict, id_dashboard: str, fermo: int) -> dict | None:
    """Corpo dell'email settimanale: tutte le scadenze vicine, la quota da mettere da parte, la soglia."""
    tutte = [x for x in (dati.get("scadenze") or []) if x.get("giorni") is not None and x["giorni"] >= 0]
    entro = [x for x in tutte if x["giorni"] <= ORIZZONTE_SCADENZE_GIORNI][:6]
    mancano_incassi = scheda.get("ricavi_anno_corrente") in (None, "")
    if not entro and not mancano_incassi and fermo < 45:
        return None

    def quando(g):
        return "oggi" if g == 0 else ("domani" if g == 1 else f"tra {g} giorni")

    def riga(x):
        imp = f" - <b>{eur(x.get('importo'))}</b>" if x.get("importo") else ""
        f24 = ""
        if x.get("f24") and x.get("data"):
            f24 = (f" (<a href='{_e(PUBLIC_URL)}/d/{_e(id_dashboard)}/f24?data={_e(x['data'])}' "
                   "style='color:#4355cc'>vedi l'F24</a>)")
        return (f"<li style='margin-bottom:6px'><b>{_e(_data_it(x.get('data')))}</b>: {_e(x.get('etichetta'))}{imp}, "
                f"{quando(x['giorni'])}{f24}</li>")

    vicine = [x for x in entro if x["giorni"] <= 7]
    altre = [x for x in entro if x["giorni"] > 7]
    pezzi = []
    if vicine:
        pezzi.append("<p><b>Questa settimana</b></p><ul style='padding-left:20px'>"
                     + "".join(riga(x) for x in vicine) + "</ul>")
    if altre:
        pezzi.append(("<p><b>Più avanti</b></p>" if vicine else "<p><b>Le prossime scadenze</b></p>")
                     + "<ul style='padding-left:20px'>" + "".join(riga(x) for x in altre) + "</ul>")
    if entro and not vicine:
        pezzi.insert(0, "<p>Questa settimana non hai scadenze: puoi stare tranquillo, ma conviene mettere da parte "
                        "ogni volta una piccola quota.</p>")
    quota = str(dati.get("quota_per_fattura") or "").replace(".", ",")
    if quota:
        pezzi.append(f"<p>Da mettere da parte su ogni fattura che incassi: <b>{_e(quota)}</b>.</p>")
    so = dati.get("soglia") or {}
    if so.get("ricavi") is not None and so.get("limite"):
        riga_soglia = f"<p>Incassato quest'anno: <b>{eur(so['ricavi'])}</b> su un limite di {eur(so['limite'])}."
        if so.get("livello") not in (None, "OK") and so.get("messaggio"):
            riga_soglia += f" <b>Attenzione:</b> {_e(so['messaggio'])}"
        pezzi.append(riga_soglia + "</p>")
    if mancano_incassi:
        pezzi.append("<p>Per stime precise mi manca una cosa: <b>quanto hai incassato quest'anno</b>. Mezzo minuto e "
                     "ricalcolo tutto.</p>")
    elif fermo >= 45:
        pezzi.append(f"<p>Sono passati {fermo} giorni dall'ultimo aggiornamento: se hai fatturato di recente, "
                     "aggiorna gli incassi e le stime si ricalcolano subito.</p>")
    if vicine:
        prima = vicine[0]
        oggetto = f"TaxScan: {prima.get('etichetta')} {quando(prima['giorni'])}"
    elif entro:
        prima = entro[0]
        oggetto = f"TaxScan: la prossima scadenza è {quando(prima['giorni'])}"
    else:
        oggetto = "TaxScan: aggiorna i tuoi numeri"
    return {"oggetto": oggetto, "titolo": "La tua settimana fiscale", "corpo": "".join(pezzi),
            "pulsante": "Apri la tua situazione"}


def _scegli(email: str, scheda: dict, dati: dict, creato_il, aggiornato_il, oggi: date,
            id_dashboard: str = "") -> dict | None:
    """Decide quale (al massimo una) email periodica mandare a questo utente adesso."""
    # 1. scadenza vicinissima: un avviso a parte, una volta sola per scadenza
    sc = _scadenza_prossima(dati)
    if sc and 0 <= sc["giorni"] <= 2:
        chiave = f"{sc.get('data')}-2"
        if not db.promemoria_gia_inviato(email, "scadenza", chiave):
            quando = "oggi" if sc["giorni"] == 0 else ("domani" if sc["giorni"] == 1 else f"tra {sc['giorni']} giorni")
            importo = f" Importo stimato: <b>{eur(sc.get('importo'))}</b>." if sc.get("importo") else ""
            quota = str(dati.get("quota_per_fattura") or "").replace(".", ",")
            extra = (f"<p>Per non trovarti scoperto, metti da parte circa <b>{_e(quota)}</b> di ogni fattura che incassi.</p>"
                     if quota else "")
            f24 = ""
            if sc.get("f24") and sc.get("data") and id_dashboard:
                f24 = (f"<p>Se paghi tu, qui trovi le righe dell'F24 da ricopiare nell'home banking: "
                       f"<a href='{_e(PUBLIC_URL)}/d/{_e(id_dashboard)}/f24?data={_e(sc['data'])}' "
                       "style='color:#4355cc;font-weight:700'>apri l'F24</a>.</p>")
            corpo = (f"<p>La prossima scadenza è <b>{_e(sc.get('etichetta'))}</b>, {quando} "
                     f"({_e(_data_it(sc.get('data')))}).{importo}</p>{extra}{f24}"
                     "<p>Nella tua pagina trovi il dettaglio e il pulsante per metterla nel calendario.</p>")
            return {"tipo": "scadenza", "chiave": chiave,
                    "oggetto": f"TaxScan: {sc.get('etichetta')} {quando}", "titolo": f"Scadenza {quando}",
                    "corpo": corpo, "pulsante": "Vedi i dettagli"}

    # 2. riepilogo settimanale (una settimana dopo l'iscrizione, poi ogni 7 giorni)
    giorni_iscritto = (oggi - creato_il.date()).days if creato_il else 0
    if giorni_iscritto < PRIMO_RIEPILOGO_DOPO_GIORNI:
        return None
    ultimo_riepilogo = db.giorni_dall_ultimo_promemoria_tipo(email, "settimanale")
    if ultimo_riepilogo is not None and ultimo_riepilogo < GIORNI_TRA_RIEPILOGHI:
        return None
    giorni_ultimo = db.giorni_dall_ultimo_promemoria(email)
    if giorni_ultimo is not None and giorni_ultimo < DISTANZA_MINIMA_GIORNI:
        return None
    fermo = (oggi - aggiornato_il.date()).days if aggiornato_il else 0
    r = _riepilogo_settimanale(email, scheda, dati, id_dashboard, fermo)
    if not r:
        return None
    iso = oggi.isocalendar()
    r.update({"tipo": "settimanale", "chiave": f"{iso[0]}-W{iso[1]:02d}"})
    return r


def esegui(prova: bool = False) -> dict:
    """Passaggio giornaliero: sceglie e manda i promemoria. Con prova=True non manda nulla e dice cosa farebbe."""
    oggi = date.today()
    esito = {"utenti": 0, "mandati": 0, "falliti": [], "previsti": [], "bandi_intro": 0, "feedback": 0}
    gia = set()  # email che hanno gia' ricevuto qualcosa in questo passaggio: al massimo una email a testa
    # invito al questionario di approfondimento che non e' partito dopo i 45 minuti (per esempio server riavviato): si recupera qui
    import approfondimento
    for r in db.utenti_approfondimento_da_mandare():
        if prova:
            esito["previsti"].append({"email": r["email"], "tipo": "approfondimento", "chiave": "1"})
            continue
        try:
            if approfondimento.manda(r["email"], r["dashboard_id"]):
                esito["bandi_intro"] += 1
                gia.add(r["email"])
        except Exception as e:
            esito["falliti"].append({"email": r["email"], "errore": str(e)[:120]})
    # richiesta di feedback (24 ore dopo l'iscrizione) e un solo promemoria dopo 3 giorni
    import feedback
    fb = feedback.invia(prova, gia)
    esito["feedback"] = fb["mandati"]
    esito["previsti"] += fb["previsti"]
    esito["falliti"] += fb["falliti"]
    gia |= fb["email"]
    # bandi nuovi approvati dall'amministratore: una email a chi ha accettato le email con spunti e ha il settore/la regione giusti
    esito["bandi_nuovi"] = 0
    try:
        da_notificare = db.incentivi_da_notificare()
    except Exception:
        da_notificare = []
    if da_notificare:
        for r in db.utenti_per_bandi():
            if r["email"] in gia:
                continue
            sc = r["scheda"] if isinstance(r["scheda"], dict) else {}
            lista = bandi_per_utente(sc, db.incentivi_gia_mostrati(r["email"]), da_notificare)
            if not lista or not db.novita_consentite(r["email"]):
                continue
            if prova:
                esito["previsti"].append({"email": r["email"], "tipo": "bandi_nuovi", "chiave": str(len(lista))})
                gia.add(r["email"])
                continue
            try:
                if manda_bandi_nuovi(r["email"], r["dashboard_id"], sc, lista):
                    esito["bandi_nuovi"] += 1
                    gia.add(r["email"])
            except Exception as e:
                esito["falliti"].append({"email": r["email"], "errore": str(e)[:120]})
    # email informativa sulla previdenza: una volta sola, dopo 10 giorni, solo a chi ha accettato le email con spunti
    esito["pensione"] = 0
    for r in db.utenti_pensione_da_mandare():
        if r["email"] in gia:
            continue
        ultimo = db.giorni_dall_ultimo_promemoria(r["email"])
        if ultimo is not None and ultimo < DISTANZA_MINIMA_GIORNI:
            continue
        if prova:
            esito["previsti"].append({"email": r["email"], "tipo": "pensione", "chiave": "1"})
            gia.add(r["email"])
            continue
        try:
            if manda_pensione(r["email"], r["dashboard_id"], r["scheda"]):
                esito["pensione"] += 1
                gia.add(r["email"])
        except Exception as e:
            esito["falliti"].append({"email": r["email"], "errore": str(e)[:120]})
    for u in db.utenti_per_promemoria():
        esito["utenti"] += 1
        email = u["email"]
        if email in gia:
            continue
        try:
            dati = db.carica_dashboard(u["dashboard_id"]) or {}
            # si rifa' la dashboard cosi' i giorni alla scadenza sono di oggi, non di quando e' stata creata
            nuovi = (dashboard.costruisci(dict(u["scheda"] or {}), 0.0) if prova
                     else dashboard._ricostruisci(u["dashboard_id"], dati, dict(u["scheda"] or {})))
            if "errore" in nuovi:
                continue
            p = _scegli(email, u["scheda"] or {}, nuovi, u["creato_il"], u["aggiornato_il"], oggi,
                        u["dashboard_id"])
            if not p:
                continue
            if prova:
                esito["previsti"].append({"email": email, "tipo": p["tipo"], "chiave": p["chiave"]})
                continue
            if not db.prenota_promemoria(email, p["tipo"], p["chiave"]):
                continue
            try:
                saluto = S.pulisci_nome((u["scheda"] or {}).get("nome"))
                if saluto:
                    p["corpo"] = f"<p>Ciao {_e(saluto)},</p>" + p["corpo"]
                auth.manda_email(email, p["oggetto"], _cornice(
                    email, p["titolo"], p["corpo"], (p["pulsante"], f"{PUBLIC_URL}/d/{u['dashboard_id']}")))
                esito["mandati"] += 1
                try:
                    db.registra_evento("promemoria_mandato", u["dashboard_id"], {"tipo": p["tipo"]})
                except Exception:
                    pass
            except Exception as e:
                db.annulla_promemoria(email, p["tipo"], p["chiave"])
                esito["falliti"].append({"email": email, "errore": str(e)[:120]})
        except Exception as e:
            esito["falliti"].append({"email": email, "errore": str(e)[:120]})
    return esito


# ---------------------------------------------------------------- pagina di disiscrizione

def pagina_disiscrizione(email: str, token: str, fatto: bool = False, riattivato: bool = False) -> str:
    if not firma_valida(email, token):
        corpo = "<p>Questo link non è valido. Scrivici a info@ltd24ore.com e ti togliamo noi.</p>"
    elif fatto:
        corpo = ("<p>Fatto: non riceverai più promemoria da TaxScan. Il tuo spazio resta disponibile quando "
                 "vuoi tornare.</p>"
                 f"<form method='post'><input type='hidden' name='e' value='{_e(email)}'>"
                 f"<input type='hidden' name='t' value='{_e(token)}'><input type='hidden' name='azione' value='riattiva'>"
                 "<button style='padding:12px 18px;border-radius:10px;border:1px solid #4355cc;background:#fff;"
                 "color:#122452;font-size:16px'>Ho cambiato idea, riattiva</button></form>")
    elif riattivato:
        corpo = "<p>Perfetto, i promemoria sono di nuovo attivi.</p>"
    else:
        corpo = (f"<p>Vuoi smettere di ricevere i promemoria TaxScan su <b>{_e(email)}</b>?</p>"
                 f"<form method='post'><input type='hidden' name='e' value='{_e(email)}'>"
                 f"<input type='hidden' name='t' value='{_e(token)}'><input type='hidden' name='azione' value='disattiva'>"
                 "<button style='padding:13px 20px;border-radius:10px;border:0;background:#4355cc;color:#fff;"
                 "font-size:16px;font-weight:600'>Sì, disiscrivimi</button></form>")
    return ("<!doctype html><html lang='it'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>Email TaxScan</title></head>"
            "<body style='margin:0;background:#f3f6fa;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;"
            "color:#1b2430'><div style='max-width:480px;margin:40px auto;background:#fff;border-radius:14px;"
            "padding:28px 24px;line-height:1.55'><div style='font-size:20px;font-weight:700;color:#122452'>TaxScan</div>"
            f"{corpo}</div></body></html>")
