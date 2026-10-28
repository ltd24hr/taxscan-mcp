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
