"""TaxScan - "Check delle attività": più attività, più coefficienti di redditività.

Nel forfettario ogni attività ha il suo coefficiente (Allegato 4 L. 190/2014). Chi svolge servizi che rientrano in gruppi
diversi applica a ciascuno il proprio coefficiente sui relativi ricavi, che vanno tenuti distinti. Per la soglia degli
85.000 euro conta invece la somma di tutti i ricavi.

Il modulo:
- tiene il catalogo dei servizi piu' comuni, in parole semplici, ciascuno con un codice ATECO INDICATIVO;
- trasforma "quanto pesa ciascun servizio" in un coefficiente medio (equivale a sommare i redditi di ogni attivita');
- confronta il calcolo "tutto sul codice principale" con quello "per attivita' vera";
- mette sempre le avvertenze che contano: servizi davvero distinti, ricavi separati in fattura, codici sulla partita IVA,
  INPS (un'attivita' commerciale puo' cambiare i contributi), soglia sulla somma.
Tutte le cifre sono stime.
"""
from __future__ import annotations

import html
import json

import calcoli
import dati_fisco as D

# quanto pesa un servizio sul fatturato: parole semplici -> peso relativo (poi si normalizza a 100)
PESI = {"poco": 5, "qualche": 15, "parecchio": 30, "meta": 50, "quasi_tutto": 80}
ETICHETTE_PESO = {"poco": "Pochissimo", "qualche": "Un po'", "parecchio": "Parecchio", "meta": "Circa metà",
                  "quasi_tutto": "Quasi tutto"}

AREE = ["Marketing e comunicazione", "Siti e tecnologia", "Grafica, foto e video", "Formazione e traduzioni",
        "Servizi per le aziende", "Vendita"]

_AVVISO_COMMERCIO = ("Vendere prodotti è un'attività commerciale: di norma comporta l'iscrizione alla gestione INPS Commercianti, "
                     "con contributi fissi anche se fatturi poco. Prima di aggiungerla verifica con l'INPS o un professionista: "
                     "potrebbe costarti più di quanto risparmi.")

# id, area, titolo, esempio, codice ATECO indicativo, parole chiave per riconoscere cio' che l'utente scrive, avviso
_VOCI = [
    ("strategia", 0, "Consulenza e strategia di marketing", "piano di marketing, analisi del mercato, posizionamento del marchio",
     "70.22.09", ["strategia", "consulen", "piano marketing", "posizionament", "brand"], ""),
    ("campagne", 0, "Campagne pubblicitarie, social e newsletter", "Meta Ads, Google Ads, gestione dei profili social, copywriting, email marketing",
     "73.11.02", ["social", "ads", "pubblicit", "campagn", "facebook", "instagram", "newsletter", "copywrit", "advertis"], ""),
    ("pr", 0, "Comunicazione e rapporti con la stampa", "comunicati stampa, relazioni con i giornalisti, eventi",
     "70.21.00", ["stampa", "comunicati", "pubbliche relazioni", "giornalist", "ufficio stampa"], ""),
    ("ricerche", 0, "Ricerche e analisi di mercato", "sondaggi, analisi dei concorrenti, report sul mercato",
     "73.20.00", ["ricerc", "analisi di mercato", "sondagg", "concorrent", "survey"], ""),
    ("sito", 1, "Creazione di siti web", "sito vetrina, negozio online, landing page, WordPress",
     "62.01.00", ["sito", "siti web", "wordpress", "landing", "ecommerce", "e-commerce", "shopify", "sviluppo web", "programm"], ""),
    ("assistenza", 1, "Assistenza tecnica e configurazioni", "configurare email, CRM e strumenti di analisi, automazioni, risolvere problemi tecnici",
     "62.09.09", ["crm", "configur", "analytics", "assistenza", "tecnic", "automazion", "integrazion", "tracking", "informatic"], ""),
    ("manutenzione", 1, "Gestione e manutenzione di siti già online", "aggiornamenti, backup, hosting, sicurezza",
     "63.11.30", ["manutenzion", "hosting", "backup", "aggiornament", "dominio", "sicurezza del sito"], ""),
    ("grafica", 2, "Grafica", "logo, banner, brochure, grafiche per i social",
     "74.10.29", ["grafic", "logo", "banner", "brochure", "design", "impagin"], ""),
    ("foto", 2, "Fotografia", "servizi fotografici per i clienti",
     "74.20.19", ["foto", "shooting", "fotograf"], ""),
    ("video", 2, "Riprese e montaggio video", "video promozionali, reel, montaggio",
     "59.11.00", ["video", "montaggio", "reel", "riprese"], ""),
    ("corsi", 3, "Corsi e workshop", "formazione ai clienti o ai loro dipendenti, lezioni, workshop",
     "85.59.20", ["corso", "corsi", "formazion", "workshop", "lezion", "docenz", "insegn"], ""),
    ("traduzioni", 3, "Traduzioni", "tradurre testi e siti",
     "74.30.00", ["traduz", "tradur"], ""),
    ("pratiche", 4, "Pratiche e attività d'ufficio per i clienti", "segreteria, prenotazioni, adempimenti, caricamento dati, gestione della posta",
     "82.19.09", ["segreteria", "pratic", "adempiment", "amministrativ", "data entry", "back office", "burocrazia", "ufficio", "inserimento dati"], ""),
    ("rivendita", 5, "Rivendita di prodotti o licenze", "vendo prodotti, abbonamenti o licenze a un prezzo mio (non solo il mio lavoro)",
     "47.91.10", ["vendo", "rivend", "prodotti", "dropshipping", "negozio", "abbonament", "licenz"], _AVVISO_COMMERCIO),
]


