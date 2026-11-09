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
                 '<section class="sez" id="video" aria-labelledby="t-video"><div class="w"><h2 id="t-video">Guarda come funziona, dall\'inizio alla fine</h2>'
                 '<p class="sotto">In 20 minuti vedi l\'agente IA al lavoro su una situazione vera: cosa legge, come ragiona e dove trova il risparmio.</p>'
                 f'<div class="vid">{video}</div>'
                 '<ol class="cap"><li><b>Cos\'è un agente IA</b> e cosa fa per una partita IVA forfettaria</li>'
                 '<li><b>Il questionario</b>: due minuti, o il certificato della partita IVA</li>'
                 '<li><b>Le fatture</b>: come capisce che lavoro fai davvero</li>'
                 '<li><b>Il risparmio</b>: attività con coefficienti diversi, fatture divise bene</li>'
                 '<li><b>I contributi INPS</b>: le riduzioni che spesso nessuno ti dice</li>'
                 '<li><b>Scadenze e acconti</b>: quanto mettere da parte, mese per mese</li>'
                 '<li><b>Il report e i passi da fare</b>, uno alla volta</li></ol></div></section>')
    sez_t = ("" if not t else
             '<section class="sez" id="dicono" aria-labelledby="t-dicono"><div class="w"><h2 id="t-dicono">Cosa ci scrivono le prime partite IVA</h2>'
             '<p class="sotto">Messaggi veri, pubblicati con il permesso di chi li ha scritti.</p><div class="tst">'
             + "".join(f'<figure><img src="/acquista/t/{_e(n)}" alt="Messaggio di una persona che usa TaxScan" loading="lazy"></figure>' for n in t)
             + '</div></div></section>')
    pulsante = ('Attiva TaxScan a 47 €' if attivo else 'Inizia gratis e scopri il tuo risparmio')
    nota = ('Pagamento sicuro con Stripe · ricevuta via email' if attivo else
            'Il pagamento online arriva a breve: intanto puoi iniziare gratis')
    return (PAGINA_HTML.replace("{{LINK}}", _e(link)).replace("{{PULSANTE}}", pulsante).replace("{{NOTA}}", nota)
            .replace("{{VIDEO}}", sez_video).replace("{{TESTIMONIANZE}}", sez_t)
            .replace("{{VAI_VIDEO}}", '<a class="video-link" href="#video"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M10 8.5v7l6-3.5z" fill="currentColor"/></svg>Guarda il video (20 min)</a>' if video else "")
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

    @mcp.custom_route("/font-s/{nome}", methods=["GET"])
    async def font_serif(request):
        """Il corsivo elegante della home (Lora Italic, licenza OFL), servito dal nostro sito: niente Google Fonts."""
        nome = request.path_params.get("nome", "")
        p = Path(__file__).resolve().parent / "static" / "fonts" / "Lora-Italic.woff"
        if nome != "Lora-Italic.woff" or not p.is_file():
            return Response(status_code=404)
        return FileResponse(p, media_type="font/woff", headers={"Cache-Control": "public, max-age=2592000"})

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
<meta name="description" content="Per partite IVA in regime forfettario: l'agente IA di TaxScan legge le tue fatture e trova dove puoi pagare meno, in regola. Offerta di lancio: 12 mesi a 47 € invece di 589 €, soddisfatto o rimborsato.">
<link rel="icon" href="/favicon.ico?v=2" sizes="any"><link rel="icon" type="image/png" sizes="48x48" href="/favicon-48.png?v=2"><link rel="apple-touch-icon" href="/apple-touch-icon.png?v=2">
<style>
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{color-scheme:light;
  --f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --bg:#f7f8fb;--surface:#fff;--ink:#122452;--ink2:#465275;--mute:#5d6787;--line:rgba(18,36,82,.11);--line2:rgba(18,36,82,.2);
  --accent:#4355cc;--accent-h:#3646bd;--accent-ink:#4355cc;--scan:#05c4b8;--scan-ink:#076b57;--scan-soft:#e3f8f5;--lav:#e8ebfa;--navy:#122452;--carta:#fffdf8}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0a1330;--surface:#101d47;--ink:#fff;--ink2:#cdd6ee;--mute:#a3afd2;--line:rgba(255,255,255,.11);--line2:rgba(255,255,255,.22);
  --accent:#4355cc;--accent-h:#3a4bc0;--accent-ink:#b3bfff;--scan-ink:#6fe8db;--scan-soft:#0d3a45;--lav:#1c3070;--navy:#0d1a42;--carta:#fffdf8}}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font:16px/1.6 var(--f-txt);-webkit-font-smoothing:antialiased;overflow-x:hidden}
::selection{background:var(--accent);color:#fff}
a{color:var(--accent-ink)}
:focus-visible{outline:3px solid var(--scan);outline-offset:3px;border-radius:6px}
.w{max-width:1160px;margin:0 auto;padding:0 20px}
h1,h2,h3{font-family:var(--f-tit);font-weight:750;letter-spacing:-.025em;line-height:1.06;text-wrap:balance}
.num{font-variant-numeric:tabular-nums}
.logo{font-family:"Poppins",var(--f-tit);font-weight:700;font-size:22px;line-height:1;text-decoration:none;color:var(--ink)}
.logo span{color:var(--accent-ink)}

.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:54px;padding:14px 24px;border-radius:12px;font-weight:700;font-size:17px;text-decoration:none;transition:transform .18s ease,box-shadow .18s ease,background .18s ease}
.btn svg{width:18px;height:18px;flex:none}
.btn-acc{background:var(--accent);color:#fff;box-shadow:0 4px 0 var(--navy)}
.btn-acc:hover{background:var(--accent-h);transform:translateY(-2px);box-shadow:0 6px 0 var(--navy)}
.btn-acc:active{transform:none;box-shadow:0 2px 0 var(--navy)}
.btn-light{background:var(--surface);color:var(--ink);border:1px solid var(--line2);min-height:50px;font-size:16px}
.btn-light:hover{box-shadow:0 8px 20px rgba(18,36,82,.08)}

.top .w{display:flex;align-items:center;justify-content:space-between;height:68px}
.top nav{display:flex;align-items:center;gap:6px;font-size:14px;font-weight:600}
.top nav a{color:var(--ink2);text-decoration:none;padding:8px 12px;border-radius:9px}
.top nav a:hover{background:var(--lav);color:var(--ink)}

/* apertura: messaggio a sinistra, scontrino a destra */
.hero .w{display:grid;grid-template-areas:"t" "s" "p";gap:32px;padding-top:28px;padding-bottom:20px;align-items:start}
.hero .testo{grid-area:t}.hero .punti{grid-area:p;margin-top:0}
.hero h1{font-size:clamp(38px,6.4vw,76px);letter-spacing:-.035em;line-height:1}
.hero h1 b{color:var(--accent-ink);font-weight:inherit}
.lead{margin-top:20px;max-width:34em;font-size:clamp(16.5px,1.8vw,19px);color:var(--ink2)}
.punti{list-style:none;display:grid;gap:12px;margin-top:26px;max-width:34em}
.punti li{display:flex;gap:12px;align-items:flex-start;color:var(--ink2)}
.punti li b{color:var(--ink);font-weight:600}
.punti svg{flex:none;width:22px;height:22px;margin-top:2px;color:var(--scan)}
.video-link{display:inline-flex;align-items:center;gap:8px;margin-top:24px;font-weight:600;text-decoration:none}
.video-link svg{width:22px;height:22px}

.scontrino{grid-area:s;position:relative;max-width:440px;width:100%;justify-self:center;margin-bottom:10px;color:#122452;filter:drop-shadow(0 24px 40px rgba(18,36,82,.14)) drop-shadow(0 2px 3px rgba(18,36,82,.08))}
.foglio{position:relative;overflow:hidden;background:var(--carta);padding:28px 26px 26px;border-radius:6px 6px 0 0}
.scontrino::after{content:"";position:absolute;left:0;right:0;bottom:-9px;height:10px;background:linear-gradient(135deg,var(--carta) 50%,transparent 50%) 0 0/16px 10px repeat-x,linear-gradient(-135deg,var(--carta) 50%,transparent 50%) 0 0/16px 10px repeat-x}
.testa{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:16px;border-bottom:1.5px dashed rgba(18,36,82,.25)}
.testa .logo{font-size:20px;color:#122452}.testa .logo span{color:#4355cc}
.testa small{font-size:12.5px;font-weight:600;color:#076b57;background:#e3f8f5;border-radius:99px;padding:3px 10px}
.voci{list-style:none;display:grid;gap:11px;padding:18px 0;border-bottom:1.5px dashed rgba(18,36,82,.25);font-size:15px}
.voci li{display:flex;justify-content:space-between;gap:12px}
.voci li span:last-child{color:#076b57;font-weight:700;white-space:nowrap}
.conti{display:grid;gap:6px;padding:16px 0 4px;font-size:15px;color:#465275}
.conti p{display:flex;justify-content:space-between;gap:12px}
.conti s{color:#5d6787}
.conti .sconto span:last-child{color:#076b57;font-weight:700}
.totale{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin-top:10px;padding-top:14px;border-top:2px solid #122452}
.totale span{font-weight:700;font-size:15px;padding-bottom:8px}
.totale b{font-family:var(--f-tit);font-size:64px;font-weight:800;letter-spacing:-.035em;line-height:.9}
.mese{margin-top:8px;font-size:13.5px;color:#465275}
.scontrino .btn{display:flex;width:100%;margin-top:22px}
.nota{margin-top:12px;text-align:center;font-size:13px;color:#465275}
.firma{display:flex;gap:10px;align-items:flex-start;margin-top:18px;padding-top:16px;border-top:1.5px dashed rgba(18,36,82,.25);font-size:13.5px;color:#2d3a63}
.firma svg{flex:none;width:26px;height:26px}
/* la scansione: una sola volta, all'apertura */
.raggio{position:absolute;left:0;right:0;top:-20%;height:18%;pointer-events:none;background:linear-gradient(rgba(5,196,184,0),rgba(5,196,184,.22));border-bottom:2px solid #05c4b8;animation:scan 1.6s cubic-bezier(.22,1,.36,1) .35s both}
@keyframes scan{from{transform:translateY(0);opacity:1}85%{opacity:1}to{transform:translateY(640%);opacity:0}}

/* sezioni */
.sez{padding:clamp(72px,9vw,120px) 0 0}
.sez h2{font-size:clamp(32px,4.6vw,56px);letter-spacing:-.03em;max-width:16em}
.sez .sotto{margin-top:16px;max-width:38em;font-size:18px;color:var(--ink2)}

.cosa{display:grid;gap:0;margin-top:44px;border-top:1px solid var(--line)}
.cosa article{display:grid;gap:8px;padding:26px 0;border-bottom:1px solid var(--line)}
.cosa h3{font-size:clamp(21px,2.2vw,26px);letter-spacing:-.02em}
.cosa p{color:var(--ink2);max-width:36em}
.gratis{margin-top:22px;font-size:15px;color:var(--mute)}

.passi{list-style:none;display:grid;gap:28px;margin-top:44px;counter-reset:p}
.passi li{counter-increment:p;position:relative;padding-top:58px}
.passi li::before{content:counter(p);position:absolute;top:0;left:0;display:grid;place-items:center;width:42px;height:42px;border-radius:50%;background:var(--navy);color:#fff;font-family:var(--f-tit);font-weight:800;font-size:18px}
.passi h3{font-size:22px;letter-spacing:-.02em}
.passi p{margin-top:8px;color:var(--ink2)}

.garanzia{margin-top:clamp(72px,9vw,120px);background:var(--navy);color:#fff}
.garanzia .w{display:grid;gap:36px;padding-top:clamp(56px,7vw,96px);padding-bottom:clamp(56px,7vw,96px);align-items:center}
.garanzia h2{font-size:clamp(34px,4.8vw,60px);letter-spacing:-.03em;max-width:13em}
.garanzia p{margin-top:16px;max-width:34em;font-size:18px;color:#d3dbf2}
.conto{display:grid;grid-template-columns:auto 1fr;gap:10px 18px;align-items:baseline;background:#1b2f66;border-radius:22px;padding:28px}
.conto b{font-family:var(--f-tit);font-size:clamp(38px,5vw,54px);font-weight:800;letter-spacing:-.03em;line-height:1;text-align:right}
.conto span{color:#d3dbf2}
.conto b.oro{color:#f6c25a}
.conto .ver{grid-column:1/-1;margin-top:8px;padding-top:16px;border-top:1px solid rgba(255,255,255,.16);color:#fff;font-weight:600}

.vid{position:relative;aspect-ratio:16/9;margin-top:36px;border-radius:20px;overflow:hidden;background:#0a1330;box-shadow:0 24px 50px rgba(18,36,82,.16)}
.vid iframe,.vid video{position:absolute;inset:0;width:100%;height:100%;border:0}
.cap{display:grid;gap:10px;margin-top:22px;padding-left:22px;color:var(--ink2)}
.tst{display:grid;gap:16px;margin-top:36px}
.tst figure{border-radius:18px;overflow:hidden;border:1px solid var(--line);background:var(--surface)}
.tst img{display:block;width:100%;height:auto}

.faq{margin-top:36px;border-top:1px solid var(--line);max-width:820px}
.faq details{border-bottom:1px solid var(--line)}
.faq summary{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:20px 0;font-family:var(--f-tit);font-size:19px;font-weight:700;letter-spacing:-.015em;cursor:pointer;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq summary svg{width:20px;height:20px;flex:none;transition:transform .25s}
.faq details[open] summary svg{transform:rotate(180deg)}
.faq p{padding:0 0 20px;max-width:40em;color:var(--ink2)}

.fine{text-align:center;padding:clamp(72px,9vw,120px) 0 clamp(56px,7vw,88px)}
.fine h2{font-size:clamp(34px,5vw,62px);letter-spacing:-.03em;max-width:14em;margin:0 auto}
.fine p{margin:16px auto 0;max-width:34em;font-size:18px;color:var(--ink2)}
.fine .btn{margin-top:30px}
.fine .nota{color:var(--mute);font-size:13.5px;margin-top:14px}

.piede{border-top:1px solid var(--line);background:var(--surface)}
.piede .w{display:grid;gap:12px;padding-top:28px;padding-bottom:32px;font-size:13px;color:var(--mute)}
.piede a{color:var(--ink2)}

@media (min-width:720px){
  .passi{grid-template-columns:repeat(3,minmax(0,1fr));gap:36px}
  .cosa{grid-template-columns:1fr 1fr;column-gap:48px}
  .tst{grid-template-columns:repeat(3,minmax(0,1fr))}
  .cap{grid-template-columns:1fr 1fr;column-gap:32px}
}
@media (min-width:940px){
  .w{padding:0 32px}
  .hero .w{grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);grid-template-areas:"t s" "p s";grid-template-rows:auto 1fr;gap:28px 56px;padding-top:56px}
  .scontrino{justify-self:end;margin-top:8px}
  .garanzia .w{grid-template-columns:1.1fr .9fr;gap:64px}
}
@media (max-width:420px){.foglio{padding:24px 20px 28px}.totale b{font-size:56px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.raggio{display:none}*{transition-duration:.01ms!important}}
</style>
</head>
<body>
<header class="top">
  <div class="w">
    <a class="logo" href="/">Tax<span>Scan</span></a>
    <nav aria-label="Navigazione"><a href="/">Home</a><a href="/accedi">Accedi</a></nav>
  </div>
</header>

<main>
<section class="hero" aria-labelledby="t-hero">
  <div class="w">
    <div class="testo">
      <h1 id="t-hero">Paga meno tasse, in regola. <b>Te lo trova il tuo agente IA.</b></h1>
      <p class="lead">Per chi ha la partita IVA in regime forfettario. TaxScan legge le tue fatture, capisce che lavoro fai davvero e ti mostra dove puoi pagare meno: attività con coefficienti diversi, riduzioni dei contributi, acconti giusti. In euro, non in teoria.</p>
      {{VAI_VIDEO}}
    </div>
      <ul class="punti">
        <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke-width="2"/><path d="m7.5 12.3 3 3 6-6.3"/></svg><span><b>Il risparmio calcolato sulle tue fatture</b>, con il ragionamento spiegato passo per passo.</span></li>
        <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke-width="2"/><path d="m7.5 12.3 3 3 6-6.3"/></svg><span><b>Un report con il tuo nome</b>, da tenere o da mostrare al commercialista.</span></li>
        <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke-width="2"/><path d="m7.5 12.3 3 3 6-6.3"/></svg><span><b>I passi da fare, uno alla volta</b>, con l'agente che ti accompagna senza gergo.</span></li>
      </ul>

    <aside class="scontrino" aria-label="Riepilogo dell'acquisto">
      <div class="foglio">
        <div class="raggio" aria-hidden="true"></div>
        <div class="testa"><span class="logo">Tax<span>Scan</span></span><small>Offerta di lancio</small></div>
        <ul class="voci">
          <li><span>Ottimizzazione fiscale con l'agente IA</span><span>incluso</span></li>
          <li><span>Report personale in PDF</span><span>incluso</span></li>
          <li><span>Da fare: passi guidati e fatture riscritte</span><span>incluso</span></li>
          <li><span>Bandi e agevolazioni</span><span>incluso</span></li>
          <li><span>Durata</span><span class="num">12 mesi</span></li>
        </ul>
        <div class="conti num">
          <p><span>Prezzo pieno</span><s>589,00 €</s></p>
          <p class="sconto"><span>Offerta di lancio</span><span>−542,00 €</span></p>
        </div>
        <div class="totale"><span>Totale, una volta sola</span><b class="num">47 €</b></div>
        <p class="mese">Meno di 4 € al mese · nessun rinnovo automatico</p>
        <a class="btn btn-acc" href="{{LINK}}">{{PULSANTE}} <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
        <p class="nota">{{NOTA}}</p>
        <p class="firma"><svg viewBox="0 0 36 36" aria-hidden="true"><path d="M18 3l12 4.5v9c0 7.6-5.1 13.6-12 16.5C11.1 30.1 6 24.1 6 16.5v-9L18 3z" fill="#e3f8f5" stroke="#05c4b8" stroke-width="2.2" stroke-linejoin="round"/><path d="M12.5 18l3.8 3.8 7.2-7.6" fill="none" stroke="#076b57" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span><b>Soddisfatto o rimborsato.</b> Se non ottieni un risparmio fiscale almeno doppio rispetto al costo del software, ti rimborsiamo tutto e non paghi.</span></p>
      </div>
    </aside>
  </div>
</section>

<section class="sez" aria-labelledby="t-cosa">
  <div class="w">
    <h2 id="t-cosa">Cosa sblocchi con 47 €</h2>
    <p class="sotto">Le domande e la Panoramica restano gratis. Con TaxScan attivo l'agente guarda le tue fatture una per una e trova dove puoi pagare meno, poi ti accompagna a ottenerlo.</p>
    <div class="cosa">
      <article><h3>Ottimizzazione fiscale</h3><p>L'agente analizza le tue fatture, riconosce le attività con un coefficiente più basso e ti mostra il risparmio in euro, con il calcolo completo.</p></article>
      <article><h3>Il tuo report in PDF</h3><p>Con il tuo nome e la tua situazione: cosa ha visto l'agente, come rifare la fattura, quanto cambia. Lo ricevi anche via email.</p></article>
      <article><h3>Da fare, in ordine</h3><p>I passi per ottenere il risparmio, dal più importante, con il pulsante Inizia: l'agente ti accompagna in ogni passaggio.</p></article>
      <article><h3>Bandi e agevolazioni</h3><p>Gli incentivi adatti alla tua attività e alla tua regione, con requisiti e scadenze spiegati in chiaro.</p></article>
    </div>
    <p class="gratis">Sempre gratis per tutti: il questionario, la Panoramica con le scadenze, quanto mettere da parte e il profilo.</p>
  </div>
</section>

<section class="sez" aria-labelledby="t-come">
  <div class="w">
    <h2 id="t-come">Non devi sapere niente di tasse</h2>
    <p class="sotto">Le domande sono poche e si risponde con un tocco. Il resto lo legge l'agente.</p>
    <ol class="passi">
      <li><h3>Due minuti di domande</h3><p>Oppure carica il certificato della partita IVA: codice ATECO e data di apertura li legge l'agente.</p></li>
      <li><h3>Carica 2 o 3 fatture</h3><p>L'agente capisce che lavoro fai davvero e quali parti il fisco tassa meno. Non conserva i file né il nome dei clienti.</p></li>
      <li><h3>Risparmio, report, passi</h3><p>Vedi quanto paghi oggi e quanto puoi pagare, ricevi il report e segui i passi in ordine.</p></li>
    </ol>
  </div>
</section>

<section class="garanzia" aria-labelledby="t-gar">
  <div class="w">
    <div>
      <h2 id="t-gar">Se non risparmi almeno il doppio, non paghi.</h2>
      <p>Garanzia soddisfatto o rimborsato: se non ottieni un risparmio fiscale almeno doppio rispetto al costo del software, ti rimborsiamo tutto. Guardiamo insieme il risparmio calcolato nella tua Ottimizzazione fiscale, senza domande complicate.</p>
    </div>
    <div class="conto num" aria-label="Come funziona la garanzia, in numeri">
      <b>47 €</b><span>quello che paghi, una volta sola</span>
      <b class="oro">94 €</b><span>il risparmio minimo in 12 mesi</span>
      <p class="ver">Sotto i 94 €? Ci scrivi e ti restituiamo tutti i 47 €.</p>
    </div>
  </div>
</section>

{{VIDEO}}

{{TESTIMONIANZE}}

<section class="sez" aria-labelledby="t-faq">
  <div class="w">
    <h2 id="t-faq">Domande frequenti</h2>
    <div class="faq">
      <details><summary>Serve ancora il commercialista?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>TaxScan prepara e spiega: puoi gestire tutto da solo, assumendoti la responsabilità di quello che dichiari, oppure far controllare i numeri a un professionista quando vuoi. Il controllo è facoltativo.</p></details>
      <details><summary>È tutto in regola?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Sì: l'agente usa solo quello che la legge prevede per il forfettario, come i coefficienti diversi per attività diverse e le riduzioni dei contributi. Non inventa spese e non ti fa dichiarare lavori che non fai. Le cifre sono stime e ogni passo è spiegato.</p></details>
      <details><summary>Cosa resta gratis?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Il questionario, la Panoramica con le scadenze, quanto mettere da parte e il tuo profilo. Con i 47 € sblocchi il report dell'Ottimizzazione fiscale, Da fare con i passi guidati e Bandi e agevolazioni.</p></details>
      <details><summary>Come funziona la garanzia?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Garanzia soddisfatto o rimborsato: se non ottieni un risparmio fiscale almeno doppio rispetto al costo del software, ti rimborsiamo tutto e non paghi. Se nei 12 mesi il risparmio trovato è sotto i 94 € (il doppio dei 47 €), ci scrivi e ti restituiamo l'intero importo.</p></details>
      <details><summary>Perché 47 € invece di 589 €?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>È l'offerta di lancio per le prime partite IVA: 12 mesi di TaxScan a 47 € invece di 589 €. Il prezzo resta bloccato per tutti i 12 mesi.</p></details>
      <details><summary>Si rinnova da solo?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>No. È un solo pagamento che vale 12 mesi dal giorno dell'acquisto. Prima della scadenza ti scriviamo: decidi tu se continuare.</p></details>
      <details><summary>E i miei dati?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Usiamo i tuoi dati solo per i calcoli. Delle fatture leggiamo le righe del lavoro e il tipo di cliente, non conserviamo il nome dei clienti né i file. I dettagli sono nella <a href="/privacy">privacy policy</a>.</p></details>
    </div>
  </div>
</section>

<section class="fine" aria-labelledby="t-fine">
  <div class="w">
    <h2 id="t-fine">Scopri quanto puoi pagare in meno</h2>
    <p>12 mesi a 47 € invece di 589 €. Se non risparmi almeno il doppio, ti rimborsiamo tutto.</p>
    <a class="btn btn-acc" href="{{LINK}}">{{PULSANTE}} <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
    <p class="nota">{{NOTA}}</p>
  </div>
</section>
</main>

<footer class="piede">
  <div class="w">
    <p>TaxScan prepara e spiega: le cifre sono stime e la responsabilità di ciò che dichiari è tua; se vuoi, le fai controllare a un professionista.</p>
    <p><a href="/termini">Termini e condizioni</a> · <a href="/privacy">Privacy policy</a> · TaxScan è un servizio offerto da LTD24</p>
  </div>
</footer>
</body>
</html>
"""
