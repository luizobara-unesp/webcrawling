{{
  config(
    materialized='table',
    schema='analytics'
  )
}}

SELECT
    page_id,
    url,
    is_active,
    last_crawled_at
FROM {{ ref('stg_pages') }}