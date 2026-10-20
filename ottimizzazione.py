"""TaxScan - sezione "Ottimizzazione fiscale" della dashboard.

Spunti legali per pagare meno o pagare meglio, costruiti SOLO su dati che abbiamo (numeri della dashboard, scheda,
risposte al questionario). Niente promesse: ogni cifra e' una stima e ogni voce dice cosa verificare.
Le voci sono semplici dizionari {"titolo", "testo", "tag", "link"?} pronti per la pagina.
"""
from __future__ import annotations

import approfondimento
import rate

# voci del questionario che nella sezione ottimizzazione non servono (hanno gia' la loro sezione o una voce dedicata)
_ESCLUDI_QUESTIONARIO = ("Bandi e finanziamenti", "Se fatturi molto di più", "Pagare meno tasse, in concreto",
                         "Grazie, abbiamo aggiornato la tua situazione")


def _eur(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", ".") + " €"
    except (TypeError, ValueError):
        return "–"


def _si(v) -> bool:
    return v is True or str(v).strip().lower() in ("si", "sì", "true", "1")


def spunti(pub: dict, scheda: dict, risposte: dict | None, id_dashboard: str, registrato: bool) -> dict:
    """pub: dati pubblici della dashboard; scheda: scheda dell'utente; risposte: questionario (o None)."""
    pub, scheda = pub or {}, scheda or {}
    voci: list[dict] = []
    prof = pub.get("profilo") or {}
    anno = pub.get("anno_corrente") or {}
    soglia = pub.get("soglia") or {}
    gest = str(prof.get("gestione") or scheda.get("gestione_previdenziale") or "").lower()

    # 0. check delle attivita': ogni servizio ha il suo coefficiente (e' la voce che pesa di piu')
    chk = pub.get("check_attivita") or {}
    if chk.get("fatto"):
        voci.append({"titolo": "Il tuo check delle attività è attivo",
                     "testo": f"I calcoli usano un coefficiente medio del {chk.get('coefficiente')}, costruito sui servizi che hai indicato. "
                              "Se cambi cosa fai per i clienti o i pesi, aggiornalo: bastano due minuti.",
                     "tag": "Fatto", "link": f"/d/{id_dashboard}/attivita", "link_testo": "Rivedi il check"})
    else:
        voci.append({"titolo": "Fai più cose di quelle che dice il tuo codice? Dillo: può cambiare le tasse",
                     "testo": "Se per i clienti svolgi servizi diversi (per esempio marketing e anche parte tecnica o pratiche), ogni attività "
                              "ha il suo coefficiente di redditività. Oggi ti calcoliamo tutto con un solo codice. Indicando i servizi che fai davvero, "
                              "il calcolo diventa più giusto e, in molti casi, le tasse stimate scendono. Conta ciò che fai davvero, tenuto separato in fattura.",
                     "tag": "Il passo che pesa di più", "link": f"/d/{id_dashboard}/attivita", "link_testo": "Fai il check (2 minuti)"})

    # 1. riduzione del 35% dei contributi INPS (artigiani e commercianti)
    if gest in ("artigiani", "commercianti") and not _si(scheda.get("riduzione_35")):
        t = ("Se sei artigiano o commerciante in regime forfettario puoi chiedere all'INPS la riduzione del 35% sui contributi. "
             "Di norma la domanda va presentata ogni anno entro il 28 febbraio. Attenzione: riduce anche i contributi "
             "che contano per la pensione.")
        if anno.get("contributi"):
            t += f" Sui contributi stimati di quest'anno ({_eur(anno['contributi'])}) varrebbe circa {_eur(float(anno['contributi']) * 0.35)} in meno."
        voci.append({"titolo": "Riduzione del 35% dei contributi INPS", "testo": t, "tag": "Da verificare con l'INPS"})

    # 2. aliquota agevolata del 5%
    dal15 = prof.get("dal_anno_15")
    if str(prof.get("aliquota") or "").startswith("5") and isinstance(dal15, int):
        t = (f"Hai l'aliquota agevolata del 5% fino al {dal15 - 1}. Dal {dal15} sarà il 15%: con gli stessi ricavi l'imposta "
             "sostitutiva sarà circa il triplo, quindi conviene metterlo nei conti per tempo.")
        if anno.get("imposta"):
            t += f" Quest'anno l'agevolazione ti fa risparmiare circa {_eur(float(anno['imposta']) * 2)} rispetto al 15%."
        voci.append({"titolo": "Il 5% non è per sempre", "testo": t, "tag": "Stima"})

    # 3. soglia degli 85.000 euro e principio di cassa
    previsione, limite = soglia.get("previsione"), soglia.get("limite") or 85000
    if (isinstance(previsione, (int, float)) and previsione >= 0.6 * limite) or soglia.get("livello") not in (None, "OK"):
        t = (f"Nel forfettario i ricavi contano per cassa: vale quando incassi, non quando emetti la fattura. "
             f"Ciò che incassi entro il 31 dicembre conta per quest'anno. Il limite è {_eur(limite)}: se lo superi esci dal "
             f"regime dall'anno dopo; oltre {_eur(soglia.get('limite_uscita') or 100000)} esci subito, in corso d'anno.")
        if soglia.get("margine") is not None:
            t += f" Oggi hai ancora circa {_eur(soglia['margine'])} di margine."
        voci.append({"titolo": "Tieni d'occhio la soglia", "testo": t, "tag": "Da seguire", "link": "#soglia", "link_testo": "Vedi il controllo della soglia"})

    # 4. acconti: se prevedi di incassare meno dell'anno scorso
    prec = (pub.get("numeri") or {}).get("ricavi_anno_precedente")
    if isinstance(prec, (int, float)) and prec > 0 and isinstance(previsione, (int, float)) and previsione < 0.85 * prec:
        voci.append({"titolo": "Se incassi meno dell'anno scorso",
                     "testo": "Per l'imposta sostitutiva gli acconti si calcolano di norma sull'anno precedente. Se prevedi di incassare "
                              "molto meno, puoi versare un acconto più basso (metodo previsionale). Attenzione: se la stima è sbagliata "
                              "si pagano sanzioni e interessi sulla differenza, quindi usalo solo con una previsione prudente.",
                     "tag": "Da valutare con attenzione"})

    # 5. pagamento a rate di saldo e primo acconto (giugno / luglio)
    pros = pub.get("prossima_scadenza") or {}
    if pros.get("data") and rate.rateizzabile(pros["data"]):
        voci.append({"titolo": "Puoi pagare a rate", "testo": "Il saldo e il primo acconto di giugno/luglio si possono pagare a rate, con gli interessi. "
                     "Ti mostriamo quanto costa ogni piano, così scegli quello che pesa meno sul tuo mese.",
                     "tag": "Da verificare", "link": f"/d/{id_dashboard}/rate?data={pros['data']}", "link_testo": "Vedi i piani a rate"})

    # 6. risposte al questionario (IMU, affitti, fondo pensione...)
    fatto = bool(risposte)
    if fatto:
        for c in approfondimento.consigli(risposte, id_dashboard):
            if c["titolo"] not in _ESCLUDI_QUESTIONARIO:
                voci.append({"titolo": c["titolo"], "testo": c["testo"], "tag": "Dal tuo questionario"})
        if set(risposte.get("progetti") or []) & {"assumere", "attrezzature", "sede"}:
            voci.append({"titolo": "Bandi per i tuoi progetti",
                         "testo": "Per assunzioni, attrezzature o una nuova sede ci sono spesso incentivi. Quelli aperti, e quelli in arrivo, sono nella sezione bandi.",
                         "tag": "Dal tuo questionario", "link": "#bandi", "link_testo": "Vai ai bandi"})
    return {"voci": voci, "questionario_fatto": fatto, "registrato": bool(registrato),
            "link_questionario": f"/d/{id_dashboard}/situazione" if registrato and not fatto else ""}