def _catalogo() -> list[dict]:
    out = []
    for vid, area, titolo, esempio, codice, kw, avviso in _VOCI:
        info = calcoli.coefficiente_da_ateco(codice)
        out.append({"id": vid, "area": AREE[area], "titolo": titolo, "esempio": esempio, "codice": codice,
                    "coeff": info["coefficiente"], "gruppo": info.get("gruppo", ""), "kw": kw, "avviso": avviso,
                    "commercio": bool(avviso)})
    return out


CATALOGO = _catalogo()
_PER_ID = {v["id"]: v for v in CATALOGO}


# ---------------------------------------------------------------- calcolo

def voci_valide(voci, principale: str | None = None) -> tuple[list[dict], str]:
    """Pulisce l'input dell'utente: solo servizi del catalogo, pesi riconosciuti, niente doppioni."""
    pulite, visti = [], set()
    for x in (voci or []):
        vid = str((x or {}).get("id") or "")
        peso = str((x or {}).get("peso") or "qualche")
        if vid in _PER_ID and vid not in visti and peso in PESI:
            pulite.append({"id": vid, "peso": peso})
            visti.add(vid)
    p = principale if principale in PESI else "quasi_tutto"
    return pulite, p


def righe(s: dict) -> list[dict] | None:
    """Le attivita' con coefficiente e quota (somma 100), oppure None se la scheda non ha un check fatto."""
    a = (s or {}).get("attivita")
    if not isinstance(a, dict) or not a.get("voci"):
        return None
    base = calcoli.coefficiente_da_ateco(s.get("codice_ateco", ""))
    if "errore" in base:
        return None
    voci, principale = voci_valide(a.get("voci"), a.get("principale"))
    if not voci:
        return None
    elenco = [{"id": "principale", "titolo": "Il mio lavoro principale", "codice": base["codice_ateco"],
               "coeff": base["coefficiente"], "peso": PESI[principale], "commercio": False}]
    for v in voci:
        c = _PER_ID[v["id"]]
        elenco.append({"id": c["id"], "titolo": c["titolo"], "codice": c["codice"], "coeff": c["coeff"],
                       "peso": PESI[v["peso"]], "commercio": c["commercio"]})
    tot = sum(r["peso"] for r in elenco)
    for r in elenco:
        r["quota"] = r["peso"] / tot
    return elenco


def coefficiente_misto(s: dict) -> float | None:
    """Coefficiente medio pesato sui ricavi di ciascuna attivita' (equivale a sommare i redditi di ogni attivita'),
    oppure None se non c'e' un check salvato."""
    r = righe(s)
    if not r:
        return None
    return round(sum(x["coeff"] * x["quota"] for x in r), 4)


def descrizione_coefficiente(s: dict) -> str | None:
    c = coefficiente_misto(s)
    return None if c is None else f"{c * 100:.0f}% (media delle tue attività)"


def _ricavi_di_riferimento(s: dict) -> float:
    for k in ("ricavi_anno_precedente", "ricavi_anno_corrente"):
        try:
            v = float(s.get(k) or 0)
        except (TypeError, ValueError):
            v = 0.0
        if v > 0:
            return v
    return 0.0


