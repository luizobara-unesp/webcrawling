from airflow.decorators import dag
from airflow.providers.standard.operators.bash import BashOperator
import pendulum

@dag(
    dag_id="unesp_daily_collection",
    description="Runs the scraper and dbt every day at 7am.",
    schedule="0 11 * * *", 
    start_date=pendulum.datetime(2025, 11, 1, tz="America/Sao_Paulo"),
    catchup=False
)
def daily_collection_pipeline():
    
    task_run_scraper = BashOperator(
        task_id="run_scraper",
        bash_command="python /opt/airflow/scripts/main.py"
    )

    task_run_dbt = BashOperator(
        task_id="run_dbt_transform",
        bash_command=(
            "dbt clean --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project && "
            "dbt deps --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project && "
            "dbt run --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project"
        )
    )
    
    task_run_scraper >> task_run_dbt

daily_collection_pipeline()