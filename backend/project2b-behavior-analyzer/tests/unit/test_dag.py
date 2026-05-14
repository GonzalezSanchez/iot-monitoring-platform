import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_dag_loads_without_import_errors():
    """DAG module imports cleanly — no syntax or import errors."""
    import importlib

    import dags.behavior_pipeline  # noqa: F401

    importlib.reload(dags.behavior_pipeline)


def test_dag_has_no_cycles():
    from dags.behavior_pipeline import dag

    dag.validate()  # raises AirflowDagCycleException if cycles exist


def test_dag_id():
    from dags.behavior_pipeline import dag

    assert dag.dag_id == "behavior_pipeline"


def test_expected_tasks_present():
    from dags.behavior_pipeline import dag

    task_ids = {task.task_id for task in dag.tasks}
    assert {"manage_partitions", "extract", "transform", "analyze"} <= task_ids


def test_task_dependencies():
    from dags.behavior_pipeline import dag

    def downstream(task_id: str) -> set[str]:
        task = dag.get_task(task_id)
        return {t.task_id for t in task.downstream_list}

    assert "extract" in downstream("manage_partitions")
    assert "transform" in downstream("extract")
    assert "analyze" in downstream("transform")


def test_schedule():
    from dags.behavior_pipeline import dag

    # Airflow 2.x uses schedule_interval, Airflow 3.x uses schedule
    schedule = getattr(dag, "schedule_interval", None) or getattr(dag, "schedule", None)
    assert schedule == "0 2 * * 1"


def test_retries_configured():
    from dags.behavior_pipeline import dag

    for task in dag.tasks:
        assert task.retries == 2
        assert task.retry_delay == __import__("datetime").timedelta(minutes=5)


def test_dag_accepts_days_back_param():
    from dags.behavior_pipeline import dag

    assert "days_back" in dag.params


def test_failure_callback_configured():
    from dags.behavior_pipeline import dag, on_failure

    for task in dag.tasks:
        callbacks = task.on_failure_callback
        if isinstance(callbacks, list):
            assert on_failure in callbacks
        else:
            assert callbacks is on_failure


def test_spark_master_in_bash_commands():
    import importlib
    import os

    import dags.behavior_pipeline

    os.environ["SPARK_MASTER"] = "spark://test-cluster:7077"
    importlib.reload(dags.behavior_pipeline)
    from dags.behavior_pipeline import dag

    spark_tasks = {t.task_id: t for t in dag.tasks if t.task_id != "manage_partitions"}
    for task_id, task in spark_tasks.items():
        assert (
            "spark://test-cluster:7077" in task.bash_command
        ), f"{task_id} does not use SPARK_MASTER"

    os.environ["SPARK_MASTER"] = "local[*]"
    importlib.reload(dags.behavior_pipeline)


def test_failure_callback_logs_task_info(capsys):
    from unittest.mock import MagicMock

    from dags.behavior_pipeline import on_failure

    ti = MagicMock()
    ti.task_id = "extract"
    dag_mock = MagicMock()
    dag_mock.dag_id = "behavior_pipeline"

    on_failure(
        {
            "task_instance": ti,
            "dag": dag_mock,
            "run_id": "manual__2026-01-01",
            "execution_date": "2026-01-01",
        }
    )

    captured = capsys.readouterr()
    assert "ALERT" in captured.out
    assert "extract" in captured.out
    assert "behavior_pipeline" in captured.out
