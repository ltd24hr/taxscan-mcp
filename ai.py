"""Livello unico per l'intelligenza artificiale di TaxScan (suggerimenti dalle fatture, codice ATECO, task, chat).

Funziona con UNA di queste chiavi, messa come variabile d'ambiente su Render (mai nel codice, mai in chat):
  ANTHROPIC_API_KEY    chiave Anthropic (modello: ASSISTENTE_MODELLO, default quello dell'assistente)
  OPENROUTER_API_KEY   chiave OpenRouter (modello: OPENROUTER_MODELLO, es. "anthropic/claude-sonnet-4.5")
Se ci sono entrambe si usa Anthropic. Senza chiavi attiva() e' False e l'app usa le liste fisse.
"""
import json
import os
import re

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _anthropic() -> bool:
    return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())


def _openrouter() -> bool:
    return bool((os.environ.get("OPENROUTER_API_KEY") or "").strip())


def attiva() -> bool:
    return _anthropic() or _openrouter()


def fornitore() -> str:
    return "anthropic" if _anthropic() else "openrouter" if _openrouter() else ""


def genera(sistema: str, utente: str, max_token: int = 1200) -> str:
    """Una domanda, una risposta di testo. Solleva RuntimeError se la chiamata fallisce."""
    if _anthropic():
        import assistente
        r = requests.post(assistente.API_URL, headers=assistente.intestazioni(), timeout=75,
                          json={"model": assistente.MODELLO, "max_tokens": max_token, "system": sistema,
                                "messages": [{"role": "user", "content": utente}]})
        if r.status_code >= 400:
            raise RuntimeError(f"anthropic {r.status_code}: {r.text[:200]}")
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()
    if _openrouter():
        modello = (os.environ.get("OPENROUTER_MODELLO") or "anthropic/claude-sonnet-4.5").strip()
        r = requests.post(OPENROUTER_URL, timeout=75,
                          headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"].strip(),
                                   "content-type": "application/json", "X-Title": "TaxScan"},
                          json={"model": modello, "max_tokens": max_token,
                                "messages": [{"role": "system", "content": sistema},
                                             {"role": "user", "content": utente}]})
        if r.status_code >= 400:
            raise RuntimeError(f"openrouter {r.status_code}: {r.text[:200]}")
        return (r.json()["choices"][0]["message"]["content"] or "").strip()
    raise RuntimeError("nessuna chiave AI configurata")


def genera_json(sistema: str, utente: str, max_token: int = 1500):
    """Come genera(), ma si aspetta un oggetto JSON nella risposta. None se non lo trova."""
    testo = genera(sistema + "\nRispondi SOLO con un oggetto JSON valido, senza testo prima o dopo e senza markdown.",
                   utente, max_token)
    m = re.search(r"\{.*\}", testo, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None
