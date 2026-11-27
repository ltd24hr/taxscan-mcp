"""TaxScan - dichiarazione dei redditi guidata per i forfettari (modello Redditi PF).

Dai dati confermati dalla persona calcola, rigo per rigo, quello che va scritto nella dichiarazione online
dell'Agenzia delle Entrate: quadro LM sezione III (forfettari) e IV, quadro RR (contributi INPS), quadro RS
(obblighi informativi dei forfettari), quadro RX (debito o credito di imposta sostitutiva), piu' gli F24 di
saldo e acconti. Regole dalle istruzioni ufficiali Redditi PF 2026 (fascicolo 2 quadro RR, fascicolo 3 quadri LM
e RS). Per l'anno d'imposta 2026 (dichiarazione 2027) vale come anteprima finche' l'Agenzia non pubblica il
modello nuovo, di solito a marzo.

Prima versione: solo chi ha esclusivamente redditi in regime forfettario. Chi ha altri redditi (lavoro dipendente,
pensione, affitti, redditi esteri, cripto) viene indirizzato a un professionista.

Archivio (tabella prova_doc): dichiarazione/<c>/<anno> -> i dati confermati nei passi.
"""
from __future__ import annotations

import datetime
import re

import dati_fisco as D

MODELLO = "Redditi PF 2026"   # istruzioni usate; per l'anno 2026 si aggiorna quando esce il modello 2027
SOGLIA_ACCONTO = 51.65
SOGLIA_RATA_UNICA = 206.0
_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


def _n(x, d=0.0) -> float:
    try:
        if isinstance(x, str):
            x = x.strip().replace("€", "").replace(" ", "")
            if "," in x:
                x = x.replace(".", "").replace(",", ".")
        return float(x)
    except (TypeError, ValueError):
        return d


def _r(x) -> int:
    """Nella dichiarazione gli importi si scrivono in unita' di euro, arrotondati."""
    return int(round(_n(x)))


def _eur(v) -> str:
    return f"{_n(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


# ------------------------------------------------------------------ dati di partenza

def vuoti(anno: int) -> dict:
    return {"anno": anno, "altri_redditi": [], "tipo": "autonomo", "ateco2025": "", "primo_anno": False,
            "aliquota5": False, "requisiti_ok": True, "attivita": [], "gestione": "separata", "altra_copertura": False,
            "riduzione": "no", "mesi": 12, "ante_1996": False, "codice_azienda": "", "codice_inps": "",
            "contributi_versati": 0.0, "fissi_versati": 0.0, "acconti_inps_versati": 0.0, "perdite": 0.0,
            "crediti": 0.0, "acconti_versati": 0.0, "eccedenza_prec": 0.0, "eccedenza_compensata": 0.0,
            "rs": {"veicoli": 0, "acquisti": 0.0, "beni_terzi": 0.0, "carburante": 0.0, "consumi": 0.0, "senza_ritenuta": []},
            "passo": 1, "fatti": []}


def pulisci(x: dict, anno: int) -> dict:
    """Tiene solo i campi previsti, con i tipi giusti."""
    v = vuoti(anno)
    x = x if isinstance(x, dict) else {}
    for k in ("primo_anno", "aliquota5", "requisiti_ok", "altra_copertura", "ante_1996"):
        if k in x:
            v[k] = bool(x[k])
    for k in ("contributi_versati", "fissi_versati", "acconti_inps_versati", "perdite", "crediti", "acconti_versati",
              "eccedenza_prec", "eccedenza_compensata"):
        if k in x:
            v[k] = max(0.0, round(_n(x[k]), 2))
    if x.get("tipo") in ("impresa", "autonomo", "impresa_familiare"):
        v["tipo"] = x["tipo"]
    if x.get("gestione") in ("separata", "artigiani", "commercianti", "cassa"):
        v["gestione"] = x["gestione"]
    if x.get("riduzione") in ("no", "35", "50"):
        v["riduzione"] = x["riduzione"]
    v["mesi"] = max(1, min(12, int(_n(x.get("mesi"), 12) or 12)))
    v["ateco2025"] = re.sub(r"[^0-9.]", "", str(x.get("ateco2025") or ""))[:10]
    v["codice_azienda"] = re.sub(r"[^0-9A-Za-z]", "", str(x.get("codice_azienda") or "")).upper()[:10]
    v["codice_inps"] = re.sub(r"[^0-9A-Za-z]", "", str(x.get("codice_inps") or "")).upper()[:17]
    v["altri_redditi"] = [a for a in (x.get("altri_redditi") or []) if a in ("dipendente", "affitti", "estero", "altro")]
    att = []
    for a in (x.get("attivita") or [])[:6]:
        if not isinstance(a, dict):
            continue
        cod = re.sub(r"[^0-9.]", "", str(a.get("ateco") or ""))[:10]
        coeff = _n(a.get("coeff"), 0)
        if coeff > 1:
            coeff = coeff / 100
        if not coeff and cod:
            import calcoli
            coeff = calcoli.coefficiente_da_ateco(cod).get("coefficiente") or 0
        att.append({"ateco": cod, "coeff": round(coeff, 2), "ricavi": max(0.0, round(_n(a.get("ricavi")), 2)),
                    "natura": "impresa" if a.get("natura") == "impresa" else "autonomo", "nome": str(a.get("nome") or "")[:80]})
    v["attivita"] = att
    rs = x.get("rs") if isinstance(x.get("rs"), dict) else {}
    v["rs"] = {"veicoli": max(0, int(_n(rs.get("veicoli"), 0))), "acquisti": max(0.0, _n(rs.get("acquisti"))),
               "beni_terzi": max(0.0, _n(rs.get("beni_terzi"))), "carburante": max(0.0, _n(rs.get("carburante"))),
               "consumi": max(0.0, _n(rs.get("consumi"))),
               "senza_ritenuta": [{"cf": re.sub(r"[^0-9A-Za-z]", "", str(p.get("cf") or "")).upper()[:16],
                                   "importo": max(0.0, _n(p.get("importo")))}
                                  for p in (rs.get("senza_ritenuta") or [])[:12] if isinstance(p, dict)]}
    v["passo"] = max(1, min(7, int(_n(x.get("passo"), 1) or 1)))
    v["fatti"] = [int(p) for p in (x.get("fatti") or []) if str(p).isdigit()][:7]
    return v


