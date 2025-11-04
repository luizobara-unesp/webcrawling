from airflow.decorators import dag
from airflow.providers.standard.operators.bash import BashOperator
import pendulum

@dag(
    dag_id="unesp_weekly_discovery",
    description="Runs the crawler 1x per week to discover new pages.",
    schedule="0 0 * * 0", 
    start_date=pendulum.datetime(2025, 11, 8, tz="America/Sao_Paulo"), 
    catchup=False
)
def weekly_discovery_pipeline():
    
    task_run_crawler = BashOperator(
        task_id="run_crawler",
        bash_command="python /opt/airflow/scripts/crawl.py" 
    )

    task_run_crawler

weekly_discovery_pipeline()