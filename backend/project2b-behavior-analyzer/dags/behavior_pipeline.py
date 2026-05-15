import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.context import Context

SPARK_MASTER = os.environ.get("SPARK_MASTER", "local[*]")
SPARK_CONF = "--conf spark.driver.memory=1g --conf spark.executor.memory=1g"
SPARK_PACKAGES = ",".join(
    [
        "org.apache.hadoop:hadoop-aws:3.4.2",
        "com.amazonaws:aws-java-sdk-bundle:1.12.262",
        "org.postgresql:postgresql:42.7.3",
    ]
)
_submit = f"spark-submit --master {SPARK_MASTER} {SPARK_CONF} --packages {SPARK_PACKAGES}"


def on_failure(context: Context) -> None:
    """Log a clear failure message after all retries are exhausted."""
    ti = context["task_instance"]
    dag_id = context["dag"].dag_id
    print(
        f"[ALERT] Task failed after all retries — dag={dag_id} task={ti.task_id} "
        f"run={context['run_id']} execution={context['execution_date']}"
    )


with DAG(
    dag_id="behavior_pipeline",
    schedule="0 2 * * 1",  # every Monday at 02:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={"days_back": 7},
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure,
    },
    tags=["project2b"],
) as dag:
    manage_partitions = BashOperator(
        task_id="manage_partitions",
        bash_command="python /opt/airflow/scripts/manage_partitions.py --months-ahead 2",
    )

    extract = BashOperator(
        task_id="extract",
        bash_command=f"{_submit} /opt/airflow/jobs/extract.py",
    )

    transform = BashOperator(
        task_id="transform",
        bash_command=f"{_submit} /opt/airflow/jobs/transform.py",
    )

    analyze = BashOperator(
        task_id="analyze",
        bash_command=f"{_submit} /opt/airflow/jobs/analyze.py",
    )

    spatial = BashOperator(
        task_id="spatial",
        bash_command="python /opt/airflow/jobs/spatial.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=("dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt"),
    )

    manage_partitions >> extract >> transform >> analyze >> spatial >> dbt_run
