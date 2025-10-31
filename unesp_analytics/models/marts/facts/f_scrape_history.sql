{{
  config(
    materialized='table',
    schema='analytics'
  )
}}

SELECT
    h.scrape_id,
    h.page_id,
    
    COALESCE(
        r.responsavel_id,
        'N/A'
    ) AS responsavel_id,

    h.scrape_timestamp,
    h.modified_date,
    h.full_modified_text,
    
    (h.scrape_timestamp::date - h.modified_date) AS dias_desde_modificacao

FROM
    {{ ref('stg_scrape_history') }} h
LEFT JOIN
    {{ ref('d_responsaveis') }} r
    ON COALESCE(h.updated_by, 'N/A') = COALESCE(r.updated_by, 'N/A')
    AND COALESCE(h.responsible, 'N/A') = COALESCE(r.responsible, 'N/A')