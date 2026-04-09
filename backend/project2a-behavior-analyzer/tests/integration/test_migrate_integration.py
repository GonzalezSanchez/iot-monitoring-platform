"""
Integration tests for scripts/migrate.py

Verifies that run_migrations() creates all expected tables and indexes
against a real PostgreSQL instance, and is idempotent.
"""

import psycopg2.extensions


def _table_exists(conn: psycopg2.extensions.connection, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        return cur.fetchone() is not None


def _index_exists(conn: psycopg2.extensions.connection, index: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_indexes " "WHERE schemaname = 'public' AND indexname = %s",
            (index,),
        )
        return cur.fetchone() is not None


class TestMigrateIntegration:
    def test_raw_sensor_data_table_exists(self, conn: psycopg2.extensions.connection) -> None:
        assert _table_exists(conn, "raw_sensor_data")

    def test_patterns_table_exists(self, conn: psycopg2.extensions.connection) -> None:
        assert _table_exists(conn, "patterns")

    def test_anomalies_table_exists(self, conn: psycopg2.extensions.connection) -> None:
        assert _table_exists(conn, "anomalies")

    def test_indexes_exist(self, conn: psycopg2.extensions.connection) -> None:
        for index in (
            "idx_raw_sensor_data_room_id",
            "idx_raw_sensor_data_ts",
            "idx_patterns_entity",
            "idx_patterns_job_id",
            "idx_anomalies_entity",
            "idx_anomalies_job_id",
        ):
            assert _index_exists(conn, index), f"Missing index: {index}"

    def test_idempotent(self, dsn: dict) -> None:
        """Running migrate twice must not raise."""
        import migrate

        migrate.run_migrations(dict(dsn))
        migrate.run_migrations(dict(dsn))  # second run — no error
