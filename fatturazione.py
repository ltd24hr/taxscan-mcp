"""TaxScan - fatture: rubrica clienti, fatture da creare e modificare, PDF e file XML FatturaPA per il forfettario.

Cosa fa:
- conserva per ogni persona (id della situazione) i suoi dati da mettere in fattura, i clienti e le fatture
  (tabella prova_doc, percorso "fatture/<id>"). Solo la persona li vede, con il link segreto della sua situazione.
- numera le fatture per anno quando si emettono (le bozze non hanno numero);
- prepara il PDF e il file XML (formato FPR12, regime RF19, IVA a zero con natura N2.2, o N2.1 per i clienti
  aziende fuori Italia, bollo virtuale da 2 euro sopra 77,47 euro, rivalsa INPS 4% facoltativa per la gestione separata).

L'invio allo SDI non lo fa: il file XML si carica gratis sul portale «Fatture e corrispettivi» dell'Agenzia delle Entrate.
"""
from __future__ import annotations

import datetime
import json
import re
import time
import uuid
from xml.sax.saxutils import escape as _x

import db

SOGLIA_BOLLO = 77.47
BOLLO = 2.0
MAX_BYTE = 600_000
RIF_NORMATIVO = "Operazione in franchigia da IVA, art. 1 c. 54-89 L. 190/2014"
DICITURA = ("Operazione effettuata ai sensi dell'art. 1, commi da 54 a 89, della Legge n. 190/2014 (regime forfettario): "
            "non soggetta a IVA né a ritenuta d'acconto.")
DICITURA_UE = "Inversione contabile: operazione non soggetta a IVA ai sensi dell'art. 7-ter del DPR 633/72."
DICITURA_BOLLO = "Imposta di bollo da 2,00 euro assolta in modo virtuale (art. 6 DM 17/06/2014)."
_PAESI_UE = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "EL", "HR", "HU", "IE", "LT", "LU",
             "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"}
_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


# --------------------------------------------------------------------------- utilità

def _t(x, n=200) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(x or "")).strip()
    return s[:n]


def _n(x, d=0.0) -> float:
    try:
        v = float(str(x).replace(",", ".")) if not isinstance(x, (int, float)) else float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def _data(x) -> str:
    s = str(x or "")[:10]
    try:
        return datetime.date.fromisoformat(s).isoformat()
    except ValueError:
        return ""


def eur(x) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def piva_valida(p: str) -> bool:
    p = re.sub(r"\D", "", p or "")
    if len(p) != 11:
        return False
    s = 0
    for i, c in enumerate(p[:10]):
        n = int(c)
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        s += n
    return (10 - s % 10) % 10 == int(p[10])


def cf_valido(cf: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]", (cf or "").upper())) \
        or piva_valida(cf)


# --------------------------------------------------------------------------- archivio

def _vuoto() -> dict:
    return {"io": {}, "clienti": [], "fatture": [], "prossimo": {}}


def carica(c: str) -> dict:
    if not _ID.match(c or ""):
        return _vuoto()
    try:
        with db._connetti() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT dati FROM prova_doc WHERE path = %s", ("fatture/" + c,))
                r = cur.fetchone()
        d = r[0] if r else None
    except Exception as e:
        print(f"fatture: non lette {e}")
        d = None
    if not isinstance(d, dict):
        return _vuoto()
    for k, v in _vuoto().items():
        d.setdefault(k, v)
    return d


def _salva(c: str, d: dict) -> bool:
    from psycopg2.extras import Json
    if len(json.dumps(d)) > MAX_BYTE:
        return False
    with db._connetti() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS prova_doc (path TEXT PRIMARY KEY, dati JSONB NOT NULL, "
                        "aggiornato TIMESTAMPTZ NOT NULL DEFAULT now())")
            cur.execute("INSERT INTO prova_doc (path, dati) VALUES (%s, %s) "
                        "ON CONFLICT (path) DO UPDATE SET dati = EXCLUDED.dati, aggiornato = now()", ("fatture/" + c, Json(d)))
        conn.commit()
    return True


# --------------------------------------------------------------------------- pulizia dei dati in arrivo