def stima(scheda_utente: dict, voci, principale: str | None, ricavi) -> dict:
    """Confronta 'tutto sul codice principale' con 'per attivita' vera'. Ritorna righe, differenze e avvertenze."""
    import scheda as S  # import qui: scheda usa questo modulo
    s = S._normalizza(scheda_utente or {})
    voci, principale = voci_valide(voci, principale)
    if not voci:
        return {"errore": "Scegli almeno un servizio."}
    try:
        ricavi = float(ricavi)
    except (TypeError, ValueError):
        ricavi = 0.0
    if ricavi <= 0:
        ricavi = _ricavi_di_riferimento(s)
    if not (0 < ricavi <= 10_000_000):
        return {"errore": "Scrivi quanto fatturi in un anno, più o meno."}

    s_base = dict(s, attivita=None)
    s_mix = dict(s, attivita={"voci": voci, "principale": principale})
    elenco = righe(s_mix)
    if not elenco:
        return {"errore": "Non riesco a leggere il codice ATECO principale: controlla la scheda."}
    base, mix = S._calcolo(s_base, ricavi), S._calcolo(s_mix, ricavi)
    if "errore" in base or "errore" in mix:
        return {"errore": (base if "errore" in base else mix)["errore"]}

    coeff_base = calcoli.coefficiente_da_ateco(s.get("codice_ateco", ""))["coefficiente"]
    coeff_mix = sum(r["coeff"] * r["quota"] for r in elenco)
    risp_righe = []
    for r in elenco:
        r_eur = ricavi * r["quota"]
        risp_righe.append({"id": r["id"], "titolo": r["titolo"], "codice": r["codice"],
                           "coefficiente": f"{r['coeff'] * 100:.0f}%", "quota": round(r["quota"] * 100),
                           "ricavi": round(r_eur), "reddito": round(r_eur * r["coeff"])})

    diff_tot = round(base["totale_da_versare"] - mix["totale_da_versare"])
    gestione = (s.get("gestione_previdenziale") or "separata")
    avvisi = []
    codici = sorted({r["codice"] for r in elenco if r["id"] != "principale"})
    avvisi.append({"titolo": "Vale solo per ciò che fai davvero",
                   "testo": "Il coefficiente dipende dalla natura di ciò che fai, non da come scrivi la fattura. Un unico lavoro non "
                            "si spezza per pagare meno: conta se sono servizi davvero distinti, con un prezzo suo."})
    avvisi.append({"titolo": "Tieni i ricavi separati",
                   "testo": "In fattura scrivi le voci distinte (una riga per ogni servizio, con il suo importo) e nei tuoi conti tieni "
                            "i totali per attività: nella dichiarazione ogni attività ha la sua riga."})
    if codici:
        avvisi.append({"titolo": "Controlla i codici sulla partita IVA",
                       "testo": "I servizi che non rientrano nel tuo codice principale hanno bisogno del proprio codice ATECO sulla "
                                f"partita IVA (indicativi: {', '.join(codici)}). Si aggiungono con una comunicazione di variazione "
                                "all'Agenzia delle Entrate, di norma gratuita, da fare entro 30 giorni da quando inizi l'attività. "
                                "I codici qui sono indicativi: il codice esatto va scelto con il tuo professionista o l'Agenzia."})
    rischio_inps = any(r["commercio"] for r in elenco) and gestione == "separata"
    if rischio_inps:
        avvisi.insert(0, {"titolo": "Attenzione ai contributi INPS", "testo": _AVVISO_COMMERCIO})
    if ricavi >= 0.7 * D.SOGLIA_RICAVI:
        avvisi.append({"titolo": "La soglia conta sul totale",
                       "testo": f"Il limite di {D.SOGLIA_RICAVI:,.0f} euro vale sulla somma di tutti i ricavi, qualunque sia l'attività.".replace(",", ".")})
    if coeff_mix > coeff_base + 1e-9:
        avvisi.insert(0, {"titolo": "Con questo calcolo paghi un po' di più",
                          "testo": "Una delle tue attività ha un coefficiente più alto del codice principale. È comunque il calcolo corretto "
                                   "e conviene saperlo ora, non in un controllo."})
    return {
        "ricavi": round(ricavi),
        "righe": risp_righe,
        "coefficiente_base": f"{coeff_base * 100:.0f}%",
        "coefficiente_misto": f"{coeff_mix * 100:.1f}%".replace(".0%", "%"),
        "oggi": {"imposta": round(base["imposta_sostitutiva"]), "contributi": round(base["contributi_previdenziali"]["totale_contributi"]),
                 "totale": round(base["totale_da_versare"]), "netto": round(base["netto_stimato"])},
        "con_check": {"imposta": round(mix["imposta_sostitutiva"]), "contributi": round(mix["contributi_previdenziali"]["totale_contributi"]),
                      "totale": round(mix["totale_da_versare"]), "netto": round(mix["netto_stimato"])},
        "differenza": diff_tot,   # > 0: risparmio; < 0: costo in piu'
        "risparmio_affidabile": not rischio_inps,  # con un'attivita' commerciale i contributi INPS potrebbero essere altri
        "avvisi": avvisi,
        "nota": "Sono stime sul fatturato che hai indicato. Il risparmio è reale solo se i servizi sono davvero distinti e i codici sono in regola.",
    }


# ---------------------------------------------------------------- per la dashboard

