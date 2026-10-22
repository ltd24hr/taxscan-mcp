"""TaxScan - "Il tuo percorso": la dashboard come un gioco da tavolo.

Una sequenza di tappe dall'alto verso il basso (dove sei -> metti da parte -> check delle attivita' -> analizza le fatture ->
attiva i codici -> confronta -> bandi). Ogni tappa ha due righe e un pulsante; i dettagli stanno nelle pagine dedicate.
Tutte le cifre sono stime: il risparmio e' sempre "stimato", e conta come ATTIVATO solo quando l'utente dice che il nuovo
codice e' gia' sulla sua partita IVA.
"""
from __future__ import annotations


def _eur(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", ".") + " €"
    except (TypeError, ValueError):
        return "–"


def costruisci(pub: dict, id_dashboard: str) -> dict:
    pub = pub or {}
    chk = pub.get("check_attivita") or {}
    pros = pub.get("prossima_scadenza") or {}
    link_att = f"/d/{id_dashboard}/attivita"
    passi: list[dict] = []

    # 1. dove sei
    if pros.get("data"):
        g = pros.get("giorni")
        quando = "oggi" if g == 0 else ("domani" if g == 1 else f"tra {g} giorni") if isinstance(g, int) and g >= 0 else "a breve"
        passi.append({"id": "qui", "titolo": "Tu sei qui", "stato": "qui",
                      "testo": f"{quando.capitalize()} devi versare circa {_eur(pros.get('importo'))}. Nessuna sorpresa: lo sai con anticipo.",
                      "link": "#situazione", "link_testo": "Vedi la scadenza"})
    # 2. metti da parte
    if pub.get("quota_per_fattura"):
        passi.append({"id": "parte", "titolo": "Metti da parte", "stato": "qui",
                      "testo": f"Da ogni fattura incassata tieni da parte {pub['quota_per_fattura']}: quando arriva la scadenza i soldi ci sono già."})
    # 3. check delle attivita'
    fatto = bool(chk.get("fatto"))
    passi.append({"id": "check", "titolo": "Check delle attività", "stato": "fatto" if fatto else "da_fare",
                  "testo": (f"Fatto. Stiamo calcolando con un coefficiente del {chk.get('coefficiente')}. Se cambia il tuo lavoro, aggiornalo."
                            if fatto else "Forse paghi più del dovuto: se fai servizi diversi, ognuno ha il suo coefficiente. Bastano 2 minuti."),
                  "link": link_att, "link_testo": "Rivedi il check" if fatto else "Fai il check"})
    # 4. analizza le fatture
    da_fatt = bool(chk.get("da_fatture"))
    passi.append({"id": "analizza", "titolo": "Analizza le tue fatture", "stato": "fatto" if da_fatt else "da_fare",
                  "testo": ("Hai usato le tue fatture per calcolare i pesi veri di ogni attività."
                            if da_fatt else "Collega Fatture in Cloud o allega le fatture: leggo cosa c'è scritto e cerco attività nascoste dentro una riga generica."),
                  "link": link_att + "#boxfat", "link_testo": "Analizza le fatture"})
    # 5. attiva i codici
    nuovi = chk.get("codici_nuovi") or []
    if fatto and nuovi:
        mancanti = [x for x in nuovi if not x.get("gia")]
        passi.append({"id": "codici", "titolo": "Attiva i nuovi codici", "stato": "da_fare" if mancanti else "fatto",
                      "testo": (f"Per usare i coefficienti giusti, {len(mancanti)} cod{'ice va aggiunto' if len(mancanti) == 1 else 'ici vanno aggiunti'} alla partita IVA "
                                "(variazione dati, di norma gratuita, entro 30 giorni dall'inizio)."
                                if mancanti else "Tutti i codici dei tuoi servizi sono sulla partita IVA."),
                      "link": link_att + "#passo4", "link_testo": "Vedi come si fa" if mancanti else "Rivedi"})
    # 6. confronta
    r = chk.get("risparmio") or {}
    risp = {"fatto": fatto, "potenziale": r.get("potenziale"), "attivato": r.get("attivato"),
            "affidabile": r.get("affidabile", True), "costa_di_piu": bool(r.get("costa_di_piu"))}
    if not fatto:
        t = "Dopo il check vedrai qui quanto potresti pagare di meno, e quanto hai già attivato."
    elif not risp["affidabile"]:
        t = "Con un'attività commerciale i contributi INPS potrebbero cambiare: il risparmio non è calcolabile in modo affidabile."
    elif risp["costa_di_piu"]:
        t = "Con questi dati il calcolo per attività non fa risparmiare: è però il calcolo corretto, e conviene saperlo ora."
    elif (risp["potenziale"] or 0) > 0:
        t = (f"Risparmio potenziale stimato: circa {_eur(risp['potenziale'])} all'anno. "
             f"Già attivato (codici sulla partita IVA): circa {_eur(risp['attivato'] or 0)}.")
    else:
        t = "Con questi dati non risulta un risparmio: il calcolo è comunque più giusto."
    passi.append({"id": "confronta", "titolo": "Confronta: prima e dopo", "stato": "fatto" if (fatto and (risp["potenziale"] or 0) > 0) else "da_fare",
                  "testo": t, "link": link_att + "#passo3" if fatto else link_att, "link_testo": "Vedi il confronto" if fatto else "Fai il check"})
    # 7. bandi
    n = len((pub.get("agevolazioni") or {}).get("curati") or [])
    passi.append({"id": "bandi", "titolo": "Bandi che possono aiutarti", "stato": "da_fare",
                  "testo": (f"Ne abbiamo selezionati {n} per la tua zona e il tuo settore: spunti da verificare, non diritti." if n
                            else "Guarda i bandi e le agevolazioni che potrebbero alleggerire le tue tasse."),
                  "link": "#bandi", "link_testo": "Vedi i bandi"})
    prossimo = next((p["id"] for p in passi if p["stato"] == "da_fare"), None)
    return {"passi": passi, "adesso": prossimo, "risparmio": risp,
            "fatti": sum(1 for p in passi if p["stato"] == "fatto"), "totale": sum(1 for p in passi if p["stato"] in ("fatto", "da_fare"))}
