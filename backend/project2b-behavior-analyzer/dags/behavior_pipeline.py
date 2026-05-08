from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="behavior_pipeline",
    schedule="0 2 * * 1",  # every Monday at 02:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={"days_back": 7},
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["project2b"],
) as dag:
    manage_partitions = BashOperator(
        task_id="manage_partitions",
        bash_command="python /opt/airflow/scripts/manage_partitions.py --months-ahead 2",
    )

    extract = BashOperator(
        task_id="extract",
        bash_command="spark-submit --master local[*] /opt/airflow/jobs/extract.py",
    )

    transform = BashOperator(
        task_id="transform",
        bash_command="spark-submit --master local[*] /opt/airflow/jobs/transform.py",
    )

    analyze = BashOperator(
        task_id="analyze",
        bash_command="spark-submit --master local[*] /opt/airflow/jobs/analyze.py",
    )

    manage_partitions >> extract >> transform >> analyze