def riepilogo(scheda_utente: dict) -> dict:
    """Quello che la dashboard mostra: se il check e' fatto e con quali numeri."""
    s = scheda_utente or {}
    r = righe(s)
    if not r:
        return {"fatto": False}
    return {"fatto": True, "coefficiente": descrizione_coefficiente(s),
            "attivita": [{"titolo": x["titolo"], "codice": x["codice"], "coefficiente": f"{x['coeff'] * 100:.0f}%",
                          "quota": round(x["quota"] * 100)} for x in r]}


# ---------------------------------------------------------------- pagina

def _chat_attiva() -> bool:
    try:
        import assistente
        return bool(assistente.attiva())
    except Exception:
        return False


def pagina(id_dashboard: str, scheda_utente: dict) -> str:
    import scheda as S
    s = S._normalizza(scheda_utente or {})
    base = calcoli.coefficiente_da_ateco(s.get("codice_ateco", ""))
    salvato = (scheda_utente or {}).get("attivita") if isinstance((scheda_utente or {}).get("attivita"), dict) else {}
    dati = {
        "id": id_dashboard,
        "catalogo": CATALOGO, "aree": AREE, "pesi": ETICHETTE_PESO,
        "principale": {"codice": base.get("codice_ateco", s.get("codice_ateco", "")), "coeff": base.get("coefficiente"),
                       "gruppo": base.get("gruppo", "")},
        "salvato": {"voci": salvato.get("voci") or [], "principale": salvato.get("principale") or "quasi_tutto",
                    "altro": salvato.get("altro") or ""},
        "ricavi": round(_ricavi_di_riferimento(s)) or "",
        "chat": _chat_attiva(),
    }
    js_dati = json.dumps(dati, ensure_ascii=False).replace("</", "<\\/")
    return _PAGINA.replace("__DATI__", js_dati).replace("__ID__", html.escape(id_dashboard))


