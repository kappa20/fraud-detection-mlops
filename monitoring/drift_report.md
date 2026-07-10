# Rapport de dérive (Livrable 9)

Référence : 142403 transactions (1ère moitié temporelle) — Récent : 142404 transactions (2nde moitié temporelle).

| Colonne | PSI | Interprétation |
|---|---|---|
| amount | 0.0027 | pas de dérive significative |
| log_amount | 0.0027 | pas de dérive significative |
| hour_of_day | 0.0034 | pas de dérive significative |

Comparaison avec 2 prédictions réelles journalisées par l'API (`monitoring/predictions_log.jsonl`) :

| Colonne | PSI | Interprétation |
|---|---|---|
| amount (trafic API) | 12.4461 | dérive significative — ré-entraînement à envisager |
