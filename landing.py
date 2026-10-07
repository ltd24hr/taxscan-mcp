"""TaxScan - pagina iniziale (/): un solo messaggio, un solo pulsante e una scena animata
(SVG + CSS dentro la pagina, nessun file esterno) che racconta cosa fa il servizio."""

PAGINA_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TaxScan - La tua partita IVA forfettaria sotto controllo</title>
<meta name="description" content="Scopri in 2 minuti quanto hai maturato di tasse, quando paghi e quanto mettere da parte.">
<style>
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{color-scheme:light;--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--bg:#eef2f8;--surface:#fff;--line:#d8e2ed;--ink:#122452;--ink2:#3d4a73;--accent:#4355cc;--accent-ink:#4355cc;--soft:#e8ebfa;
  --scena-alone:#dde4f6;--scena-linea:#c3cde6;--scena-bordo:#d8e2ed;--scena-ombra:rgba(18,36,82,.10);--scan:#05c4b8;--tratto:#c3cfe6}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0a1330;--surface:#122452;--line:#25397a;--ink:#fff;--ink2:#c9d3ec;--accent:#5566dd;--accent-ink:#a6b4ff;--soft:#1c3070;
  --scena-alone:#14285c;--scena-linea:#3a50a0;--scena-bordo:transparent;--scena-ombra:rgba(0,0,0,.28);--scan:#05d5c8;--tratto:#4a5f9e}}
*{box-sizing:border-box;margin:0}
h1,h2,h3,.logo{font-family:var(--f-tit)}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-txt);padding:24px 16px 40px}
.pg{max-width:560px;margin:0 auto}
.logo{font-weight:800;font-size:18px;letter-spacing:-.01em;margin-bottom:28px}
.logo span{color:#05d5c8}
h1{font-size:32px;line-height:1.12;letter-spacing:-.02em;margin-bottom:12px}
.lead{font-size:17px;color:var(--ink2);margin-bottom:18px}
.cta{display:block;text-align:center;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;font-size:18px;padding:16px;border-radius:14px;transition:transform .15s ease,box-shadow .15s ease}
.cta:hover{transform:translateY(-1px);box-shadow:0 8px 20px rgba(67,85,204,.28)}
.cta:active{transform:none;box-shadow:none}
.cta:focus-visible,.sub a:focus-visible,.by a:focus-visible{outline:3px solid #05d5c8;outline-offset:3px}
.sub{font-size:13px;color:var(--ink2);text-align:center;margin-top:10px}
.sub a{color:var(--accent-ink);font-weight:700}

/* ---- scena animata: il certificato viene letto e diventa tre risposte ---- */
.scena{margin-bottom:18px}
.scena svg{display:block;width:100%;height:auto}
.scena text{font-family:var(--f-txt)}
.sc-pop,.sc-timbro,.sc-moneta,.sc-livello{transform-box:fill-box;transform-origin:50% 50%}
.sc-livello{transform-origin:50% 100%}
.sc-raggio{opacity:0}
.sc-fantasma{opacity:0}
.sc-angoli{opacity:.4}
@media (prefers-reduced-motion:no-preference){
  .sc-raggio{animation:sc-raggio 9s linear infinite both}
  .sc-angoli{animation:sc-angoli 9s linear infinite both}
  .sc-cifra{animation:sc-cifra 9s linear infinite both}
  .sc-ateco{animation:sc-ateco 9s linear infinite both}
  .sc-riga{animation:sc-riga 9s linear infinite both}
  .sc-timbro{animation:sc-timbro 9s linear infinite both}
  .sc-filo{animation:sc-filo 9s linear infinite both}
  .sc-fantasma{animation:sc-fantasma 9s linear infinite both}
  .sc-pop{animation:sc-pop 9s linear infinite both}
  .sc-moneta{animation:sc-moneta 9s linear infinite both}
  .sc-livello{animation:sc-livello 9s linear infinite both}
  .sc-riga.sc-giu{animation-name:sc-riga-giu}
  .sc-pop.sc-t2{animation-name:sc-pop2}.sc-pop.sc-t3{animation-name:sc-pop3}
  .sc-fantasma.sc-t2{animation-name:sc-fantasma2}.sc-fantasma.sc-t3{animation-name:sc-fantasma3}
}
@keyframes sc-raggio{0%,4%{transform:translateY(-50px);opacity:0}6%{opacity:1}31%{opacity:1}33%,100%{transform:translateY(166px);opacity:0}}
@keyframes sc-angoli{0%,3%{opacity:.4}6%,32%{opacity:1}37%,100%{opacity:.4}}
@keyframes sc-cifra{0%,9%{fill:#dfe5f6}11%,93%{fill:#4355cc}97%,100%{fill:#dfe5f6}}
@keyframes sc-riga{0%,12%{fill:#dfe5f6}15%,93%{fill:#b9c4ee}97%,100%{fill:#dfe5f6}}
@keyframes sc-ateco{0%,17%{fill:#dfe5f6}20%,93%{fill:#05d5c8}97%,100%{fill:#dfe5f6}}
@keyframes sc-timbro{0%,23%{opacity:0;transform:scale(1.7) rotate(-18deg)}27%{opacity:1;transform:scale(.92) rotate(-8deg)}29%,93%{opacity:1;transform:scale(1) rotate(-8deg)}97%,100%{opacity:0;transform:scale(1) rotate(-8deg)}}
@keyframes sc-filo{0%,33%{opacity:0}38%,93%{opacity:1}97%,100%{opacity:0}}
@keyframes sc-riga-giu{0%,19%{fill:#dfe5f6}22%,93%{fill:#b9c4ee}97%,100%{fill:#dfe5f6}}
@keyframes sc-fantasma{0%,36%{opacity:1}42%,94%{opacity:0}99%,100%{opacity:1}}
@keyframes sc-fantasma2{0%,44%{opacity:1}50%,94%{opacity:0}99%,100%{opacity:1}}
@keyframes sc-fantasma3{0%,52%{opacity:1}58%,94%{opacity:0}99%,100%{opacity:1}}
@keyframes sc-pop{0%,36%{opacity:0;transform:scale(.72)}40%{opacity:1;transform:scale(1.05)}43%,93%{opacity:1;transform:scale(1)}97%,100%{opacity:0;transform:scale(.96)}}
@keyframes sc-pop2{0%,44%{opacity:0;transform:scale(.72)}48%{opacity:1;transform:scale(1.05)}51%,93%{opacity:1;transform:scale(1)}97%,100%{opacity:0;transform:scale(.96)}}
@keyframes sc-pop3{0%,52%{opacity:0;transform:scale(.72)}56%{opacity:1;transform:scale(1.05)}59%,93%{opacity:1;transform:scale(1)}97%,100%{opacity:0;transform:scale(.96)}}
@keyframes sc-moneta{0%,41%{opacity:0;transform:translateY(-14px)}46%{opacity:1;transform:translateY(1.5px)}48%,100%{opacity:1;transform:none}}
@keyframes sc-livello{0%,60%{transform:scaleY(.18)}74%,100%{transform:scaleY(1)}}

/* ---- i tre passi, ognuno con la sua icona ---- */
ul{list-style:none;padding:0;margin-top:28px}
li{display:flex;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:10px}
li b{display:block}
li span{font-size:14px;color:var(--ink2)}
.ico{flex:none;position:relative;width:52px;height:52px;border-radius:14px;background:var(--soft)}
.ico svg{display:block;width:100%;height:100%}
.ico i{position:absolute;left:-6px;top:-6px;width:21px;height:21px;border-radius:50%;background:var(--accent);color:#fff;font:700 11px/21px var(--f-txt);text-align:center;box-shadow:0 0 0 2px var(--surface)}
.ic-t{fill:none;stroke:var(--ink);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.ic-c{fill:var(--surface)}
.ic-r{fill:none;stroke:var(--accent-ink);stroke-width:2.2;stroke-linecap:round}
.ic-barra,.ic-punto{transform-box:fill-box;transform-origin:50% 100%}
.ic-punto{transform-origin:50% 50%}
.ic-spunta{stroke-dasharray:22;stroke-dashoffset:0}
@media (prefers-reduced-motion:no-preference){
  li.on .ic-luce{animation:ic-luce 1.5s ease-in-out both}
  li.on .ic-r{animation:ic-r .5s ease-out both}
  li.on .ic-r2{animation-delay:.18s}li.on .ic-r3{animation-delay:.36s}
  li.on .ic-barra{animation:ic-barra .55s cubic-bezier(.2,.9,.3,1.25) both}
  li.on .ic-b2{animation-delay:.14s}li.on .ic-b3{animation-delay:.28s}
  li.on .ic-soglia{animation:ic-soglia .5s ease-out .5s both}
  li.on .ic-spunta{animation:ic-spunta .45s ease-out .25s both}
  li.on .ic-punto{animation:ic-punto .5s cubic-bezier(.2,.9,.3,1.5) .65s both}
}
@keyframes ic-luce{0%{transform:translateY(-9px);opacity:0}15%{opacity:1}50%{transform:translateY(17px)}85%{opacity:1}100%{transform:translateY(-9px);opacity:0}}
@keyframes ic-r{from{stroke:var(--tratto)}to{stroke:var(--accent-ink)}}
@keyframes ic-barra{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes ic-soglia{from{opacity:0;stroke-dashoffset:14}to{opacity:1;stroke-dashoffset:0}}
@keyframes ic-spunta{from{stroke-dashoffset:22}to{stroke-dashoffset:0}}
@keyframes ic-punto{from{transform:scale(0)}to{transform:scale(1)}}
.ic-luce{opacity:0}

.by{font-size:12px;color:var(--ink2);margin-top:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}.by a{display:inline-flex;color:var(--ink);font-weight:700;text-decoration:none}.by img{height:20px;width:auto}
.foot{font-size:12px;color:var(--ink2);margin-top:24px;line-height:1.5}

/* schermi bassi (telefoni piccoli): il pulsante resta in alto, la scena scende sotto */
@media (max-width:899px) and (max-height:650px){
  .hero{display:flex;flex-direction:column}
  .azione{order:2}
  .scena{order:3;margin:22px 0 0}
}

@media (min-width:900px){
  body{padding:36px 32px 56px}
  .pg{max-width:1080px}
  .logo{font-size:20px;margin-bottom:44px}
  .hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.08fr);column-gap:56px}
  .txt{grid-column:1;grid-row:1;align-self:end}
  .azione{grid-column:1;grid-row:2;align-self:start}
  .scena{grid-column:2;grid-row:1 / span 2;align-self:center;margin-bottom:0}
  h1{font-size:50px;line-height:1.06;margin-bottom:18px}
  .lead{font-size:19px;margin-bottom:26px;max-width:30em}
  .cta{display:inline-block;padding:16px 44px}
  .sub{text-align:left}
  ul{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:56px}
  li{flex-direction:column;gap:16px;padding:22px;margin-bottom:0}
  li b{font-size:17px;margin-bottom:4px}
  .foot{max-width:64em}
}
</style>
</head>
<body>
<div class="pg">
<div class="logo">Tax<span>Scan</span></div>
<div class="hero">
<div class="txt">
<h1>La tua partita IVA forfettaria, sotto controllo.</h1>
<p class="lead">In 2 minuti scopri quanto hai maturato di tasse, quando paghi e quanto mettere da parte. Senza domande difficili.</p>
</div>
<div class="scena">
<svg viewBox="0 16 360 204" role="img" aria-label="Il certificato della partita IVA viene letto e diventa tre risposte: quanto hai maturato, quando paghi, quanto mettere da parte.">
<defs>
<linearGradient id="scLuce" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05d5c8" stop-opacity="0"/><stop offset="1" stop-color="#05d5c8" stop-opacity=".5"/></linearGradient>
<clipPath id="scFoglio"><path d="M0 8a8 8 0 0 1 8-8H94L118 24V152a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8Z"/></clipPath>
<clipPath id="scVaso"><path d="M9 13h18v2c3 1.5 4 4 4 7v8a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4v-8c0-3 1-5.5 4-7Z"/></clipPath>
</defs>
<circle cx="87" cy="118" r="86" style="fill:var(--scena-alone)"/>
<g class="sc-angoli" fill="none" stroke="#05d5c8" stroke-width="3" stroke-linecap="round">
<path d="M10 39V29a8 8 0 0 1 8-8H28"/><path d="M146 21H156a8 8 0 0 1 8 8V39"/><path d="M164 197V207a8 8 0 0 1-8 8H146"/><path d="M28 215H18a8 8 0 0 1-8-8V197"/>
</g>
<g transform="rotate(-4 87 118)"><g transform="translate(28 38)">
<path d="M0 8a8 8 0 0 1 8-8H94L118 24V152a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8Z" transform="translate(3 5)" style="fill:var(--scena-ombra)"/>
<path d="M0 8a8 8 0 0 1 8-8H94L118 24V152a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8Z" fill="#fff"/>
<path d="M94 0V16a8 8 0 0 0 8 8H118Z" fill="#c9d6ea"/>
<rect x="14" y="16" width="46" height="9" rx="4.5" fill="#122452"/>
<g fill="#4355cc">
<rect class="sc-cifra" x="14" y="36" width="6.6" height="10" rx="1.5"/><rect class="sc-cifra" x="22.2" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.03s"/><rect class="sc-cifra" x="30.4" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.06s"/><rect class="sc-cifra" x="38.6" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.09s"/><rect class="sc-cifra" x="46.8" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.12s"/><rect class="sc-cifra" x="55" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.15s"/><rect class="sc-cifra" x="63.2" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.18s"/><rect class="sc-cifra" x="71.4" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.21s"/><rect class="sc-cifra" x="79.6" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.24s"/><rect class="sc-cifra" x="87.8" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.27s"/><rect class="sc-cifra" x="96" y="36" width="6.6" height="10" rx="1.5" style="animation-delay:.3s"/>
</g>
<g fill="#b9c4ee">
<rect class="sc-riga" x="14" y="57" width="84" height="5" rx="2.5"/><rect class="sc-riga" x="14" y="67" width="60" height="5" rx="2.5" style="animation-delay:.12s"/>
<rect class="sc-riga sc-giu" x="14" y="112" width="52" height="5" rx="2.5"/><rect class="sc-riga sc-giu" x="14" y="122" width="38" height="5" rx="2.5" style="animation-delay:.1s"/><rect class="sc-riga sc-giu" x="14" y="132" width="46" height="5" rx="2.5" style="animation-delay:.2s"/>
</g>
<rect class="sc-ateco" x="14" y="84" width="62" height="16" rx="8" fill="#05d5c8"/>
<circle cx="23" cy="92" r="3" fill="#fff"/><rect x="30" y="89.5" width="36" height="5" rx="2.5" fill="#fff"/>
<g transform="translate(90 132)"><g class="sc-timbro" transform="rotate(-8)"><circle r="14" fill="#fff" stroke="#efac35" stroke-width="2.6"/><path d="M-6.5 .5l4.5 4.5 8.5-9.5" fill="none" stroke="#efac35" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></g></g>
<g clip-path="url(#scFoglio)"><g class="sc-raggio"><rect width="118" height="44" fill="url(#scLuce)"/><rect y="42.5" width="118" height="3" fill="#05d5c8"/></g></g>
</g></g>
<g class="sc-filo" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-dasharray=".1 6" style="stroke:var(--scan)">
<path d="M174 118C196 118 186 52 206 52"/><path d="M174 118H206"/><path d="M174 118C196 118 186 184 206 184"/>
</g>
<circle class="sc-filo" cx="172" cy="118" r="4.5" style="fill:var(--scan)"/>
<g fill="none" style="stroke:var(--scena-linea)" stroke-width="1.4" stroke-dasharray="3 5">
<rect class="sc-fantasma" x="206" y="26" width="142" height="52" rx="12"/><rect class="sc-fantasma sc-t2" x="206" y="92" width="142" height="52" rx="12"/><rect class="sc-fantasma sc-t3" x="206" y="158" width="142" height="52" rx="12"/>
</g>
<g transform="translate(206 26)"><g class="sc-pop">
<rect y="3" width="142" height="52" rx="12" style="fill:var(--scena-ombra)"/><rect width="142" height="52" rx="12" fill="#fff" style="stroke:var(--scena-bordo)"/>
<g transform="translate(10 8)">
<path d="M5 25v4.5a13 5.5 0 0 0 26 0V25Z" fill="#c98a1b"/><ellipse cx="18" cy="25" rx="13" ry="5.5" fill="#efac35"/>
<path d="M5 18.5v4.5a13 5.5 0 0 0 26 0v-4.5Z" fill="#c98a1b"/><ellipse cx="18" cy="18.5" rx="13" ry="5.5" fill="#efac35"/>
<g class="sc-moneta"><path d="M5 12v4.5a13 5.5 0 0 0 26 0V12Z" fill="#c98a1b"/><ellipse cx="18" cy="12" rx="13" ry="5.5" fill="#f6c25a"/></g>
</g>
<text x="56" y="24" font-size="13" font-weight="700" fill="#122452">Quanto</text><text x="56" y="39" font-size="9.5" fill="#3d4a73">hai maturato</text>
</g></g>
<g transform="translate(206 92)"><g class="sc-pop sc-t2">
<rect y="3" width="142" height="52" rx="12" style="fill:var(--scena-ombra)"/><rect width="142" height="52" rx="12" fill="#fff" style="stroke:var(--scena-bordo)"/>
<g transform="translate(10 8)">
<rect x="3" y="5" width="30" height="28" rx="6" fill="#e8ebfa"/><path d="M3 11a6 6 0 0 1 6-6h18a6 6 0 0 1 6 6v3H3Z" fill="#4355cc"/>
<rect x="10" y="2" width="3" height="7" rx="1.5" fill="#122452"/><rect x="23" y="2" width="3" height="7" rx="1.5" fill="#122452"/>
<text x="18" y="28.5" text-anchor="middle" font-size="12" font-weight="700" fill="#122452">30</text>
</g>
<text x="56" y="24" font-size="13" font-weight="700" fill="#122452">Quando</text><text x="56" y="39" font-size="9.5" fill="#3d4a73">paghi</text>
</g></g>
<g transform="translate(206 158)"><g class="sc-pop sc-t3">
<rect y="3" width="142" height="52" rx="12" style="fill:var(--scena-ombra)"/><rect width="142" height="52" rx="12" fill="#fff" style="stroke:var(--scena-bordo)"/>
<g transform="translate(10 8)">
<path d="M9 13h18v2c3 1.5 4 4 4 7v8a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4v-8c0-3 1-5.5 4-7Z" fill="#e8ebfa"/>
<g clip-path="url(#scVaso)"><rect class="sc-livello" x="4" y="20" width="28" height="15" fill="#05d5c8"/></g>
<path d="M9 13h18v2c3 1.5 4 4 4 7v8a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4v-8c0-3 1-5.5 4-7Z" fill="none" stroke="#122452" stroke-width="2"/>
<rect x="7" y="7" width="22" height="6" rx="2.5" fill="#122452"/><circle cx="14.5" cy="27.5" r="3.4" fill="#efac35"/><circle cx="21.5" cy="29" r="3.4" fill="#f6c25a"/>
</g>
<text x="56" y="24" font-size="13" font-weight="700" fill="#122452">Da parte</text><text x="56" y="39" font-size="9.5" fill="#3d4a73">su ogni fattura</text>
</g></g>
</svg>
</div>
<div class="azione">
<a class="cta" href="/colloquio/nuovo">Inizia, è gratis</a>
<p class="sub">Basta il certificato della partita IVA, oppure qualche tocco sul telefono.</p>
<p class="sub">Hai già un profilo? <a href="/accedi">Accedi</a></p>
</div>
</div>
<ul>
<li><div class="ico"><i>1</i><svg viewBox="0 0 48 48" aria-hidden="true"><path class="ic-t ic-c" d="M15 9h13l8 8v19a3 3 0 0 1-3 3H15a3 3 0 0 1-3-3V12a3 3 0 0 1 3-3Z"/><path class="ic-t" d="M28 9v6a2 2 0 0 0 2 2h6"/><path class="ic-r" d="M17 24h14"/><path class="ic-r ic-r2" d="M17 29h9"/><path class="ic-r ic-r3" d="M17 34h12"/><path class="ic-luce" d="M7 21h34" fill="none" stroke="#05d5c8" stroke-width="2.8" stroke-linecap="round"/></svg></div><div><b>Dici chi sei</b><span>Carichi il certificato di attribuzione e scegli fra poche risposte. Il resto lo capiamo noi.</span></div></li>
<li><div class="ico"><i>2</i><svg viewBox="0 0 48 48" aria-hidden="true"><path class="ic-soglia" d="M9 12h30" fill="none" stroke="#efac35" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="3 4"/><rect class="ic-barra" x="12" y="28" width="6" height="10" rx="1.5" style="fill:var(--accent-ink)"/><rect class="ic-barra ic-b2" x="21" y="22" width="6" height="16" rx="1.5" style="fill:var(--accent-ink)"/><rect class="ic-barra ic-b3" x="30" y="16" width="6" height="22" rx="1.5" fill="#05d5c8"/><path class="ic-t" d="M9 39h30"/></svg></div><div><b>Vedi la tua situazione</b><span>Prossima scadenza, quota da mettere da parte su ogni fattura, distanza dagli 85.000&nbsp;€.</span></div></li>
<li><div class="ico"><i>3</i><svg viewBox="0 0 48 48" aria-hidden="true"><rect class="ic-t ic-c" x="9" y="12" width="30" height="27" rx="5"/><path class="ic-t" d="M9 20h30M17 8v7M31 8v7"/><path class="ic-spunta" d="M17 29l5 5 9-9.5" fill="none" stroke="#05d5c8" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/><circle class="ic-punto" cx="39.5" cy="11.5" r="4.8" fill="#efac35" style="stroke:var(--soft)" stroke-width="2.4"/></svg></div><div><b>Non perdi più nulla</b><span>Scadenze nel calendario del telefono e spunti su bandi e agevolazioni per la tua zona.</span></div></li>
</ul>
<p class="foot">TaxScan prepara e spiega: sono stime a scopo informativo. Il tuo commercialista controlla e firma. Non sostituisce il parere di un professionista abilitato.</p>
<p class="by">TaxScan è un servizio offerto da <a href="https://ltd24.co.uk" target="_blank" rel="noopener"><picture><source srcset="/logo-ltd24-scuro.png" media="(prefers-color-scheme: dark)"><img src="/logo-ltd24.png" alt="LTD24" onerror="this.replaceWith(document.createTextNode('LTD24'))"></picture></a> · <a href="/privacy">Privacy</a></p>
</div>
<script>
(function(){
  var passi=document.querySelectorAll("ul li");
  function avvia(li){li.classList.remove("on");void li.offsetWidth;li.classList.add("on")}
  if(!("IntersectionObserver" in window)){return}
  var oss=new IntersectionObserver(function(voci){voci.forEach(function(v){if(v.isIntersecting){avvia(v.target);oss.unobserve(v.target)}})},{threshold:.6});
  passi.forEach(function(li){oss.observe(li);li.addEventListener("pointerenter",function(){avvia(li)})});
})();
</script>
</body>
</html>
"""


ACCEDI_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Accedi - TaxScan</title>
<style>
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{color-scheme:light;--f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--bg:#eef2f8;--surface:#fff;--line:#d8e2ed;--ink:#122452;--ink2:#3d4a73;--accent:#4355cc;--accent-ink:#4355cc;--crit:#d03b3b;--soft:#e8ebfa;--punto:#b9c4ee}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0a1330;--surface:#122452;--line:#25397a;--ink:#fff;--ink2:#c9d3ec;--accent:#5566dd;--accent-ink:#a6b4ff;--soft:#1c3070;--punto:#4a5f9e}}
*{box-sizing:border-box;margin:0}
h1,h2,h3,.logo{font-family:var(--f-tit)}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--f-txt);padding:24px 16px 40px;max-width:480px;margin:0 auto}
.logo{font-weight:800;font-size:18px;margin-bottom:28px}.logo span{color:#05d5c8}
h1{font-size:26px;line-height:1.15;margin-bottom:8px}
.lead{color:var(--ink2);margin-bottom:18px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px}
input{width:100%;padding:14px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;margin-bottom:10px}
button{width:100%;border:0;border-radius:12px;padding:14px;background:var(--accent);color:#fff;font:inherit;font-weight:700;cursor:pointer}
.msg{font-size:14px;color:var(--ink2);margin-top:10px;min-height:20px}.msg.err{color:var(--crit)}
a{color:var(--accent-ink);font-weight:600}
.by{font-size:12px;color:var(--ink2);margin-top:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}.by a{display:inline-flex;color:var(--ink);font-weight:700;text-decoration:none}.by img{height:20px;width:auto}
.nascosto{display:none}
.ill{margin:0 0 14px}.ill svg{display:block;width:112px;height:84px}
.a-carta{fill:var(--soft)}.a-p{fill:var(--punto);transition:fill .25s}
.a-busta{fill:var(--surface);stroke:var(--ink);stroke-width:2.2}.a-lembo{fill:none;stroke:var(--ink);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.ill.inviato .a-p{fill:#05d5c8}
button:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid #05d5c8;outline-offset:2px}
@media (prefers-reduced-motion:no-preference){.a-foglio{animation:a-esce .6s cubic-bezier(.2,.9,.3,1.2) .15s both}}
@keyframes a-esce{from{transform:translateY(22px)}to{transform:none}}
</style>
</head>
<body>
<div class="logo">Tax<span>Scan</span></div>
<div class="ill" id="ill" aria-hidden="true"><svg viewBox="0 0 112 84"><g class="a-foglio"><rect x="24" y="2" width="64" height="44" rx="8" class="a-carta"/><circle class="a-p" cx="36" cy="16" r="3" style="transition-delay:0ms"/><circle class="a-p" cx="44" cy="16" r="3" style="transition-delay:90ms"/><circle class="a-p" cx="52" cy="16" r="3" style="transition-delay:180ms"/><circle class="a-p" cx="60" cy="16" r="3" style="transition-delay:270ms"/><circle class="a-p" cx="68" cy="16" r="3" style="transition-delay:360ms"/><circle class="a-p" cx="76" cy="16" r="3" style="transition-delay:450ms"/></g><rect class="a-busta" x="14" y="30" width="84" height="50" rx="9"/><path class="a-lembo" d="M16 35l40 25 40-25"/></svg></div>
<h1>Bentornato</h1>
<p class="lead">Scrivi l'email che hai usato: ti mandiamo un codice a 6 cifre. Niente password da ricordare.</p>
<div class="card">
  <div id="passo1"><input id="em" type="email" inputmode="email" autocomplete="email" placeholder="La tua email"><button id="ok1">Ricevi il codice</button></div>
  <div id="passo2" class="nascosto"><p class="lead" style="margin-bottom:10px" id="inviato"></p><input id="cod" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="Codice"><button id="ok2">Entra</button></div>
  <p class="msg" id="msg"></p>
</div>
<p class="lead" style="margin-top:18px;font-size:14px">Non hai ancora un profilo? <a href="/colloquio/nuovo">Inizia da qui</a>, ci vogliono 2 minuti.</p>
<p class="by">TaxScan è un servizio offerto da <a href="https://ltd24.co.uk" target="_blank" rel="noopener"><picture><source srcset="/logo-ltd24-scuro.png" media="(prefers-color-scheme: dark)"><img src="/logo-ltd24.png" alt="LTD24" onerror="this.replaceWith(document.createTextNode('LTD24'))"></picture></a> · <a href="/privacy">Privacy</a></p>
<script>
const $=i=>document.getElementById(i);
const msg=(t,e)=>{$("msg").textContent=t;$("msg").className="msg"+(e?" err":"")};
async function post(p,b){const r=await fetch(p,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)});let j={};try{j=await r.json()}catch(e){}return j}
let email="";
$("ok1").onclick=async()=>{email=$("em").value.trim();
  if(!/^\S+@\S+\.\S+$/.test(email))return msg("Scrivi un'email valida.",true);
  msg("Un attimo…");const j=await post("/api/accedi/email",{email});
  if(!j.ok)return msg(j.errore||"Non ci sono riuscito, riprova.",true);
  $("passo1").classList.add("nascosto");$("passo2").classList.remove("nascosto");$("ill").classList.add("inviato");
  $("inviato").textContent="Se "+email+" ha un profilo, ti abbiamo scritto un codice (guarda anche nello spam).";msg("");$("cod").focus()};
$("em").onkeydown=e=>{if(e.key==="Enter")$("ok1").click()};
$("ok2").onclick=async()=>{msg("Controllo…");const j=await post("/api/accedi/codice",{email,codice:$("cod").value.trim()});
  if(j.ok){msg("Ti porto alla tua situazione…");location.href=j.dashboard}else msg(j.errore||"Codice non valido.",true)};
$("cod").onkeydown=e=>{if(e.key==="Enter")$("ok2").click()};
</script>
</body>
</html>
"""