# ------------------------------------------------------------------ calcolo

def _gruppo(cod: str) -> str:
    import calcoli
    return calcoli.coefficiente_da_ateco(cod).get("gruppo") or cod


def calcola(v: dict) -> dict:
    """Righi della dichiarazione, F24 e controlli a partire dai dati confermati."""
    anno = int(v.get("anno") or datetime.date.today().year)
    avvisi, righi = [], []

    def rigo(quadro, r, col, desc, val, nota=""):
        righi.append({"quadro": quadro, "rigo": r, "col": col, "desc": desc, "val": val, "nota": nota})

    if v.get("altri_redditi"):
        avvisi.append({"livello": "importante", "testo": "Hai anche altri redditi: oltre a questi quadri servono quelli per gli altri redditi "
                                                         "e il quadro RN. Ti consiglio di farla controllare da un commercialista."})

    # attivita': una riga per gruppo di coefficiente (LM22-LM27), codice dell'attivita' prevalente del gruppo
    gruppi: dict = {}
    for a in v.get("attivita") or []:
        g = (a["coeff"], _gruppo(a["ateco"]) if a["ateco"] else str(a["coeff"]))
        x = gruppi.setdefault(g, {"ateco": a["ateco"], "coeff": a["coeff"], "ricavi": 0.0, "max": -1, "natura": a["natura"]})
        x["ricavi"] += a["ricavi"]
        if a["ricavi"] > x["max"]:
            x.update({"max": a["ricavi"], "ateco": a["ateco"], "natura": a["natura"]})
    righe_att = sorted(gruppi.values(), key=lambda x: -x["ricavi"])[:6]
    ricavi_tot = sum(x["ricavi"] for x in righe_att)
    if ricavi_tot > 85000:
        avvisi.append({"livello": "importante", "testo": f"Gli incassi superano 85.000 € ({_eur(ricavi_tot)}): dall'anno dopo si esce dal forfettario"
                                                         + (" e sopra i 100.000 € si esce subito, già da quest'anno. Serve un professionista." if ricavi_tot > 100000 else ".")})

    # LM21
    rigo("LM", "LM21", "1", "Requisiti del regime rispettati (incassi, spese per il personale)", "Barrata" if v.get("requisiti_ok", True) else "Da verificare")
    rigo("LM", "LM21", "2", "Nessuna causa di esclusione dal regime", "Barrata" if v.get("requisiti_ok", True) else "Da verificare")
    rigo("LM", "LM21", "3", "Nuova attività: imposta al 5%", "Barrata" if v.get("aliquota5") else "Non barrata")
    rigo("LM", "LM21", "4", "Codice ATECO 2025 dell'attività", v.get("ateco2025") or (righe_att[0]["ateco"] if righe_att else ""),
         "Il codice in vigore dal 2025: lo trovi nel cassetto fiscale o sul certificato di attribuzione aggiornato.")
    rigo("LM", "LM21", "Casella", "Tipo di attività", {"impresa": "Impresa", "autonomo": "Autonomo", "impresa_familiare": "Impresa familiare"}[v.get("tipo", "autonomo")])

    lordo_imp = lordo_aut = 0.0
    for i, x in enumerate(righe_att):
        n = f"LM{22 + i}"
        red = round(x["ricavi"] * x["coeff"], 2)
        if x["natura"] == "impresa":
            lordo_imp += red
        else:
            lordo_aut += red
        rigo("LM", n, "1", "Codice ATECO 2007 dell'attività prevalente del gruppo", x["ateco"])
        rigo("LM", n, "2", "Coefficiente di redditività", f"{x['coeff'] * 100:.0f}")
        rigo("LM", n, "3", "Ricavi o compensi incassati nell'anno", _r(x["ricavi"]))
        rigo("LM", n, "5", "Reddito (colonna 3 × coefficiente)", _r(red))
        rigo("LM", n, "6", "Natura dell'attività", "1 (impresa)" if x["natura"] == "impresa" else "2 (lavoro autonomo)")
    lordo = round(lordo_imp + lordo_aut, 2)
    gest = v.get("gestione") or "separata"
    col1 = lordo_imp if gest in ("artigiani", "commercianti") else 0.0
    col2 = lordo_aut if gest == "separata" else 0.0
    if col1:
        rigo("LM", "LM34", "1", "Reddito lordo per la gestione artigiani e commercianti", _r(col1))
    if col2:
        rigo("LM", "LM34", "2", "Reddito lordo per la gestione separata", _r(col2))
    rigo("LM", "LM34", "3", "Reddito lordo (somma dei redditi delle attività)", _r(lordo))

    contrib = round(_n(v.get("contributi_versati")), 2)
    capienti = min(contrib, lordo)
    eccedenza_contr = round(contrib - capienti, 2)
    rigo("LM", "LM35", "1", "Contributi previdenziali versati nell'anno", _r(contrib),
         "Quelli pagati davvero nell'anno (per cassa), anche se riferiti all'anno prima.")
    rigo("LM", "LM35", "2", "Contributi che trovano capienza nel reddito", _r(capienti))
    netto = round(lordo - capienti, 2)
    rigo("LM", "LM36", "", "Reddito netto", _r(netto))
    perdite = min(round(_n(v.get("perdite")), 2), netto)
    if perdite:
        rigo("LM", "LM37", "5", "Perdite degli anni precedenti usate", _r(perdite))
    imponibile = round(netto - perdite, 2)
    rigo("LM", "LM38", "", "Reddito soggetto a imposta sostitutiva", _r(imponibile))
    aliq = 0.05 if v.get("aliquota5") else 0.15
    imposta = round(max(0.0, _r(imponibile)) * aliq, 2)
    rigo("LM", "LM39", "", f"Imposta sostitutiva ({int(aliq * 100)}%)", _r(imposta))
    crediti = min(round(_n(v.get("crediti")), 2), imposta)
    if crediti:
        rigo("LM", "LM40", "41", "Crediti d'imposta usati", _r(crediti))
    diff = round(_r(imposta) - _r(crediti), 2)
    rigo("LM", "LM42", "", "Differenza (imposta meno crediti)", _r(diff))
    ecc_prec, ecc_comp = _n(v.get("eccedenza_prec")), _n(v.get("eccedenza_compensata"))
    if ecc_prec:
        rigo("LM", "LM43", "", "Credito d'imposta sostitutiva della dichiarazione precedente", _r(ecc_prec))
    if ecc_comp:
        rigo("LM", "LM44", "", "Parte di quel credito già usata in F24", _r(ecc_comp))
    acc = _n(v.get("acconti_versati"))
    rigo("LM", "LM45", "2", "Acconti versati per l'anno (codici 1790 e 1791)", _r(acc))
    saldo = _r(diff) - _r(ecc_prec) + _r(ecc_comp) - _r(acc)
    if saldo >= 0:
        rigo("LM", "LM46", "1", "Imposta a debito (saldo da pagare con codice 1792)", saldo)
        rigo("RX", "RX31", "1", "Imposta sostitutiva a debito (da LM46)", saldo)
    else:
        rigo("LM", "LM47", "1", "Imposta a credito", -saldo)
        rigo("RX", "RX31", "2", "Imposta sostitutiva a credito (da LM47)", -saldo)
        rigo("RX", "RX31", "5", "Credito da usare in compensazione (o chiedi il rimborso in colonna 4)", -saldo)
    if eccedenza_contr > 0:
        rigo("LM", "LM49", "", "Contributi in più del reddito (deducibili dagli altri redditi, quadro RP rigo RP21)", _r(eccedenza_contr))
        avvisi.append({"livello": "informativo", "testo": "Hai versato più contributi del reddito forfettario: l'eccedenza va nel rigo LM49 e si "
                                                          "deduce dagli altri redditi nel quadro RP (rigo RP21)."})

    # quadro RR
    f24 = []
    contrib_anno = 0.0
    acconti_inps_prox = []
    if gest == "separata":
        import calcoli
        c = calcoli._contributi_gestione_separata(col2 or lordo, bool(v.get("altra_copertura")))
        contrib_anno = c["totale_contributi"]
        vers = _n(v.get("acconti_inps_versati"))
        rigo("RR", "RR5", "1", "Codice del reddito", "1")
        rigo("RR", "RR5", "2", "Reddito (dal rigo LM34 colonna 2)", _r(col2 or lordo))
        rigo("RR", "RR5", "11", "Reddito imponibile previdenziale", _r(c["imponibile_previdenziale"]))
        rigo("RR", "RR5", "12-13", "Periodo (dal mese / al mese)", f"{13 - v.get('mesi', 12):02d} / 12")
        rigo("RR", "RR5", "14", "Codice aliquota", "A (24%)" if v.get("altra_copertura") else "C (26,07%)")
        rigo("RR", "RR5", "15", "Contributo dovuto", _r(contrib_anno))
        rigo("RR", "RR5", "16", "Acconti versati per l'anno con F24", _r(vers))
        rigo("RR", "RR6", "1", "Totale contributi dovuti", _r(contrib_anno))
        rigo("RR", "RR6", "2", "Totale acconti versati", _r(vers))
        dov = _r(contrib_anno) - _r(vers)
        if dov >= 0:
            rigo("RR", "RR7", "", "Contributo a debito (saldo, codice PXX)", dov)
        else:
            rigo("RR", "RR8", "1", "Contributo a credito", -dov)
        rigo("RR", "RR12", "1", "Totale contributi dovuti alla gestione separata", _r(contrib_anno))
        if dov >= 0:
            rigo("RR", "RR12", "2", "Totale contributi a debito", dov)
        else:
            rigo("RR", "RR12", "3", "Totale contributi a credito", -dov)
        if dov > 0:
            f24.append({"quando": "giugno", "sezione": "INPS", "codice": "PXX", "anno": anno, "desc": "Saldo contributi gestione separata", "importo": dov})
        acc_inps = round(contrib_anno * 0.80, 2)
        if acc_inps > 0:
            m = round(acc_inps / 2, 2)
            acconti_inps_prox = [{"quando": "giugno", "sezione": "INPS", "codice": "P10", "anno": anno + 1, "desc": "1° acconto contributi gestione separata", "importo": m},
                                 {"quando": "novembre", "sezione": "INPS", "codice": "P11", "anno": anno + 1, "desc": "2° acconto contributi gestione separata", "importo": m}]
    elif gest in ("artigiani", "commercianti"):
        import calcoli
        P = D.ARTIGIANI_COMMERCIANTI
        mesi = v.get("mesi", 12)
        rid = v.get("riduzione")
        c = calcoli._contributi_artigiani_commercianti(col1 or lordo, gest, rid == "35", bool(v.get("ante_1996")), mesi,
                                                       mesi if rid == "50" else 0)
        contrib_anno = c["totale_contributi"]
        minimale = round(P["minimale_reddito"] * mesi / 12, 2)
        massimale = P["massimale_ante_1996"] if v.get("ante_1996") else P["massimale_post_1996"]
        ecc_red = max(0.0, min(col1 or lordo, massimale) - minimale)
        mat = round(P["maternita_mensile"] * mesi, 2)
        fissi = round(c["contributi_fissi"], 2)
        ivs_min = round(fissi - mat, 2)
        if rid == "35":
            # lo sconto del 35% vale sulla quota per la pensione, non sulla maternita'
            ivs_min = round((P[gest]["fisso_annuo"] * mesi / 12 - mat) * (1 - P["riduzione_forfettari"]), 2)
        var = round(c["contributi_variabili"], 2)
        if v.get("codice_azienda"):
            rigo("RR", "RR1", "1", "Codice azienda INPS", v["codice_azienda"])
        rigo("RR", "RR2", "Tipologia", "Tipologia iscritto", "1 (titolare)")
        rigo("RR", "RR2", "2", "Codice INPS della posizione (17 caratteri, è quello dell'F24 dei contributi)", v.get("codice_inps") or "Da completare")
        rigo("RR", "RR2", "3", "Reddito d'impresa dell'anno (dal rigo LM34 colonna 1)", _r(col1 or lordo))
        rigo("RR", "RR2", "4-5", "Periodo (dal mese / al mese)", f"{13 - mesi:02d} / 12")
        if not v.get("ante_1996"):
            rigo("RR", "RR2", "6", "Iscritto dal 1996 senza contributi precedenti", "Barrata")
        if rid in ("35", "50"):
            rigo("RR", "RR2", "7", "Codice agevolazione", "C (riduzione 35% forfettari)" if rid == "35" else "E (riduzione 50% nuovi iscritti)")
            rigo("RR", "RR2", "8-9", "Periodo della riduzione", f"{13 - mesi:02d} / 12")
        rigo("RR", "RR2", "10", "Reddito minimale", _r(minimale))
        rigo("RR", "RR2", "11", "Contributi IVS sul minimale (già al netto delle riduzioni)", _r(ivs_min))
        rigo("RR", "RR2", "12", "Contributo di maternità", round(mat, 2))
        fv = _n(v.get("fissi_versati"))
        rigo("RR", "RR2", "14", "Contributi fissi versati (rate di maggio, agosto, novembre e febbraio)", _r(fv))
        d1 = _r(ivs_min) + _r(mat) - _r(fv)
        rigo("RR", "RR2", "16" if d1 >= 0 else "17", "Contributi sul minimale a debito" if d1 >= 0 else "Contributi sul minimale a credito", abs(d1))
        rigo("RR", "RR2", "24", "Reddito eccedente il minimale", _r(ecc_red))
        rigo("RR", "RR2", "25", "Contributi IVS sul reddito eccedente", _r(var))
        av = _n(v.get("acconti_inps_versati"))
        rigo("RR", "RR2", "27", "Acconti versati sul reddito eccedente", _r(av))
        d2 = _r(var) - _r(av)
        rigo("RR", "RR2", "29" if d2 >= 0 else "30", "Saldo a debito sul reddito eccedente" if d2 >= 0 else "Credito sul reddito eccedente", abs(d2))
        cod = "AP" if gest == "artigiani" else "CP"
        if d2 > 0:
            f24.append({"quando": "giugno", "sezione": "INPS", "codice": cod, "anno": anno, "desc": "Saldo contributi sul reddito eccedente il minimale", "importo": d2})
        if d1 > 10:
            avvisi.append({"livello": "informativo", "testo": f"Risultano {_eur(d1)} di contributi fissi non ancora versati: controlla le rate e versale con il codice "
                                                             + ("AF" if gest == "artigiani" else "CF") + "."})
        if var > 0:
            m = round(var / 2, 2)
            acconti_inps_prox = [{"quando": "giugno", "sezione": "INPS", "codice": cod, "anno": anno + 1, "desc": "1° acconto contributi sul reddito eccedente", "importo": m},
                                 {"quando": "novembre", "sezione": "INPS", "codice": cod, "anno": anno + 1, "desc": "2° acconto contributi sul reddito eccedente", "importo": m}]
        avvisi.append({"livello": "informativo", "testo": "I contributi fissi dell'anno prossimo si pagano a rate (16 maggio, 20 agosto, 16 novembre e 16 febbraio) "
                                                         "con i moduli che l'INPS mette nel Cassetto previdenziale."})
    else:
        avvisi.append({"livello": "informativo", "testo": "Con una cassa professionale il quadro RR non si compila: i contributi si dichiarano alla tua cassa, "
                                                         "con le sue regole e scadenze."})

    # quadro RS
    rs = v.get("rs") or {}
    for i, p in enumerate((rs.get("senza_ritenuta") or [])[:12]):
        n = f"RS{371 + (i % 3)}"
        rigo("RS", n, "1", "Codice fiscale di chi hai pagato senza ritenuta" + (f" (modulo {i // 3 + 1})" if i >= 3 else ""), p["cf"])
        rigo("RS", n, "2", "Importo pagato", _r(p["importo"]))
    if v.get("tipo") in ("impresa", "impresa_familiare") or lordo_imp:
        rigo("RS", "RS375", "", "Veicoli usati per l'attività a fine anno", int(rs.get("veicoli") or 0))
        rigo("RS", "RS376", "", "Acquisti di materie prime, merci e lavorazioni di terzi", _r(rs.get("acquisti")))
        rigo("RS", "RS377", "", "Affitti, noleggi, leasing e royalties", _r(rs.get("beni_terzi")))
        rigo("RS", "RS378", "", "Carburante per i veicoli", _r(rs.get("carburante")))
    if v.get("tipo") == "autonomo" or lordo_aut:
        rigo("RS", "RS381", "", "Consumi: telefono, luce, carburante", _r(rs.get("consumi")))

    # F24 dell'imposta
    if saldo > 0:
        f24.append({"quando": "giugno", "sezione": "Erario", "codice": "1792", "anno": anno, "desc": "Saldo imposta sostitutiva", "importo": saldo})
    base_acc = _r(diff)
    acconti_prox = []
    if base_acc > SOGLIA_ACCONTO:
        if base_acc <= SOGLIA_RATA_UNICA:
            acconti_prox = [{"quando": "novembre", "sezione": "Erario", "codice": "1791", "anno": anno + 1, "desc": "Acconto imposta sostitutiva (unica rata)", "importo": base_acc}]
        else:
            m = round(base_acc / 2, 2)
            acconti_prox = [{"quando": "giugno", "sezione": "Erario", "codice": "1790", "anno": anno + 1, "desc": "1° acconto imposta sostitutiva", "importo": m},
                            {"quando": "novembre", "sezione": "Erario", "codice": "1791", "anno": anno + 1, "desc": "2° acconto imposta sostitutiva", "importo": m}]
    tutti = f24 + [x for x in acconti_prox + acconti_inps_prox]
    giugno = round(sum(x["importo"] for x in tutti if x["quando"] == "giugno"), 2)
    novembre = round(sum(x["importo"] for x in tutti if x["quando"] == "novembre"), 2)

    if not righe_att or not ricavi_tot:
        avvisi.append({"livello": "importante", "testo": "Mancano gli incassi dell'anno: senza non posso calcolare il reddito."})
    if v.get("aliquota5") and not v.get("requisiti_ok", True):
        avvisi.append({"livello": "importante", "testo": "Il 5% spetta solo se l'attività è davvero nuova: verificalo prima di barrare LM21 colonna 3."})

    return {"anno": anno, "modello": MODELLO, "righi": righi, "avvisi": avvisi,
            "riepilogo": {"ricavi": round(ricavi_tot, 2), "reddito_lordo": lordo, "contributi_dedotti": capienti,
                          "imponibile": imponibile, "aliquota": int(aliq * 100), "imposta": imposta, "saldo_imposta": saldo,
                          "contributi_anno": round(contrib_anno, 2), "giugno": giugno, "novembre": novembre},
            "f24": tutti, "scadenze": {"giugno": f"30 giugno {anno + 1}", "novembre": f"30 novembre {anno + 1}"},
            "nota": ("Calcolo preparato da TaxScan sulle istruzioni ufficiali del modello " + MODELLO + ". "
                     + (f"Per i redditi {anno} la dichiarazione si presenta nel {anno + 1}: quando l'Agenzia pubblica il modello nuovo "
                        "(di solito a marzo) controllo e aggiorno i righi. " if anno >= 2026 else "")
                     + "È una guida: i numeri sono quelli che hai confermato tu, e resti tu responsabile di quello che dichiari.")}