def _io(x: dict) -> dict:
    x = x if isinstance(x, dict) else {}
    io = {k: _t(x.get(k), n) for k, n in (("nome", 60), ("cognome", 60), ("indirizzo", 80), ("comune", 60),
                                         ("provincia", 2), ("cap", 5), ("iban", 34), ("email", 120), ("telefono", 30))}
    io["piva"] = re.sub(r"\D", "", str(x.get("piva") or ""))[:11]
    io["cf"] = re.sub(r"[^A-Za-z0-9]", "", str(x.get("cf") or "")).upper()[:16]
    io["provincia"] = io["provincia"].upper()
    io["cap"] = re.sub(r"\D", "", io["cap"])
    io["iban"] = re.sub(r"\s", "", io["iban"]).upper()
    io["rivalsa"] = bool(x.get("rivalsa"))
    io["bollo_cliente"] = x.get("bollo_cliente") is not False
    io["scadenza_giorni"] = int(max(0, min(180, _n(x.get("scadenza_giorni"), 30))))
    return io


def _cliente(x: dict) -> dict:
    x = x if isinstance(x, dict) else {}
    naz = re.sub(r"[^A-Za-z]", "", str(x.get("nazione") or "IT")).upper()[:2] or "IT"
    c = {"id": _t(x.get("id"), 40) or uuid.uuid4().hex[:12],
         "tipo": "privato" if x.get("tipo") == "privato" else "azienda",
         "denominazione": _t(x.get("denominazione"), 80), "nome": _t(x.get("nome"), 60), "cognome": _t(x.get("cognome"), 60),
         "piva": re.sub(r"[^A-Za-z0-9]", "", str(x.get("piva") or "")).upper()[:28],
         "cf": re.sub(r"[^A-Za-z0-9]", "", str(x.get("cf") or "")).upper()[:16],
         "indirizzo": _t(x.get("indirizzo"), 80), "cap": _t(x.get("cap"), 10), "comune": _t(x.get("comune"), 60),
         "provincia": _t(x.get("provincia"), 2).upper(), "nazione": naz,
         "sdi": re.sub(r"[^A-Za-z0-9]", "", str(x.get("sdi") or "")).upper()[:7], "pec": _t(x.get("pec"), 120).lower(),
         "email": _t(x.get("email"), 120).lower(), "note": _t(x.get("note"), 300)}
    if naz != "IT":
        c["provincia"] = ""
    return c


def nome_cliente(c: dict) -> str:
    c = c or {}
    if c.get("tipo") == "privato":
        return (" ".join(x for x in (c.get("nome"), c.get("cognome")) if x)).strip() or c.get("denominazione") or ""
    return c.get("denominazione") or (" ".join(x for x in (c.get("nome"), c.get("cognome")) if x)).strip()


def _righe(lst) -> list:
    out = []
    for r in (lst or [])[:40]:
        if not isinstance(r, dict):
            continue
        desc = _t(r.get("descrizione"), 1000)
        q = round(_n(r.get("quantita"), 1.0), 2) or 1.0
        p = round(_n(r.get("prezzo")), 2)
        if not desc and not p:
            continue
        out.append({"descrizione": desc, "quantita": q, "prezzo": p})
    return out


def totali(f: dict, io: dict) -> dict:
    """Imponibile, rivalsa INPS 4%, bollo, totale. Il bollo si conta sull'importo senza il bollo stesso."""
    imp = round(sum(r["quantita"] * r["prezzo"] for r in f.get("righe") or []), 2)
    riv = round(imp * 0.04, 2) if f.get("rivalsa") else 0.0
    base = round(imp + riv, 2)
    bollo = BOLLO if base > SOGLIA_BOLLO else 0.0
    addebito = bollo if (bollo and f.get("bollo_cliente", True)) else 0.0
    return {"imponibile": imp, "rivalsa": riv, "base": base, "bollo": bollo, "bollo_addebitato": addebito,
            "totale": round(base + addebito, 2)}


def _natura(cl: dict) -> str:
    return "N2.1" if cl.get("nazione", "IT") != "IT" and cl.get("tipo") == "azienda" else "N2.2"


