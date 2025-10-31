{{ config(materialized='view') }}

SELECT
    id AS scrape_id,
    page_id,
    scrape_timestamp,
    (
        SPLIT_PART(modified_date, '/', 3) || '-' ||
        (CASE SPLIT_PART(modified_date, '/', 2)
            WHEN 'Jan' THEN '01'
            WHEN 'Fev' THEN '02'
            WHEN 'Mar' THEN '03'
            WHEN 'Abr' THEN '04'
            WHEN 'Mai' THEN '05'
            WHEN 'Jun' THEN '06'
            WHEN 'Jul' THEN '07'
            WHEN 'Ago' THEN '08'
            WHEN 'Set' THEN '09'
            WHEN 'Out' THEN '10'
            WHEN 'Nov' THEN '11'
            WHEN 'Dez' THEN '12'
            ELSE NULL
        END) || '-' ||
        LPAD(SPLIT_PART(modified_date, '/', 1), 2, '0')
    )::date AS modified_date,
    updated_by,
    responsible,
    full_modified_text
FROM {{ source('raw_scrape_data', 'scrape_history') }}