# ------------------------------------------------------------------ dai dati che TaxScan ha gia'

def anno_da_preparare(oggi: datetime.date | None = None) -> int:
    """Fino a ottobre si prepara la dichiarazione dell'anno prima; da novembre quella dell'anno in corso (in anteprima)."""
    oggi = oggi or datetime.date.today()
    return oggi.year if oggi.month >= 11 else oggi.year - 1


def precompila(sch: dict, anno: int, oggi: datetime.date | None = None) -> dict:
    """Riempie i passi con quello che la scheda di TaxScan sa gia'. 'stime' elenca i campi da far controllare."""
    import calcoli
    import scheda as S
    oggi = oggi or datetime.date.today()
    s = S._normalizza(dict(sch or {}))
    v = vuoti(anno)
    stime = []
    ges = s.get("gestione_previdenziale") or "separata"
    if ges == "non_so":
        ges = "separata"
    v["gestione"] = ges
    tipo = s.get("tipo_attivita")
    v["tipo"] = "impresa" if tipo in ("artigiano", "commerciante") or ges in ("artigiani", "commercianti") else "autonomo"
    v["altra_copertura"] = bool(s.get("altra_copertura_previdenziale"))
    v["mesi"] = max(1, S.mesi_attivita(s, anno) or 12)
    if S.mesi_riduzione_50(s, anno):
        v["riduzione"] = "50"
    elif s.get("riduzione_35"):
        v["riduzione"] = "35"
    ing = s.get("anno_ingresso_forfettario")
    try:
        entro5 = not ing or anno - int(ing) < 5
    except (TypeError, ValueError):
        entro5 = True
    v["aliquota5"] = str(s.get("aliquota")) == "5" and entro5
    if s.get("redditi_dipendente_pensione"):
        v["altri_redditi"] = ["dipendente"]
    try:
        ap = int(str(s.get("data_apertura") or "")[:4])
        v["primo_anno"] = ap == anno
        if ap < 1996:
            v["ante_1996"] = True
    except ValueError:
        pass
    cod = s.get("codice_ateco") or ""
    v["ateco2025"] = cod

    cur = oggi.year
    ricavi = s.get("ricavi_anno_corrente") if anno == cur else s.get("ricavi_anno_precedente") if anno == cur - 1 else 0
    ricavi = round(_n(ricavi), 2)
    if anno == cur:
        stime.append("ricavi")
    try:
        import attivita
        rr = attivita.righe(s)
    except Exception:
        rr = None
    if rr:
        for x in rr:
            nat = "impresa" if v["tipo"] == "impresa" or x.get("commercio") else "autonomo"
            v["attivita"].append({"ateco": x["codice"], "coeff": x["coeff"], "ricavi": round(ricavi * x["quota"], 2),
                                  "natura": nat, "nome": x["titolo"]})
    else:
        info = calcoli.coefficiente_da_ateco(cod) if cod else {}
        v["attivita"].append({"ateco": cod, "coeff": info.get("coefficiente") or 0.78, "ricavi": ricavi, "natura": v["tipo"],
                              "nome": "La tua attività"})

    # quello che si e' versato nell'anno: lo stimo dall'anno prima, va controllato sugli F24
    prev = None
    rprev = s.get("ricavi_anno_precedente") if anno == cur else None
    if rprev:
        try:
            prev = S._calcolo(s, float(rprev), s.get("contributi_versati_anno_precedente"), anno - 1)
        except Exception:
            prev = None
    if anno == cur - 1 and s.get("contributi_versati_anno_precedente"):
        v["contributi_versati"] = round(_n(s.get("contributi_versati_anno_precedente")), 2)
    if isinstance(prev, dict) and "errore" not in prev:
        cp = prev.get("contributi_previdenziali") or {}
        tot = _n(cp.get("totale_contributi"))
        imp = _n(prev.get("imposta_sostitutiva"))
        v["contributi_versati"] = round(tot, 2)
        stime.append("contributi_versati")
        v["acconti_versati"] = round(imp, 2) if imp > SOGLIA_ACCONTO else 0.0
        stime.append("acconti_versati")
        if ges == "separata":
            v["acconti_inps_versati"] = round(tot * 0.8, 2)
            stime.append("acconti_inps_versati")
        elif ges in ("artigiani", "commercianti"):
            v["acconti_inps_versati"] = round(_n(cp.get("contributi_variabili")), 2)
            stime.append("acconti_inps_versati")
    if ges in ("artigiani", "commercianti"):
        P = D.ARTIGIANI_COMMERCIANTI
        f = P[ges]["fisso_annuo"] * v["mesi"] / 12
        if v["riduzione"] == "35":
            f *= 1 - P["riduzione_forfettari"]
        v["fissi_versati"] = round(f, 2)
        stime.append("fissi_versati")
    v["stime"] = stime
    return v


