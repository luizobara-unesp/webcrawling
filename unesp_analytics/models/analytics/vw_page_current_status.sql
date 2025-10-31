{{ config(materialized='view', schema='analytics') }}

WITH latest_scrape_event AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY page_id ORDER BY scrape_timestamp DESC) as rn
    FROM {{ ref('f_scrape_history') }}
)
SELECT
    p.page_id,
    p.url,
    p.is_active,
    p.last_crawled_at,
    ls.scrape_timestamp AS last_scrape_timestamp,
    ls.modified_date AS last_modified_date,
    r.updated_by AS last_updated_by,       
    r.responsible AS last_responsible,   
    ls.full_modified_text AS last_full_modified_text,
    ls.dias_desde_modificacao
FROM
    {{ ref('d_paginas') }} p
LEFT JOIN
    latest_scrape_event ls ON p.page_id = ls.page_id AND ls.rn = 1 
LEFT JOIN
    {{ ref('d_responsaveis') }} r ON ls.responsavel_id = r.responsavel_id
WHERE
    p.is_active = true 
ORDER BY
    ls.scrape_timestamp DESC NULLS LAST,
    p.page_id