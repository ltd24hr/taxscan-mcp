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

import auth
import agevolazioni
import calendario
import db
import scheda as S

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
    return {k: v for k, v in dati.items() if not k.startswith("_")}


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
    try:
        nuovo = db.salva_scheda(email, scheda_utente)
    except Exception:
        return {"ok": False, "errore": "Non riesco a salvare in questo momento. Riprova tra poco."}
    return {"ok": True, "nuovo": bool(nuovo), "scheda": scheda_utente, "email": email.strip().lower()}


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
    nuovi = costruisci(scheda_utente, 0.0)
    if "errore" in nuovi:
        return nuovi
    db.salva_dashboard(id_dashboard, nuovi)
    return dati_pubblici(id_dashboard)


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
:root{
  color-scheme:light;
  --bg:#f4f3ef; --surface:#fcfcfb; --line:#e4e2dc; --track:#cde2fb;
  --ink:#0b0b0b; --ink2:#52514e; --ink3:#7c7a74;
  --accent:#2a78d6; --accent-ink:#184f95; --accent-soft:#e6f0fc;
  --good:#0ca30c; --good-ink:#087308; --warn:#fab219; --warn-ink:#8a5a00; --serious:#ec835a; --crit:#d03b3b;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --bg:#121211; --surface:#1a1a19; --line:#2e2e2b; --track:#1c3a5f;
    --ink:#ffffff; --ink2:#c3c2b7; --ink3:#8f8e86;
    --accent:#3987e5; --accent-ink:#86b6ef; --accent-soft:#17283d;
    --good-ink:#5bd65b; --warn-ink:#fab219;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#121211; --surface:#1a1a19; --line:#2e2e2b; --track:#1c3a5f;
  --ink:#ffffff; --ink2:#c3c2b7; --ink3:#8f8e86;
  --accent:#3987e5; --accent-ink:#86b6ef; --accent-soft:#17283d;
  --good-ink:#5bd65b; --warn-ink:#fab219;
}
*{box-sizing:border-box;margin:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  padding:16px 16px 40px;max-width:640px;margin:0 auto}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin:4px 0 16px}
header>div{min-width:0}
h1{font-size:21px;white-space:nowrap;line-height:1.2;font-weight:700}
.sub{color:var(--ink2);font-size:14px;margin-top:2px}
.chip{flex:none;display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:600;padding:6px 10px;border-radius:999px;
  border:1px solid var(--line);background:var(--surface);white-space:nowrap}