def _fattura(x: dict, vecchia: dict | None, io: dict) -> dict:
    x = x if isinstance(x, dict) else {}
    v = dict(vecchia or {})
    f = {"id": v.get("id") or uuid.uuid4().hex[:12], "stato": v.get("stato") or "bozza",
         "numero": v.get("numero") or "", "anno": v.get("anno"),
         "tipo": "TD04" if x.get("tipo") == "TD04" else "TD01",
         "data": _data(x.get("data")) or datetime.date.today().isoformat(),
         "cliente_id": _t(x.get("cliente_id"), 40),
         "cliente": _cliente(x.get("cliente")) if isinstance(x.get("cliente"), dict) else (v.get("cliente") or {}),
         "righe": _righe(x.get("righe")),
         "rivalsa": bool(x.get("rivalsa")) if "rivalsa" in x else bool(io.get("rivalsa")),
         "bollo_cliente": (x.get("bollo_cliente") is not False) if "bollo_cliente" in x else io.get("bollo_cliente", True),
         "scadenza": _data(x.get("scadenza")), "iban": re.sub(r"\s", "", str(x.get("iban") or io.get("iban") or "")).upper()[:34],
         "note": _t(x.get("note"), 600), "rif": _t(x.get("rif"), 40),
         "incasso": v.get("incasso"), "creata": v.get("creata") or int(time.time()), "modificata": int(time.time())}
    if f["stato"] == "emessa":   # dopo l'emissione numero e data restano quelli
        f["data"] = v.get("data") or f["data"]
    return f


# --------------------------------------------------------------------------- operazioni

def _cerca(lst, i):
    return next((x for x in lst if x.get("id") == i), None)


def _prossimo(d: dict, anno: int) -> int:
    usati = [int(f["numero"]) for f in d["fatture"] if f.get("anno") == anno and str(f.get("numero") or "").isdigit()]
    return max([int(d["prossimo"].get(str(anno)) or 1)] + [n + 1 for n in usati])


def operazione(c: str, op: str, dati: dict | None = None) -> dict:
    """Una sola porta per la pagina: legge, salva i tuoi dati, i clienti, le fatture; emette, duplica, elimina, incassa."""
    if not _ID.match(c or ""):
        return {"ok": False, "errore": "Serve la tua situazione salvata."}
    if not db.carica_dashboard(c):
        return {"ok": False, "errore": "Situazione non trovata."}
    x = dati if isinstance(dati, dict) else {}
    d = carica(c)
    oggi = datetime.date.today()
    msg = ""
    numeri = None
    if op == "get":
        return {"ok": True, "dati": _per_pagina(d, c)}
    if op == "io":
        d["io"] = _io(x.get("io"))
        pn = int(_n(x.get("prossimo_numero"), 0))
        if pn > 0:
            d["prossimo"][str(oggi.year)] = min(pn, 99999)
    elif op == "cliente":
        cl = _cliente(x.get("cliente"))
        if not nome_cliente(cl):
            return {"ok": False, "errore": "Scrivi almeno il nome o la ragione sociale del cliente."}
        vecchio = _cerca(d["clienti"], cl["id"])
        if vecchio:
            d["clienti"][d["clienti"].index(vecchio)] = cl
        else:
            if len(d["clienti"]) >= 500:
                return {"ok": False, "errore": "Hai raggiunto il massimo di clienti in rubrica."}
            d["clienti"].append(cl)
        msg = cl["id"]
    elif op == "elimina_cliente":
        d["clienti"] = [k for k in d["clienti"] if k.get("id") != _t(x.get("id"), 40)]
    elif op == "fattura":
        vecchia = _cerca(d["fatture"], _t(x.get("id"), 40))
        f = _fattura(x.get("fattura") if isinstance(x.get("fattura"), dict) else x, vecchia, d["io"])
        cl = _cerca(d["clienti"], f["cliente_id"]) if f["cliente_id"] else None
        if cl and f["stato"] == "bozza":
            f["cliente"] = dict(cl)
        if vecchia:
            d["fatture"][d["fatture"].index(vecchia)] = f
        else:
            if len(d["fatture"]) >= 1500:
                return {"ok": False, "errore": "Archivio pieno: scarica e archivia le fatture più vecchie."}
            d["fatture"].append(f)
        msg = f["id"]
    elif op == "emetti":
        f = _cerca(d["fatture"], _t(x.get("id"), 40))
        if not f:
            return {"ok": False, "errore": "Fattura non trovata."}
        prob = controlla(f, d["io"])
        if prob:
            return {"ok": False, "errore": prob[0], "problemi": prob}
        if f["stato"] != "emessa":
            anno = int(f["data"][:4])
            n = _prossimo(d, anno)
            f.update({"stato": "emessa", "numero": str(n), "anno": anno, "emessa_il": int(time.time())})
            d["prossimo"][str(anno)] = n + 1
            f["cliente"] = dict(_cerca(d["clienti"], f.get("cliente_id")) or f.get("cliente") or {})
        msg = f["id"]
    elif op == "duplica":
        f = _cerca(d["fatture"], _t(x.get("id"), 40))
        if not f:
            return {"ok": False, "errore": "Fattura non trovata."}
        n = dict(f, id=uuid.uuid4().hex[:12], stato="bozza", numero="", anno=None, incasso=None,
                 data=oggi.isoformat(), scadenza="", creata=int(time.time()), modificata=int(time.time()))
        n.pop("emessa_il", None)
        d["fatture"].append(n)
        msg = n["id"]
    elif op == "elimina":
        f = _cerca(d["fatture"], _t(x.get("id"), 40))
        if f and f.get("stato") == "emessa":
            # una fattura emessa si toglie solo se e' l'ultima dell'anno: altrimenti resta un buco nella numerazione
            ult = max([int(k["numero"]) for k in d["fatture"] if k.get("anno") == f.get("anno") and str(k.get("numero") or "").isdigit()] or [0])
            if str(f.get("numero")) != str(ult):
                return {"ok": False, "errore": "Si può eliminare solo l'ultima fattura emessa dell'anno. Per annullarne una già inviata si fa una nota di credito."}
            d["prossimo"][str(f["anno"])] = int(f["numero"])
        d["fatture"] = [k for k in d["fatture"] if k.get("id") != _t(x.get("id"), 40)]
    elif op == "incassa":
        f = _cerca(d["fatture"], _t(x.get("id"), 40))
        if not f or f.get("stato") != "emessa":
            return {"ok": False, "errore": "Si segnano come incassate solo le fatture emesse."}
        import prova
        numeri = None
        if x.get("annulla"):
            vecchio = f.get("incasso") or {}
            if vecchio.get("segnato"):
                r = prova.togli_incasso(c, vecchio.get("importo"), vecchio.get("data"))
                numeri = r.get("numeri")
            f["incasso"] = None
        else:
            if f.get("incasso"):
                return {"ok": True, "id": f["id"], "dati": _per_pagina(d, c)}
            dt = _data(x.get("data")) or oggi.isoformat()
            if dt > oggi.isoformat():
                return {"ok": False, "errore": "La data dell'incasso non può essere nel futuro."}
            imp = round(_n(x.get("importo"), totali(f, d["io"])["totale"]), 2)
            f["incasso"] = {"data": dt, "importo": imp}
            if dt[:4] == str(oggi.year):
                # l'incasso entra nei conti dell'anno: tasse, quota da mettere da parte e soglia si rifanno
                r = prova.incasso(c, imp, dt)
                if r.get("ok"):
                    f["incasso"]["segnato"] = True
                    numeri = r.get("numeri")
        msg = f["id"]
    else:
        return {"ok": False}
    if not _salva(c, d):
        return {"ok": False, "errore": "Archivio troppo grande: elimina qualche bozza o cliente che non usi."}
    try:
        db.registra_evento("fatture_" + op, c, {})
    except Exception:
        pass
    out = {"ok": True, "id": msg, "dati": _per_pagina(d, c)}
    if op == "incassa" and numeri:
        out["numeri"] = numeri
    return out