_PAGINA = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Check delle attività - TaxScan</title>
<style>
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{--bg:#eef2f8;--card:#fff;--ink:#122452;--ink2:#3d4a73;--line:#d8e2ed;--accent:#4355cc;--ok:#0f8f6a;--warn:#efac35;--bad:#b3261e;
--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#0a1330;--card:#122452;--ink:#fff;--ink2:#c9d3ec;--line:#25397a;--accent:#7a89ee;--ok:#3ed1a5;--bad:#ff8a80}}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-txt);padding:16px 16px 56px;max-width:820px;margin:0 auto}
h1,h2,h3{font-family:var(--f-tit)} h1{font-size:25px;margin:8px 0 4px} h2{font-size:18px;margin:0 0 6px}
a{color:var(--accent)} .sub{color:var(--ink2)} .piccolo{font-size:13px;color:var(--ink2)}
.box{background:var(--card);border:1px solid var(--line);padding:16px;margin:16px 0}
.regola{border-left:4px solid var(--warn)}
.num{display:inline-block;background:var(--ink);color:var(--bg);font-weight:700;width:26px;height:26px;line-height:26px;text-align:center;margin-right:8px}
textarea,input[type=number],select{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);padding:10px;width:100%}
textarea{min-height:64px;resize:vertical}
button{font:inherit;font-weight:700;padding:11px 18px;background:var(--accent);color:#fff;border:1px solid var(--accent);cursor:pointer}
button.sec{background:transparent;color:var(--accent)} button:disabled{opacity:.5;cursor:default}
.area{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);margin:16px 0 6px}
.voce{display:flex;gap:10px;align-items:flex-start;padding:10px;border:1px solid var(--line);margin:6px 0;cursor:pointer;background:var(--bg)}
.voce.on{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
.voce input{margin-top:5px;width:18px;height:18px;flex:none}
.voce b{display:block} .voce span{font-size:13px;color:var(--ink2)}
.voce .av{display:block;color:var(--bad);margin-top:4px}
.riga{display:grid;grid-template-columns:1fr 170px;gap:10px;align-items:center;margin:8px 0}
@media (max-width:560px){.riga{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:14px} th,td{padding:8px;border-bottom:1px solid var(--line);text-align:left}
th{font-size:12px;color:var(--ink2);font-weight:500} .n{text-align:right;white-space:nowrap}
.conf{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}
.conf div{border:1px solid var(--line);padding:12px;background:var(--bg)} .conf big{display:block;font:700 22px var(--f-tit)}
.risp{padding:16px;margin:14px 0;font-weight:700;font-size:17px;background:var(--ink);color:var(--bg)}
@media (prefers-color-scheme:dark){.risp{background:#05d5c8;color:#122452}}
.risp.neg{background:var(--warn);color:#122452}
.av2{border-left:4px solid var(--warn);padding:8px 12px;margin:8px 0;background:var(--bg);font-size:14px}
.av2.rosso{border-color:var(--bad)} .ok{color:var(--ok);font-weight:700} .err{color:var(--bad);font-weight:700}
.nascosto{display:none}

.fabx{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:20;border:0;border-radius:999px;padding:14px 18px;background:var(--accent);color:#fff;font:inherit;font-weight:700;box-shadow:0 6px 20px rgba(0,0,0,.28);cursor:pointer;display:flex;gap:8px;align-items:center}
.fabx svg{width:18px;height:18px}
@media (prefers-reduced-motion:no-preference){.fabx.trilla{animation:fabwob 1.8s ease-in-out 8}}
@keyframes fabwob{0%,60%,100%{transform:rotate(0) scale(1)}8%{transform:rotate(-7deg) scale(1.07)}16%{transform:rotate(7deg) scale(1.07)}24%{transform:rotate(-5deg) scale(1.05)}32%{transform:rotate(5deg) scale(1.05)}40%{transform:rotate(0) scale(1)}}
.fbub{position:fixed;right:16px;bottom:calc(78px + env(safe-area-inset-bottom));z-index:20;max-width:min(260px,calc(100vw - 32px));background:var(--card);color:var(--ink);border:1px solid var(--line);padding:12px 34px 12px 14px;font-size:14px;line-height:1.4;box-shadow:0 8px 24px rgba(0,0,0,.22)}
.fbub .x{position:absolute;top:2px;right:4px;border:0;background:none;color:var(--ink2);font-size:22px;line-height:1;cursor:pointer;padding:2px 6px}
.fbub::after{content:"";position:absolute;right:32px;bottom:-8px;width:14px;height:14px;background:var(--card);border-right:1px solid var(--line);border-bottom:1px solid var(--line);transform:rotate(45deg)}
.cx{position:fixed;left:0;right:0;bottom:0;z-index:40;margin:0 auto;max-width:640px;height:min(82vh,640px);background:var(--card);border:1px solid var(--line);border-bottom:0;box-shadow:0 -8px 30px rgba(0,0,0,.3);display:flex;flex-direction:column}
.cx[hidden]{display:none}
.cx header{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid var(--line)}
.cx header small{display:block;color:var(--ink2);font-size:12px;font-weight:400}
.cx header button{border:0;background:none;color:var(--ink2);font-size:28px;line-height:1;cursor:pointer;padding:0 4px}
.cx .ms{flex:1;overflow-y:auto;padding:14px 16px;display:flex;flex-direction:column;gap:10px}
.cm{max-width:88%;padding:10px 13px;font-size:15px;line-height:1.45;word-wrap:break-word}
.cm.u{align-self:flex-end;background:var(--accent);color:#fff}
.cm.a{align-self:flex-start;background:var(--bg);border:1px solid var(--line)}
.cm.p{color:var(--ink2);font-style:italic}
.cm .sp{display:block;margin-top:8px;font-size:14px;padding:8px 12px}
.cx .ch{display:flex;flex-wrap:wrap;gap:8px;padding:0 16px 8px}
.cx .ch button{background:var(--bg);color:var(--ink);border:1px solid var(--line);padding:8px 12px;font-size:13px;font-weight:400}
.cx form{display:flex;gap:8px;padding:10px 16px;border-top:1px solid var(--line)}
.cx form input{flex:1;font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);padding:10px}
.cx .nt{font-size:12px;color:var(--ink2);padding:0 16px 12px}
</style></head><body>
<p><a href="/d/__ID__">← Torna alla tua situazione</a></p>
<h1>Check delle attività</h1>
<p class="sub">Un solo codice ATECO non sempre racconta tutto il tuo lavoro. Se fai servizi diversi, ognuno ha il suo coefficiente: dirci bene cosa fai può cambiare le tasse che paghi. Servono 2 minuti.</p>

<div class="box regola"><b>La regola, in due righe.</b> Per ogni attività vale il suo coefficiente, applicato ai ricavi di quella attività (tenuti separati). Per il limite degli 85.000 € si sommano invece tutti i ricavi. Conta ciò che fai davvero: non si inventano servizi e non si spezza un unico lavoro per pagare meno.</div>

<div class="box">
<h2><span class="num">1</span>Cosa fai per i tuoi clienti?</h2>
<p class="piccolo">Scrivi con parole tue, per esempio: «faccio campagne social, creo e sistemo siti e a volte configuro il CRM». Poi spunta le voci che ti somigliano.</p>
<textarea id="libero" placeholder="Cosa fai per i clienti, anche in modo disordinato…"></textarea>
<p style="margin-top:8px"><button class="sec" id="suggerisci" type="button">Suggerisci le voci</button> <span class="piccolo" id="sugg_msg"></span></p>
<div id="elenco"></div>
<p class="piccolo" style="margin-top:12px">Non trovi una voce? Scrivila qui, la salviamo per farla vedere al tuo professionista (non entra nel calcolo):</p>
<input type="text" id="altro" maxlength="300" style="font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);padding:10px;width:100%">
</div>

<div class="box nascosto" id="passo2">
<h2><span class="num">2</span>Quanto pesa ciascuna sul tuo fatturato?</h2>
<p class="piccolo">Basta una risposta a occhio. Il lavoro principale è quello del tuo codice ATECO attuale (<span id="cod_princ"></span>).</p>
<div id="pesi"></div>
<div class="riga"><label for="ricavi"><b>Quanto fatturi in un anno, più o meno?</b><br><span class="piccolo">Serve solo per tradurre il risultato in euro.</span></label><input type="number" id="ricavi" min="1" step="1000" inputmode="numeric" placeholder="es. 40000"></div>
<p><button id="calcola" type="button">Vedi il risultato</button> <span id="err" class="err"></span></p>
</div>

<div class="box nascosto" id="passo3">
<h2><span class="num">3</span>Il risultato</h2>
<div id="ris"></div>
<p style="margin-top:12px"><button id="salva" type="button">Usa questi numeri nella mia dashboard</button> <button class="sec" id="togli" type="button">Togli il check</button> <span id="esito"></span></p>
<p class="piccolo" style="margin-top:8px">Salvando, la dashboard calcola imposta e contributi con questi coefficienti. Puoi cambiare idea quando vuoi.</p>
</div>

<p class="piccolo">Stime a fini informativi: la responsabilità di ciò che dichiari e paghi resta tua. Se vuoi, puoi farti aiutare da un professionista (la consulenza gratuita di LTD24 è un'opzione, non un obbligo). I codici ATECO mostrati sono indicativi.</p>


<button type="button" class="fabx nascosto" id="fabx" aria-label="Chiedi aiuto all'assistente per capire le tue attività"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4h14v9H8l-4 3.5V13H3z"/></svg>Non sai cosa scrivere?</button>
<div class="fbub nascosto" id="fbub" role="status"><button type="button" class="x" id="fbub-x" aria-label="Chiudi il suggerimento">×</button><b>Ti aiuto io.</b> Raccontami cosa fai e ti dico quali voci spuntare.</div>
<div class="cx" id="cx" role="dialog" aria-label="Assistente TaxScan" hidden>
<header><div><b>Assistente TaxScan</b><small>Assistente virtuale basato su intelligenza artificiale</small></div><button type="button" id="cx-x" aria-label="Chiudi">×</button></header>
<div class="ms" id="ms"></div><div class="ch" id="ch"></div>
<form id="cf"><input id="ci" maxlength="600" placeholder="Scrivi cosa fai per i tuoi clienti" autocomplete="off"><button type="submit">Invia</button></form>
<p class="nt" id="nt">Risposte indicative, non sono una consulenza. Le domande vengono salvate per migliorare il servizio.</p>
</div>

<script>
var D=__DATI__;
var $=function(i){return document.getElementById(i)};
function h(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function eur(n){return Number(n).toLocaleString('it-IT')+' €'}
var scelte={}; // id -> peso
(D.salvato.voci||[]).forEach(function(v){scelte[v.id]=v.peso});
var principale=D.salvato.principale||'quasi_tutto';
$('cod_princ').textContent=D.principale.codice+(D.principale.coeff?' · coefficiente '+Math.round(D.principale.coeff*100)+'%':'');
$('ricavi').value=D.ricavi||''; $('altro').value=D.salvato.altro||'';

function disegnaElenco(){
  var out='';
  D.aree.forEach(function(a){
    var voci=D.catalogo.filter(function(v){return v.area===a});
    if(!voci.length)return;
    out+='<div class="area">'+h(a)+'</div>';
    voci.forEach(function(v){
      var on=scelte[v.id]!==undefined;
      out+='<label class="voce'+(on?' on':'')+'"><input type="checkbox" data-id="'+h(v.id)+'"'+(on?' checked':'')+'><div><b>'+h(v.titolo)+'</b><span>'+h(v.esempio)+'</span>'+(v.avviso?'<span class="av">'+h(v.avviso)+'</span>':'')+'</div></label>';
    });
  });
  $('elenco').innerHTML=out;
  Array.prototype.forEach.call($('elenco').querySelectorAll('input'),function(c){
    c.onchange=function(){
      var id=c.getAttribute('data-id');
      if(c.checked){scelte[id]=scelte[id]||'qualche'}else{delete scelte[id]}
      c.parentNode.className='voce'+(c.checked?' on':'');
      disegnaPesi();
    };
  });
  disegnaPesi();
}
function opzioni(sel){
  return Object.keys(D.pesi).map(function(k){return '<option value="'+k+'"'+(k===sel?' selected':'')+'>'+h(D.pesi[k])+'</option>'}).join('');
}
function disegnaPesi(){
  var ids=Object.keys(scelte);
  $('passo2').className='box'+(ids.length?'':' nascosto');
  $('passo3').className='box nascosto';
  var out='<div class="riga"><div><b>Il mio lavoro principale</b><br><span class="piccolo">codice '+h(D.principale.codice)+'</span></div><select data-id="principale">'+opzioni(principale)+'</select></div>';
  ids.forEach(function(id){
    var v=D.catalogo.filter(function(x){return x.id===id})[0]; if(!v)return;
    out+='<div class="riga"><div><b>'+h(v.titolo)+'</b></div><select data-id="'+h(id)+'">'+opzioni(scelte[id])+'</select></div>';
  });
  $('pesi').innerHTML=out;
  Array.prototype.forEach.call($('pesi').querySelectorAll('select'),function(sl){
    sl.onchange=function(){var id=sl.getAttribute('data-id'); if(id==='principale'){principale=sl.value}else{scelte[id]=sl.value}; $('passo3').className='box nascosto';};
  });
}
$('suggerisci').onclick=function(){
  var t=' '+$('libero').value.toLowerCase()+' ', n=0;
  D.catalogo.forEach(function(v){
    if(scelte[v.id]!==undefined)return;
    if(v.kw.some(function(k){return t.indexOf(k)>=0})){scelte[v.id]='qualche'; n++}
  });
  $('sugg_msg').textContent=t.trim()===''?'Scrivi prima qualcosa sopra.':(n?('Ho spuntato '+n+' voci: controlla che siano giuste.'):'Non ho riconosciuto voci nuove: spunta tu quelle che ti somigliano.');
  disegnaElenco();
};
function corpo(){
  return {voci:Object.keys(scelte).map(function(id){return {id:id,peso:scelte[id]}}),principale:principale,ricavi:Number($('ricavi').value||0),altro:$('altro').value};
}
function chiama(url,body){
  return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j}})});
}
$('calcola').onclick=function(){
  $('err').textContent=''; $('calcola').disabled=true;
  chiama('/api/dashboard/'+D.id+'/attivita/stima',corpo()).then(function(x){
    $('calcola').disabled=false;
    if(!x.ok||x.j.errore){$('err').textContent=x.j.errore||'Non riesco a calcolare adesso.';return}
    mostra(x.j);
  }).catch(function(){$('calcola').disabled=false;$('err').textContent='Non riesco a calcolare adesso. Riprova.'});
};
function mostra(r){
  var righe=r.righe.map(function(x){return '<tr><td>'+h(x.titolo)+'<br><span class="piccolo">codice '+h(x.codice)+'</span></td><td class="n">'+x.quota+'%</td><td class="n">'+h(x.coefficiente)+'</td><td class="n">'+eur(x.reddito)+'</td></tr>'}).join('');
  var d=r.differenza, pos=d>0;
  if(r.risparmio_affidabile===false){d=-1}
  var frase=r.risparmio_affidabile===false?'Il risparmio non è calcolabile in modo affidabile: con un\'attività commerciale i contributi INPS potrebbero cambiare':d>0?('Risparmio stimato: circa '+eur(d)+' all\'anno'):(d<0?('Con questo calcolo paghi circa '+eur(-d)+' in più all\'anno'):'Nessuna differenza rilevante');
  var av=r.avvisi.map(function(a,i){return '<div class="av2'+(i===0&&d<0?' rosso':'')+'"><b>'+h(a.titolo)+'.</b> '+h(a.testo)+'</div>'}).join('');
  $('ris').innerHTML='<table><thead><tr><th>Attività</th><th class="n">Peso</th><th class="n">Coefficiente</th><th class="n">Reddito forfettario</th></tr></thead><tbody>'+righe+'</tbody></table>'+
   '<div class="conf"><div><span class="piccolo">Oggi (tutto sul codice principale)</span><big>'+eur(r.oggi.totale)+'</big><span class="piccolo">tra imposta e contributi · coefficiente '+h(r.coefficiente_base)+'</span></div>'+
   '<div><span class="piccolo">Con il check (per attività)</span><big>'+eur(r.con_check.totale)+'</big><span class="piccolo">tra imposta e contributi · coefficiente '+h(r.coefficiente_misto)+'</span></div></div>'+
   '<div class="risp'+(d<0?' neg':'')+'">'+h(frase)+'</div>'+av+'<p class="piccolo">'+h(r.nota)+'</p>';
  $('passo3').className='box';
  $('passo3').scrollIntoView({behavior:'smooth',block:'start'});
}
$('salva').onclick=function(){
  $('esito').textContent=''; $('salva').disabled=true;
  chiama('/api/dashboard/'+D.id+'/attivita/salva',corpo()).then(function(x){
    $('salva').disabled=false;
    if(!x.ok||x.j.errore){$('esito').className='err';$('esito').textContent=x.j.errore||'Non riesco a salvare adesso.';return}
    $('esito').className='ok'; $('esito').innerHTML='Fatto. <a href="/d/'+D.id+'#ottimizzazione">Torna alla dashboard</a>';
  }).catch(function(){$('salva').disabled=false;$('esito').className='err';$('esito').textContent='Non riesco a salvare adesso.'});
};
$('togli').onclick=function(){
  if(!confirm('Tolgo il check? La dashboard tornerà a usare solo il codice principale.'))return;
  chiama('/api/dashboard/'+D.id+'/attivita/salva',{voci:[],altro:$('altro').value}).then(function(x){
    if(x.ok){scelte={};disegnaElenco();$('sugg_msg').textContent='Check tolto: la dashboard usa di nuovo solo il codice principale.'}
  });
};
disegnaElenco();

// ---- assistente per capire le proprie attivita'
(function(){
  if(!D.chat)return;
  var fab=$('fabx'), bub=$('fbub'), cx=$('cx'), ms=$('ms'), storia=[], occupato=false, avviato=false;
  fab.className='fabx trilla'; bub.className='fbub';
  setTimeout(function(){fab.className='fabx'; bub.className='fbub nascosto'},15000);
  $('fbub-x').onclick=function(){bub.className='fbub nascosto'};
  function agg(cl,testo){var m=document.createElement('div');m.className='cm '+cl;m.innerHTML=h(testo).replace(/\n/g,'<br>');ms.appendChild(m);ms.scrollTop=ms.scrollHeight;return m}
  function apri(){
    bub.className='fbub nascosto'; fab.className='fabx'; fab.style.display='none'; cx.hidden=false;
    if(!avviato){avviato=true;
      agg('a','Ciao! Raccontami con parole tue cosa fai per i clienti, anche in modo disordinato: ti aiuto a capire quali voci della lista ti somigliano. Se non sai da dove partire, scrivimi "non so cosa scrivere" e ti faccio qualche domanda.');
      $('ch').innerHTML=['Non so cosa scrivere','Faccio marketing e a volte altro','Cosa conta come attività diversa?'].map(function(x){return '<button type="button">'+h(x)+'</button>'}).join('');
      Array.prototype.forEach.call($('ch').querySelectorAll('button'),function(b){b.onclick=function(){invia(b.textContent)}});
    }
    $('ci').focus();
  }
  function chiudi(){cx.hidden=true; fab.style.display=''}
  fab.onclick=apri; $('cx-x').onclick=chiudi;
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!cx.hidden)chiudi()});
  function spunta(ids){
    var nuove=0; ids.forEach(function(id){if(scelte[id]===undefined){scelte[id]='qualche';nuove++}});
    disegnaElenco(); chiudi();
    $('sugg_msg').textContent=nuove?('L\'assistente ha spuntato '+nuove+(nuove===1?' voce':' voci')+': controlla che siano giuste.'):'Quelle voci erano già spuntate.';
    document.getElementById('elenco').scrollIntoView({behavior:'smooth',block:'start'});
  }
  function invia(testo){
    testo=(testo||'').trim(); if(!testo||occupato)return; occupato=true; $('ch').innerHTML=''; $('ci').value='';
    agg('u',testo); var att=agg('a p','Ci penso…');
    fetch('/api/dashboard/'+D.id+'/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domanda:testo,storia:storia,contesto:'attivita'})})
      .then(function(r){return r.json()}).then(function(j){
        att.remove();
        if(j.ok){
          storia.push({ruolo:'utente',testo:testo},{ruolo:'assistente',testo:j.risposta}); storia=storia.slice(-6);
          var m=agg('a',j.risposta);
          var ids=(j.voci||[]);
          if(ids.length){var b=document.createElement('button');b.type='button';b.className='sp';b.textContent='Spunta le voci che mi hai suggerito ('+ids.length+')';b.onclick=function(){spunta(ids)};m.appendChild(b)}
          if(j.rimaste!=null)$('nt').textContent='Risposte indicative, non sono una consulenza. Domande rimaste oggi: '+j.rimaste+'.';
        }else{agg('a',j.errore||'Non riesco a rispondere ora.')}
        occupato=false; $('ci').focus();
      }).catch(function(){att.remove();agg('a','Connessione persa: riprova tra un momento.');occupato=false});
  }
  $('cf').onsubmit=function(e){e.preventDefault();invia($('ci').value)};
})();

if(Object.keys(scelte).length&&D.ricavi){/* check gia' fatto: si puo' rivedere con un clic */}
</script></body></html>
"""
