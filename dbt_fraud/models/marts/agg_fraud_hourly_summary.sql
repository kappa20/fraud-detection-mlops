-- Produit analytique ("Data Product", Chapitre 1) : synthèse horaire du
-- taux de fraude, consommable directement par un tableau de bord ou un
-- Data Analyst sans passer par les tables détaillées. Réutilise
-- hour_of_day déjà calculé dans fct_transactions_features (principe Lean
-- "Simplify and Reuse" du Chapitre 2 plutôt que de recalculer).

select
    hour_of_day,
    count(*) as nb_transactions,
    sum(is_fraud) as nb_fraud,
    round(sum(is_fraud)::double / count(*), 6) as fraud_rate,
    round(avg(amount), 2) as avg_amount
from {{ ref('fct_transactions_features') }}
group by 1
order by 1
