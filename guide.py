"""
TaxScan - guide pubbliche per Google (/guide/...).

Pagine brevi sulle domande che i forfettari cercano davvero ("quanto pago a novembre", "come si calcola"),
con un esempio in euro e un invito a fare il calcolo vero su TaxScan. I numeri vengono da dati_fisco.py:
quando cambia l'anno si aggiornano da soli; il testo delle regole va riletto ogni anno.
"""
import html as _html

import dati_fisco as D

BASE = "https://taxscan.it"
AGGIORNATA = "1 novembre 2026"


def _eur(x: float, dec: int = 0) -> str:
    s = f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def _pct(x: float) -> str:
    return (f"{x * 100:.2f}".rstrip("0").rstrip(".")).replace(".", ",") + "%"


# Esempio unico, usato in tutte le guide: professionista in gestione separata, 30.000 € incassati.
_RICAVI = 30_000
_COEFF = 0.78
_REDDITO = _RICAVI * _COEFF
_GS = D.GESTIONE_SEPARATA["aliquota_senza_altra_copertura"]
_CONTRIB = _REDDITO * _GS
_VERSATI = 4_000                      # contributi effettivamente versati nell'anno (si deducono per cassa)
_IMPONIBILE = _REDDITO - _VERSATI
_IMPOSTA = _IMPONIBILE * D.ALIQUOTA_ORDINARIA
_IMPOSTA_START = _IMPONIBILE * D.ALIQUOTA_STARTUP


