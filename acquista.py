"""TaxScan - pagina di acquisto (/acquista): 47 EUR per 12 mesi, sblocca Ottimizzazione fiscale e report.

Tutto quello che cambia nel tempo si imposta su Render, senza toccare il codice:
- ACQUISTA_LINK   link di pagamento (per esempio un Payment Link di Stripe). Se manca, il pulsante porta a iniziare gratis.
                  Al link si aggiungono ?client_reference_id=<c> e ?prefilled_email=... quando la pagina li conosce,
                  cosi' il pagamento si potra' collegare alla situazione della persona.
- ACQUISTA_VIDEO  il video tutorial: link YouTube o Vimeo (si incorpora) oppure un file .mp4. Se manca, la sezione video non c'e'.
Le testimonianze sono SOLO screenshot veri, con il consenso di chi li ha scritti: si mettono in static/testimonianze/
(png, jpg o webp; il nome del file decide l'ordine). Se la cartella e' vuota, la sezione non compare.
"""
import html
import os
import re
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

PREZZO = 47
CARTELLA_T = Path(__file__).parent / "static" / "testimonianze"
_IMG = re.compile(r"^[A-Za-z0-9_.-]{1,80}\.(png|jpe?g|webp)$", re.I)


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def _video_html(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith("https://"):
        return ""
    u = urlparse(url)
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    vid = ""
    if host in ("youtube.com", "youtube-nocookie.com"):
        vid = (parse_qs(u.query).get("v") or [""])[0] or (u.path.split("/embed/")[-1] if "/embed/" in u.path else "")
    elif host == "youtu.be":
        vid = u.path.strip("/")
    if vid and re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid):
        src = f"https://www.youtube-nocookie.com/embed/{vid}?rel=0"
        return f'<iframe src="{_e(src)}" title="Come funziona TaxScan" loading="lazy" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>'
    if host in ("vimeo.com", "player.vimeo.com"):
        m = re.search(r"(\d{6,12})", u.path)
        if m:
            return (f'<iframe src="https://player.vimeo.com/video/{m.group(1)}?dnt=1" title="Come funziona TaxScan" loading="lazy" '
                    'allow="fullscreen; picture-in-picture" allowfullscreen></iframe>')
    if u.path.lower().endswith(".mp4"):
        return f'<video src="{_e(url)}" controls preload="metadata" playsinline></video>'
    return ""


def _testimonianze() -> list[str]:
    try:
        return sorted(p.name for p in CARTELLA_T.iterdir() if p.is_file() and _IMG.match(p.name))[:12]
    except Exception:
        return []


def _link_acquisto(c: str, email: str) -> str:
    base = (os.environ.get("ACQUISTA_LINK") or "").strip()
    if not base.startswith("https://"):
        return "/prova" + (f"?c={_e(c)}&vai=g" if c else "")
    extra = {}
    if c:
        extra["client_reference_id"] = c
    if email:
        extra["prefilled_email"] = email
    if not extra:
        return base
    return base + ("&" if "?" in base else "?") + urlencode(extra)


