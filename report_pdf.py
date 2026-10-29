"""Report PDF di TaxScan, senza librerie esterne (solo Python standard).
Genera un PDF A4 con font Helvetica: riepilogo, dati di partenza, prestazioni, prima/dopo, metodologia, compiti, avvertenze."""
import datetime
import re

_W = {}
for _c, _w in zip(range(32, 127), [
        278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
        556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
        1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333,
        556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556,
        556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]):
    _W[chr(_c)] = _w

PAGE_W, PAGE_H, MARG = 595, 842, 48
BLU = (0.263, 0.333, 0.8)
SCURO = (0.07, 0.14, 0.32)
GRIGIO = (0.38, 0.43, 0.55)
VERDE = (0.05, 0.55, 0.38)


def _lar(t, size, bold=False):
    k = 1.07 if bold else 1.0
    return sum(_W.get(ch, 556) for ch in t) * size / 1000.0 * k


def _esc(t):
    b = t.encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _eur(x):
    try:
        n = int(round(float(x)))
    except Exception:
        n = 0
    s = f"{abs(n):,}".replace(",", ".")
    return ("-" if n < 0 else "") + s + " €"


def _pc(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except Exception:
        return "-"


class _Pdf:
    def __init__(self):
        self.pages = []
        self.y = 0
        self.nuova()

    def nuova(self):
        self.pages.append([])
        self.y = PAGE_H - MARG

    def _o(self, s):
        self.pages[-1].append(s if isinstance(s, bytes) else s.encode("latin-1"))

    def colore(self, c, fill=True):
        self._o("%.3f %.3f %.3f %s" % (c[0], c[1], c[2], "rg" if fill else "RG"))

    def testo(self, x, y, t, size=10, bold=False, col=SCURO):
        self.colore(col)
        self._o(b"BT /%s %s Tf %.2f %.2f Td (" % (b"F2" if bold else b"F1", str(size).encode(), x, y) + _esc(t) + b") Tj ET")

    def rett(self, x, y, w, h, col):
        self.colore(col)
        self._o("%.2f %.2f %.2f %.2f re f" % (x, y, w, h))

    def linea(self, x1, y1, x2, y2, col=(0.85, 0.88, 0.93)):
        self.colore(col, False)
        self._o("0.6 w %.2f %.2f m %.2f %.2f l S" % (x1, y1, x2, y2))

    def righe(self, t, w, size, bold=False):
        out = []
        for par in str(t).split("\n"):
            cur = ""
            for parola in par.split(" "):
                prova = (cur + " " + parola).strip()
                if cur and _lar(prova, size, bold) > w:
                    out.append(cur)
                    cur = parola
                else:
                    cur = prova
            out.append(cur)
        return out

    def serve(self, h):
        if self.y - h < MARG + 20:
            self.nuova()

    def par(self, t, size=10, bold=False, col=SCURO, w=None, dopo=6, x=MARG, lead=1.45):
        w = w or (PAGE_W - 2 * MARG)
        for r in self.righe(t, w, size, bold):
            self.serve(size * lead)
            self.y -= size * lead
            self.testo(x, self.y, r, size, bold, col)
        self.y -= dopo

    def titolo(self, t):
        self.serve(48)
        self.y -= 22
        self.rett(MARG, self.y - 4, 4, 18, BLU)
        self.testo(MARG + 12, self.y, t, 14, True, SCURO)
        self.y -= 14

    def tabella(self, colonne, righe, size=9):
        """colonne: [(titolo, larghezza, allineamento 'l'|'r')]"""
        tot = sum(c[1] for c in colonne)
        sc = (PAGE_W - 2 * MARG) / float(tot)
        cw = [c[1] * sc for c in colonne]

        def intest():
            self.serve(26)
            self.rett(MARG, self.y - 18, PAGE_W - 2 * MARG, 20, (0.91, 0.93, 0.98))
            x = MARG
            for (t, _, al), w in zip(colonne, cw):
                tx = x + 6 if al == "l" else x + w - 6 - _lar(t, size, True)
                self.testo(tx, self.y - 12, t, size, True, SCURO)
                x += w
            self.y -= 20
        intest()
        for r in righe:
            celle = [self.righe(str(v), w - 12, size) for v, w in zip(r, cw)]
            h = max(len(c) for c in celle) * (size * 1.35) + 8
            if self.y - h < MARG + 20:
                self.nuova()
                intest()
            x = MARG
            for c, w, (_, _, al) in zip(celle, cw, colonne):
                yy = self.y - size * 1.35
                for riga in c:
                    tx = x + 6 if al == "l" else x + w - 6 - _lar(riga, size)
                    self.testo(tx, yy - 1, riga, size, False, SCURO)
                    yy -= size * 1.35
                x += w
            self.y -= h
            self.linea(MARG, self.y, PAGE_W - MARG, self.y)
        self.y -= 8

    def kpi(self, voci):
        self.serve(70)
        n = len(voci)
        gap = 10
        w = (PAGE_W - 2 * MARG - gap * (n - 1)) / float(n)
        top = self.y - 4
        for i, (et, val, sub) in enumerate(voci):
            x = MARG + i * (w + gap)
            self.rett(x, top - 60, w, 60, (0.93, 0.96, 0.99))
            self.testo(x + 10, top - 16, et.upper(), 7, True, GRIGIO)
            self.testo(x + 10, top - 38, val, 17, True, VERDE)
            self.testo(x + 10, top - 52, sub, 8, False, GRIGIO)
        self.y -= 74

    def bytes(self):
        n = len(self.pages)
        oggetti = []

        def nuovo(c):
            oggetti.append(c)
            return len(oggetti)
        cat = nuovo(b"")
        pgs = nuovo(b"")
        f1 = nuovo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = nuovo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        kids = []
        for i, pg in enumerate(self.pages):
            corpo = list(pg)
            corpo.append(b"0.45 0.5 0.6 rg BT /F1 8 Tf 48 28 Td (" + _esc("TaxScan · stima non vincolante · pagina %d di %d" % (i + 1, n)) + b") Tj ET")
            cont = b"\n".join(corpo)
            cs = nuovo(b"<< /Length %d >>\nstream\n" % len(cont) + cont + b"\nendstream")
            pid = nuovo(("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
                         "/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> >>" % (pgs, PAGE_W, PAGE_H, cs, f1, f2)).encode())
            kids.append(pid)
        oggetti[pgs - 1] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join("%d 0 R" % k for k in kids), n)).encode()
        oggetti[cat - 1] = ("<< /Type /Catalog /Pages %d 0 R >>" % pgs).encode()
        out = bytearray(b"%PDF-1.4\n")
        pos = []
        for i, o in enumerate(oggetti):
            pos.append(len(out))
            out += b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n"
        xr = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(oggetti) + 1)
        for p in pos:
            out += b"%010d 00000 n \n" % p
        out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(oggetti) + 1, cat, xr)
        return bytes(out)


