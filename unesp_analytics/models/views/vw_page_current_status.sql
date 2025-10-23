{{ config(materialized='view') }}

SELECT
    p.id AS page_id,
    p.url,
    p.is_active,
    p.last_crawled_at,
    h.scrape_timestamp AS last_scrape_timestamp,
    h.modified_date AS last_modified_date,
    h.updated_by AS last_updated_by,
    h.responsible AS last_responsible,
    h.full_modified_text AS last_full_modified_text
FROM {{ source('raw_scrape_data', 'pages') }} p
LEFT JOIN {{ ref('vw_latest_scrape_history') }} h
    ON p.id = h.page_id
WHERE
    p.is_active = true
ORDER BY
    h.scrape_timestamp DESC NULLS LAST,
    p.id