def pagina(c: str = "", email: str = "") -> str:
    c = re.sub(r"[^A-Za-z0-9_-]", "", c or "")[:64]
    email = email if re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,}", email or "") else ""
    link = _link_acquisto(c, email)
    attivo = link.startswith("https://")
    video = _video_html(os.environ.get("ACQUISTA_VIDEO", ""))
    t = _testimonianze()
    sez_video = ("" if not video else
                 '<section class="sez" id="video" aria-labelledby="t-video"><h2 id="t-video">Guarda come funziona, dall\'inizio alla fine</h2>'
                 '<p class="lead2">In 20 minuti vedi l\'agente IA al lavoro su una situazione vera: cosa legge, come ragiona e dove trova il risparmio.</p>'
                 f'<div class="vid">{video}</div>'
                 '<ol class="cap"><li><b>Cos\'è un agente IA</b> e cosa fa per una partita IVA forfettaria</li>'
                 '<li><b>Il questionario</b>: due minuti, o il certificato della partita IVA</li>'
                 '<li><b>Le fatture</b>: come capisce che lavoro fai davvero</li>'
                 '<li><b>Il risparmio</b>: attività con coefficienti diversi, fatture divise bene</li>'
                 '<li><b>I contributi INPS</b>: le riduzioni che spesso nessuno ti dice</li>'
                 '<li><b>Scadenze e acconti</b>: quanto mettere da parte, mese per mese</li>'
                 '<li><b>Il report e i passi da fare</b>, uno alla volta</li></ol></section>')
    sez_t = ("" if not t else
             '<section class="sez" id="dicono" aria-labelledby="t-dicono"><h2 id="t-dicono">Cosa ci scrivono le prime partite IVA</h2>'
             '<p class="lead2">Messaggi veri, pubblicati con il permesso di chi li ha scritti.</p><div class="tst">'
             + "".join(f'<figure><img src="/acquista/t/{_e(n)}" alt="Messaggio di una persona che usa TaxScan" loading="lazy"></figure>' for n in t)
             + '</div></section>')
    pulsante = ('Sblocca il tuo risparmio a 47 €' if attivo else 'Inizia gratis e scopri il tuo risparmio')
    nota = ('Pagamento sicuro · un solo pagamento per 12 mesi' if attivo else
            'Il pagamento online arriva a breve: intanto puoi iniziare gratis')
    return (PAGINA_HTML.replace("{{LINK}}", _e(link)).replace("{{PULSANTE}}", pulsante).replace("{{NOTA}}", nota)
            .replace("{{VIDEO}}", sez_video).replace("{{TESTIMONIANZE}}", sez_t)
            .replace("{{VAI_VIDEO}}", '<a class="sec" href="#video">Guarda il video (20 min)</a>' if video else "")
            .replace(" €", "\u00a0€"))   # «47 €» non va mai a capo tra numero e simbolo