def _per_pagina(d: dict, c: str) -> dict:
    io = d.get("io") or {}
    out = []
    for f in sorted(d.get("fatture") or [], key=lambda k: (k.get("data") or "", int(k["numero"]) if str(k.get("numero") or "").isdigit() else 0), reverse=True):
        t = totali(f, io)
        out.append(dict(f, tot=t, cliente_nome=nome_cliente(f.get("cliente")), problemi=controlla(f, io) if f.get("stato") != "emessa" else []))
    anno = datetime.date.today().year
    return {"io": io, "clienti": sorted(d.get("clienti") or [], key=lambda k: nome_cliente(k).lower()), "fatture": out,
            "prossimo": _prossimo(d, anno), "io_completo": not controlla_io(io)}


# --------------------------------------------------------------------------- controlli prima di emettere

def controlla_io(io: dict) -> list:
    p = []
    if not (io.get("nome") and io.get("cognome")):
        p.append("Mancano il tuo nome e cognome (I tuoi dati in fattura).")
    if not piva_valida(io.get("piva")):
        p.append("Manca la tua partita IVA o non è valida (I tuoi dati in fattura).")
    if not cf_valido(io.get("cf")):
        p.append("Manca il tuo codice fiscale (I tuoi dati in fattura).")
    if not (io.get("indirizzo") and re.fullmatch(r"\d{5}", io.get("cap") or "") and io.get("comune") and re.fullmatch(r"[A-Z]{2}", io.get("provincia") or "")):
        p.append("Manca l'indirizzo completo della tua attività: via, CAP, comune e sigla della provincia (I tuoi dati in fattura).")
    return p