# ------------------------------------------------------------------ archivio e richieste dell'app

def _chiave(c: str, anno: int) -> str:
    return f"dichiarazione/{c}/{anno}"


def apri(c: str, anno: int | None = None) -> dict:
    """I dati della dichiarazione: quelli salvati, o quelli precompilati da TaxScan."""
    import db
    import pagamenti
    if not c or not _ID.match(c):
        return {"ok": False}
    dati = db.carica_dashboard(c)
    if not dati:
        return {"ok": False}
    oggi = datetime.date.today()
    anno = int(anno or anno_da_preparare(oggi))
    if anno not in (oggi.year, oggi.year - 1):
        anno = anno_da_preparare(oggi)
    salv = pagamenti._get(_chiave(c, anno))
    stime = []
    if isinstance(salv, dict) and salv.get("v"):
        v = pulisci(salv["v"], anno)
    else:
        v = precompila(dati.get("_scheda") or {}, anno, oggi)
        stime = v.pop("stime", [])
    return {"ok": True, "anno": anno, "anni": [oggi.year - 1, oggi.year] if oggi.month >= 11 else [oggi.year - 1],
            "anteprima": anno >= 2026, "dati": v, "stime": stime, "salvato": bool(salv), "risultato": calcola(v),
            "attivo": (not pagamenti.attivo()) or pagamenti.pagato(c)}