def registra(mcp) -> None:
    from starlette.responses import HTMLResponse, FileResponse, Response

    @mcp.custom_route("/acquista", methods=["GET", "HEAD"])
    async def acquista_pagina(request):
        qp = request.query_params
        try:
            import db
            db.registra_evento("acquista_visita", re.sub(r"[^A-Za-z0-9_-]", "", qp.get("c", ""))[:64] or "anonimo",
                               {"fonte": qp.get("utm_source", "")[:40]})
        except Exception:
            pass
        return HTMLResponse(pagina(qp.get("c", ""), qp.get("email", "")), headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/acquista/t/{nome}", methods=["GET"])
    async def acquista_testimonianza(request):
        nome = request.path_params.get("nome", "")
        p = CARTELLA_T / nome
        if not _IMG.match(nome) or not p.is_file():
            return Response(status_code=404)
        return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


PAGINA_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TaxScan · Paga meno tasse con il tuo agente IA · 47 € per 12 mesi</title>
<meta name="description" content="Per partite IVA in regime forfettario: l'agente IA di TaxScan legge le tue fatture e trova dove puoi pagare meno, in regola. 47 € per 12 mesi, con garanzia risparmio doppio.">
<link rel="icon" href="/favicon.ico?v=2" sizes="any"><link rel="icon" type="image/png" sizes="48x48" href="/favicon-48.png?v=2"><link rel="apple-touch-icon" href="/apple-touch-icon.png?v=2">
<style>
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{color-scheme:light;--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --bg:#eef2f8;--surface:#fff;--line:#d8e2ed;--ink:#122452;--ink2:#3d4a73;--accent:#4355cc;--accent-ink:#4355cc;--soft:#e8ebfa;--scan:#05c4b8;--ok:#087a63}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0a1330;--surface:#122452;--line:#25397a;--ink:#fff;--ink2:#c9d3ec;--accent:#5566dd;--accent-ink:#a6b4ff;--soft:#1c3070;--scan:#05d5c8;--ok:#5fe0c5}}
*{box-sizing:border-box;margin:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--f-txt);padding:0 16px 48px}
h1,h2,h3,.logo{font-family:var(--f-tit);letter-spacing:-.02em}
a{color:var(--accent-ink)}
.pg{max-width:1040px;margin:0 auto}
.top{display:flex;align-items:center;justify-content:space-between;padding:20px 0 8px}
.logo{font-family:"Poppins",sans-serif;font-weight:700;font-size:22px;text-decoration:none;color:var(--ink)}.logo span{color:#4355cc}
@media (prefers-color-scheme:dark){.logo span{color:#a6b4ff}}
.top a.ent{font-size:14px;font-weight:600;text-decoration:none}
.hero{display:grid;gap:28px;padding:28px 0 12px;align-items:start}
@media (min-width:880px){.hero{grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);padding-top:44px}}
.eye{display:inline-block;font-size:13px;font-weight:600;color:var(--accent-ink);background:var(--soft);border-radius:99px;padding:4px 12px;margin-bottom:14px}
h1{font-size:clamp(30px,5.2vw,46px);line-height:1.08;margin-bottom:16px}
h1 em{font-style:normal;color:var(--accent-ink)}
.lead{font-size:clamp(16px,2.2vw,18px);color:var(--ink2);margin-bottom:18px;max-width:34em}
.punti{list-style:none;padding:0;display:grid;gap:10px;margin-bottom:22px}
.punti li{display:flex;gap:10px;align-items:flex-start}
.punti svg{flex:none;margin-top:3px}
.prezzo{background:var(--surface);border:1px solid var(--line);border-radius:22px;padding:26px 24px;box-shadow:0 18px 40px rgba(18,36,82,.08)}
.prezzo .cosa{font-size:14px;font-weight:600;color:var(--ink2)}
.cifra{display:flex;align-items:baseline;gap:8px;margin:6px 0 2px}
.cifra b{font-family:var(--f-tit);font-size:56px;line-height:1;letter-spacing:-.03em}
.cifra span{font-size:16px;color:var(--ink2)}
.mese{font-size:14px;color:var(--ink2);margin-bottom:18px}
.cta{display:block;text-align:center;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;font-size:18px;padding:16px 18px;border-radius:14px;transition:transform .15s ease,box-shadow .15s ease,background .15s ease}
@media (max-width:420px){.cta{font-size:17px;padding:15px 14px}}
.cta:hover{background:#3646bd;transform:translateY(-1px);box-shadow:0 8px 20px rgba(67,85,204,.28)}
.cta:active{background:#2b3aa6;transform:none;box-shadow:none}
.cta:focus-visible,.sec:focus-visible,details summary:focus-visible{outline:3px solid #05d5c8;outline-offset:3px}
.nota{font-size:13px;color:var(--ink2);text-align:center;margin-top:10px}
.gar{display:flex;gap:12px;align-items:flex-start;margin-top:18px;padding:14px;border-radius:14px;background:var(--soft)}
.gar svg{flex:none}
.gar p{font-size:14px}
.sec{display:inline-block;margin-top:14px;font-weight:600;font-size:15px}
.incl{border-top:1px solid var(--line);margin-top:18px;padding-top:14px;font-size:14px;color:var(--ink2)}
.incl li{margin:4px 0 0 18px}
.sez{padding:44px 0 0}
.sez h2{font-size:clamp(24px,3.6vw,32px);line-height:1.15;margin-bottom:10px}
.lead2{color:var(--ink2);font-size:16px;max-width:40em;margin-bottom:22px}
.vid{position:relative;aspect-ratio:16/9;border-radius:18px;overflow:hidden;background:#0a1330;box-shadow:0 18px 40px rgba(18,36,82,.12)}
.vid iframe,.vid video{position:absolute;inset:0;width:100%;height:100%;border:0}
.cap{display:grid;gap:8px;margin:18px 0 0;padding-left:22px;color:var(--ink2)}
@media (min-width:760px){.cap{grid-template-columns:1fr 1fr;column-gap:28px}}
.passi{display:grid;gap:14px;counter-reset:p}
@media (min-width:760px){.passi{grid-template-columns:repeat(3,minmax(0,1fr))}}
.passo,.card{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:20px}
.passo h3,.card h3{font-size:18px;margin-bottom:6px}
.passo p,.card p{color:var(--ink2);font-size:14.5px}
.passo .n{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;margin-bottom:10px}
.griglia{display:grid;gap:14px}
@media (min-width:760px){.griglia{grid-template-columns:repeat(2,minmax(0,1fr))}}
.card .ic{width:44px;height:44px;border-radius:12px;background:var(--soft);display:grid;place-items:center;margin-bottom:10px}
.gratis{margin-top:14px;font-size:14px;color:var(--ink2)}
.gbox{display:grid;gap:18px;align-items:center;background:var(--surface);border:2px solid var(--scan);border-radius:22px;padding:24px}
@media (min-width:760px){.gbox{grid-template-columns:auto 1fr}}
.gbox h2{margin-bottom:8px}
.gbox p{color:var(--ink2);margin-top:6px}
.tst{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}
.tst figure{margin:0;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:8px}
.tst img{display:block;width:100%;height:auto;border-radius:10px}
.faq{display:grid;gap:10px}
details{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:0 18px}
summary{cursor:pointer;font-weight:600;padding:16px 0;list-style:none;display:flex;justify-content:space-between;gap:12px}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";font-size:20px;line-height:1;color:var(--accent-ink)}
details[open] summary::after{content:"–"}
details p{color:var(--ink2);padding:0 0 16px}
.fine{margin-top:48px;text-align:center;background:var(--surface);border:1px solid var(--line);border-radius:22px;padding:32px 20px}
.fine h2{font-size:clamp(24px,3.6vw,32px);margin-bottom:8px}
.fine p{color:var(--ink2);margin-bottom:18px}
.fine .cta{max-width:420px;margin:0 auto}
.legal{font-size:12.5px;color:var(--ink2);text-align:center;margin-top:28px;line-height:1.6}
.legal a{color:inherit;font-weight:600}
</style>
</head>
<body>
<div class="pg">
<header class="top"><a class="logo" href="/">Tax<span>Scan</span></a><a class="ent" href="/prova">Entra</a></header>

<main>
<section class="hero" aria-labelledby="t-hero">
  <div>
    <span class="eye">Per partite IVA in regime forfettario</span>
    <h1 id="t-hero">Paga meno tasse, <em>in regola</em>. Te lo trova il tuo agente IA.</h1>
    <p class="lead">TaxScan legge le tue fatture, capisce che lavoro fai davvero e ti mostra dove puoi pagare meno: attività con coefficienti diversi, riduzioni dei contributi, acconti giusti. In euro, non in teoria.</p>
    <ul class="punti">
      <li><svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10" fill="#05c4b8"/><path d="M5.5 10.3l3 3 6-6.3" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span><b>Il tuo risparmio, calcolato sulle tue fatture</b>, con il ragionamento spiegato passo per passo.</span></li>
      <li><svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10" fill="#05c4b8"/><path d="M5.5 10.3l3 3 6-6.3" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span><b>Un report con il tuo nome</b>, da tenere o da mostrare al commercialista.</span></li>
      <li><svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10" fill="#05c4b8"/><path d="M5.5 10.3l3 3 6-6.3" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span><b>I passi da fare, uno alla volta</b>: ti accompagna l'agente, senza gergo.</span></li>
    </ul>
    {{VAI_VIDEO}}
  </div>
  <aside class="prezzo" aria-label="Prezzo">
    <p class="cosa">Ottimizzazione fiscale + report · 12 mesi</p>
    <p class="cifra"><b>47 €</b><span>per 12 mesi</span></p>
    <p class="mese">Meno di 4 € al mese. Un solo pagamento.</p>
    <a class="cta" href="{{LINK}}">{{PULSANTE}}</a>
    <p class="nota">{{NOTA}}</p>
    <div class="gar">
      <svg width="36" height="36" viewBox="0 0 36 36" aria-hidden="true"><path d="M18 3l12 4.5v9c0 7.6-5.1 13.6-12 16.5C11.1 30.1 6 24.1 6 16.5v-9L18 3z" fill="#e6faf7" stroke="#05c4b8" stroke-width="2.2" stroke-linejoin="round"/><path d="M12.5 18l3.8 3.8 7.2-7.6" fill="none" stroke="#087a63" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <p><b>Garanzia risparmio doppio.</b> Se TaxScan non ti trova un risparmio di almeno 94 € (il doppio del prezzo), ti rimborsiamo tutto.</p>
    </div>
    <ul class="incl"><li>Ottimizzazione fiscale con l'agente IA</li><li>Report personale in PDF</li><li>Passi da fare guidati e fatture riscritte</li></ul>
  </aside>
</section>

{{VIDEO}}

<section class="sez" aria-labelledby="t-come"><h2 id="t-come">Come funziona</h2>
  <p class="lead2">Non devi sapere niente di tasse: le domande sono poche e si risponde con un tocco.</p>
  <div class="passi">
    <div class="passo"><span class="n">1</span><h3>Due minuti di domande</h3><p>Oppure carica il certificato della partita IVA: codice ATECO e data di apertura li legge l'agente.</p></div>
    <div class="passo"><span class="n">2</span><h3>Carica 2 o 3 fatture</h3><p>L'agente capisce che lavoro fai davvero e quali parti il fisco tassa meno. Del cliente non conserva il nome.</p></div>
    <div class="passo"><span class="n">3</span><h3>Il risparmio, il report, i passi</h3><p>Vedi quanto paghi oggi e quanto puoi pagare, scarichi il report e segui i passi in ordine.</p></div>
  </div>
</section>

<section class="sez" aria-labelledby="t-cosa"><h2 id="t-cosa">Cosa sblocchi con 47 €</h2>
  <div class="griglia">
    <div class="card"><div class="ic"><svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18l5-5 4 4 7-8" fill="none" stroke="#4355cc" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></div><h3>Ottimizzazione fiscale</h3><p>L'agente IA analizza le tue fatture, trova le attività con un coefficiente più basso e ti mostra il risparmio in euro, con il calcolo completo.</p></div>
    <div class="card"><div class="ic"><svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v13H7z" fill="none" stroke="#4355cc" stroke-width="2" stroke-linejoin="round"/><path d="M10 13h6M10 17h4" stroke="#05c4b8" stroke-width="2" stroke-linecap="round"/></svg></div><h3>Il tuo report in PDF</h3><p>Con il tuo nome e la tua situazione: cosa ha visto l'agente, come rifare la fattura, quanto cambia. Lo ricevi anche via email.</p></div>
    <div class="card"><div class="ic"><svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14M5 12h14M5 18h9" stroke="#4355cc" stroke-width="2.2" stroke-linecap="round"/></svg></div><h3>I passi da fare, guidati</h3><p>In «Da fare» trovi cosa fare in ordine di importanza, con il pulsante Inizia: l'agente ti accompagna in ogni passaggio.</p></div>
    <div class="card"><div class="ic"><svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16v11H4z" fill="none" stroke="#4355cc" stroke-width="2" stroke-linejoin="round"/><path d="M4 7l8 6 8-6" fill="none" stroke="#05c4b8" stroke-width="2" stroke-linejoin="round"/></svg></div><h3>12 mesi di analisi</h3><p>Ogni nuova fattura, una nuova verifica: se il tuo lavoro cambia, l'agente rifà i conti e te lo dice.</p></div>
  </div>
  <p class="gratis">Restano gratis per tutti: il questionario, la Panoramica con le scadenze e quanto mettere da parte.</p>
</section>

<section class="sez" aria-labelledby="t-gar">
  <div class="gbox">
    <svg width="72" height="72" viewBox="0 0 36 36" aria-hidden="true"><path d="M18 3l12 4.5v9c0 7.6-5.1 13.6-12 16.5C11.1 30.1 6 24.1 6 16.5v-9L18 3z" fill="#e6faf7" stroke="#05c4b8" stroke-width="2" stroke-linejoin="round"/><path d="M12.5 18l3.8 3.8 7.2-7.6" fill="none" stroke="#087a63" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <div><h2 id="t-gar">Garanzia «risparmio doppio»</h2>
      <p>Se entro 12 mesi dall'acquisto l'Ottimizzazione fiscale di TaxScan non ti trova un risparmio di almeno <b>94 €</b>, cioè il doppio di quello che paghi, scrivici: ti rimborsiamo tutti i 47 €.</p>
      <p>Guardiamo insieme il risparmio calcolato nella tua Ottimizzazione fiscale, senza domande complicate.</p></div>
  </div>
</section>

{{TESTIMONIANZE}}

<section class="sez" aria-labelledby="t-faq"><h2 id="t-faq">Domande frequenti</h2>
  <div class="faq">
    <details><summary>Serve ancora il commercialista?</summary><p>TaxScan prepara e spiega: puoi gestire tutto da solo, assumendoti la responsabilità di quello che dichiari, oppure far controllare i numeri a un professionista quando vuoi. Il controllo è facoltativo.</p></details>
    <details><summary>È tutto in regola?</summary><p>Sì: l'agente usa solo quello che la legge prevede per il forfettario, come i coefficienti diversi per attività diverse e le riduzioni dei contributi. Non inventa spese e non ti fa dichiarare lavori che non fai. Le cifre sono stime e ogni passo è spiegato.</p></details>
    <details><summary>Cosa resta gratis?</summary><p>Il questionario, la Panoramica con le scadenze, quanto mettere da parte e il tuo profilo. Con i 47 € sblocchi l'Ottimizzazione fiscale, il report e i passi guidati.</p></details>
    <details><summary>Come funziona la garanzia?</summary><p>Se entro 12 mesi dall'acquisto l'Ottimizzazione fiscale non ti trova un risparmio di almeno 94 €, ci scrivi e ti restituiamo l'intero importo.</p></details>
    <details><summary>E i miei dati?</summary><p>Usiamo i tuoi dati solo per i calcoli. Delle fatture leggiamo le righe del lavoro e il tipo di cliente, non conserviamo il nome dei clienti né i file. I dettagli sono nella <a href="/privacy">privacy policy</a>.</p></details>
    <details><summary>Quanto dura?</summary><p>12 mesi dal giorno dell'acquisto. Prima della scadenza ti scriviamo: decidi tu se continuare.</p></details>
  </div>
</section>

<section class="fine" aria-labelledby="t-fine">
  <h2 id="t-fine">Scopri quanto puoi pagare in meno</h2>
  <p>47 € per 12 mesi, con la garanzia del risparmio doppio.</p>
  <a class="cta" href="{{LINK}}">{{PULSANTE}}</a>
  <p class="nota">{{NOTA}}</p>
</section>
</main>

<p class="legal">TaxScan prepara e spiega: le cifre sono stime e la responsabilità di ciò che dichiari è tua; se vuoi, le fai controllare a un professionista.<br>
<a href="/termini">Termini e condizioni</a> · <a href="/privacy">Privacy policy</a> · TaxScan è un servizio offerto da LTD24</p>
</div>
</body>
</html>
"""