GUIDE = {
    "acconto-30-novembre-forfettario": {
        "titolo": "Secondo acconto del 30 novembre per i forfettari: quanto si paga",
        "descrizione": "Il 30 novembre i forfettari versano il secondo acconto di imposta sostitutiva e contributi INPS. "
                       "Come si calcola, chi non lo paga e un esempio in euro.",
        "corpo": f"""
<p class="lead">Il 30 novembre i forfettari pagano il <b>secondo acconto</b> dell'imposta sostitutiva e, se dovuto, dei
contributi INPS. Per l'imposta è in genere <b>metà dell'imposta dell'anno prima</b>.</p>

<h2>Quanto vale il secondo acconto dell'imposta</h2>
<p>L'acconto totale è il 100% dell'imposta sostitutiva dell'anno precedente. Per i forfettari si divide in <b>due rate
uguali</b>: 50% entro il 30 giugno e 50% entro il 30 novembre (art. 58 DL 124/2019, lo stesso riparto dei soggetti ISA).
Non è il 40/60 che si legge spesso.</p>
<ul>
<li>Imposta dell'anno prima fino a <b>51,65&nbsp;€</b>: nessun acconto.</li>
<li>Fino a <b>206&nbsp;€</b>: acconto tutto in un'unica rata il 30 novembre.</li>
<li>Oltre: metà a giugno, metà a novembre.</li>
</ul>

<h2>Esempio</h2>
<p>Nell'anno precedente hai pagato {_eur(_IMPOSTA)} di imposta sostitutiva. L'acconto totale è {_eur(_IMPOSTA)}:
{_eur(_IMPOSTA / 2)} a giugno e <b>{_eur(_IMPOSTA / 2)} il 30 novembre</b>.</p>

<h2>E i contributi INPS</h2>
<p>Chi è in <b>gestione separata</b> versa come acconto l'80% dei contributi dell'anno prima, in due rate uguali a giugno
e a novembre. Con {_eur(6_100)} di contributi l'anno prima: acconto {_eur(4_880)}, cioè <b>{_eur(2_440)} a novembre</b>.
Artigiani e commercianti pagano a novembre il secondo acconto solo sulla parte di reddito sopra il minimale; i contributi
fissi hanno la loro rata il 16 novembre.</p>

<h2>Se quest'anno guadagni meno</h2>
<p>Puoi pagare un acconto più basso con il <b>metodo previsionale</b>: versi quanto prevedi di dovere davvero per
quest'anno. Se la previsione è sbagliata per difetto, sulla differenza si pagano sanzioni e interessi, salvo
ravvedimento. Il secondo acconto <b>non si può rateizzare</b>.</p>

<h2>Chi ha aperto la partita IVA quest'anno</h2>
<p>Nel primo anno non c'è un'imposta dell'anno prima: con il metodo storico l'acconto è zero. Il conto arriva tutto
insieme a giugno dell'anno dopo, con saldo e primo acconto: conviene mettere da parte una quota di ogni fattura.</p>
""",
    },
    "saldo-acconto-30-giugno-forfettario": {
        "titolo": "Saldo e primo acconto del 30 giugno per i forfettari: come funziona",
        "descrizione": "A giugno i forfettari pagano il saldo dell'anno prima e il primo acconto di quello in corso, "
                       "per imposta e contributi. Esempio in euro, rate e proroga a luglio.",
        "corpo": f"""
<p class="lead">Entro il 30 giugno i forfettari pagano due cose insieme: il <b>saldo</b> dell'anno precedente e il
<b>primo acconto</b> dell'anno in corso, sia per l'imposta sostitutiva sia per i contributi INPS.</p>

<h2>Cosa c'è nel conto di giugno</h2>
<ul>
<li><b>Saldo imposta</b>: imposta dell'anno precedente meno gli acconti già versati.</li>
<li><b>Primo acconto imposta</b>: il 50% dell'imposta dell'anno precedente (se supera 206&nbsp;€).</li>
<li><b>Contributi INPS</b>: saldo dell'anno precedente e primo acconto (gestione separata: 40% dei contributi dell'anno
prima; artigiani e commercianti: sulla parte di reddito sopra il minimale).</li>
</ul>

<h2>Esempio</h2>
<p>Imposta dell'anno precedente {_eur(_IMPOSTA)}, nessun acconto versato perché era il primo anno. A giugno paghi
{_eur(_IMPOSTA)} di saldo più {_eur(_IMPOSTA / 2)} di primo acconto: <b>{_eur(_IMPOSTA * 1.5)} di sola imposta</b>, a cui
si aggiungono i contributi. È il motivo per cui il secondo anno di partita IVA sorprende molti.</p>

<h2>Si può pagare a rate o più tardi</h2>
<p>Saldo e primo acconto si possono <b>rateizzare</b> in rate mensili, con interessi. Di norma si può
anche pagare entro il 30 luglio con una maggiorazione dello 0,40%. Il secondo acconto di novembre invece non si rateizza.</p>
""",
    },
    "come-si-calcolano-tasse-forfettario": {
        "titolo": f"Come si calcolano le tasse nel regime forfettario ({D.ANNO})",
        "descrizione": "Coefficiente di redditività, contributi INPS e imposta al 15% o al 5%: il calcolo delle tasse "
                       "del forfettario passo per passo, con un esempio su 30.000 euro.",
        "corpo": f"""
<p class="lead">Nel forfettario non si scaricano le spese: si applica un <b>coefficiente</b> agli incassi, si tolgono i
contributi versati e sul resto si paga un'imposta del {_pct(D.ALIQUOTA_ORDINARIA)} (o del {_pct(D.ALIQUOTA_STARTUP)}
nei primi cinque anni, se hai i requisiti).</p>

<h2>Il calcolo in tre passi</h2>
<ol>
<li><b>Reddito</b> = incassi dell'anno × coefficiente del tuo codice ATECO (dal 40% al 86%; 78% per molte attività
professionali, 67% per informatica e altre attività).</li>
<li><b>Imponibile</b> = reddito − contributi INPS versati nell'anno.</li>
<li><b>Imposta</b> = imponibile × {_pct(D.ALIQUOTA_ORDINARIA)} (o {_pct(D.ALIQUOTA_STARTUP)}).</li>
</ol>

<h2>Esempio: professionista con {_eur(_RICAVI)} incassati</h2>
<ul>
<li>Reddito: {_eur(_RICAVI)} × 78% = {_eur(_REDDITO)}</li>
<li>Contributi gestione separata dovuti: {_eur(_REDDITO)} × {_pct(_GS)} = {_eur(_CONTRIB)}</li>
<li>Se nell'anno hai versato {_eur(_VERSATI)} di contributi, imponibile: {_eur(_IMPONIBILE)}</li>
<li>Imposta al {_pct(D.ALIQUOTA_ORDINARIA)}: <b>{_eur(_IMPOSTA)}</b>; al {_pct(D.ALIQUOTA_STARTUP)}: {_eur(_IMPOSTA_START)}</li>
</ul>

<h2>Le soglie da tenere d'occhio</h2>
<p>Si resta nel forfettario fino a {_eur(D.SOGLIA_RICAVI)} di incassi. Tra {_eur(D.SOGLIA_RICAVI)} e
{_eur(D.SOGLIA_USCITA_IMMEDIATA)} si esce dall'anno dopo; oltre {_eur(D.SOGLIA_USCITA_IMMEDIATA)} si esce subito, con
l'IVA già dalla fattura che supera la soglia.</p>

<h2>Artigiani e commercianti</h2>
<p>Pagano contributi fissi sul minimale (circa {_eur(D.ARTIGIANI_COMMERCIANTI['artigiani']['fisso_annuo'])} l'anno gli
artigiani, {_eur(D.ARTIGIANI_COMMERCIANTI['commercianti']['fisso_annuo'])} i commercianti) anche se incassano poco, più
una percentuale sulla parte sopra {_eur(D.ARTIGIANI_COMMERCIANTI['minimale_reddito'])}. I forfettari possono chiedere la
riduzione del 35% entro il 28 febbraio.</p>
""",
    },
}


def _e(x) -> str:
    return _html.escape(str(x))


