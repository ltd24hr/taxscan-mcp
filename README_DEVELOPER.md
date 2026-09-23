# TaxScan MCP server (MVP) — developer notes

Public, stateless MCP server for the Italian "regime forfettario". No database, no personal data
stored, no connection to the Agenzia delle Entrate: every figure is supplied by the user at
call time. Python + FastMCP, Streamable HTTP, endpoint `/mcp`.

## Files
- `dati_fisco.py` — all 2026 tax parameters (coefficients, INPS rates, thresholds, deadlines).
  The ONLY file to update each year.
- `calcoli.py` — pure calculation functions, no MCP dependency.
- `server.py` — the six MCP tools.

## Tools
`coefficiente_ateco`, `calcola_tasse_forfettario`, `monitora_soglia_85000`, `scadenze_fiscali`,
`verifica_requisiti_forfettario`, `prenota_consulenza`.

## Run and deploy
    pip install -r requirements.txt && python server.py     # http://localhost:8000/mcp
Deploy the Dockerfile on Render / Railway / Fly.io (uses `$PORT`). Same procedure already used
for the Ltd24 server.

## Known simplifications (intentional for the MVP)
- Contributions are deducted on an accrual basis unless `contributi_versati_nell_anno` is passed;
  the real rule is cash basis.
- Professional funds (`gestione='cassa'`) use a single flat rate, no minimum contributions.
- ATECO mapping follows the Allegato 4 groups by division prefix. Divisions 46 and 47 are flagged
  as ambiguous because of the ATECO 2025 reclassification (DL 81/2025).
- No handling of partial-year activity, multiple ATECO codes, or regional surcharges (not due
  under this scheme).

## Before charging customers for this
Have a qualified Italian professional (commercialista or tributarista) review `dati_fisco.py`
and the logic in `calcoli.py`, and sign off on the disclaimer wording.
