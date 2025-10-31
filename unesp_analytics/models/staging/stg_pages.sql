{{ config(materialized='view') }}

SELECT
    id AS page_id, 
    url,
    is_active,
    last_crawled_at
FROM {{ source('raw_scrape_data', 'pages') }}