{# Test générique "domaine de valeurs" (Chapitre 3, famille "Tests de
   Contenu"), écrit à la main plutôt que d'ajouter une dépendance externe
   (dbt_utils/dbt-expectations) pour un seul test. #}

{% test accepted_range(model, column_name, min_value=none, max_value=none) %}

select *
from {{ model }}
where
    {% if min_value is not none %}
    {{ column_name }} < {{ min_value }}
    {% if max_value is not none %} or {% endif %}
    {% endif %}
    {% if max_value is not none %}
    {{ column_name }} > {{ max_value }}
    {% endif %}

{% endtest %}
