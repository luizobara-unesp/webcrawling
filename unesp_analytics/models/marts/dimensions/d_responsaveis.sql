{{
  config(
    materialized='table',
    schema='analytics'
  )
}}

WITH all_responsibles AS (
    SELECT DISTINCT
        updated_by,
        responsible
    FROM {{ ref('stg_scrape_history') }}
    WHERE updated_by IS NOT NULL OR responsible IS NOT NULL
)
SELECT
    {{ dbt_utils.generate_surrogate_key(['updated_by', 'responsible']) }} AS responsavel_id,
    updated_by,
    responsible
FROM all_responsibles

UNION ALL

SELECT
    'N/A' AS responsavel_id,
    'N/A' AS updated_by,
    'N/A' AS responsible