{{ config(materialized='view', schema='analytics') }}

SELECT *
FROM {{ ref('vw_page_current_status') }} 
WHERE
    last_updated_by LIKE '%Not Found%'
    AND last_full_modified_text NOT LIKE '%Not Found%'