def controlla(f: dict, io: dict) -> list:
    p = controlla_io(io)
    cl = f.get("cliente") or {}
    if not nome_cliente(cl):
        p.append("Scegli il cliente.")
    else:
        it = cl.get("nazione", "IT") == "IT"
        if it and cl.get("tipo") == "azienda" and not piva_valida(cl.get("piva")) and not cf_valido(cl.get("cf")):
            p.append("Il cliente è un'azienda italiana: serve la sua partita IVA (11 cifre) o il codice fiscale.")
        if it and cl.get("tipo") == "privato" and not cf_valido(cl.get("cf")):
            p.append("Il cliente è un privato: serve il suo codice fiscale.")
        if cl.get("tipo") == "privato" and not (cl.get("nome") and cl.get("cognome")):
            p.append("Per un privato servono nome e cognome.")
        if not (cl.get("indirizzo") and cl.get("comune")) or (it and not re.fullmatch(r"\d{5}", cl.get("cap") or "")):
            p.append("Manca l'indirizzo del cliente (via, CAP e comune).")
        if it and cl.get("sdi") and len(cl["sdi"]) != 7:
            p.append("Il codice destinatario del cliente ha 7 caratteri.")
    if not f.get("righe"):
        p.append("Aggiungi almeno una riga con descrizione e importo.")
    elif any(not r["descrizione"] for r in f["righe"]):
        p.append("Ogni riga ha bisogno di una descrizione.")
    elif totali(f, io)["imponibile"] <= 0:
        p.append("L'importo della fattura deve essere maggiore di zero.")
    return p


# --------------------------------------------------------------------------- file XML FatturaPA

def _d2(x) -> str:
    return f"{x:.2f}"


def _sede(s: dict, estero_ok=True) -> str:
    naz = s.get("nazione") or "IT"
    cap = re.sub(r"\D", "", s.get("cap") or "") if naz == "IT" else "00000"
    out = (f"<Sede><Indirizzo>{_x(_t(s.get('indirizzo'), 60))}</Indirizzo><CAP>{cap[:5].zfill(5)}</CAP>"
           f"<Comune>{_x(_t(s.get('comune'), 60))}</Comune>")
    if naz == "IT" and re.fullmatch(r"[A-Z]{2}", s.get("provincia") or ""):
        out += f"<Provincia>{s['provincia']}</Provincia>"
    return out + f"<Nazione>{naz}</Nazione></Sede>"