def salva(c: str, anno, x: dict) -> dict:
    import db
    import pagamenti
    if not c or not _ID.match(c) or not db.carica_dashboard(c):
        return {"ok": False}
    oggi = datetime.date.today()
    try:
        anno = int(anno)
    except (TypeError, ValueError):
        anno = anno_da_preparare(oggi)
    if anno not in (oggi.year, oggi.year - 1):
        return {"ok": False, "errore": "Anno non valido."}
    v = pulisci(x, anno)
    pagamenti._set(_chiave(c, anno), {"v": v, "agg": oggi.isoformat()})
    try:
        db.registra_evento("dichiarazione_salvata", c, {"anno": anno, "passo": v["passo"]})
    except Exception:
        pass
    return {"ok": True, "anno": anno, "dati": v, "risultato": calcola(v)}


def ricomincia(c: str, anno) -> dict:
    import pagamenti
    if not c or not _ID.match(c):
        return {"ok": False}
    try:
        pagamenti._set(_chiave(c, int(anno)), {})
    except Exception:
        return {"ok": False}
    return apri(c, int(anno))


_CONTROLLI: dict = {}


def chiedi_controllo(c: str, anno, nota: str = "") -> dict:
    """«Falla controllare a un commercialista»: la richiesta arriva a TaxScan, che la affida a un commercialista partner.
    Serve l'email confermata (cosi' il professionista sa a chi rispondere); al massimo due richieste al giorno."""
    import html as H
    import os
    import time
    import auth
    import azioni
    import db
    if not c or not _ID.match(c):
        return {"ok": False}
    try:
        mia, ok = azioni.verificata(c)
    except Exception:
        mia, ok = "", False
    if not ok or not mia:
        return {"ok": False, "errore": "Prima conferma la tua email nel Profilo: così il commercialista sa a chi rispondere."}
    ora = time.time()
    l = [t for t in _CONTROLLI.get(c, []) if ora - t < 86400]
    if len(l) >= 2:
        return {"ok": False, "errore": "Hai già mandato la richiesta oggi: ti rispondiamo appena possibile."}
    admin = os.environ.get("ADMIN_EMAIL", "")
    a = apri(c, anno)
    if not a.get("ok") or not admin:
        return {"ok": False, "errore": "Non è partita: riprova tra poco."}
    r = a["risultato"]
    rp = r["riepilogo"]
    tab = "".join(f"<tr><td>{H.escape(x['rigo'])}</td><td>{H.escape(str(x['col']))}</td><td>{H.escape(x['desc'])}</td>"
                  f"<td style='text-align:right'>{H.escape(str(x['val']))}</td></tr>" for x in r["righi"])
    corpo = (f"<p>Richiesta di controllo della dichiarazione (redditi {r['anno']}).</p>"
             f"<p><b>Email della persona:</b> {H.escape(mia)}<br><b>Situazione:</b> {H.escape(c)}</p>"
             + (f"<p><b>Nota:</b> {H.escape(str(nota)[:800])}</p>" if str(nota or '').strip() else "")
             + f"<p>Incassi {_eur(rp['ricavi'])} · imposta {_eur(rp['imposta'])} ({rp['aliquota']}%) · contributi dell'anno {_eur(rp['contributi_anno'])}</p>"
             + "<table border='1' cellpadding='4' style='border-collapse:collapse;font-size:13px'><tr><th>Rigo</th><th>Col.</th><th>Cosa</th><th>Valore</th></tr>"
             + tab + "</table>"
             + "".join(f"<p>! {H.escape(x['testo'])}</p>" for x in r["avvisi"]))
    try:
        auth.manda_email(admin, f"TaxScan: controllo dichiarazione {r['anno']}", corpo)
        auth.manda_email(mia, "TaxScan: abbiamo ricevuto la tua richiesta di controllo",
                         "<p>Ciao, abbiamo ricevuto la richiesta di far controllare la tua dichiarazione dei redditi "
                         f"{r['anno'] + 1}. Un commercialista che collabora con TaxScan ti scrive a questo indirizzo, "
                         "con quello che controlla e quanto costa, prima di iniziare.</p><p>Il team di TaxScan</p>")
    except Exception as e:
        print(f"dichiarazione: controllo non inviato: {e}")
        return {"ok": False, "errore": "Non è partita: riprova tra poco."}
    _CONTROLLI[c] = l + [ora]
    try:
        db.registra_evento("dichiarazione_controllo", c, {"anno": r["anno"]})
    except Exception:
        pass
    return {"ok": True}