_CSS = """
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{color-scheme:light;--bg:#eef2f8;--surface:#fff;--line:#d8e2ed;--ink:#122452;--ink2:#3d4a73;--accent:#4355cc;--accent-ink:#4355cc}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0a1330;--surface:#122452;--line:#25397a;--ink:#fff;--ink2:#c9d3ec;--accent:#5566dd;--accent-ink:#a6b4ff}}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--ink);font:16px/1.6 "Poppins",system-ui,sans-serif;padding:24px 16px 48px}
main{max-width:720px;margin:0 auto}h1,h2{font-family:"Rethink Sans","Poppins",sans-serif;line-height:1.2}
.logo{font-weight:700;font-size:22px;text-decoration:none;color:var(--ink);display:inline-block;margin-bottom:24px}.logo span{color:var(--accent-ink)}
h1{font-size:clamp(28px,6vw,40px);margin-bottom:14px}h2{font-size:21px;margin:28px 0 8px}
p,ul,ol{margin-bottom:12px;color:var(--ink2)}b{color:var(--ink)}ul,ol{padding-left:22px}li{margin-bottom:6px}
.lead{font-size:18px}
.box{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px;margin:32px 0}
.box p{margin-bottom:14px}.cta{display:block;text-align:center;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;font-size:18px;padding:15px;border-radius:14px}
.meta{font-size:13px;color:var(--ink2)}.altre a{color:var(--accent-ink);font-weight:600}
"""


def pagina(slug: str) -> str | None:
    g = GUIDE.get(slug)
    if not g:
        return None
    altre = "".join(f"<li><a href='/guide/{s}'>{_e(x['titolo'])}</a></li>" for s, x in GUIDE.items() if s != slug)
    cta = f"/colloquio/nuovo?utm_source=guida&utm_campaign={slug}"
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(g['titolo'])} - TaxScan</title>
<meta name="description" content="{_e(g['descrizione'])}">
<link rel="canonical" href="{BASE}/guide/{slug}">
<meta property="og:title" content="{_e(g['titolo'])}"><meta property="og:description" content="{_e(g['descrizione'])}">
<meta property="og:type" content="article"><meta property="og:url" content="{BASE}/guide/{slug}">
<style>{_CSS}</style></head><body><main>
<a class="logo" href="/?utm_source=guida">Tax<span>Scan</span></a>
<h1>{_e(g['titolo'])}</h1>
<p class="meta">Aggiornata al {AGGIORNATA} · regole e importi {D.ANNO}</p>
{g['corpo']}
<div class="box"><p><b>Il tuo conto, non quello dell'esempio.</b> TaxScan legge il certificato della partita IVA e in 2
minuti ti dice quanto pagare a ogni scadenza e quanto mettere da parte su ogni fattura. Gratis.</p>
<a class="cta" href="{_e(cta)}">Calcola le mie tasse</a></div>
<h2>Altre guide</h2><ul class="altre">{altre}</ul>
<p class="meta">Le guide spiegano le regole generali e non sono una consulenza: il calcolo definitivo dipende dalla tua
situazione (altri redditi, acconti già versati, casse professionali). Per un caso specifico chiedi a un professionista.</p>
<p class="meta"><a href="/privacy">Privacy</a> · <a href="/termini">Termini</a></p>
</main></body></html>"""


def elenco() -> str:
    voci = "".join(f"<li><a href='/guide/{s}'>{_e(g['titolo'])}</a><br><span class='meta'>{_e(g['descrizione'])}</span></li>"
                   for s, g in GUIDE.items())
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Guide per forfettari - TaxScan</title>
<meta name="description" content="Guide brevi per partite IVA in regime forfettario: acconti, saldo, calcolo delle tasse.">
<link rel="canonical" href="{BASE}/guide"><style>{_CSS}</style></head><body><main>
<a class="logo" href="/?utm_source=guida">Tax<span>Scan</span></a><h1>Guide per forfettari</h1>
<ul class="altre">{voci}</ul></main></body></html>"""


def registra(mcp, evento=None) -> None:
    """evento(tipo, riferimento, dettaglio): se c'è, ogni lettura di una guida conta come visita nel pannello /admin,
    con la provenienza (Google, social...) e la guida letta."""
    from starlette.responses import HTMLResponse

    @mcp.custom_route("/guide", methods=["GET"])
    async def guide_elenco(request):
        return HTMLResponse(elenco(), headers={"Cache-Control": "public, max-age=3600"})

    @mcp.custom_route("/guide/{slug}", methods=["GET"])
    async def guida(request):
        slug = request.path_params.get("slug", "")
        p = pagina(slug)
        if p is not None and evento is not None:
            try:
                import asyncio
                import admin_pannello
                fonte = admin_pannello.fonte_visita(dict(request.query_params), request.headers.get("referer", ""),
                                                    request.headers.get("user-agent", ""))
                if fonte:
                    asyncio.get_running_loop().run_in_executor(None, evento, "visita", None,
                                                               {"fonte": fonte, "pagina": "guide/" + slug})
            except Exception:
                pass
        if p is None:
            return HTMLResponse("<p>Guida non trovata. <a href='/guide'>Tutte le guide</a></p>", status_code=404)
        return HTMLResponse(p, headers={"Cache-Control": "public, max-age=3600"})
