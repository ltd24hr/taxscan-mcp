# TaxScan — versione leggera (MVP)

## Cos'è
Un connettore che trasforma Claude in un assistente per le partite IVA in regime forfettario.
Non entra nell'Agenzia delle Entrate e non conserva nessun dato: i numeri li dice l'utente,
il software calcola.

## Cosa sa fare
1. Dice il coefficiente di redditività partendo dal codice ATECO del singolo cliente.
2. Calcola reddito, contributi INPS e imposta sostitutiva, con il netto che resta in tasca.
3. Avvisa se il cliente rischia di superare gli 85.000 € (e i 100.000 €).
4. Elenca le prossime scadenze fiscali e contributive.
5. Verifica i requisiti di accesso e permanenza nel regime.
6. Propone la consulenza gratuita.

## Come metterlo online
Identica procedura del server Ltd24: carica i file su GitHub in un nuovo repository
(chiamalo taxscan-mcp), poi su Render crea un nuovo Web Service da quel repository.
L'indirizzo finale sarà tipo https://taxscan-mcp.onrender.com/mcp

## Prima di venderlo
Fai controllare i calcoli e i parametri a un commercialista italiano. I valori inseriti sono
quelli ufficiali 2026, ma la responsabilità verso i clienti paganti è di chi firma.

## Da aggiornare ogni gennaio
Solo il file dati_fisco.py: minimale INPS, contributi fissi, aliquote e soglie cambiano ogni anno.
