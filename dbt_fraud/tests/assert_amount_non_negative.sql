-- Test singulier (Chapitre 3, famille "Tests Métier" — cohérence métier) :
-- un dbt test réussit quand la requête ne retourne aucune ligne.
select *
from {{ ref('fct_transactions_clean') }}
where amount < 0