def xml(f: dict, io: dict) -> tuple[str, str]:
    """Il file XML della fattura e il nome del file (IT + codice fiscale + progressivo)."""
    t = totali(f, io)
    cl = f.get("cliente") or {}
    naz = cl.get("nazione") or "IT"
    nat = _natura(cl)
    cf_io = io.get("cf") or io.get("piva")
    prog = (re.sub(r"[^A-Za-z0-9]", "", f"{f.get('anno') or ''}{f.get('numero') or ''}") or "1")[-10:]
    if naz == "IT":
        dest = cl.get("sdi") if (cl.get("sdi") and len(cl["sdi"]) == 7) else "0000000"
    else:
        dest = "XXXXXXX"
    pec = f"<PECDestinatario>{_x(cl['pec'])}</PECDestinatario>" if (naz == "IT" and dest == "0000000" and cl.get("pec")) else ""
    # cliente
    if naz == "IT":
        idf = f"<IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{cl['piva']}</IdCodice></IdFiscaleIVA>" if piva_valida(cl.get("piva")) else ""
        cfc = f"<CodiceFiscale>{cl['cf']}</CodiceFiscale>" if cl.get("cf") and cf_valido(cl["cf"]) else ""
    else:
        vat = re.sub(r"^[A-Z]{2}", "", cl.get("piva") or "") if (cl.get("piva") or "")[:2] == naz else (cl.get("piva") or "")
        idf = f"<IdFiscaleIVA><IdPaese>{naz}</IdPaese><IdCodice>{_x(vat or '99999999999')}</IdCodice></IdFiscaleIVA>"
        cfc = ""
    if cl.get("tipo") == "privato" and cl.get("nome") and cl.get("cognome"):
        ana = f"<Anagrafica><Nome>{_x(cl['nome'])}</Nome><Cognome>{_x(cl['cognome'])}</Cognome></Anagrafica>"
    else:
        ana = f"<Anagrafica><Denominazione>{_x(nome_cliente(cl)[:80])}</Denominazione></Anagrafica>"
    linee = ""
    for i, r in enumerate(f.get("righe") or [], 1):
        linee += (f"<DettaglioLinee><NumeroLinea>{i}</NumeroLinea><Descrizione>{_x(r['descrizione'][:1000])}</Descrizione>"
                  f"<Quantita>{_d2(r['quantita'])}</Quantita><PrezzoUnitario>{_d2(r['prezzo'])}</PrezzoUnitario>"
                  f"<PrezzoTotale>{_d2(round(r['quantita'] * r['prezzo'], 2))}</PrezzoTotale><AliquotaIVA>0.00</AliquotaIVA>"
                  f"<Natura>{nat}</Natura></DettaglioLinee>")
    n = len(f.get("righe") or [])
    riep = (f"<DatiRiepilogo><AliquotaIVA>0.00</AliquotaIVA><Natura>{nat}</Natura><ImponibileImporto>{_d2(t['base'])}</ImponibileImporto>"
            f"<Imposta>0.00</Imposta><RiferimentoNormativo>{_x(RIF_NORMATIVO if nat == 'N2.2' else 'Art. 7-ter DPR 633/72')}</RiferimentoNormativo></DatiRiepilogo>")
    if t["bollo_addebitato"]:
        linee += (f"<DettaglioLinee><NumeroLinea>{n + 1}</NumeroLinea><Descrizione>Rimborso imposta di bollo</Descrizione>"
                  f"<Quantita>1.00</Quantita><PrezzoUnitario>2.00</PrezzoUnitario><PrezzoTotale>2.00</PrezzoTotale>"
                  f"<AliquotaIVA>0.00</AliquotaIVA><Natura>N1</Natura></DettaglioLinee>")
        riep += ("<DatiRiepilogo><AliquotaIVA>0.00</AliquotaIVA><Natura>N1</Natura><ImponibileImporto>2.00</ImponibileImporto>"
                 "<Imposta>0.00</Imposta><RiferimentoNormativo>Escluso art. 15 DPR 633/72</RiferimentoNormativo></DatiRiepilogo>")
    bollo = "<DatiBollo><BolloVirtuale>SI</BolloVirtuale><ImportoBollo>2.00</ImportoBollo></DatiBollo>" if t["bollo"] else ""
    cassa = (f"<DatiCassaPrevidenziale><TipoCassa>TC22</TipoCassa><AlCassa>4.00</AlCassa><ImportoContributoCassa>{_d2(t['rivalsa'])}</ImportoContributoCassa>"
             f"<ImponibileCassa>{_d2(t['imponibile'])}</ImponibileCassa><AliquotaIVA>0.00</AliquotaIVA><Natura>{nat}</Natura></DatiCassaPrevidenziale>") if t["rivalsa"] else ""
    causali = [DICITURA] + ([DICITURA_UE] if nat == "N2.1" else []) + ([DICITURA_BOLLO] if t["bollo"] else [])
    if t["rivalsa"]:
        causali.append("Rivalsa INPS 4% ai sensi dell'art. 1, comma 212, L. 662/1996.")
    if f.get("note"):
        causali += [f["note"][i:i + 200] for i in range(0, min(len(f["note"]), 600), 200)]
    caus = "".join(f"<Causale>{_x(c[:200])}</Causale>" for c in causali)
    pag = ""
    if f.get("iban") or f.get("scadenza"):
        pag = ("<DatiPagamento><CondizioniPagamento>TP02</CondizioniPagamento><DettaglioPagamento><ModalitaPagamento>MP05</ModalitaPagamento>"
               + (f"<DataScadenzaPagamento>{f['scadenza']}</DataScadenzaPagamento>" if f.get("scadenza") else "")
               + f"<ImportoPagamento>{_d2(t['totale'])}</ImportoPagamento>"
               + (f"<IBAN>{_x(f['iban'])}</IBAN>" if re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", f.get("iban") or "") else "")
               + "</DettaglioPagamento></DatiPagamento>")
    s = ('<?xml version="1.0" encoding="UTF-8"?>\n'
         '<p:FatturaElettronica versione="FPR12" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
         'xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" '
         'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
         'xsi:schemaLocation="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2 '
         'http://www.fatturapa.gov.it/export/fatturazione/sdi/fatturapa/v1.2/Schema_del_file_xml_FatturaPA_versione_1.2.xsd">'
         "<FatturaElettronicaHeader>"
         f"<DatiTrasmissione><IdTrasmittente><IdPaese>IT</IdPaese><IdCodice>{cf_io}</IdCodice></IdTrasmittente>"
         f"<ProgressivoInvio>{prog}</ProgressivoInvio><FormatoTrasmissione>FPR12</FormatoTrasmissione>"
         f"<CodiceDestinatario>{dest}</CodiceDestinatario>{pec}</DatiTrasmissione>"
         "<CedentePrestatore><DatiAnagrafici>"
         f"<IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{io.get('piva')}</IdCodice></IdFiscaleIVA>"
         + (f"<CodiceFiscale>{io['cf']}</CodiceFiscale>" if io.get("cf") else "")
         + f"<Anagrafica><Nome>{_x(io.get('nome') or '')}</Nome><Cognome>{_x(io.get('cognome') or '')}</Cognome></Anagrafica>"
         "<RegimeFiscale>RF19</RegimeFiscale></DatiAnagrafici>"
         + _sede(dict(io, nazione="IT")) + "</CedentePrestatore>"
         f"<CessionarioCommittente><DatiAnagrafici>{idf}{cfc}{ana}</DatiAnagrafici>{_sede(cl)}</CessionarioCommittente>"
         "</FatturaElettronicaHeader>"
         "<FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento>"
         f"<TipoDocumento>{f.get('tipo') or 'TD01'}</TipoDocumento><Divisa>EUR</Divisa><Data>{f['data']}</Data>"
         f"<Numero>{_x(str(f.get('numero') or 'BOZZA'))}</Numero>{bollo}{cassa}"
         f"<ImportoTotaleDocumento>{_d2(t['totale'])}</ImportoTotaleDocumento>{caus}"
         "</DatiGeneraliDocumento></DatiGenerali>"
         f"<DatiBeniServizi>{linee}{riep}</DatiBeniServizi>{pag}"
         "</FatturaElettronicaBody></p:FatturaElettronica>")
    nome = f"IT{cf_io}_{prog[-5:].zfill(5)}.xml"
    return s, nome


# --------------------------------------------------------------------------- PDF

def pdf(f: dict, io: dict) -> bytes:
    import report_pdf as R
    p = R._Pdf()
    p.piede = "Documento preparato con TaxScan"
    t = totali(f, io)
    cl = f.get("cliente") or {}
    p.rett(0, R.PAGE_H - 8, R.PAGE_W, 8, R.BLU)
    tit = ("NOTA DI CREDITO" if f.get("tipo") == "TD04" else "FATTURA") + (" N. " + str(f["numero"]) if f.get("numero") else " (BOZZA)")
    dat = "Data: " + "/".join(reversed(str(f.get("data") or "").split("-")))
    p.testo(R.MARG, R.PAGE_H - 50, tit, 18, True, R.SCURO)
    p.testo(R.MARG, R.PAGE_H - 66, dat, 9.5, False, R.GRIGIO)
    y0 = R.PAGE_H - 96
    da = [" ".join(x for x in (io.get("nome"), io.get("cognome")) if x), io.get("indirizzo") or "",
          " ".join(x for x in (io.get("cap"), io.get("comune"), ("(" + io["provincia"] + ")") if io.get("provincia") else "") if x),
          "P.IVA " + (io.get("piva") or ""), "C.F. " + (io.get("cf") or "")]
    a = [nome_cliente(cl), cl.get("indirizzo") or "",
         " ".join(x for x in (cl.get("cap"), cl.get("comune"), ("(" + cl["provincia"] + ")") if cl.get("provincia") else "",
                              cl.get("nazione") if cl.get("nazione") not in (None, "", "IT") else "") if x)]
    if cl.get("piva"):
        a.append(("P.IVA " if cl.get("nazione", "IT") == "IT" else "VAT ") + cl["piva"])
    if cl.get("cf"):
        a.append("C.F. " + cl["cf"])
    if cl.get("sdi") or cl.get("pec"):
        a.append("Cod. destinatario " + cl["sdi"] if cl.get("sdi") else "PEC " + cl["pec"])
    alt = 16 + 13 * max(len(da), len(a)) + 6
    for i, (ti, rr) in enumerate((("Da", da), ("Per", a))):
        x = R.MARG + i * ((R.PAGE_W - 2 * R.MARG) / 2 + 10)
        p.rett(x, y0 - alt, (R.PAGE_W - 2 * R.MARG) / 2 - 10, alt, R.CHIARO)
        p.testo(x + 10, y0 - 14, ti.upper(), 8, True, R.GRIGIO)
        for k, r in enumerate([r for r in rr if r]):
            p.testo(x + 10, y0 - 30 - k * 13, R._t(r, 60), 9.5, k == 0, R.SCURO)
    p.y = y0 - alt - 18
    righe = [[r["descrizione"], (f"{r['quantita']:g}").replace(".", ","), eur(r["prezzo"]), eur(round(r["quantita"] * r["prezzo"], 2))]
             for r in f.get("righe") or []]
    p.tabella([("Descrizione", 6, "l"), ("Q.tà", 0.8, "r"), ("Prezzo", 1.6, "r"), ("Importo", 1.6, "r")], righe or [["", "", "", ""]])
    voci = [("Imponibile", t["imponibile"])]
    if t["rivalsa"]:
        voci.append(("Rivalsa INPS 4%", t["rivalsa"]))
    if t["bollo_addebitato"]:
        voci.append(("Rimborso imposta di bollo", t["bollo_addebitato"]))
    voci.append(("IVA", 0.0))
    p.serve(20 * (len(voci) + 2))
    for k, (l, v) in enumerate(voci):
        p.testo(R.PAGE_W - R.MARG - 220, p.y - 12, l, 9.5, False, R.GRIGIO)
        p.testo(R.PAGE_W - R.MARG - 10 - R._lar(eur(v), 9.5), p.y - 12, eur(v), 9.5, False, R.SCURO)
        p.y -= 16
    p.rett(R.PAGE_W - R.MARG - 230, p.y - 26, 230, 26, R.CHIARO)
    p.testo(R.PAGE_W - R.MARG - 220, p.y - 17, "Totale documento", 10.5, True, R.SCURO)
    p.testo(R.PAGE_W - R.MARG - 10 - R._lar(eur(t["totale"]), 11, True), p.y - 17, eur(t["totale"]), 11, True, R.SCURO)
    p.y -= 44
    dic = [DICITURA] + ([DICITURA_UE] if _natura(cl) == "N2.1" else []) + ([DICITURA_BOLLO] if t["bollo"] else [])
    if t["rivalsa"]:
        dic.append("Rivalsa INPS 4% ai sensi dell'art. 1, comma 212, L. 662/1996.")
    for d in dic:
        p.par(d, 8.5, False, R.GRIGIO, dopo=3)
    if f.get("iban") or f.get("scadenza"):
        p.y -= 4
        p.par("Pagamento: bonifico" + (" su IBAN " + f["iban"] if f.get("iban") else "")
              + (" entro il " + "/".join(reversed(f["scadenza"].split("-"))) if f.get("scadenza") else ""), 9.5, True, R.SCURO, dopo=4)
    if f.get("note"):
        p.par(f["note"], 9, False, R.SCURO, dopo=4)
    if f.get("stato") != "emessa":
        p.y -= 6
        p.par("Bozza: non è ancora una fattura valida. Diventa valida quando il file XML viene inviato allo SDI.", 8.5, True, R.BLU, dopo=2)
    else:
        p.y -= 6
        p.par("Copia di cortesia. La fattura valida è il file XML trasmesso al Sistema di Interscambio.", 8, False, R.GRIGIO, dopo=2)
    return p.bytes()


def file_fattura(c: str, fid: str, tipo: str):
    """(bytes, nome, media type) del PDF o dell'XML; None se non c'e'."""
    if not _ID.match(c or "") or not db.carica_dashboard(c):
        return None
    d = carica(c)
    f = _cerca(d["fatture"], _t(fid, 40))
    if not f:
        return None
    io = d.get("io") or {}
    nome_base = ("fattura-" + (f"{f['anno']}-{f['numero']}" if f.get("numero") else "bozza")).replace("/", "-")
    if tipo == "xml":
        s, nome = xml(f, io)
        return s.encode("utf-8"), (nome if f.get("stato") == "emessa" else nome_base + ".xml"), "application/xml"
    return pdf(f, io), nome_base + ".pdf", "application/pdf"


def incassi_anno(c: str, anno: int) -> float:
    d = carica(c)
    return round(sum(_n((f.get("incasso") or {}).get("importo")) for f in d["fatture"]
                     if f.get("incasso") and str(f["incasso"].get("data") or "")[:4] == str(anno)), 2)
