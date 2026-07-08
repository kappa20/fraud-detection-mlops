-- Features dérivées honnêtes : on ne fabrique pas de colonnes métier
-- fictives sur les composantes PCA (V1-V28, anonymisées et opaques par
-- construction — voir docs/01_vision.md, section Data Strategy). On se
-- limite à des dérivations légitimes des seules colonnes interprétables
-- (time_seconds, amount), utilisées ensuite par ml/prepare_data.py.

select
    transaction_id,
    load_id,
    time_seconds,
    floor((time_seconds % 86400) / 3600.0)::integer as hour_of_day,
    v1, v2, v3, v4, v5, v6, v7, v8, v9, v10,
    v11, v12, v13, v14, v15, v16, v17, v18, v19, v20,
    v21, v22, v23, v24, v25, v26, v27, v28,
    amount,
    ln(amount + 1) as log_amount,
    case
        when amount = 0 then 'zero'
        when amount < 10 then 'low'
        when amount < 100 then 'medium'
        when amount < 1000 then 'high'
        else 'very_high'
    end as amount_bucket,
    is_fraud
from {{ ref('fct_transactions_clean') }}
