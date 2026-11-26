"""TaxScan - pagina iniziale (/): ispirata alla bozza fatta in Figma (stile Notion), con i colori, il logo e i testi
di TaxScan. Tutto dentro la pagina (CSS e SVG), nessun servizio esterno: i caratteri arrivano dal nostro sito."""

PAGINA_HTML = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TaxScan - Il primo agente IA per pagare meno tasse (forfettari)</title><link rel="icon" href="/favicon.ico?v=2" sizes="any"><link rel="icon" type="image/png" sizes="48x48" href="/favicon-48.png?v=2"><link rel="apple-touch-icon" href="/apple-touch-icon.png?v=2">
<link rel="canonical" href="https://taxscan.it/">
<meta property="og:title" content="TaxScan: quanto paghi di tasse? Scoprilo in 2 minuti"><meta property="og:description" content="TaxScan, il primo agente IA specializzato nel risparmio fiscale per partite IVA in regime forfettario: quanto pagare, quando e quanto mettere da parte su ogni fattura. Gratis."><meta property="og:url" content="https://taxscan.it/"><meta property="og:type" content="website"><meta property="og:site_name" content="TaxScan"><meta property="og:image" content="https://taxscan.it/og-avatar.jpg?v=2"><meta property="og:image:width" content="600"><meta property="og:image:height" content="600"><meta property="og:image:alt" content="Avatar di TaxScan"><meta name="twitter:card" content="summary"><meta name="twitter:image" content="https://taxscan.it/og-avatar.jpg?v=2">
<meta name="description" content="TaxScan, il primo agente IA specializzato nel risparmio fiscale: paghi meno tasse. Per partite IVA in regime forfettario. Scopri quanto puoi risparmiare.">
<style>
<style>
@font-face{font-family:"Poppins";font-weight:400;font-display:swap;src:url(/font/Poppins-Regular.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:500;font-display:swap;src:url(/font/Poppins-Medium.ttf) format("truetype")}
@font-face{font-family:"Poppins";font-weight:700;font-display:swap;src:url(/font/Poppins-Bold.ttf) format("truetype")}
@font-face{font-family:"Rethink Sans";font-weight:400 800;font-display:swap;src:url(/font/RethinkSans-VariableFont_wght.ttf) format("truetype")}
:root{color-scheme:light;
  --f-tit:"Rethink Sans","Poppins",system-ui,sans-serif;--f-txt:"Poppins",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --bg:#f7f8fb;--surface:#fff;--ink:#122452;--ink2:#4a5578;--mute:#5d6787;--line:rgba(18,36,82,.10);--line2:rgba(18,36,82,.18);
  --accent:#4355cc;--accent-h:#3646bd;--accent-ink:#4355cc;--scan:#05c4b8;--scan-ink:#087a63;--scan-soft:#e6faf7;
  --gold:#f6c25a;--gold-soft:#fde9bd;--lav:#e8ebfa;--navy:#122452;--navy2:#1b2f66;--ombra:#c9d2e8}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0a1330;--surface:#101d47;--ink:#fff;--ink2:#c9d3ec;--mute:#94a1c8;--line:rgba(255,255,255,.10);--line2:rgba(255,255,255,.2);
  --accent:#4355cc;--accent-h:#3a4bc0;--accent-ink:#a6b4ff;--scan-ink:#5fe3d6;--scan-soft:#0d3a45;--lav:#1c3070;--navy:#0d1a42;--navy2:#162a63;--ombra:#050b20}}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:80px}
body{background:var(--bg);color:var(--ink);font:16px/1.6 var(--f-txt);-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit}
::selection{background:var(--accent);color:#fff}
.w{max-width:1200px;margin:0 auto;padding:0 20px}
h1,h2,h3{font-family:var(--f-tit);font-weight:750;letter-spacing:-.022em;line-height:1.06}
.ser{color:var(--accent-ink)}
.logo{font-family:"Poppins",var(--f-tit);font-weight:700;font-size:22px;line-height:1;text-decoration:none;color:var(--ink);white-space:nowrap}
.logo span{color:var(--accent-ink)}
:focus-visible{outline:3px solid var(--scan);outline-offset:3px;border-radius:6px}

/* bottoni */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:50px;padding:13px 22px;border-radius:12px;font-weight:700;font-size:16px;text-decoration:none;border:0;cursor:pointer;transition:transform .18s ease,box-shadow .18s ease,background .18s ease}
.btn svg{width:18px;height:18px;flex:none}
.btn:hover{transform:translateY(-2px)}
.btn:active{transform:none}
.btn-acc{background:var(--accent);color:#fff;box-shadow:0 4px 0 var(--navy)}
.btn-acc:hover{background:var(--accent-h);box-shadow:0 6px 0 var(--navy)}
.btn-dark{background:var(--navy);color:#fff;box-shadow:0 4px 0 var(--ombra)}
.btn-dark:hover{box-shadow:0 6px 0 var(--ombra)}
.btn-light{background:var(--surface);color:var(--ink);border:1px solid var(--line2)}
.btn-light:hover{box-shadow:0 6px 18px rgba(18,36,82,.08)}
.btn-sm{min-height:40px;padding:9px 16px;font-size:14px}

/* testata */
.top{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-bottom:1px solid transparent;transition:border-color .2s}
.top.su{border-color:var(--line)}
.top .w{display:flex;align-items:center;justify-content:space-between;height:68px;gap:16px}
.nav{display:none;gap:28px;font-size:14px;font-weight:500}
.nav a{position:relative;text-decoration:none;color:var(--ink2);padding:6px 0}
.nav a::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:var(--scan);transform:scaleX(0);transform-origin:right;transition:transform .2s ease}
.nav a:hover{color:var(--ink)}.nav a:hover::after{transform:scaleX(1);transform-origin:left}
.dx{display:none;align-items:center;gap:6px}
.dx .acc{font-size:14px;font-weight:600;text-decoration:none;padding:8px 12px}
.ham{display:grid;place-items:center;width:42px;height:42px;border-radius:10px;border:1px solid var(--line2);background:var(--surface);color:var(--ink);cursor:pointer}
.ham svg{width:20px;height:20px}
.menu{display:none;border-top:1px solid var(--line);background:var(--bg);padding:12px 20px 20px}
.menu.on{display:block}
.menu a{display:block;padding:12px;border-radius:10px;font-weight:600;text-decoration:none}
.menu a:hover{background:var(--lav)}
.menu .btn{display:flex;margin-top:10px}

/* hero */
.hero{position:relative;padding:52px 0 0;text-align:center}
.griglia{position:absolute;inset:0 0 auto;height:760px;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:48px 48px;-webkit-mask-image:linear-gradient(#000,transparent 88%);mask-image:linear-gradient(#000,transparent 88%);opacity:.55;pointer-events:none}
.hero .w{position:relative}
.eye{display:inline-flex;text-align:left;align-items:center;gap:10px;margin-bottom:26px;padding:8px 14px;border:1px solid var(--line2);border-radius:999px;background:color-mix(in srgb,var(--surface) 80%,transparent);font-size:12.5px;font-weight:600;color:var(--ink2);box-shadow:0 4px 14px rgba(18,36,82,.05)}
.punto{position:relative;width:8px;height:8px;flex:none}
.punto::before,.punto::after{content:"";position:absolute;inset:0;border-radius:50%;background:var(--scan)}
.punto::before{animation:ping 1.6s cubic-bezier(0,0,.2,1) infinite;opacity:.6}
@keyframes ping{75%,100%{transform:scale(2.4);opacity:0}}
.h1{font-size:clamp(46px,9vw,112px);line-height:.95;letter-spacing:-.04em;max-width:980px;margin:0 auto}
.giro{display:inline-block;text-align:left;white-space:nowrap}
.giro span{display:inline-block;color:var(--accent-ink);animation:dentro .55s cubic-bezier(.22,1,.36,1) both}
@keyframes dentro{from{opacity:0;transform:translateY(.35em) rotate(2deg);filter:blur(5px)}to{opacity:1;transform:none;filter:none}}
.h1 .ser{position:relative;display:inline-block;color:var(--ink)}
@media (max-width:639px){.h1 .ser svg{display:none}.h1 .ser{text-decoration:underline;text-decoration-color:var(--scan);text-decoration-thickness:.07em;text-underline-offset:.14em}.eye{font-size:12px}}
.h1 .ser svg{position:absolute;left:4%;right:-1%;bottom:-.1em;width:96%;height:.16em;color:var(--scan)}
.lead{max-width:660px;margin:34px auto 0;font-size:clamp(17px,2vw,20px);color:var(--ink2)}
.lead b{color:var(--ink);font-weight:600}
.azioni{display:flex;flex-direction:column;align-items:stretch;gap:12px;margin-top:32px;max-width:400px;margin-left:auto;margin-right:auto}
.nota{margin-top:14px;font-size:12.5px;font-weight:500;color:var(--mute)}
.lancio{display:block;background:var(--scan-soft);color:var(--scan-ink);text-decoration:none;font-size:14px;border-bottom:1px solid color-mix(in srgb,var(--scan) 30%,transparent)}
.lancio .w{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:4px 10px;min-height:44px;padding-top:8px;padding-bottom:8px;text-align:center}
.lancio b{font-weight:700}.lancio s{opacity:.75}.lancio u{font-weight:600;text-underline-offset:3px}
.lancio:hover u{text-decoration-thickness:2px}
@media (max-width:639px){.lancio .gr{display:none}.lancio{font-size:13px}}
#prezzo:target .prezzo{animation:apri 1.4s cubic-bezier(.22,1,.36,1) both}
@keyframes apri{0%{transform:scale(.97);box-shadow:0 0 0 0 rgba(5,196,184,.0)}35%{transform:none;box-shadow:0 0 0 6px rgba(5,196,184,.35)}100%{box-shadow:0 0 0 0 rgba(5,196,184,0)}}
.offerta{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:18px;padding:8px 14px;border-radius:999px;background:var(--scan-soft);color:var(--scan-ink);font-size:13.5px;text-decoration:none;border:1px solid color-mix(in srgb,var(--scan) 35%,transparent)}
.offerta b{font-weight:700}.offerta s{opacity:.7}
.offerta:hover{border-color:var(--scan)}

/* mockup dell'app */
.mock{position:relative;max-width:1060px;margin:64px auto 0}
.freccia{display:none;position:absolute;left:-6px;top:-58px;transform:rotate(-5deg);font-size:15px;font-weight:600;color:var(--ink2);text-align:left}
.freccia svg{display:block;width:56px;height:40px;margin-left:120px;color:var(--ink2)}
.app{overflow:hidden;text-align:left;border:1px solid var(--line2);border-bottom:0;border-radius:22px 22px 0 0;background:#fff;color:#122452;box-shadow:0 30px 80px rgba(18,36,82,.14),0 4px 0 var(--navy)}
.barra{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;border-bottom:1px solid rgba(18,36,82,.08)}
.barra i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;background:#dfe4ef}
.barra .url{font-size:12px;font-weight:600;color:#5d6787;background:#f1f4f9;border-radius:999px;padding:4px 14px}
.barra .es{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#087a63;background:#e6faf7;border-radius:999px;padding:4px 10px}
.corpo{display:grid}
.lato{display:none;border-right:1px solid rgba(18,36,82,.08);padding:20px 16px}
.lato .logo{font-size:18px;color:#122452}.lato .logo span{color:#4355cc}
.lato ul{list-style:none;margin-top:30px;display:grid;gap:4px;font-size:13px;font-weight:600;color:#5d6787}
.lato li{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:9px}
.lato li::before{content:"";width:8px;height:8px;border-radius:2px;background:rgba(18,36,82,.15)}
.lato li.on{background:#e8ebfa;color:#122452}.lato li.on::before{background:#4355cc}
.pann{background:#f4f6fb;padding:18px}
.ciao{font-size:12px;font-weight:700;letter-spacing:.06em;color:#5d6787}
.pann h2{font-size:24px;margin-top:2px;letter-spacing:-.03em}
.ag{display:flex;align-items:center;gap:12px;margin-top:16px;padding:14px;border-radius:16px;background:#fff;border:1px solid #cfd6f5}
.ag img{width:40px;height:40px;border-radius:50%;object-fit:cover;flex:none;background:#e8ebfa}
.ag p{font-size:13.5px;line-height:1.5}
.kpi{display:grid;gap:14px;margin-top:14px}
.box{border-radius:16px;background:#fff;border:1px solid rgba(18,36,82,.08);padding:18px;box-shadow:0 4px 14px rgba(18,36,82,.03)}
.lbl{font-size:12px;font-weight:700;letter-spacing:.06em;color:#5d6787}
.num{font-family:var(--f-tit);font-size:32px;font-weight:750;letter-spacing:-.025em;margin-top:6px;line-height:1.1}
.sotto{font-size:12.5px;color:#5d6787}
.bars{display:flex;align-items:flex-end;gap:7px;height:110px;margin-top:22px}
.bars i{flex:1;border-radius:4px 4px 0 0;background:#e3e8f4}
.bars i.on{background:#4355cc}
.mesi{display:flex;justify-content:space-between;margin-top:8px;font-size:11px;font-weight:700;color:#6b7596}
.lati{display:grid;gap:14px}
.box.scura{background:#122452;color:#fff;border:0}
.box.scura .lbl{color:rgba(255,255,255,.78)}
.prog{height:6px;border-radius:99px;background:rgba(255,255,255,.15);margin-top:16px;overflow:hidden}
.prog i{display:block;height:100%;width:68%;border-radius:99px;background:#05c4b8}
.box.oro{background:#fde9bd;border-color:#f3d48e}
.data{font-family:var(--f-tit);font-weight:750;font-size:28px;letter-spacing:-.02em;margin-top:12px;line-height:1.1}

/* panoramica di esempio interattiva */
.corpo{grid-template-columns:minmax(0,1fr)}
.lato{display:block;min-width:0;padding:10px 12px;border-right:0;border-bottom:1px solid rgba(18,36,82,.08)}
.lato .logo{display:none}
.lato ul{display:flex;gap:6px;margin-top:0;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
.lato li{flex:none;padding:0}.lato li::before{display:none}
.lato button{display:flex;align-items:center;gap:10px;width:100%;min-height:40px;padding:9px 12px;border:0;border-radius:9px;background:none;font:inherit;color:inherit;text-align:left;cursor:pointer;white-space:nowrap}
.lato button::before{content:"";width:8px;height:8px;border-radius:2px;background:rgba(18,36,82,.15);flex:none}
.lato button:hover{background:#f1f4f9}
.lato button.on{background:#e8ebfa;color:#122452}.lato button.on::before{background:#4355cc}
.lato button:focus-visible,.dbtn:focus-visible,.bm:focus-visible,.dtodo button:focus-visible{outline:2px solid #4355cc;outline-offset:2px}
.cnt{margin-left:auto;min-width:20px;height:20px;padding:0 6px;border-radius:99px;background:#c62f3a;color:#fff;font-size:11px;display:inline-flex;align-items:center;justify-content:center}
.cnt.zero{background:#087a63}
.dv{animation:dvin .35s ease}
@keyframes dvin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.dbtn{margin-top:8px;min-height:36px;padding:8px 14px;border:0;border-radius:10px;background:#4355cc;color:#fff;font:600 13px/1 var(--f-txt);cursor:pointer}
.dbtn:hover{background:#3646bd}
.dcalc{margin-top:10px;padding:14px 16px;border-radius:14px;background:#fff;border:1px dashed #b9c3ee;animation:dvin .35s ease}
.dr{display:flex;justify-content:space-between;gap:12px;padding:7px 0;font-size:13.5px;color:#3d4a73;border-top:1px solid rgba(18,36,82,.07)}
.dr:first-child{border-top:0}.dr b{color:#122452;text-align:right}
.dr.tot{font-weight:700;color:#122452}.dr.tot b{color:#4355cc}
.dnota{font-size:12.5px;color:#5d6787;margin-top:6px}
.bars .bm{flex:1;border:0;padding:0;border-radius:4px 4px 0 0;background:#e3e8f4;cursor:pointer;transition:background .2s}
.bars .bm:hover,.bars .bm.sel{background:#9fabe6}.bars .bm.on{background:#4355cc}
.bars .vuoto{flex:1;border-radius:4px 4px 0 0;border:1.5px dashed #c3cbe6;box-sizing:border-box}
.dcmp{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
.dris{margin-top:14px}
.dtodo{list-style:none;display:grid;gap:10px;margin-top:16px}
.dtodo button{display:flex;gap:12px;align-items:flex-start;width:100%;padding:14px;border-radius:14px;border:1px solid rgba(18,36,82,.1);background:#fff;font:inherit;font-size:13.5px;line-height:1.45;color:#3d4a73;text-align:left;cursor:pointer}
.dtodo b{color:#122452}
.ck{flex:none;width:22px;height:22px;border-radius:7px;border:2px solid #b9c3ee;display:flex;align-items:center;justify-content:center;color:transparent}
.ck svg{width:14px;height:14px}
.dtodo .fatto{background:#f4f6fb}.dtodo .fatto b{text-decoration:line-through;color:#6b7596}
.dtodo .fatto .ck{background:#087a63;border-color:#087a63;color:#fff}
.dband{position:relative;margin-top:14px}.dband .lbl{padding-right:64px}
@media (max-width:640px){.barra>span:first-child{display:none}.barra .es{font-size:11px}}.dband h3{font-size:18px;margin:6px 0 4px;letter-spacing:-.02em}
.dtag{position:absolute;top:14px;right:14px;font-size:11px;font-weight:700;padding:3px 9px;border-radius:99px;background:#e6faf7;color:#087a63}
.dreq{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.dreq span{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:#087a63;background:#e6faf7;border-radius:99px;padding:4px 10px}
.dreq svg{width:13px;height:13px}
.dprof{margin-top:14px}
/* fascia sezioni */
.fascia{border-block:1px solid var(--line);background:var(--surface);padding:34px 0;text-align:center}
.fascia p{font-size:12px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--mute)}
.chips{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;margin-top:20px}
.chips span{border:1px solid var(--line2);border-radius:999px;padding:8px 16px;font-size:14px;font-weight:600;color:var(--ink2);background:var(--bg)}

/* sezioni */
.sez{padding:clamp(76px,10vw,132px) 0}
.etic{display:inline-block;padding-bottom:7px;border-bottom:1px solid var(--line2);font-size:11.5px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--mute)}
.tit{font-size:clamp(38px,5.6vw,78px);line-height:1;letter-spacing:-.035em}
.due{display:grid;gap:40px}
.testo{margin-top:22px;max-width:28em;font-size:18px;color:var(--ink2)}
.passi{border-block:1px solid var(--line)}
.passo{display:grid;gap:16px;padding:32px 0;border-top:1px solid var(--line)}
.passo:first-child{border-top:0}
.passo .n{font-family:var(--f-tit);font-weight:750;font-size:18px;color:var(--mute)}
.ico{display:grid;place-items:center;width:46px;height:46px;border-radius:13px;background:var(--lav);color:var(--accent-ink);margin-bottom:16px;transition:transform .2s ease}
.ico svg{width:22px;height:22px}
.passo:hover .ico{transform:rotate(-4deg) scale(1.05)}
.passo h3{font-size:clamp(23px,2.6vw,28px);max-width:17em;letter-spacing:-.022em}
.passo p{margin-top:10px;max-width:34em;color:var(--ink2)}
.tag{width:fit-content;height:fit-content;border:1px solid var(--line2);border-radius:999px;padding:6px 12px;font-size:12px;font-weight:600;color:var(--mute);white-space:nowrap}

/* sezione scura */
.scuro{background:var(--navy);color:#fff}
.scuro .etic{color:rgba(255,255,255,.6);border-color:rgba(255,255,255,.22)}
.scuro .tit .ser{color:#7fe6dc}
.carte{display:grid;gap:18px;margin-top:56px}
.carta{border-radius:24px;padding:clamp(24px,4vw,40px);background:var(--navy2);border:1px solid rgba(255,255,255,.08);overflow:hidden}
.kick{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.72)}
.carta h3{font-size:clamp(25px,2.8vw,34px);margin-top:12px;letter-spacing:-.025em;line-height:1.08}
.carta p{margin-top:12px;max-width:30em;color:rgba(255,255,255,.78)}
.vetrina{position:relative;margin-top:44px;min-height:280px}
.vetrina>div{position:absolute;inset:auto 0 0;margin:0 auto;max-width:380px;border-radius:28px 28px 0 0;border:1px solid rgba(255,255,255,.12);border-bottom:0;background:#0d1a42;padding:26px 26px 0}
.riga2{display:flex;justify-content:space-between;font-size:13px;color:rgba(255,255,255,.75)}
.linea{height:8px;border-radius:99px;background:rgba(255,255,255,.1);margin-top:10px;overflow:hidden}
.linea i{display:block;height:100%;width:100%;background:linear-gradient(90deg,#4355cc,#05c4b8);border-radius:99px}
.vetrina .grande{font-family:var(--f-tit);font-size:44px;font-weight:750;letter-spacing:-.03em;margin-top:4px;color:#fff}
.ok{display:flex;align-items:center;gap:12px;margin-top:26px;padding:18px 0;border-top:1px solid rgba(255,255,255,.1);font-size:14px}
.ok b{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#05c4b8;color:#0d1a42;flex:none}
.ok svg{width:16px;height:16px}
.carta.oro{background:#f6c25a;color:#122452;border:0}
.carta.oro .kick{color:rgba(18,36,82,.82)}.carta.oro p{color:rgba(18,36,82,.72)}
.dist{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-top:30px;padding:18px 20px;border-radius:18px;background:#fde9bd}
.dist .lbl{color:rgba(18,36,82,.8)}
.dist b{font-family:var(--f-tit);font-size:26px;letter-spacing:-.03em}
.dist span{border-radius:99px;background:rgba(255,255,255,.75);padding:6px 12px;font-size:12px;font-weight:700}
.carta.lav{background:#e8ebfa;color:#122452;border:0}
.carta.lav .kick{color:rgba(18,36,82,.8)}.carta.lav p{color:rgba(18,36,82,.7)}
.bolle{display:flex;margin-top:24px}
.bolle span{display:grid;place-items:center;width:50px;height:50px;border-radius:50%;border:3px solid #e8ebfa;margin-left:-10px;font-weight:700;font-size:15px;color:#122452}
.bolle span:first-child{margin-left:0;background:#9fb0f2}.bolle span:nth-child(2){background:#8fe3da}.bolle span:nth-child(3){background:#f6c25a}

/* esempio */
.storia{border-radius:28px;border:1px solid var(--line);background:var(--surface);padding:clamp(24px,4vw,40px);box-shadow:0 20px 60px rgba(18,36,82,.08)}
.chi{display:flex;align-items:center;gap:14px;padding-bottom:22px;border-bottom:1px solid var(--line)}
.chi .av{display:grid;place-items:center;width:48px;height:48px;border-radius:50%;background:var(--gold);color:#122452;font-weight:800;flex:none}
.chi b{display:block}
.chi small{font-size:14px;color:var(--mute)}
.storia ol{list-style:none;display:grid;gap:18px;margin-top:24px;counter-reset:p}
.storia li{display:flex;gap:14px;color:var(--ink2);counter-increment:p}
.storia li::before{content:counter(p);display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;font-size:12.5px;font-weight:700;flex:none;margin-top:1px}
.zero{margin-top:26px;border-radius:14px;background:var(--lav);padding:14px 16px;font-size:14.5px;font-weight:500}

/* prezzo */
.prezzo{display:grid;gap:28px;border-radius:28px;border:1px solid var(--line);background:var(--surface);padding:clamp(24px,4vw,44px)}
.pill{display:inline-block;border-radius:999px;background:var(--scan-soft);color:var(--scan-ink);font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:5px 12px}
.cifra{display:flex;align-items:baseline;flex-wrap:wrap;gap:10px;margin-top:14px}
.cifra b{font-family:var(--f-tit);font-size:64px;line-height:1;letter-spacing:-.03em}
.cifra s{font-size:24px;font-weight:600;color:var(--mute)}
.cifra span{color:var(--ink2)}
.incl{list-style:none;display:grid;gap:10px;margin-top:18px}
.incl li{display:flex;gap:10px;align-items:flex-start}
.incl li::before{content:"";width:20px;height:20px;border-radius:50%;flex:none;margin-top:2px;background:var(--scan) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M5.5 10.3l3 3 6-6.3' fill='none' stroke='%23fff' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center/20px no-repeat}
.gratis{margin-top:14px;font-size:14px;color:var(--mute)}
.gar{display:flex;gap:14px;align-items:flex-start;border-radius:18px;background:var(--lav);padding:18px}
.gar svg{width:34px;height:34px;flex:none}
.gar p{font-size:14.5px}
.prezzo .azioni{align-items:stretch;margin:20px 0 0;max-width:none}

/* invito finale */
.invito{position:relative;overflow:hidden;border-radius:32px;background:var(--accent);color:#fff;text-align:center;padding:clamp(64px,9vw,104px) 24px}
.puntini{position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.5) 1px,transparent 1px);background-size:18px 18px;-webkit-mask-image:radial-gradient(circle at center,#000,transparent 70%);mask-image:radial-gradient(circle at center,#000,transparent 70%);opacity:.35}
.invito>*{position:relative}
.invito .sopra{font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.invito h2{font-size:clamp(40px,6.6vw,88px);line-height:1;letter-spacing:-.035em;margin-top:18px}
.invito h2 .ser{color:#fff;text-decoration:underline;text-decoration-color:#7fe6dc;text-decoration-thickness:.06em;text-underline-offset:.12em}
.invito p.l{max-width:36em;margin:22px auto 0;font-size:18px}
.invito .btn{margin-top:34px;background:#fff;color:#122452;box-shadow:0 4px 0 var(--navy)}
.invito .btn:hover{box-shadow:0 6px 0 var(--navy)}
.invito small{display:block;margin-top:14px;font-size:13px;font-weight:600}

/* domande */
.faq{border-block:1px solid var(--line)}
.faq details{border-top:1px solid var(--line)}
.faq details:first-child{border-top:0}
.faq summary{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:22px 0;font-family:var(--f-tit);font-size:19px;font-weight:700;letter-spacing:-.02em;cursor:pointer;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq summary svg{width:20px;height:20px;flex:none;transition:transform .25s}
.faq details[open] summary svg{transform:rotate(180deg)}
.faq p{padding:0 0 22px;max-width:36em;color:var(--ink2)}
.faq a{color:var(--accent-ink);font-weight:600}

/* piede */
.piede{border-top:1px solid var(--line);background:var(--surface);margin-top:24px}
.piede .w{padding-top:48px;padding-bottom:40px}
.cols{display:grid;gap:36px}
.cols>div>p{margin-top:14px;max-width:22em;font-size:14px;color:var(--mute)}
.cols h4{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.cols nav{display:grid;gap:10px;margin-top:14px;font-size:14px}
.cols nav a{color:var(--ink2);text-decoration:none}.cols nav a:hover{color:var(--ink)}
.legale{margin-top:40px;padding-top:22px;border-top:1px solid var(--line);font-size:12.5px;color:var(--mute);display:grid;gap:10px}
.by a{text-decoration:none}
.by img{height:16px;vertical-align:-3px}

/* comparsa al passaggio */
/* calcolatore con la linea dell'anno */
.calc{padding:clamp(64px,8vw,110px) 0}
/* simulatore del risparmio */
.ancora{display:block;position:relative;top:-90px;height:0}
#simula [hidden]{display:none!important}
.stima{gap:14px}
.sth{display:flex;align-items:center;gap:10px;margin:0;font:700 19px/1.2 var(--f-tit)}
.sth svg{width:26px;height:26px;color:var(--accent);flex:none}
.srow{margin:0;display:flex;flex-direction:column}
.srow div{display:flex;justify-content:space-between;gap:12px;align-items:baseline;padding:11px 0;border-bottom:1px solid var(--line)}
.srow dt{font-size:15px;color:var(--ink2)}
.srow dd{margin:0;font:600 16px/1.2 var(--f-txt);font-variant-numeric:tabular-nums;white-space:nowrap}
.srow .sfo dt{color:var(--ink);font-weight:700}.srow .sfo dd{font:800 20px/1.1 var(--f-tit)}
#simula .rsp{padding:14px 16px;gap:6px}
.rtop{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.rtop .rk{margin:0}
#simula .rnum b{font:800 22px/1.1 var(--f-tit)}
.rtit{margin:0;font-size:14.5px;color:var(--ink2)}
#simula .rlis li{padding:8px 12px}
.rl1 span{font-weight:600}
.sq{display:flex!important;flex-direction:column;gap:0;margin:0 0 4px;padding:0;list-style:none}
.sq li{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14px}
.sq li.lt{font-weight:700;border-bottom:0;padding-bottom:2px}
.rok .sq{width:100%;align-self:stretch}.sq li{background:none!important;border-radius:0!important;margin:0!important;padding:8px 0!important}
.snota{margin:0;font-size:12.5px;color:var(--mute);line-height:1.45}

.seg.s2{grid-template-columns:repeat(2,minmax(0,1fr))}
.sub{margin-top:12px;padding:14px;border-radius:14px;background:var(--bg);border:1px solid var(--line)}
.sub .seg{background:var(--surface)}
.lbl3{display:block;font-weight:600;font-size:14px;margin-bottom:8px;color:var(--ink2)}
.lbl3 b{color:var(--ink)}
.sub input[type=range]{width:100%;accent-color:var(--accent);height:28px;cursor:pointer}
.aiuto{font-size:13.5px;color:var(--mute);margin:-4px 0 10px;line-height:1.45}
.rsp{border-radius:18px;padding:20px;background:var(--soft,#eef1fb);border:1.5px solid var(--accent);display:flex;flex-direction:column;gap:10px}
.rsp.zero{border-color:var(--line)}
.rk{margin:0;font-size:12.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent-ink)}
.rsp h3{margin:0;font:700 clamp(19px,2vw,23px)/1.2 var(--f-tit);letter-spacing:-.01em}
.rnum{margin:0;font-size:15px;color:var(--ink2)}
.rnum b{font:800 clamp(28px,3.2vw,38px)/1.1 var(--f-tit);color:var(--accent-ink);letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.vela{filter:blur(7px);user-select:none;-webkit-user-select:none}
.rlis{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.rlis li{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.rl1{display:flex;justify-content:space-between;gap:12px;align-items:baseline;font-size:14.5px}
.re{font-weight:700;color:var(--accent-ink);white-space:nowrap;font-variant-numeric:tabular-nums}
.rlis p{margin:6px 0 0;font-size:13.5px;color:var(--ink2);line-height:1.45}
.rform{display:flex;flex-direction:column;gap:10px;margin-top:4px}
.rinv{margin:0;font-size:14.5px}
.rrow{display:flex;gap:8px;flex-wrap:wrap}
.rrow input{flex:1 1 220px;min-height:46px;font:inherit;font-size:15px;padding:10px 14px;border:1px solid var(--line2,var(--line));border-radius:12px;background:var(--surface);color:var(--ink)}
.rrow input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rrow .btn{min-height:46px}
@media (max-width:520px){.rrow{flex-direction:column}.rrow input{flex:none;width:100%;min-width:0;box-sizing:border-box}.rrow .btn{width:100%;justify-content:center}#simula .seg.s2,#simula .sub .seg{grid-template-columns:repeat(2,minmax(0,1fr))}#simula .sub .seg{grid-template-columns:repeat(3,minmax(0,1fr))}}
.rchk{font-size:13.5px}
.rchk input{width:18px;height:18px}
.rpriv{margin:0;font-size:12.5px;color:var(--mute)}
.rpriv a{color:inherit}
#s-err:empty{display:none}#s-err{color:var(--crit,#c62f3a);font-weight:600}
.rok{display:flex;flex-direction:column;gap:12px;align-items:flex-start}
.rok p{margin:0;font-size:14.5px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.sim .cpie{display:block;border-top:1px solid var(--line);padding-top:14px;margin:0;font-size:13px;color:var(--mute)}
.calc .tit{font-size:clamp(34px,4.6vw,60px)}
.cbox{margin-top:36px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:20px;align-items:stretch}
.cin,.cout{background:var(--surface);border:1px solid var(--line);border-radius:22px;padding:26px}
.cin{display:flex;flex-direction:column;gap:22px}
.cin .lbl2{font-weight:700;font-size:15px;margin-bottom:10px;display:block}
.seg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;background:var(--bg);border:1px solid var(--line);border-radius:14px;padding:5px}
.seg button{font:inherit;font-size:14px;font-weight:600;min-height:44px;border:0;border-radius:10px;background:none;color:var(--ink2);cursor:pointer;padding:6px 8px;line-height:1.2}
.seg button[aria-pressed=true]{background:var(--surface);color:var(--ink);box-shadow:0 1px 0 var(--line2),0 4px 12px rgba(18,36,82,.08)}
.seg button:focus-visible,.cin input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.cval{font:700 clamp(30px,3.4vw,40px)/1.1 var(--f-tit);letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.cin input[type=range]{width:100%;accent-color:var(--accent);height:28px;margin-top:6px;cursor:pointer}
.crange{display:flex;justify-content:space-between;font-size:12.5px;color:var(--mute);font-variant-numeric:tabular-nums}
.chk{display:flex;gap:10px;align-items:flex-start;font-size:15px;color:var(--ink2);cursor:pointer}
.chk input{width:20px;height:20px;accent-color:var(--accent);margin-top:2px;flex:none}
.cout{display:flex;flex-direction:column;gap:18px}
.ctre{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.ctre div{border-radius:16px;padding:14px;background:var(--bg)}
.ctre div.forte{background:var(--navy);color:#fff}
.ctre small{display:block;font-size:13px;color:var(--ink2);line-height:1.3}
.ctre div.forte small{color:rgba(255,255,255,.78)}
.ctre b{display:block;font:700 clamp(20px,2.2vw,26px)/1.15 var(--f-tit);margin-top:6px;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.anno h3{font-size:16px;font-weight:700;margin-bottom:4px}
.anno p.sott{font-size:14px;color:var(--ink2)}
.cline{position:relative;margin:54px 6px 0;height:52px}
.cline .traccia{position:absolute;left:0;right:0;top:9px;height:6px;border-radius:3px;background:var(--lav)}
.cline .pieno{position:absolute;left:0;top:9px;height:6px;border-radius:3px;background:var(--scan);width:0;transition:width 1.4s cubic-bezier(.22,1,.36,1)}
.cline.on .pieno{width:100%}
.cline .mm{position:absolute;top:34px;transform:translateX(-50%);font-size:11.5px;font-weight:600;color:var(--mute)}
.cline .pg{position:absolute;top:0;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center}
.cline .pg i{width:24px;height:24px;border-radius:50%;background:var(--gold);border:4px solid var(--surface);box-shadow:0 0 0 1px var(--line2)}
.cline .pg.inps i{background:var(--accent)}
.cline .pg span{position:absolute;bottom:30px;white-space:nowrap;font-size:12.5px;font-weight:700;background:var(--surface);border:1px solid var(--line2);border-radius:8px;padding:3px 7px;font-variant-numeric:tabular-nums;opacity:0;transform:translateY(6px);transition:opacity .4s ease,transform .4s ease}
.cline.on .pg span{opacity:1;transform:none}
.lista{list-style:none;display:none;flex-direction:column;gap:8px;margin-top:14px}
.lista li{display:flex;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:12px;background:var(--bg);font-size:14px}
.lista b{font-variant-numeric:tabular-nums;white-space:nowrap}
.cleg{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--ink2);margin-top:8px}
.cleg span{display:inline-flex;align-items:center;gap:6px}.cleg i{width:10px;height:10px;border-radius:50%;background:var(--gold)}.cleg i.inps{background:var(--accent)}
.cpie{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--line);padding-top:16px}
.cpie p{font-size:13px;color:var(--mute);max-width:36em}
@media (max-width:900px){.cbox{grid-template-columns:minmax(0,1fr)}.cline{display:none}.lista{display:flex}.cleg{display:none}.ctre b{font-size:20px}}
@media (max-width:520px){.seg{grid-template-columns:minmax(0,1fr)}.ctre{grid-template-columns:minmax(0,1fr)}.ctre div{display:flex;justify-content:space-between;align-items:baseline;gap:10px}.ctre b{margin:0}.cin,.cout{padding:20px}}
@media (prefers-reduced-motion:reduce){.cline .pieno{transition:none}.cline .pg span{transition:none}}

/* lo spot */
.hspot{margin:clamp(48px,6vw,80px) auto 0;max-width:1180px;text-align:left}
.sgr{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:clamp(28px,4vw,64px);align-items:center}
.socchio{margin:0 0 10px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent-ink)}
.spot .tit{font-size:clamp(32px,3.6vw,52px)}
.spot .testo{max-width:30em;margin-bottom:26px}
@media (max-width:900px){.sgr{grid-template-columns:1fr}}
.svid{position:relative;border-radius:24px;overflow:hidden;background:var(--navy);box-shadow:0 24px 60px -24px rgba(18,36,82,.45);aspect-ratio:16/9}
.svid video{display:block;width:100%;height:100%;object-fit:cover}
.sbtn{position:absolute;right:16px;bottom:16px;display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:10px 16px;border:0;border-radius:999px;background:rgba(255,255,255,.94);color:var(--navy);font:600 14px/1 var(--f-txt);cursor:pointer;box-shadow:0 6px 18px rgba(10,20,50,.25)}
.sbtn svg{width:18px;height:18px}
.sbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (max-width:640px){.svid{border-radius:16px}.sbtn{right:10px;bottom:10px;font-size:13px}}

.vedi{opacity:0;transform:translateY(18px);transition:opacity .7s ease,transform .7s cubic-bezier(.22,1,.36,1)}
.vedi.on{opacity:1;transform:none}

@media (min-width:640px){
  .azioni{flex-direction:row;justify-content:center;max-width:none}
  .pann{padding:28px}
  .lati{grid-template-columns:1fr 1fr}
  .passo{grid-template-columns:52px 1fr auto;align-items:start;padding:40px 0}
  .prezzo .azioni{flex-direction:row;justify-content:flex-start}
}
@media (min-width:860px){
  .w{padding:0 32px}
  .nav,.dx{display:flex}.ham,.menu,.menu.on{display:none}
  .hero{padding-top:84px}
  .corpo{grid-template-columns:200px minmax(0,1fr)}.lato{display:block;padding:20px 16px;border-bottom:0;border-right:1px solid rgba(18,36,82,.08)}.lato .logo{display:inline}.lato ul{display:grid;overflow:visible;margin-top:30px;padding:0}.lato li{flex:none}
  .pann{padding:34px}
  .kpi{grid-template-columns:1.35fr .65fr}
  .lati{grid-template-columns:1fr}
  .freccia{display:block}
  .mock{margin-top:84px}
  .due{grid-template-columns:.8fr 1.2fr;gap:88px;align-items:start}
  .due.centro{align-items:center}
  .carte{grid-template-columns:1fr 1fr}
  .carta.alta{grid-row:span 2}
  .prezzo{grid-template-columns:1.1fr .9fr;align-items:center}
  .cols{grid-template-columns:1.6fr 1fr 1fr}
  .legale{grid-template-columns:1fr auto;align-items:center}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}.vedi{opacity:1;transform:none}}
</style>
</head>
<body>
<a class="lancio" href="#prezzo"><span class="w"><b>Offerta di lancio</b><span class="pz">12 mesi a 47&nbsp;€ invece di <s>589&nbsp;€</s></span><span class="gr">· soddisfatto o rimborsato</span><u>Scopri l'offerta <span aria-hidden="true">→</span></u></span></a>
<header class="top" id="top">
  <div class="w">
    <a class="logo" href="/" aria-label="TaxScan, torna all'inizio">Tax<span>Scan</span></a>
    <nav class="nav" aria-label="Navigazione principale">
      <a href="#come-funziona">Come funziona</a>
      <a href="#simula">Simulatore</a>
      <a href="#esempio">Un esempio</a>
      <a href="#prezzo">Prezzo</a>
      <a href="#domande">Domande</a>
    </nav>
    <div class="dx">
      <a class="acc" href="/accedi">Accedi</a>
      <a class="btn btn-dark btn-sm" href="/colloquio/nuovo">Prova TaxScan <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
    </div>
    <button class="ham" id="ham" type="button" aria-expanded="false" aria-controls="menu" aria-label="Apri il menu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 8h16M4 16h16"/></svg></button>
  </div>
  <nav class="menu" id="menu" aria-label="Menu">
    <a href="#come-funziona">Come funziona</a>
    <a href="#simula">Simulatore</a>
    <a href="#esempio">Un esempio</a>
    <a href="#prezzo">Prezzo</a>
    <a href="#domande">Domande</a>
    <a href="/accedi">Accedi</a>
    <a class="btn btn-acc" href="/colloquio/nuovo">Scopri quanto puoi risparmiare</a>
  </nav>
</header>

<main>
<section class="hero" aria-labelledby="t-hero">
  <div class="griglia" aria-hidden="true"></div>
  <div class="w">
    <h1 class="h1" id="t-hero">Più <span class="giro"><span id="giro">risparmio.</span></span><br><span class="ser">Meno fisco da capire.<svg viewBox="0 0 500 18" preserveAspectRatio="none" aria-hidden="true"><path d="M4 13C126 1 359 3 496 10" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round"/></svg></span></h1>
    <p class="lead"><b>Il primo agente IA specializzato nel risparmio fiscale.</b> Prepara i conti della tua partita IVA forfettaria e ti dice quanto pagare, quando e dove puoi pagare meno, in regola.</p>
    <div class="azioni">
      <a class="btn btn-acc" href="/colloquio/nuovo">Scopri quanto puoi risparmiare <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
    </div>

    <div class="sgr hspot" id="spot">
      <div class="stx vedi">
        <h2 class="tit" id="t-spot">Ti riconosci in una di queste storie?</h2>
        <p class="testo">Gianni, Paola, Sara e Luca hanno la partita IVA. Le tasse che non si aspettavano, l'INPS che arriva anche quando il lavoro si ferma, il commercialista che non richiama. In 27 secondi, perché abbiamo creato TaxScan.</p>
      </div>
      <div class="svid vedi">
        <video id="spotv" muted playsinline loop preload="metadata" poster="https://cdn.creatify.ai/video-composer/footage/4c31435c-0781-40c6-9101-9c1ccc015131.png" aria-label="Lo spot di TaxScan, 27 secondi, con sottotitoli">
          <source src="https://cdn.creatify.ai/video-composer/d40e4fe8-6c5c-439b-af84-6b8a2027a22f.mp4" type="video/mp4">
        </video>
        <button type="button" class="sbtn" id="spota" aria-pressed="false"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4V5z"/><path d="M23 9l-6 6M17 9l6 6"/></svg><span>Attiva l'audio</span></button>
      </div>
    </div>

    <div class="mock vedi">
      <div class="freccia ser" aria-hidden="true">Il tuo agente IA ti guida<svg viewBox="0 0 60 44" fill="none"><path d="M3 3c12 5 22 13 28 24M21 25l11 3 2-12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></div>
      <div class="app" id="demo" aria-label="Esempio interattivo di TaxScan: puoi cliccare sul menu e sui pulsanti">
        <div class="barra"><span><i></i><i></i><i></i></span><span class="url">taxscan.it</span><span class="es">Esempio · prova a cliccare</span></div>
        <div class="corpo">
          <aside class="lato">
            <span class="logo">Tax<span>Scan</span></span>
            <ul role="tablist" aria-label="Sezioni di esempio">
              <li><button type="button" role="tab" class="on" aria-selected="true" data-v="pan">Panoramica</button></li>
              <li><button type="button" role="tab" aria-selected="false" data-v="ott">Ottimizzazione fiscale</button></li>
              <li><button type="button" role="tab" aria-selected="false" data-v="todo">Da fare <b class="cnt" id="dcnt">2</b></button></li>
              <li><button type="button" role="tab" aria-selected="false" data-v="bandi">Bandi e agevolazioni</button></li>
              <li><button type="button" role="tab" aria-selected="false" data-v="prof">Profilo</button></li>
            </ul>
          </aside>
          <div class="pann">
            <div class="dv on" data-p="pan" role="tabpanel">
              <p class="ciao">CIAO, GIULIA</p>
              <h2>La tua panoramica</h2>
              <div class="ag"><img src="/og-avatar.jpg?v=2" alt="" width="40" height="40" loading="lazy"><div><p><b>Sono il tuo agente IA.</b> La prossima scadenza è tra 21 giorni: vuoi vedere come ho calcolato l'importo?</p><button type="button" class="dbtn" id="dcalc" aria-expanded="false">Sì, mostramelo</button></div></div>
              <div class="dcalc" id="dcalcbox" hidden>
                <div class="dr"><span>Imposta sostitutiva · 2° acconto</span><b>1.140&nbsp;€</b></div>
                <div class="dr"><span>Contributi INPS · 2° acconto</span><b>1.000&nbsp;€</b></div>
                <div class="dr tot"><span>Da pagare entro il 30 novembre</span><b>2.140&nbsp;€</b></div>
                <p class="dnota">Calcolato sull'anno scorso, come prevede la legge. Ti preparo anche l'F24 già compilato.</p>
              </div>
              <div class="kpi">
                <div class="box">
                  <p class="lbl">INCASSI E SOGLIA DEL FORFETTARIO</p>
                  <p class="num">52.400&nbsp;€</p>
                  <p class="sotto" id="dmese">su 85.000&nbsp;€ l'anno · tocca un mese</p>
                  <div class="bars"><button type="button" class="bm" style="height:47%" data-m="Gennaio: 3.100&nbsp;€" aria-label="Gennaio: 3100 euro"></button><button type="button" class="bm" style="height:55%" data-m="Febbraio: 3.600&nbsp;€" aria-label="Febbraio: 3600 euro"></button><button type="button" class="bm" style="height:52%" data-m="Marzo: 3.400&nbsp;€" aria-label="Marzo: 3400 euro"></button><button type="button" class="bm" style="height:70%" data-m="Aprile: 4.600&nbsp;€" aria-label="Aprile: 4600 euro"></button><button type="button" class="bm" style="height:64%" data-m="Maggio: 4.200&nbsp;€" aria-label="Maggio: 4200 euro"></button><button type="button" class="bm" style="height:76%" data-m="Giugno: 5.000&nbsp;€" aria-label="Giugno: 5000 euro"></button><button type="button" class="bm" style="height:74%" data-m="Luglio: 4.900&nbsp;€" aria-label="Luglio: 4900 euro"></button><button type="button" class="bm" style="height:85%" data-m="Agosto: 5.600&nbsp;€" aria-label="Agosto: 5600 euro"></button><button type="button" class="bm" style="height:80%" data-m="Settembre: 5.300&nbsp;€" aria-label="Settembre: 5300 euro"></button><button type="button" class="bm" style="height:92%" data-m="Ottobre: 6.100&nbsp;€" aria-label="Ottobre: 6100 euro"></button><button type="button" class="bm on" style="height:100%" data-m="Novembre: 6.600&nbsp;€" aria-label="Novembre: 6600 euro"></button><i class="vuoto" style="height:12%"></i></div>
                  <div class="mesi"><span>GEN</span><span>APR</span><span>LUG</span><span>DIC</span></div>
                </div>
                <div class="lati">
                  <div class="box scura"><p class="lbl">DA METTERE DA PARTE</p><p class="num" style="font-size:24px">24% di ogni incasso</p><div class="prog"><i></i></div><p class="sotto" style="color:rgba(255,255,255,.75);margin-top:8px">Imposta e contributi stimati</p></div>
                  <div class="box oro"><p class="lbl" style="color:#4a4128">PROSSIMA SCADENZA</p><p class="data">30 novembre</p><p class="sotto" style="color:#4a4128">Secondo acconto · 2.140&nbsp;€</p></div>
                </div>
              </div>
            </div>
            <div class="dv" data-p="ott" role="tabpanel" hidden>
              <p class="ciao">OTTIMIZZAZIONE FISCALE</p>
              <h2>Ho letto le tue fatture</h2>
              <div class="ag"><img src="/og-avatar.jpg?v=2" alt="" width="40" height="40" loading="lazy"><p><b>Hai fatturato 14.000&nbsp;€ di siti web</b> come se fossero consulenza marketing. Hanno un coefficiente più basso: si paga meno, in regola.</p></div>
              <div class="dcmp">
                <div class="box"><p class="lbl">COME FAI ORA</p><p class="num">78%</p><p class="sotto">tutto come consulenza</p></div>
                <div class="box scura"><p class="lbl">CON IL CODICE GIUSTO</p><p class="num">67%</p><p class="sotto" style="color:rgba(255,255,255,.75)">per la parte dei siti web</p></div>
              </div>
              <div class="box dris"><p class="lbl">RISPARMIO STIMATO IN UN ANNO</p><p class="num" style="color:#087a63">circa 600&nbsp;€</p><p class="sotto">Tra imposta e contributi. Nel report trovi il calcolo passo per passo.</p></div>
            </div>
            <div class="dv" data-p="todo" role="tabpanel" hidden>
              <p class="ciao">DA FARE</p>
              <h2>Le tue prossime cose</h2>
              <ul class="dtodo">
                <li><button type="button" aria-pressed="false"><span class="ck"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg></span><span><b>Paga il secondo acconto</b><br>2.140&nbsp;€ entro il 30 novembre, l'F24 è pronto</span></button></li>
                <li><button type="button" aria-pressed="false"><span class="ck"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg></span><span><b>Carica le fatture di novembre</b><br>così aggiorno incassi e soglia</span></button></li>
                <li><button type="button" aria-pressed="true" class="fatto"><span class="ck"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg></span><span><b>Conferma il codice ATECO</b><br>fatto il 12 novembre</span></button></li>
              </ul>
              <p class="sotto" id="dfine" style="margin-top:14px">Tocca una voce per segnarla come fatta.</p>
            </div>
            <div class="dv" data-p="bandi" role="tabpanel" hidden>
              <p class="ciao">BANDI E AGEVOLAZIONI</p>
              <h2>Adatti a te</h2>
              <div class="box dband"><span class="dtag">Nuovo</span><p class="lbl">CONTRIBUTO REGIONALE · ESEMPIO</p><h3>Strumenti digitali per professionisti</h3><p class="sotto">Fino al 50% della spesa per computer e software. Domanda entro il 31 gennaio.</p><div class="dreq"><span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg> Partita IVA attiva</span><span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg> Sede in regione</span></div></div>
              <div class="box dband"><p class="lbl">RIDUZIONE CONTRIBUTI · ESEMPIO</p><h3>Controllo dei requisiti</h3><p class="sotto">Verifico se puoi pagare meno INPS e ti dico come chiederlo.</p></div>
            </div>
            <div class="dv" data-p="prof" role="tabpanel" hidden>
              <p class="ciao">PROFILO</p>
              <h2>Quello che so di te</h2>
              <div class="box dprof">
                <div class="dr"><span>Attività</span><b>Consulenza marketing e siti web</b></div>
                <div class="dr"><span>Regime</span><b>Forfettario, imposta al 15%</b></div>
                <div class="dr"><span>Contributi</span><b>Gestione separata INPS</b></div>
                <div class="dr"><span>Partita IVA aperta</span><b>2023</b></div>
              </div>
              <p class="sotto" style="margin-top:12px">Lo leggo dal certificato della partita IVA: niente moduli da compilare.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>


<script>
(function(){
  var v=document.getElementById("spotv"),b=document.getElementById("spota");if(!v||!b)return;
  var calma=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ON='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/></svg><span>Togli l\'audio</span>';
  var OFF=b.innerHTML;
  b.addEventListener("click",function(){var muto=!v.muted;v.muted=muto;if(!muto){v.currentTime=0;v.play().catch(function(){})}
    b.innerHTML=muto?OFF:ON;b.setAttribute("aria-pressed",muto?"false":"true")});
  if(calma){v.setAttribute("controls","");return}
  if("IntersectionObserver" in window){new IntersectionObserver(function(x){x.forEach(function(e){if(e.isIntersecting)v.play().catch(function(){});else v.pause()})},{threshold:.5}).observe(v)}
})();
</script>

<section class="calc sim" id="simula" aria-labelledby="t-sim">
  <span id="cosa-fa" class="ancora"></span><span id="calcola" class="ancora"></span>
  <div class="w">
    <div class="vedi">
      <p class="socchio">Simulatore gratuito</p>
      <h2 class="tit" id="t-sim">Quante tasse paghi, e quanto puoi risparmiare? <span class="ser">Scoprilo in un minuto.</span></h2>
      <p class="testo">Rispondi a quattro domande: stimiamo imposta e contributi 2026 e cerchiamo dove puoi pagare meno.</p>
    </div>
    <div class="cbox vedi">
      <div class="cin">
        <div><span class="lbl2" id="s-tipo-l">1. Che lavoro fai?</span>
          <div class="seg" role="group" aria-labelledby="s-tipo-l" data-q="tipo">
            <button type="button" data-v="pro" aria-pressed="true">Libero professionista</button>
            <button type="button" data-v="art" aria-pressed="false">Artigiano</button>
            <button type="button" data-v="com" aria-pressed="false">Commerciante</button>
          </div></div>
        <div><label class="lbl2" for="s-inc">2. Quanto incassi in un anno?</label>
          <div class="cval" id="s-incv" aria-hidden="true">30.000 €</div>
          <input type="range" id="s-inc" min="5000" max="85000" step="1000" value="30000" aria-valuetext="30.000 euro">
          <div class="crange" aria-hidden="true"><span>5.000 €</span><span>85.000 €</span></div></div>
        <div><span class="lbl2" id="s-ap-l">3. Quando hai aperto la partita IVA?</span>
          <div class="seg s2" role="group" aria-labelledby="s-ap-l" data-q="ap">
            <button type="button" data-v="nuova" aria-pressed="false">Meno di 5 anni fa</button>
            <button type="button" data-v="vecchia" aria-pressed="true">5 anni fa o più</button>
          </div>
          <div class="sub" id="s-sub5" hidden>
            <span class="lbl3" id="s-ali-l">Che imposta paghi oggi?</span>
            <div class="seg" role="group" aria-labelledby="s-ali-l" data-q="ali">
              <button type="button" data-v="15" aria-pressed="false">15%</button>
              <button type="button" data-v="5" aria-pressed="false">5%</button>
              <button type="button" data-v="ns" aria-pressed="true">Non lo so</button>
            </div></div></div>
        <div id="s-q4pro"><span class="lbl2" id="s-alt-l">4. Fai anche lavori di tipo diverso?</span>
          <p class="aiuto">Per esempio vendi corsi o prodotti digitali, gestisci siti o strumenti per i clienti.</p>
          <div class="seg s2" role="group" aria-labelledby="s-alt-l" data-q="alt">
            <button type="button" data-v="no" aria-pressed="true">No</button>
            <button type="button" data-v="si" aria-pressed="false">Sì, una parte</button>
          </div>
          <div class="sub" id="s-subalt" hidden>
            <label class="lbl3" for="s-quota">Quanto pesano sugli incassi? <b id="s-quotav">20%</b></label>
            <input type="range" id="s-quota" min="10" max="50" step="5" value="20" aria-valuetext="20 per cento">
          </div></div>
        <div id="s-q4ac" hidden><span class="lbl2" id="s-rid-l">4. Paghi già i contributi INPS ridotti del 35%?</span>
          <div class="seg" role="group" aria-labelledby="s-rid-l" data-q="rid">
            <button type="button" data-v="si" aria-pressed="false">Sì</button>
            <button type="button" data-v="no" aria-pressed="false">No</button>
            <button type="button" data-v="ns" aria-pressed="true">Non lo so</button>
          </div></div>
      </div>
      <div class="cout stima" aria-live="polite">
        <h3 class="sth"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6M9 11h6M9 15h3"/></svg>La tua stima</h3>
        <dl class="srow">
          <div><dt>Reddito imponibile</dt><dd id="s-red">–</dd></div>
          <div><dt>Contributi INPS</dt><dd id="s-inps" class="vela">●.●●● €</dd></div>
          <div><dt>Imposta sostitutiva</dt><dd id="s-imp" class="vela">●.●●● €</dd></div>
          <div class="sfo"><dt>Totale da versare</dt><dd id="s-tot" class="vela">●.●●● €</dd></div>
          <div><dt>Ti resta in tasca all'anno</dt><dd id="s-netto" class="vela">●●.●●● €</dd></div>
          <div><dt>Al mese</dt><dd id="s-mese" class="vela">●.●●● €</dd></div>
        </dl>
        <div class="rsp" id="s-rsp">
          <div class="rtop"><span class="rk">Puoi risparmiare</span><span class="rnum" id="s-rnum"><span class="vela">fino a ●.●●● €</span></span></div>
          <p class="rtit" id="s-rtit">Abbiamo trovato 1 modo per pagare meno</p>
          <ul class="rlis" id="s-rlis"></ul>
        </div>
        <form class="rform" id="s-form" novalidate>
          <p class="rinv"><b>Vedi il risultato completo</b><br>Lascia la tua email: ti mostriamo subito tasse, risparmio e netto.</p>
          <div class="rrow"><label class="sr" for="s-mail">La tua email</label>
            <input type="email" id="s-mail" name="email" placeholder="nome@email.it" autocomplete="email" required>
            <button type="submit" class="btn btn-acc btn-sm" id="s-btn">Mostra</button></div>
          <label class="chk rchk"><input type="checkbox" id="s-nov"><span>Voglio ricevere ogni tanto consigli per pagare meno tasse (facoltativo).</span></label>
          <p class="rpriv" id="s-err" role="alert"></p>
          <p class="rpriv">Ti mandiamo anche il riepilogo via email. <a href="/privacy">Privacy policy</a>.</p>
        </form>
        <div class="rok" id="s-ok" hidden>
          <ul class="lista sq" id="s-lista" aria-label="Quando paghi"></ul>
          <a class="btn btn-acc btn-sm" href="/colloquio/nuovo?utm_source=simulatore">Calcola sui miei numeri veri</a>
        </div>
        <p class="snota" id="s-nota"></p>
      </div>
    </div>
  </div>
</section>
<script type="application/json" id="c-dati">__CALC_DATI__</script>
<script>
(function(){
  var K={gs:.2607,gsMax:122295,min:18808,sog:56224,max:122295,art:{f:4521.36,a:.24,b:.25},com:{f:4611.64,a:.2448,b:.2548},ord:.15,st:.05,anno:2026};
  try{var j=JSON.parse(document.getElementById("c-dati").textContent);for(var k in j)K[k]=j[k]}catch(e){}
  var T={pro:{c:.78,nome:"libero professionista"},art:{c:.67,nome:"artigiano"},com:{c:.40,nome:"commerciante"}};
  var COEF_ALT=.67, RID=.35;
  var S={tipo:"pro",ap:"vecchia",ali:"ns",alt:"no",rid:"ns"},sbl=false;
  var $=function(i){return document.getElementById(i)};
  var r=$("s-inc"),rq=$("s-quota"),lis=$("s-lista");
  var eur=function(v){return String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g,".")+" €"};
  var MES=["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
  // reddito -> contributi e imposta (i contributi pagati si deducono dal reddito)
  function conti(red,aliq,rid){var fis=0,va;
    if(S.tipo==="pro"){va=Math.min(red,K.gsMax)*K.gs}
    else{var p=S.tipo==="art"?K.art:K.com,rr=Math.min(red,K.max),ecc=Math.max(0,rr-K.min),fino=Math.min(ecc,Math.max(0,K.sog-K.min));fis=p.f;va=fino*p.a+(ecc-fino)*p.b;
      if(rid){fis*=1-RID;va*=1-RID}}
    var imp=Math.max(0,red-fis-va)*aliq;return {fis:fis,va:va,imp:imp,tot:fis+va+imp}}
  function stato(){var inc=+r.value,c=T[S.tipo].c,q=S.tipo==="pro"&&S.alt==="si"?(+rq.value)/100:0;
    var aliq=S.ap==="nuova"&&S.ali==="5"?K.st:K.ord, ridOra=S.tipo!=="pro"&&S.rid==="si";
    var ora=conti(inc*c,aliq,ridOra),leve=[];
    if(S.ap==="nuova"&&S.ali!=="5"){var a=conti(inc*c,K.st,ridOra);if(ora.tot-a.tot>=1)leve.push({t:"Imposta al 5% invece del 15%",e:ora.tot-a.tot,d:"Nei primi 5 anni, se l'attività è davvero nuova (non è il lavoro che facevi prima da dipendente o da collaboratore), l'imposta è al 5%. Va verificato il requisito: TaxScan te lo controlla."})}
    var aliqL=leve.length?K.st:aliq;
    if(q>0){var red2=inc*(1-q)*c+inc*q*COEF_ALT,b=conti(inc*c,aliqL,ridOra),b2=conti(red2,aliqL,ridOra);if(b.tot-b2.tot>=1)leve.push({t:"Il coefficiente giusto per ogni attività",e:b.tot-b2.tot,d:"Le attività diverse dalla principale possono avere un coefficiente più basso (per esempio 67% invece di 78%): su quella parte si pagano meno tasse e meno contributi, in regola. Serve il codice ATECO giusto."})}
    if(S.tipo!=="pro"&&S.rid!=="si"){var x=conti(inc*c,aliqL,false),y=conti(inc*c,aliqL,true);if(x.tot-y.tot>=1)leve.push({t:"Contributi INPS ridotti del 35%",e:x.tot-y.tot,d:"Chi è nel forfettario come artigiano o commerciante può chiedere all'INPS la riduzione del 35% dei contributi (la domanda si fa di solito entro il 28 febbraio). Attenzione: riduce anche la pensione futura, va scelta con calma."})}
    return {inc:inc,ora:ora,leve:leve,tot:leve.reduce(function(s,l){return s+l.e},0)}}
  function rata(m,g,imp,cosa){return {m:m,g:g,imp:imp,cosa:cosa}}
  function put(id,txt,fin){var e=$(id);if(sbl){e.textContent=txt;e.classList.remove("vela")}else{e.textContent=fin;e.classList.add("vela")}}
  function disegna(){var st=stato(),c=st.ora,inc=st.inc,red=inc*T[S.tipo].c;
    $("s-incv").textContent=eur(inc);r.setAttribute("aria-valuetext",eur(inc).replace("€","euro"));
    $("s-quotav").textContent=rq.value+"%";rq.setAttribute("aria-valuetext",rq.value+" per cento");
    $("s-red").textContent=eur(red);
    put("s-inps",eur(c.fis+c.va),"●.●●● €");put("s-imp",eur(c.imp),"●.●●● €");put("s-tot",eur(c.tot),"●.●●● €");
    put("s-netto",eur(inc-c.tot),"●●.●●● €");put("s-mese",eur((inc-c.tot)/12),"●.●●● €");
    var n=st.leve.length;$("s-rsp").classList.toggle("zero",!n);
    $("s-rtit").textContent=n?("Abbiamo trovato "+(n===1?"1 modo":n+" modi")+" per pagare meno"):"Dai dati di base non vediamo risparmi immediati: spesso sono nelle fatture.";
    $("s-rnum").innerHTML=!n?"":(sbl?"fino a <b>"+eur(st.tot)+"</b> l'anno":'<span class="vela">fino a ●.●●● €</span>');
    $("s-rlis").innerHTML=st.leve.map(function(l){return '<li><div class="rl1"><span>'+l.t+'</span>'+(sbl?'<b class="re">'+eur(l.e)+'</b>':'<b class="re vela">●●● €</b>')+'</div>'+(sbl?'<p>'+l.d+'</p>':'')+'</li>'}).join("");
    if(sbl){var R=[rata(5,30,c.imp*.5+c.va*.6,"saldo e 1° acconto"),rata(10,30,c.imp*.5+c.va*.4,"2° acconto")];
      if(c.fis){R.push(rata(1,16,c.fis/4,"contributi fissi INPS"),rata(4,18,c.fis/4,"contributi fissi INPS"),rata(7,20,c.fis/4,"contributi fissi INPS"),rata(10,16,c.fis/4,"contributi fissi INPS"))}
      R.sort(function(a,b){return a.m-b.m||a.g-b.g});
      lis.innerHTML='<li class="lt"><span>Quando paghi, se incassi così ogni anno</span></li>'+R.map(function(x){return '<li><span>'+x.g+' '+MES[x.m].toLowerCase()+' · '+x.cosa+'</span><b>'+eur(x.imp)+'</b></li>'}).join("")}
    $("s-nota").textContent="Stima indicativa "+K.anno+" per "+T[S.tipo].nome+" con il coefficiente tipico ("+Math.round(T[S.tipo].c*100)+"%)"+(S.tipo==="pro"?" e gestione separata INPS":"")+"; i contributi pagati si deducono dal reddito. Non include acconti già versati e non è una consulenza."}
  [].forEach.call(document.querySelectorAll("#simula .seg"),function(g){var q=g.getAttribute("data-q");
    [].forEach.call(g.querySelectorAll("button"),function(b){b.addEventListener("click",function(){S[q]=b.getAttribute("data-v");
      [].forEach.call(g.querySelectorAll("button"),function(x){x.setAttribute("aria-pressed",x===b?"true":"false")});
      $("s-sub5").hidden=S.ap!=="nuova";$("s-subalt").hidden=S.alt!=="si";$("s-q4pro").hidden=S.tipo!=="pro";$("s-q4ac").hidden=S.tipo==="pro";disegna()})})});
  r.addEventListener("input",disegna);rq.addEventListener("input",disegna);disegna();
  // email: sblocca il risultato e manda il riepilogo
  $("s-form").addEventListener("submit",function(e){e.preventDefault();var m=$("s-mail").value.trim(),er=$("s-err");er.textContent="";
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(m)){er.textContent="Controlla l'email: sembra incompleta.";$("s-mail").focus();return}
    var st=stato(),btn=$("s-btn");btn.disabled=true;btn.textContent="Un attimo…";
    fetch("/api/simulatore",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:m,novita:$("s-nov").checked,
      dati:{tipo:S.tipo,incassi:st.inc,apertura:S.ap,aliquota:S.ali,altre_attivita:S.alt,quota_altre:S.alt==="si"?+rq.value:0,riduzione:S.rid},
      risultato:{totale:Math.round(st.ora.tot),netto:Math.round(st.inc-st.ora.tot),risparmio:Math.round(st.tot),leve:st.leve.map(function(l){return {titolo:l.t,euro:Math.round(l.e),spiegazione:l.d}})}})})
    .then(function(x){return x.json().then(function(j){return {ok:x.ok&&j.ok,j:j}})})
    .then(function(o){btn.disabled=false;btn.textContent="Mostrami il risparmio";if(!o.ok){er.textContent=(o.j&&o.j.errore)||"Non sono riuscito a salvare: riprova tra poco.";return}
      sbl=true;$("s-form").hidden=true;$("s-ok").hidden=false;$("simula").classList.add("aperto");disegna();if(typeof gtag==="function")try{gtag("event","simulatore_email")}catch(x){}})
    .catch(function(){btn.disabled=false;btn.textContent="Mostrami il risparmio";er.textContent="Connessione assente: riprova tra poco."})});
})();
</script>

<section class="sez" id="come-funziona" aria-labelledby="t-come">
  <div class="w due">
    <div class="vedi">
      <h2 class="tit" id="t-come">Non devi capire il fisco da solo.</h2>
      <p class="testo">Il tuo agente IA legge, deduce e poi ti chiede conferma. Ti propone sempre il passo successivo, senza gergo e senza interrogatori.</p>
    </div>
    <div class="passi">
      <article class="passo vedi">
        <span class="n">01</span>
        <div><h3>Rispondi a poche domande. O carica il certificato.</h3>
          <p>L'agente legge il certificato della partita IVA, riconosce il codice ATECO e la data di apertura e ti chiede solo quello che non può capire da solo. Si risponde con un tocco.</p></div>
        <span class="tag">2 minuti</span>
      </article>
      <article class="passo vedi">
        <span class="n">02</span>
        <div><h3>Carica 2 o 3 fatture. Al resto pensa l'agente.</h3>
          <p>Le legge in XML, PDF o foto per capire che lavoro fai davvero. Usa le descrizioni e gli importi: non conserva i file né i nomi dei tuoi clienti.</p></div>
        <span class="tag">Privacy prima di tutto</span>
      </article>
      <article class="passo vedi">
        <span class="n">03</span>
        <div><h3>Scopri se puoi pagare meno, in regola.</h3>
          <p>Confronta la tua situazione con i coefficienti delle attività che svolgi davvero, le riduzioni dei contributi INPS e gli acconti. Se non c'è risparmio, te lo dice chiaramente.</p></div>
        <span class="tag">Stima trasparente</span>
      </article>
    </div>
  </div>
</section>

<section class="sez" id="esempio" aria-labelledby="t-es">
  <div class="w due centro">
    <div class="vedi">
      <h2 class="tit" id="t-es" style="font-size:clamp(34px,4.2vw,56px)">Da «consulenza» a un quadro chiaro.</h2>
      <p class="testo">La storia è un esempio, ma il percorso è quello vero di TaxScan.</p>
    </div>
    <div class="storia vedi">
      <div class="chi"><span class="av" aria-hidden="true">G</span><div><b>Giulia, libera professionista</b><small>Supporto alla scrittura di tesi</small></div></div>
      <ol>
        <li>Carica le fatture, che dicono solo «consulenza».</li>
        <li>L'agente IA le chiede di raccontare con parole sue cosa fa davvero per i clienti.</li>
        <li>TaxScan trova le prestazioni che hanno un coefficiente più basso, come ricerca, grafica e impaginazione.</li>
        <li>Giulia vede il prima e il dopo in euro, riceve il report e segue i passi in Da fare, uno alla volta.</li>
      </ol>
      <p class="zero">Se il risparmio è zero, TaxScan lo dice subito. Anche questo è un risultato utile.</p>
    </div>
  </div>
</section>

<section class="sez" id="prezzo" aria-labelledby="t-prezzo" style="padding-top:0">
  <div class="w">
    <div class="prezzo vedi">
      <div>
        <span class="pill">Offerta di lancio</span>
        <h2 class="tit" id="t-prezzo" style="font-size:clamp(32px,4vw,52px)">Prima scopri il risparmio. Poi decidi.</h2>
        <div class="cifra"><b>47&nbsp;€</b><s aria-label="invece di 589 euro">589&nbsp;€</s><span>per 12 mesi · un solo pagamento</span></div>
        <ul class="incl">
          <li>Il report completo dell'Ottimizzazione fiscale, con il tuo nome</li>
          <li>Da fare: i passi guidati e le fatture riscritte</li>
          <li>Bandi e agevolazioni per la tua attività</li>
        </ul>
        <p class="gratis">Restano sempre gratis: le domande, la Panoramica con le scadenze, quanto mettere da parte e il profilo.</p>
      </div>
      <div>
        <div class="gar"><svg viewBox="0 0 36 36" aria-hidden="true"><path d="M18 3l12 4.5v9c0 7.6-5.1 13.6-12 16.5C11.1 30.1 6 24.1 6 16.5v-9L18 3z" fill="#e6faf7" stroke="#05c4b8" stroke-width="2.2" stroke-linejoin="round"/><path d="M12.5 18l3.8 3.8 7.2-7.6" fill="none" stroke="#087a63" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <p><b>Garanzia soddisfatto o rimborsato.</b> Se non ottieni un risparmio fiscale almeno doppio rispetto al costo del software, ti rimborsiamo tutto e non paghi.</p></div>
        <div class="azioni">
          <a class="btn btn-acc" href="/colloquio/nuovo">Scopri il tuo risparmio, gratis</a>
          <a class="btn btn-light" href="/acquista?utm_source=home_prezzo">Cosa include</a>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="w" aria-labelledby="t-invito">
  <div class="invito vedi">
    <div class="puntini" aria-hidden="true"></div>
    <p class="sopra">La prima analisi è gratis</p>
    <h2 id="t-invito">Scopri cosa puoi<br><span class="ser">davvero risparmiare.</span></h2>
    <p class="l">Rispondi a poche domande, carica le tue fatture e ottieni una stima trasparente. Nessuna promessa: se il risparmio non c'è, te lo diciamo.</p>
    <a class="btn" href="/colloquio/nuovo">Scopri quanto puoi risparmiare <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
    <small>2 minuti · I file delle fatture non vengono conservati</small>
  </div>
</section>

<section class="sez" id="domande" aria-labelledby="t-faq">
  <div class="w due">
    <div class="vedi">
      <h2 class="tit" id="t-faq" style="font-size:clamp(36px,5vw,60px)">Dubbi? Facciamo chiarezza.</h2>
      <p class="testo">Hai un'altra domanda? Chiedila al tuo agente IA: <a href="/colloquio/nuovo" style="color:var(--accent-ink);font-weight:600">inizia da qui</a>.</p>
    </div>
    <div class="faq vedi">
      <details open><summary>TaxScan sostituisce il commercialista?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>No. TaxScan prepara e spiega: puoi gestire tutto da solo, assumendoti la responsabilità di ciò che dichiari e paghi, oppure far controllare numeri e report a un professionista quando vuoi.</p></details>
      <details><summary>Posso parlare con un consulente vero?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Sì. TaxScan ti prepara i numeri, ma se la tua situazione è particolare o vuoi una conferma puoi parlare con un consulente in carne e ossa. La prima consulenza è gratuita: <a href="https://calendly.com/ltd24ore?utm_source=taxscan_home" target="_blank" rel="noopener">prenotala qui</a>.</p></details>
      <details><summary>Devo registrarmi per provarlo?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Per iniziare no. L'email te la chiediamo per salvarti la situazione, mandarti le scadenze e, se vuoi, il report.</p></details>
      <details><summary>Le mie fatture vengono salvate?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>No. TaxScan legge le righe del lavoro e gli importi, non conserva i file né il nome dei tuoi clienti. I dettagli sono nella <a href="/privacy">privacy policy</a>.</p></details>
      <details><summary>Quanto posso risparmiare?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Dipende dal lavoro che fai davvero. Se alcune prestazioni rientrano in attività con un coefficiente più basso, o se hai diritto a riduzioni dei contributi, vedi una stima in euro. Altrimenti il risultato è zero, senza promesse forzate.</p></details>
      <details><summary>È legale?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Sì, quando le attività le svolgi davvero, le fatturi separatamente e il codice ATECO è attivo sulla partita IVA. TaxScan usa solo quello che la legge prevede per il forfettario; ogni cifra è una stima da verificare.</p></details>
      <details><summary>Quanto costa?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary><p>Le domande, la Panoramica, le scadenze e quanto mettere da parte sono gratis. Con l'offerta di lancio sblocchi il report dell'Ottimizzazione fiscale, Da fare e Bandi: 12 mesi a 47&nbsp;€ invece di 589&nbsp;€, soddisfatto o rimborsato. <a href="/acquista?utm_source=home_faq">Vedi i dettagli</a>.</p></details>
    </div>
  </div>
</section>
</main>
<script>
(function(){
  var d=document.getElementById("demo");if(!d)return;
  var tabs=d.querySelectorAll(".lato button"),pans=d.querySelectorAll(".dv");
  tabs.forEach(function(t){t.addEventListener("click",function(){
    try{t.scrollIntoView({block:"nearest",inline:"nearest"})}catch(e){}
    tabs.forEach(function(x){var s=x===t;x.classList.toggle("on",s);x.setAttribute("aria-selected",s?"true":"false")});
    pans.forEach(function(p){var s=p.getAttribute("data-p")===t.getAttribute("data-v");p.hidden=!s;p.classList.toggle("on",s)});
  })});
  var c=document.getElementById("dcalc"),cb=document.getElementById("dcalcbox");
  if(c)c.addEventListener("click",function(){var o=cb.hidden;cb.hidden=!o;c.setAttribute("aria-expanded",o?"true":"false");c.textContent=o?"Chiudi il calcolo":"Sì, mostramelo"});
  var m=document.getElementById("dmese"),m0=m?m.innerHTML:"";
  d.querySelectorAll(".bm").forEach(function(b){
    function on(){d.querySelectorAll(".bm.sel").forEach(function(x){x.classList.remove("sel")});b.classList.add("sel");m.innerHTML="<b>"+b.getAttribute("data-m")+"</b> incassati"}
    b.addEventListener("click",on);b.addEventListener("mouseenter",on);b.addEventListener("focus",on);
  });
  var bars=d.querySelector(".bars");if(bars)bars.addEventListener("mouseleave",function(){d.querySelectorAll(".bm.sel").forEach(function(x){x.classList.remove("sel")});m.innerHTML=m0});
  var n=document.getElementById("dcnt"),fine=document.getElementById("dfine");
  function conta(){var k=d.querySelectorAll(".dtodo button:not(.fatto)").length;n.textContent=k;n.classList.toggle("zero",k===0);if(k===0)fine.textContent="Tutto fatto. Ti avviso io quando arriva la prossima scadenza."}
  d.querySelectorAll(".dtodo button").forEach(function(b){b.addEventListener("click",function(){var f=!b.classList.contains("fatto");b.classList.toggle("fatto",f);b.setAttribute("aria-pressed",f?"true":"false");conta()})});
})();
</script>


<footer class="piede">
  <div class="w">
    <div class="cols">
      <div><a class="logo" href="/">Tax<span>Scan</span></a><p>Il primo agente IA specializzato nel risparmio fiscale per chi ha la partita IVA in regime forfettario.</p></div>
      <div><h4>Prodotto</h4><nav aria-label="Prodotto"><a href="#come-funziona">Come funziona</a><a href="#simula">Simulatore</a><a href="/acquista?utm_source=home_piede">Prezzi</a><a href="/accedi">Accedi</a></nav></div>
      <div><h4>Informazioni</h4><nav aria-label="Informazioni"><a href="/termini">Termini e condizioni</a><a href="/privacy">Privacy policy</a><a href="#" class="tsck-open">Cookie</a></nav></div>
    </div>
    <div class="legale">
      <p>TaxScan prepara e spiega: sono stime a scopo informativo, calcolate sui dati che inserisci tu. Puoi gestire tutto da solo, assumendoti la responsabilità di ciò che dichiari e paghi, oppure far controllare le cifre a un professionista quando vuoi. Non è una consulenza.</p>
      <p class="by">TaxScan è un servizio offerto da <a href="https://ltd24.co.uk" target="_blank" rel="noopener"><picture><source srcset="/logo-ltd24-scuro.png" media="(prefers-color-scheme: dark)"><img src="/logo-ltd24.png" alt="LTD24" onerror="this.replaceWith(document.createTextNode('LTD24'))"></picture></a></p>
    </div>
  </div>
</footer>

<script>
(function(){
  var calma=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  // la parola che cambia nel titolo: lo spazio e' largo quanto la parola piu' lunga, cosi' "Più" resta fermo
  var parole=["risparmio.","chiarezza.","controllo.","tempo.","serenità."],i=0,box=document.querySelector(".giro"),g=document.getElementById("giro");
  function misura(){if(!box||!g)return;box.style.width="";var m=0,t=g.textContent;parole.forEach(function(p){g.textContent=p;m=Math.max(m,g.getBoundingClientRect().width)});g.textContent=t;box.style.width=Math.ceil(m+2)+"px"}
  if(box&&g){misura();if(document.fonts&&document.fonts.ready)document.fonts.ready.then(misura);addEventListener("resize",misura);
    if(!calma)setInterval(function(){i=(i+1)%parole.length;var s=document.createElement("span");s.id="giro";s.textContent=parole[i];g.replaceWith(s);g=s},2500)}
  // menu del telefono
  var h=document.getElementById("ham"),m=document.getElementById("menu");
  if(h&&m){h.addEventListener("click",function(){var on=m.classList.toggle("on");h.setAttribute("aria-expanded",on?"true":"false");h.setAttribute("aria-label",on?"Chiudi il menu":"Apri il menu")});
    m.addEventListener("click",function(e){if(e.target.tagName==="A"){m.classList.remove("on");h.setAttribute("aria-expanded","false")}})}
  // riga sotto la testata quando si scorre
  var t=document.getElementById("top");function su(){t.classList.toggle("su",scrollY>8)}addEventListener("scroll",su,{passive:true});su();
  // comparsa morbida delle sezioni
  var v=document.querySelectorAll(".vedi");
  if(!("IntersectionObserver" in window)||calma){v.forEach(function(e){e.classList.add("on")});return}
  var o=new IntersectionObserver(function(x){x.forEach(function(e){if(e.isIntersecting){e.target.classList.add("on");o.unobserve(e.target)}})},{threshold:.12,rootMargin:"0px 0px -40px 0px"});
  v.forEach(function(e){o.observe(e)});
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
<title>Accedi - TaxScan</title><link rel="icon" href="/favicon.ico?v=2" sizes="any"><link rel="icon" type="image/png" sizes="48x48" href="/favicon-48.png?v=2"><link rel="apple-touch-icon" href="/apple-touch-icon.png?v=2">
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
.logo{font-family:"Poppins",var(--f-tit);font-weight:700;font-size:22px;line-height:1.05;margin-bottom:28px}.logo span{color:var(--accent-ink)}
h1{font-size:26px;line-height:1.15;margin-bottom:8px}
.lead{color:var(--ink2);margin-bottom:18px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px}
input{width:100%;padding:14px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;margin-bottom:10px}
button{width:100%;border:0;border-radius:12px;padding:14px;background:var(--accent);color:#fff;font:inherit;font-weight:700;cursor:pointer}
.msg{font-size:14px;color:var(--ink2);margin-top:10px;min-height:20px}.msg.err{color:var(--crit)}
a{color:var(--accent-ink);font-weight:600}
.by{font-size:12px;color:var(--ink2);margin-top:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}.by a{display:inline-flex;color:var(--ink);font-weight:700;text-decoration:none}.by img{height:20px;width:auto}
.legal{font-size:13px;color:var(--ink2);margin:14px 0 0}.legal a{color:inherit;font-weight:600}
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
<p class="legal"><a href="/termini">Termini e condizioni</a> · <a href="/privacy">Privacy policy</a> · <a href="#" class="tsck-open">Cookie</a></p>
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


# Il calcolatore della home usa le stesse regole dell'app: i numeri arrivano da dati_fisco (unico file da aggiornare ogni anno).
try:
    import json as _json
    import dati_fisco as _D
    _AC = _D.ARTIGIANI_COMMERCIANTI
    _CALC = {"gs": _D.GESTIONE_SEPARATA["aliquota_senza_altra_copertura"], "gsMax": _D.GESTIONE_SEPARATA["massimale"],
             "min": _AC["minimale_reddito"], "sog": _AC["soglia_aliquota_maggiorata"], "max": _AC["massimale_post_1996"],
             "art": {"f": _AC["artigiani"]["fisso_annuo"], "a": _AC["artigiani"]["aliquota"], "b": _AC["artigiani"]["aliquota_oltre_soglia"]},
             "com": {"f": _AC["commercianti"]["fisso_annuo"], "a": _AC["commercianti"]["aliquota"], "b": _AC["commercianti"]["aliquota_oltre_soglia"]},
             "ord": _D.ALIQUOTA_ORDINARIA, "st": _D.ALIQUOTA_STARTUP, "anno": _D.ANNO}
    PAGINA_HTML = PAGINA_HTML.replace("__CALC_DATI__", _json.dumps(_CALC))
except Exception:
    PAGINA_HTML = PAGINA_HTML.replace("__CALC_DATI__", "{}")