def _n(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def _t(x, n=200):
    return re.sub(r"\s+", " ", str(x or "")).strip()[:n]


PERIODI = {"sett": "Ogni settimana", "mese": "Ogni mese", "anno": "Qualche volta l'anno", "rara": "Raramente o una tantum"}


def genera(d: dict) -> bytes:
    """d: dati puliti dal chiamante (vedi prova.report)."""
    p = _Pdf()
    # intestazione
    p.rett(0, PAGE_H - 120, PAGE_W, 120, BLU)
    p.testo(MARG, PAGE_H - 52, "TaxScan", 13, True, (1, 1, 1))
    p.testo(MARG, PAGE_H - 84, "Report di ottimizzazione fiscale", 24, True, (1, 1, 1))
    p.testo(MARG, PAGE_H - 104, "Preparato per %s · %s" % (_t(d.get("nome"), 60) or "te", datetime.date.today().strftime("%d/%m/%Y")), 10, False, (0.85, 0.9, 1))
    p.y = PAGE_H - 140
    ris = _n(d.get("risparmio"))
    oggi, dopo = d.get("oggi") or {}, d.get("dopo") or {}
    p.titolo("In sintesi")
    p.kpi([("Ogni anno", _eur(ris), "tasse e contributi in meno"), ("Ogni mese", _eur(ris / 12), "in più nel tuo netto"), ("In 5 anni", _eur(ris * 5), "a parità di incassi")])
    p.par("Con le prestazioni che hai indicato, il coefficiente di redditività medio passa da %s a %s. È una stima fatta sui tuoi incassi di %s all'anno: "
          "non è una promessa di risultato." % (_pc(d.get("coef_prima")), _pc(d.get("coef_dopo")), _eur(d.get("incassi"))))

    p.titolo("I tuoi dati di partenza")
    pr = d.get("principale") or {}
    p.tabella([("Dato", 3, "l"), ("Valore", 4, "l")], [
        ["Attività principale", _t(pr.get("nome"), 90)],
        ["Codice ATECO principale", _t(pr.get("cod"), 12)],
        ["Coefficiente di redditività del codice principale", _pc(pr.get("coef"))],
        ["Incassi annui considerati", _eur(d.get("incassi"))],
        ["Aliquota dell'imposta sostitutiva", _pc(d.get("aliquota"))],
        ["Quota di contributi sul reddito", _pc(d.get("contributi"))]])

    p.titolo("Le prestazioni e come le abbiamo considerate")
    righe = []
    for r in d.get("righe") or []:
        righe.append([_t(r.get("nome"), 110), _t(r.get("categoria"), 70) + (" (" + _t(r.get("cod"), 12) + ")" if r.get("cod") else ""),
                      _pc(r.get("coef")), PERIODI.get(_t(r.get("per"), 10), "—"), "%d%%" % int(_n(r.get("quota")))])
    p.tabella([("Prestazione", 5, "l"), ("Categoria per il fisco", 4, "l"), ("Coeff.", 1.3, "r"), ("Periodicità", 2.4, "l"), ("Quota", 1.2, "r")], righe or [["Solo il lavoro principale", "", "", "", "100%"]])

    p.titolo("Prima e dopo, in un anno")
    L = lambda a, k: [a, _eur(oggi.get(k)), _eur(dopo.get(k)), _eur(_n(dopo.get(k)) - _n(oggi.get(k)))]
    p.tabella([("Voce", 4, "l"), ("Oggi", 2.2, "r"), ("Con la strategia", 2.6, "r"), ("Differenza", 2.2, "r")], [
        ["Reddito su cui paghi", _eur(oggi.get("red")), _eur(dopo.get("red")), _eur(_n(dopo.get("red")) - _n(oggi.get("red")))],
        L("Imposta sostitutiva", "imp"), L("Contributi", "con"), L("Totale tasse e contributi", "tot"), L("Quello che ti resta", "net")])

    p.titolo("Metodologia: come è stato fatto il calcolo")
    passi = [
        ("1. Il regime forfettario.", "Nel regime forfettario non si deducono i costi reali: il reddito su cui paghi si ottiene moltiplicando i ricavi per un coefficiente di redditività, "
         "stabilito dalla legge (L. 190/2014, allegato 4) per ogni codice ATECO. Più il coefficiente è basso, più il reddito imponibile è basso."),
        ("2. Più attività, più coefficienti.", "Chi svolge attività che rientrano in codici ATECO diversi applica a ciascuna il proprio coefficiente, sui ricavi di quella attività, tenendoli distinti. "
         "Il limite degli 85.000 € si calcola invece sulla somma di tutti i ricavi."),
        ("3. Da prestazione a categoria.", "Le prestazioni che hai indicato sono piccole attività svolte insieme al lavoro principale. Per ognuna TaxScan individua la categoria ufficiale (codice ATECO) "
         "in cui rientra e ne usa il coefficiente. Sono considerate solo le categorie con un coefficiente più basso di quello principale."),
        ("4. Il peso di ogni prestazione.", "Hai indicato il livello di tempo dedicato a ciascuna attività. Ho trasformato i livelli in percentuali sul totale, che non superano mai il 100%, "
         "e le ho usate come quota dei tuoi incassi, ipotizzando che gli incassi seguano il tempo dedicato."),
        ("5. Reddito imponibile.", "Reddito = somma, per ogni attività, di (incassi × quota × coefficiente). Con i tuoi dati: %s × coefficiente medio %s = %s." % (
            _eur(d.get("incassi")), _pc(d.get("coef_dopo")), _eur(dopo.get("red")))),
        ("6. Contributi e imposta.", "I contributi sono stimati come %s del reddito imponibile. L'imposta sostitutiva (%s) si applica al reddito al netto dei contributi versati. "
         "Il risparmio è la differenza tra il totale pagato oggi e quello con la strategia." % (_pc(d.get("contributi")), _pc(d.get("aliquota")))),
    ]
    for t, x in passi:
        p.serve(40)
        p.par(t, 10, True, dopo=2)
        p.par(x, 10, False, dopo=8, x=MARG + 8, w=PAGE_W - 2 * MARG - 8)

    tk = d.get("task") or []
    if tk:
        p.titolo("Cosa fare ora")
        for i, t in enumerate(tk, 1):
            p.serve(46)
            p.par("%d. %s" % (i, _t(t.get("titolo"), 120)), 10, True, dopo=2)
            if t.get("perche"):
                p.par(_t(t.get("perche"), 260), 10, False, GRIGIO, dopo=2, x=MARG + 8, w=PAGE_W - 2 * MARG - 8)
            if t.get("come"):
                p.par("Come: " + _t(t.get("come"), 280), 10, False, GRIGIO, dopo=8, x=MARG + 8, w=PAGE_W - 2 * MARG - 8)

    p.titolo("Limiti e avvertenze")
    for t in [
        "Tutte le cifre sono stime basate sulle informazioni che hai indicato e sulle regole di calcolo semplificate sopra descritte. Non sono una promessa di risultato.",
        "Il risparmio esiste solo se le prestazioni sono svolte davvero, fatturate con righe distinte e se il relativo codice ATECO è attivo sulla tua partita IVA "
        "(variazione dati con il modello AA9/12, o con la procedura che ti indica il tuo intermediario).",
        "Non sono considerati casi particolari: rivendita di prodotti (può cambiare la gestione INPS), casse professionali, superamento delle soglie, agevolazioni per i primi anni di attività.",
        "TaxScan prepara e spiega: puoi gestire tutto in autonomia, assumendoti la responsabilità di ciò che dichiari e paghi, oppure far controllare i numeri a un commercialista quando vuoi. Il controllo è facoltativo.",
    ]:
        p.par("• " + t, 10, False, dopo=5, x=MARG + 4, w=PAGE_W - 2 * MARG - 4)
    return p.bytes()


# ================= v2: report dettagliato dell'Ottimizzazione fiscale (fattura divisa) e modello di fattura =================
NAVY = (0.07, 0.14, 0.32)
CHIARO = (0.93, 0.95, 0.99)
VERDE_CH = (0.90, 0.97, 0.93)
ARANCIO = (0.85, 0.48, 0.17)


def _logo(p, x, y, size=22, sfondo_scuro=False):
    """Logo TaxScan disegnato come testo: «Tax» scuro (o bianco) e «Scan» blu."""
    p.testo(x, y, "Tax", size, True, (1, 1, 1) if sfondo_scuro else NAVY)
    p.testo(x + _lar("Tax", size, True), y, "Scan", size, True, (0.62, 0.7, 1) if sfondo_scuro else BLU)


def _intestazione(p, titolo, sotto):
    p.rett(0, PAGE_H - 132, PAGE_W, 132, NAVY)
    p.rett(0, PAGE_H - 136, PAGE_W, 4, BLU)
    _logo(p, MARG, PAGE_H - 50, 22, True)
    p.testo(MARG, PAGE_H - 66, "Il primo agente IA specializzato nel risparmio fiscale", 8, False, (0.75, 0.8, 0.95))
    p.testo(MARG, PAGE_H - 98, titolo, 21, True, (1, 1, 1))
    p.testo(MARG, PAGE_H - 117, sotto, 9.5, False, (0.8, 0.85, 1))
    p.y = PAGE_H - 156


def _barre(p, voci, col_a=GRIGIO, col_b=VERDE):
    """voci: [(etichetta, oggi, dopo)] -> barre orizzontali affiancate, scala comune."""
    mx = max([max(abs(_n(a)), abs(_n(b))) for _, a, b in voci] + [1])
    w = PAGE_W - 2 * MARG - 170
    for et, a, b in voci:
        p.serve(40)
        p.testo(MARG, p.y - 11, et, 9, True, SCURO)
        for i, (v, c, lab) in enumerate(((a, col_a, "Oggi"), (b, col_b, "Dopo"))):
            yy = p.y - 24 - i * 12
            p.testo(MARG, yy + 1, lab, 7.5, False, GRIGIO)
            p.rett(MARG + 34, yy, max(2, w * abs(_n(v)) / mx), 8, c)
            p.testo(MARG + 40 + w * abs(_n(v)) / mx, yy + 1, _eur(v), 8, True, SCURO)
        p.y -= 50


def genera_v2(d: dict) -> bytes:
    p = _Pdf()
    _intestazione(p, "Report di risparmio fiscale", "Preparato per %s · %s" % (_t(d.get("nome"), 60) or "te", datetime.date.today().strftime("%d/%m/%Y")))
    ris = _n(d.get("risparmio"))
    oggi, dopo = d.get("oggi") or {}, d.get("dopo") or {}
    cp, cd = _n(d.get("coef_prima")), _n(d.get("coef_dopo"))
    p.titolo("In sintesi")
    p.kpi([("Risparmio annuo", _eur(ris), "tasse e contributi in meno"), ("Ogni mese", _eur(ris / 12), "in più nel tuo netto"),
           ("Coefficiente medio", _pc(cd), "invece del %s" % _pc(cp))])
    p.par("Abbiamo analizzato %s e individuato %d micro-attività che svolgi (o puoi svolgere) insieme al tuo lavoro principale e che, per il fisco, "
          "rientrano in categorie con un coefficiente di redditività più basso. Dividendo la fattura in righe separate, ognuna con il suo importo e il suo "
          "coefficiente, il reddito su cui paghi scende da %s a %s. Su incassi annui di %s il risparmio stimato è di circa %s l'anno. È una stima, non una promessa di risultato." % (
              "la tua fattura" if len(d.get("fatture") or []) == 1 else "le tue fatture", len(d.get("micro") or []),
              _eur(oggi.get("red")), _eur(dopo.get("red")), _eur(d.get("incassi")), _eur(ris)))
    _barre(p, [("Reddito su cui paghi", oggi.get("red"), dopo.get("red")), ("Totale tasse e contributi", oggi.get("tot"), dopo.get("tot"))])

    p.titolo("I dati di partenza")
    pr = d.get("principale") or {}
    p.tabella([("Dato", 3, "l"), ("Valore", 4, "l")], [
        ["Attività principale", _t(pr.get("nome"), 90) or "—"],
        ["Codice ATECO attuale", _t(pr.get("cod"), 12) or "—"],
        ["Coefficiente di redditività attuale", _pc(pr.get("coef"))],
        ["Incassi annui considerati", _eur(d.get("incassi"))],
        ["Aliquota dell'imposta sostitutiva", _pc(d.get("aliquota"))],
        ["Contributi previdenziali (quota sul reddito)", _pc(d.get("contributi"))]])

    for k, f in enumerate(d.get("fatture") or [], 1):
        p.titolo("La prestazione analizzata" + (" (fattura %d)" % k if len(d.get("fatture") or []) > 1 else ""))
        cl = _t(f.get("cliente"), 120)
        p.par("Cliente: %s. Importo della fattura: %s." % (cl or "non indicato", _eur(f.get("importo"))), 10, False, dopo=4)
        p.tabella([("Righe della fattura originale", 6, "l"), ("Importo", 1.6, "r")],
                  [[_t(r.get("testo"), 160), _eur(r.get("importo"))] for r in (f.get("righe_orig") or [])[:12]] or [["—", ""]])
        if _t(f.get("dettagli"), 10):
            p.par("Cosa ci hai raccontato del lavoro svolto: «%s»" % _t(f.get("dettagli"), 700), 9.5, False, GRIGIO, dopo=6)

    p.titolo("Le micro-attività individuate")
    p.par("Per ognuna: perché è collegata al tuo lavoro, in quale categoria la mette il fisco, quanto pesa nella fattura e quanto contribuisce al risparmio.", 9.5, False, GRIGIO, dopo=6)
    for i, m in enumerate(d.get("micro") or [], 1):
        p.serve(110)
        p.y -= 4
        p.rett(MARG, p.y - 22, PAGE_W - 2 * MARG, 22, CHIARO)
        p.testo(MARG + 8, p.y - 15, "%d. %s" % (i, _t(m.get("nome"), 90)), 10.5, True, SCURO)
        p.y -= 28
        x8, w8 = MARG + 8, PAGE_W - 2 * MARG - 8
        if m.get("descrizione"):
            p.par(_t(m.get("descrizione"), 300), 9.5, False, SCURO, dopo=2, x=x8, w=w8)
        if m.get("collegamento"):
            p.par("Perché c'entra: " + _t(m.get("collegamento"), 300), 9.5, False, GRIGIO, dopo=2, x=x8, w=w8)
        p.par("Categoria: %s · codice ATECO %s · coefficiente %s (invece del %s)." % (_t(m.get("categoria"), 80) or "—", _t(m.get("cod"), 12), _pc(m.get("coef")), _pc(cp)),
              9.5, False, SCURO, dopo=2, x=x8, w=w8)
        p.par("Peso nella fattura: %s · quota degli incassi: %s (circa %s l'anno) · contributo al risparmio: circa %s l'anno." % (
            _t(m.get("peso"), 20), "%.0f%%" % (_n(m.get("quota")) * 100), _eur(m.get("ricavi_anno")), _eur(m.get("risparmio_attr"))), 9.5, True, VERDE, dopo=2, x=x8, w=w8)
        if m.get("riga"):
            p.par("Come scriverla in fattura: «%s»" % _t(m.get("riga"), 180), 9.5, False, SCURO, dopo=2, x=x8, w=w8)
        if m.get("attenzione"):
            p.par("Attenzione: " + _t(m.get("attenzione"), 300), 9.5, False, ARANCIO, dopo=2, x=x8, w=w8)
        p.y -= 6

    for k, f in enumerate(d.get("fatture") or [], 1):
        p.titolo("Come rifare la fattura" + (" %d" % k if len(d.get("fatture") or []) > 1 else ""))
        p.par("Stesso totale per il cliente: cambia solo il modo in cui le prestazioni sono descritte e divise. Ogni riga ha il suo importo; "
              "i codici ATECO non vanno scritti in fattura, servono a te per calcolare il reddito di ciascuna attività.", 9.5, False, GRIGIO, dopo=6)
        p.tabella([("Riga della nuova fattura", 5.2, "l"), ("Attività (codice)", 2.2, "l"), ("Coeff.", 1, "r"), ("Importo", 1.6, "r")],
                  [[_t(r.get("testo"), 160), _t(r.get("cod"), 12), _pc(r.get("coef")), _eur(r.get("importo"))] for r in (f.get("righe_nuove") or [])[:14]] +
                  [["Totale", "", "", _eur(f.get("importo"))]])

    p.titolo("Il calcolo, passo per passo")
    fat = _n(d.get("contributi")) + (1 - _n(d.get("contributi"))) * _n(d.get("aliquota"))
    for t, x in [
        ("1. Oggi.", "Tutti gli incassi (%s) usano il coefficiente del %s: reddito = %s." % (_eur(d.get("incassi")), _pc(cp), _eur(oggi.get("red")))),
        ("2. Con la fattura divisa.", "Ogni parte di incasso usa il coefficiente della sua attività. Le quote sono quelle della fattura divisa, applicate agli incassi "
         "dell'anno: coefficiente medio %s, reddito = %s." % (_pc(cd), _eur(dopo.get("red")))),
        ("3. Contributi e imposta.", "Contributi stimati al %s del reddito; imposta sostitutiva al %s sul reddito al netto dei contributi. Ogni euro di reddito in meno "
         "fa risparmiare circa %s centesimi tra tasse e contributi." % (_pc(d.get("contributi")), _pc(d.get("aliquota")), "%.0f" % (fat * 100))),
        ("4. Il risparmio.", "Totale oggi %s, totale con la fattura divisa %s: differenza circa %s l'anno." % (_eur(oggi.get("tot")), _eur(dopo.get("tot")), _eur(ris)))]:
        p.serve(36)
        p.par(t, 10, True, dopo=1)
        p.par(x, 9.5, False, dopo=6, x=MARG + 8, w=PAGE_W - 2 * MARG - 8)
    L = lambda a, k: [a, _eur(oggi.get(k)), _eur(dopo.get(k)), _eur(_n(dopo.get(k)) - _n(oggi.get(k)))]
    p.tabella([("Voce", 4, "l"), ("Oggi", 2.2, "r"), ("Con la fattura divisa", 2.8, "r"), ("Differenza", 2.2, "r")],
              [L("Reddito su cui paghi", "red"), L("Imposta sostitutiva", "imp"), L("Contributi", "con"), L("Totale tasse e contributi", "tot")])

    tk = d.get("task") or []
    if tk:
        p.titolo("Come ottenere il risparmio, in ordine di priorità")
        for i, t in enumerate(tk, 1):
            p.serve(44)
            p.par("%d. %s" % (i, _t(t.get("titolo"), 120)), 10, True, dopo=1)
            if t.get("perche"):
                p.par(_t(t.get("perche"), 300), 9.5, False, GRIGIO, dopo=1, x=MARG + 8, w=PAGE_W - 2 * MARG - 8)
            if t.get("come"):
                p.par("Come: " + _t(t.get("come"), 400), 9.5, False, GRIGIO, dopo=6, x=MARG + 8, w=PAGE_W - 2 * MARG - 8)
        p.par("Trovi tutti i compiti nella sezione «Da fare» di TaxScan, con il pulsante Inizia per farti guidare.", 9.5, False, BLU, dopo=4)

    p.titolo("Limiti e avvertenze")
    for t in [
        "Le cifre sono stime basate sulla fattura analizzata, su quello che ci hai indicato e su regole di calcolo semplificate. Non sono una promessa di risultato.",
        "Il risparmio esiste solo se le micro-attività sono svolte davvero, descritte con precisione in fattura su righe separate e se il relativo codice ATECO è attivo sulla tua partita IVA.",
        "Commercio e intermediazione possono richiedere Camera di Commercio e INPS Commercianti, con contributi minimi fissi non inclusi in questo calcolo. Casse professionali e Ordini hanno regole proprie.",
        "TaxScan prepara e spiega: puoi gestire tutto in autonomia, assumendoti la responsabilità di ciò che dichiari e paghi, oppure far controllare i numeri a un commercialista. Il controllo è facoltativo.",
    ]:
        p.par("• " + t, 9.5, False, dopo=4, x=MARG + 4, w=PAGE_W - 2 * MARG - 4)
    return p.bytes()


def genera_fattura(d: dict) -> bytes:
    """Modello di fattura con le righe separate (template da copiare nel proprio programma di fatturazione)."""
    p = _Pdf()
    p.rett(0, PAGE_H - 8, PAGE_W, 8, BLU)
    _logo(p, MARG, PAGE_H - 44, 14)
    p.testo(MARG, PAGE_H - 58, "Modello di fattura con le prestazioni separate", 8.5, False, GRIGIO)
    p.testo(PAGE_W - MARG - _lar("FATTURA N. [numero]", 18, True), PAGE_H - 50, "FATTURA N. [numero]", 18, True, SCURO)
    p.testo(PAGE_W - MARG - _lar("Data: [gg/mm/aaaa]", 9), PAGE_H - 66, "Data: [gg/mm/aaaa]", 9, False, GRIGIO)
    y0 = PAGE_H - 100
    for i, (tit, righe) in enumerate((("Da", ["[Il tuo nome e cognome]", "[Indirizzo]", "P.IVA [la tua partita IVA]", "C.F. [il tuo codice fiscale]"]),
                                      ("A", ["[Ragione sociale del cliente]", "[Indirizzo, paese]", "P.IVA / VAT [del cliente]", "[PEC o codice destinatario, se italiano]"]))):
        x = MARG + i * ((PAGE_W - 2 * MARG) / 2 + 10)
        p.rett(x, y0 - 78, (PAGE_W - 2 * MARG) / 2 - 10, 78, CHIARO)
        p.testo(x + 10, y0 - 16, tit.upper(), 8, True, GRIGIO)
        for k, r in enumerate(righe):
            p.testo(x + 10, y0 - 32 - k * 13, r, 9.5, k == 0, SCURO)
    p.y = y0 - 96
    righe = [[_t(r.get("testo"), 160), "1", _eur(r.get("importo")), _eur(r.get("importo"))] for r in (d.get("righe") or [])[:14]]
    p.tabella([("Descrizione della prestazione", 6, "l"), ("Q.tà", 0.8, "r"), ("Prezzo", 1.6, "r"), ("Importo", 1.6, "r")], righe or [["[descrizione]", "1", "", ""]])
    tot = sum(_n(r.get("importo")) for r in (d.get("righe") or []))
    p.serve(30)
    p.rett(PAGE_W - MARG - 200, p.y - 24, 200, 24, CHIARO)
    p.testo(PAGE_W - MARG - 190, p.y - 16, "Totale documento", 10, True, SCURO)
    p.testo(PAGE_W - MARG - 10 - _lar(_eur(tot), 11, True), p.y - 16, _eur(tot), 11, True, SCURO)
    p.y -= 40
    p.par("Diciture da riportare (regime forfettario):", 9.5, True, dopo=2)
    for t in ["Operazione effettuata ai sensi dell'art. 1, commi da 54 a 89, della Legge n. 190/2014 (regime forfettario): non soggetta a IVA né a ritenuta d'acconto.",
              "Imposta di bollo da 2,00 € assolta sull'originale, se l'importo supera 77,47 €.",
              "Cliente estero: usa la natura dell'operazione e la dicitura che il tuo programma di fatturazione propone per le prestazioni verso l'estero (per esempio N2.1, art. 7-ter DPR 633/72)."]:
        p.par("• " + t, 9, False, GRIGIO, dopo=3, x=MARG + 4, w=PAGE_W - 2 * MARG - 4)
    p.y -= 6
    p.par("Come usarlo: copia le righe nel tuo programma di fatturazione, una riga per ogni prestazione, con il suo importo. Scrivi in ogni riga cosa hai fatto davvero. "
          "I codici ATECO non vanno in fattura: tieni a parte, per ogni attività, il totale incassato.", 9, False, BLU, dopo=4)
    return p.bytes()