.chip svg{width:14px;height:14px;flex:none}
.chip.ok{color:var(--good-ink)} .chip.ok svg{color:var(--good)}
.chip.chk{color:var(--warn-ink)} .chip.chk svg{color:var(--warn)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:12px}
.eyebrow{font-size:13px;color:var(--ink2);font-weight:600}
.hero .valore{font-size:52px;line-height:1.05;font-weight:700;letter-spacing:-.02em;margin:6px 0 2px}
.hero .quando{font-size:16px;color:var(--ink)}
.hero .quando b{font-weight:700}
.hero .det{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;color:var(--ink2);font-size:14px}
.hero .det div{display:flex;justify-content:space-between;gap:12px;padding:2px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.grid .card{margin:0;padding:16px}
.tile .valore{font-size:28px;font-weight:700;line-height:1.1;margin:6px 0 2px;letter-spacing:-.01em}
.tile .nota{font-size:13px;color:var(--ink2)}
h2{font-size:17px;font-weight:700;margin-bottom:2px}
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
button.btn{width:100%;border:0;font:inherit;font-weight:600;cursor:pointer}
.msg{font-size:13px;color:var(--ink2);margin-top:8px;min-height:18px}
.msg.err{color:var(--crit)}
.lk{display:block;padding:10px 0;border-top:1px solid var(--line);font-size:14px;color:var(--accent-ink);text-decoration:none;font-weight:600}
.lk small{display:block;color:var(--ink2);font-weight:400;font-size:12px}
.sub2{font-size:13px;font-weight:700;color:var(--ink2);margin:14px 0 2px}
.cur{padding:10px 0;border-top:1px solid var(--line);font-size:14px}
.cur b{display:block}
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
function eur(n,dec){if(n==null||isNaN(n))return "–";return Number(n).toLocaleString("it-IT",{minimumFractionDigits:dec||0,maximumFractionDigits:dec||0})+"\u00a0€"}
function dataIt(iso){const [y,m,d]=iso.split("-").map(Number);return {g:d,m:MESI[m-1],mm:MESI_LUNGHI[m-1],a:y}}
function giorni(n){if(n==null)return "";if(n<=0)return "oggi";if(n===1)return "domani";if(n<45)return "tra "+n+" giorni";const m=Math.round(n/30);return "tra circa "+m+" mesi"}

function render(d){
  const app=document.getElementById("app");
  const ok=d.stato==="in_ordine";
  const agg=dataIt(d.aggiornato_il);
  let html='';
  html+='<header><div><h1>La tua situazione</h1><div class="sub">'+agg.g+' '+agg.mm+' '+agg.a+' · stime</div></div>'
    +'<span class="chip '+(ok?'ok':'chk')+'">'+(ok?ICONE.ok:ICONE.warn)+(ok?'Tutto in ordine':'Da controllare')+'</span></header>';

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

  // scadenze
  const sc=d.scadenze||[];
  if(sc.length){
    html+='<section class="card"><h2>Le prossime scadenze</h2><div class="lead">Totale da versare: '+eur(d.totale_da_versare,0)+(d.periodo?' · '+h(d.periodo):'')+'</div>'
      +sc.map(x=>{const dt=dataIt(x.data);
        return '<div class="sc"><div class="data"><b>'+dt.g+'</b><span>'+dt.m+'</span></div><div style="flex:1"><div style="display:flex;gap:8px"><div class="t">'+h(x.etichetta)+'</div><div class="imp">'+eur(x.importo,0)+'</div></div>'
          +(x.dettaglio||[]).map(r=>'<div class="d">'+h(r)+'</div>').join('')+'<div class="g">'+giorni(x.giorni)+'</div></div></div>'}).join('')
      +'<a class="btn sec" href="/d/'+encodeURIComponent(ID)+'/calendario">Metti le scadenze nel calendario del telefono</a></section>';
  }

  // profilo
  const pr=d.profilo||{};
  html+='<section class="card"><h2>Il tuo regime</h2>'
    +'<div class="kv" style="border:0;margin-top:6px;padding-top:0"><span>Aliquota imposta</span><b>'+h(pr.aliquota||"–")+'</b></div>'
    +(pr.dal_anno_15?'<div class="kv" style="border:0;margin-top:0;padding-top:4px"><span>Il 5% vale fino al</span><b>'+(pr.dal_anno_15-1)+'</b></div>':'')
    +'<div class="kv" style="border:0;margin-top:0;padding-top:4px"><span>Coefficiente di redditività</span><b>'+h(pr.coefficiente||"–")+'</b></div>'
    +'<div class="kv" style="border:0;margin-top:0;padding-top:4px"><span>Codice ATECO</span><b>'+h(pr.codice_ateco||"–")+'</b></div>'
    +'</section>';

  // avvisi
  const av=d.avvisi||[];
  if(av.length){
    const L={importante:["Importante",ICONE.crit],attenzione:["Attenzione",ICONE.warn],informativo:["Da sapere",ICONE.info]};
    html+='<section class="card"><h2>Da tenere d\'occhio</h2>'
      +av.map(a=>{const l=L[a.livello]||L.informativo;
        return '<div class="av '+h(a.livello)+'">'+l[1]+'<div><div class="l">'+l[0]+'</div>'+(a.titolo?'<div class="tt">'+h(a.titolo)+'</div>':'')+'<div class="tx">'+h(a.testo)+'</div></div></div>'}).join('')
      +'</section>';
  }

  // cose da fare
  const td=d.cose_da_fare||[];
  if(td.length){
    html+='<section class="card"><h2>Cosa fare adesso</h2><ul class="todo">'+td.map(x=>'<li><span>'+h(x)+'</span></li>').join('')+'</ul>'
      +(/^https:\/\//.test(d.link_professionista||'')?'<a class="btn" href="'+h(d.link_professionista)+'" target="_blank" rel="noopener">Parla con un professionista</a>':'')+'</section>';
  }

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

  // salva
  html+='<section class="card" id="salva"><h2>Ritrova tutto quando vuoi</h2><div class="lead">Salva la tua situazione con la tua email: la ritrovi alla prossima visita e ti scriviamo se cambia una norma che ti riguarda. Niente password: ti mandiamo un codice.</div>'
    +'<div id="salva-box"><input class="campo" id="em" type="email" inputmode="email" autocomplete="email" placeholder="La tua email"><button class="btn" id="em-ok" style="margin-top:0">Ricevi il codice</button><p class="msg" id="em-msg"></p></div></section>';

  html+='<p class="foot"><b>Sono stime, non una dichiarazione.</b> TaxScan prepara e spiega; il tuo commercialista controlla e firma. '
    +h(d.disclaimer||"")+'</p>';
  app.innerHTML=html;
  const post=async(p,b)=>{const r=await fetch('/api/dashboard/'+encodeURIComponent(ID)+p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});let j={};try{j=await r.json()}catch(e){}return j};
  const msg=(id,t,err)=>{const e=document.getElementById(id);if(e){e.textContent=t;e.className='msg'+(err?' err':'')}};
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
      if(r.ok)document.getElementById('salva-box').innerHTML='<div class="stato ok">'+ICONE.ok+'<div><b>Fatto.</b> La tua situazione è salvata con '+h(email)+'. Ti scriveremo se cambia una norma che ti riguarda.</div></div>';
      else msg('cod-msg',r.errore||'Codice non valido.',true)}};

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
