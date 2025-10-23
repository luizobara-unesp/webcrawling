{{ config(materialized='view') }}

WITH ranked_history AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY page_id ORDER BY scrape_timestamp DESC) as rn
    FROM {{ source('raw_scrape_data', 'scrape_history') }} 
)

SELECT
    id,
    page_id,
    scrape_timestamp,
    modified_date,
    updated_by,
    responsible,
    full_modified_text
FROM ranked_history
WHERE rn = 1 