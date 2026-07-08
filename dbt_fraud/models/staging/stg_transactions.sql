-- Staging : typage et renommage des colonnes brutes, ajout d'une clé
-- surrogate stable (transaction_id) réutilisant l'identifiant unique déjà
-- attribué par dlt à chaque ligne ingérée (_dlt_id), et conservation du
-- load_id dlt pour la traçabilité (quelle exécution d'ingestion a produit
-- cette ligne — cf. les "5 Q" de traçabilité du Chapitre 1).

select
    _dlt_id as transaction_id,
    _dlt_load_id as load_id,
    time as time_seconds,
    v1, v2, v3, v4, v5, v6, v7, v8, v9, v10,
    v11, v12, v13, v14, v15, v16, v17, v18, v19, v20,
    v21, v22, v23, v24, v25, v26, v27, v28,
    amount,
    class as is_fraud
from {{ source('raw', 'transactions_raw') }}
