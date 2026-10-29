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


def _via_anthropic(sistema: str, utente: str, max_token: int, modello: str = "") -> str:
    import assistente
    r = requests.post(assistente.API_URL, headers=assistente.intestazioni(), timeout=75,
                      json={"model": modello or assistente.MODELLO, "max_tokens": max_token, "system": sistema,
                            "messages": [{"role": "user", "content": utente}]})
    if r.status_code >= 400:
        raise RuntimeError(f"anthropic {r.status_code}: {r.text[:200]}")
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()


def _via_openrouter(sistema: str, utente: str, max_token: int, modello: str = "", attesa: int = 75) -> str:
    modello = (modello or os.environ.get("OPENROUTER_MODELLO") or "anthropic/claude-sonnet-4.5").strip()
    r = requests.post(OPENROUTER_URL, timeout=attesa,
                      headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"].strip(),
                               "content-type": "application/json", "X-Title": "TaxScan"},
                      json={"model": modello, "max_tokens": max_token,
                            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": utente}]})
    if r.status_code >= 400:
        raise RuntimeError(f"openrouter {r.status_code}: {r.text[:200]}")
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


# modello veloce per i compiti brevi (codici ATECO, suggerimenti): se non risponde si ripiega sul modello normale
MODELLO_VELOCE = (os.environ.get("AI_MODELLO_VELOCE") or "claude-haiku-4-5-20251001").strip()


def genera(sistema: str, utente: str, max_token: int = 1200, veloce: bool = False) -> str:
    """Una domanda, una risposta di testo. Se Anthropic fallisce e c'e' anche OpenRouter, prova con quella.
    veloce=True: usa il modello piu' rapido (compiti brevi); se fallisce, riprova con quello normale."""
    errore = None
    if _anthropic():
        if veloce and MODELLO_VELOCE:
            try:
                return _via_anthropic(sistema, utente, max_token, MODELLO_VELOCE)
            except Exception as e:
                print(f"ai: modello veloce non risponde, uso quello normale: {e}")
        try:
            return _via_anthropic(sistema, utente, max_token)
        except Exception as e:
            errore = e
            print(f"ai: anthropic non risponde: {e}")
            if not _openrouter():
                raise
    if _openrouter():
        return _via_openrouter(sistema, utente, max_token)
    raise errore or RuntimeError("nessuna chiave AI configurata")


def diagnosi() -> dict:
    """Prova reale, per capire perche' l'AI non risponde (pagina /admin/ai)."""
    out = {"anthropic_chiave": _anthropic(), "openrouter_chiave": _openrouter(),
           "openrouter_modello": (os.environ.get("OPENROUTER_MODELLO") or "(non impostato: uso anthropic/claude-sonnet-4.5)"),
           "ottimizzazione_modello": MODELLO_OTTIMIZZA + (" (via OpenRouter)" if _openrouter() else " (OpenRouter non configurato: uso il modello normale)")}
    for nome, f, ok in (("anthropic", _via_anthropic, _anthropic()), ("openrouter", _via_openrouter, _openrouter())):
        if not ok:
            out[nome] = "chiave non impostata"
            continue
        try:
            t = f("Rispondi solo con la parola: ok", "Test", 20)
            out[nome] = "FUNZIONA (risposta: %s)" % (t[:30] or "vuota")
        except Exception as e:
            out[nome] = "ERRORE: %s" % str(e)[:300]
    return out


# modello per il lavoro piu' importante (le micro-attivita' dell'ottimizzazione fiscale): Claude Opus 5.5 su OpenRouter
MODELLO_OTTIMIZZA = (os.environ.get("OTTIMIZZA_MODELLO") or "anthropic/claude-opus-5.5").strip()


def genera_json_ottimizza(sistema: str, utente: str, max_token: int = 4000):
    """Come genera_json, ma con Claude Opus 5.5 su OpenRouter (OTTIMIZZA_MODELLO per cambiarlo).
    Se OpenRouter non c'e' o non risponde, ripiega sul modello normale. Ritorna (json, modello usato)."""
    sis = sistema + "\nRispondi SOLO con un oggetto JSON valido, senza testo prima o dopo e senza markdown."
    testo, usato = "", ""
    if _openrouter():
        try:
            testo, usato = _via_openrouter(sis, utente, max_token, MODELLO_OTTIMIZZA, 170), MODELLO_OTTIMIZZA
        except Exception as e:
            print(f"ai: {MODELLO_OTTIMIZZA} su openrouter non risponde, uso il modello normale: {e}")
    if not testo:
        testo, usato = genera(sis, utente, max_token), "normale"
    m = re.search(r"\{.*\}", testo, re.S)
    if not m:
        return None, usato
    try:
        return json.loads(m.group(0)), usato
    except ValueError:
        return None, usato


def genera_json(sistema: str, utente: str, max_token: int = 1500, veloce: bool = False):
    """Come genera(), ma si aspetta un oggetto JSON nella risposta. None se non lo trova."""
    testo = genera(sistema + "\nRispondi SOLO con un oggetto JSON valido, senza testo prima o dopo e senza markdown.",
                   utente, max_token, veloce)
    m = re.search(r"\{.*\}", testo, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None
