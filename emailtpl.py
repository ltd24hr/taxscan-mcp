"""
Modello grafico delle email di TaxScan (colori e font del marchio LTD24).

Nota: molti programmi di posta (Gmail in particolare) non caricano font esterni. Per questo il font e'
indicato con una lista di ripiego: dove c'e' Poppins/Rethink Sans si vedono, altrove un carattere pulito
di sistema. I colori e il logo si vedono ovunque.
"""
import html as _html
import os

PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://taxscan-mcp.onrender.com").rstrip("/")
FONT_TIT = "Rethink Sans,Poppins,-apple-system,Segoe UI,Roboto,Arial,sans-serif"
FONT_TXT = "Poppins,-apple-system,Segoe UI,Roboto,Arial,sans-serif"

_STILE = (
    "<style>"
    f"@font-face{{font-family:'Poppins';font-weight:400;src:url({PUBLIC_URL}/font/Poppins-Regular.ttf) format('truetype')}}"
    f"@font-face{{font-family:'Poppins';font-weight:700;src:url({PUBLIC_URL}/font/Poppins-Bold.ttf) format('truetype')}}"
    f"@font-face{{font-family:'Rethink Sans';font-weight:400 800;"
    f"src:url({PUBLIC_URL}/font/RethinkSans-VariableFont_wght.ttf) format('truetype')}}"
    "</style>"
)


def _e(x) -> str:
    return _html.escape(str(x if x is not None else ""))


def cornice(titolo: str, corpo: str, pulsante: tuple | None = None, piede: str = "") -> str:
    bottone = ""
    if pulsante:
        bottone = (f"<p style='margin:24px 0'><a href='{_e(pulsante[1])}' style='background:#4355cc;color:#ffffff;"
                   f"text-decoration:none;padding:14px 24px;border-radius:0;font-weight:700;display:inline-block;"
                   f"font-family:{FONT_TXT}'>{_e(pulsante[0])}</a></p>")
    return (
        _STILE +
        f"<div style='background:#eef2f8;padding:24px 12px;font-family:{FONT_TXT}'>"
        "<div style='max-width:560px;margin:0 auto;background:#ffffff;color:#122452;line-height:1.6;font-size:15px'>"
        "<div style='background:#122452;padding:18px 24px'>"
        f"<span style='font-family:{FONT_TIT};font-size:22px;font-weight:800;color:#ffffff;vertical-align:middle'>"
        "Tax<span style='color:#05d5c8'>Scan</span></span>"
        f"<img src='{PUBLIC_URL}/logo-ltd24-scuro.png' alt='LTD24' height='22' "
        "style='height:22px;float:right;margin-top:2px;border:0'>"
        "</div>"
        "<div style='height:4px;background:#05d5c8'></div>"
        "<div style='padding:26px 24px'>"
        f"<h1 style='font-family:{FONT_TIT};font-size:22px;line-height:1.25;margin:0 0 14px;color:#122452'>{_e(titolo)}</h1>"
        f"{corpo}{bottone}{piede}"
        "</div></div></div>"
    )
