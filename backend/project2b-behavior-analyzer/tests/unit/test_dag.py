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

    assert dag.check_cycle() is None


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

    assert dag.schedule == "0 2 * * 1"


def test_retries_configured():
    from dags.behavior_pipeline import dag

    for task in dag.tasks:
        assert task.retries == 2
        assert task.retry_delay == __import__("datetime").timedelta(minutes=5)


def test_dag_accepts_days_back_param():
    from dags.behavior_pipeline import dag

    assert "days_back" in dag.params