QUADRI = {"LM": "Quadro LM – Reddito dei forfettari", "RR": "Quadro RR – Contributi INPS",
          "RS": "Quadro RS – Informazioni dei forfettari", "RX": "Quadro RX – Debito o credito di imposta"}


def pdf(c: str, anno) -> bytes | None:
    """Promemoria stampabile: i righi da copiare, gli F24, gli avvisi."""
    import report_pdf as R
    a = apri(c, anno)
    if not a.get("ok"):
        return None
    r = a["risultato"]
    p = R._Pdf()
    p.piede = "Preparato con TaxScan · è una guida, non sostituisce la dichiarazione"
    p.rett(0, R.PAGE_H - 8, R.PAGE_W, 8, R.BLU)
    p.testo(R.MARG, R.PAGE_H - 50, f"Dichiarazione dei redditi {r['anno'] + 1} · redditi {r['anno']}", 17, True, R.SCURO)
    p.testo(R.MARG, R.PAGE_H - 66, "Regime forfettario · righi da copiare nella dichiarazione online · " + MODELLO, 9.5, False, R.GRIGIO)
    p.y = R.PAGE_H - 90
    rp = r["riepilogo"]
    p.kpi([("Incassi", R._eur(rp["ricavi"]), "nell'anno"), ("Imposta " + str(rp["aliquota"]) + "%", R._eur(rp["imposta"]), "sostitutiva"),
           ("Giugno", R._eur(rp["giugno"]), "saldo e 1° acconto"), ("Novembre", R._eur(rp["novembre"]), "2° acconto")])
    if a.get("anteprima"):
        p.par("Anteprima: calcolata con le regole del modello " + MODELLO + ". Quando l'Agenzia pubblica il modello nuovo "
              "TaxScan controlla e aggiorna i righi.", 8.5, True, R.BLU, dopo=6)
    for q in ("LM", "RR", "RS", "RX"):
        rr = [x for x in r["righi"] if x["quadro"] == q]
        if not rr:
            continue
        p.titolo(QUADRI[q])
        p.tabella([("Rigo", 1, "l"), ("Col.", 0.8, "l"), ("Cosa", 5.4, "l"), ("Valore", 2, "r")],
                  [[x["rigo"], x["col"], R._t(x["desc"], 90), R._t(str(x["val"]), 30)] for x in rr])
    if r["f24"]:
        p.titolo("I pagamenti con F24")
        p.tabella([("Quando", 1.4, "l"), ("Sezione", 1.2, "l"), ("Codice", 1, "l"), ("Anno", 0.9, "l"), ("Cosa", 4, "l"), ("Importo", 1.6, "r")],
                  [[r["scadenze"].get(f["quando"], f["quando"]), f["sezione"], f["codice"], str(f["anno"]), R._t(f["desc"], 60), _eur(f["importo"])]
                   for f in r["f24"]])
        p.par("Sezione INPS: nel modello F24 servono anche il codice sede e la matricola INPS (li trovi nel Cassetto previdenziale). "
              "Chi paga oltre giugno può farlo entro il 30 luglio con lo 0,40% in più.", 8.5, False, R.GRIGIO, dopo=6)
    if r["avvisi"]:
        p.titolo("Da controllare")
        for x in r["avvisi"]:
            p.par("• " + x["testo"], 9, x["livello"] == "importante", R.SCURO, dopo=3)
    p.titolo("Prima di inviare")
    for t in ("Nel frontespizio scegli la destinazione dell'8, del 5 e del 2 per mille: non costano nulla.",
              "Controlla che i dati anagrafici e il domicilio fiscale siano giusti.",
              "Se vuoi, prima di inviarla falla controllare a un commercialista: da TaxScan basta un clic."):
        p.par("• " + t, 9, False, R.SCURO, dopo=3)
    p.y -= 4
    p.par(r["nota"], 8.5, False, R.GRIGIO, dopo=2)
    return p.bytes()


def registra(mcp) -> None:
    from starlette.responses import JSONResponse, Response
    import asyncio

    @mcp.custom_route("/api/prova/dichiarazione", methods=["POST"])
    async def prova_dichiarazione(request):
        try:
            q = await request.json()
            c, op = str(q.get("c", "")), q.get("op")
            if op == "salva":
                esito = await asyncio.to_thread(salva, c, q.get("anno"), q.get("dati") or {})
            elif op == "controllo":
                esito = await asyncio.to_thread(chiedi_controllo, c, q.get("anno"), str(q.get("nota") or ""))
            elif op == "ricomincia":
                esito = await asyncio.to_thread(ricomincia, c, q.get("anno"))
            elif op == "calcola":   # anteprima senza salvare
                anno = int(q.get("anno") or anno_da_preparare())
                esito = {"ok": True, "risultato": calcola(pulisci(q.get("dati") or {}, anno))}
            else:
                esito = await asyncio.to_thread(apri, c, q.get("anno"))
        except Exception as e:
            print(f"dichiarazione: {e}")
            return JSONResponse({"ok": False}, status_code=500)
        return JSONResponse(esito, status_code=200 if esito.get("ok") or esito.get("errore") else 404)

    @mcp.custom_route("/api/prova/dichiarazione.pdf", methods=["GET"])
    async def prova_dichiarazione_pdf(request):
        c = request.query_params.get("c", "")
        try:
            b = await asyncio.to_thread(pdf, c, request.query_params.get("anno"))
        except Exception as e:
            print(f"dichiarazione pdf: {e}")
            b = None
        if not b:
            return JSONResponse({"ok": False}, status_code=404)
        return Response(b, media_type="application/pdf",
                        headers={"Content-Disposition": 'inline; filename="taxscan-dichiarazione.pdf"'})
