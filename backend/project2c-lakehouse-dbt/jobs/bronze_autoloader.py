"""Auto Loader job: reads JSON from ADLS Bronze → Delta Bronze table.

Pipeline position:
    ADLS Bronze (raw JSON files)
        ↓  cloudFiles (Auto Loader)
    {catalog}.bronze.sensor_events  (Unity Catalog managed Delta table)

Runs as a Databricks Job with serverless compute.
Authentication via Access Connector Managed Identity — no keys needed.

cloudFiles is a Databricks-only feature and cannot run outside a Databricks cluster.
Test coverage is provided by ruff + mypy in CI only.

Environment variables (injected by Databricks Job or local .env):
    AZURE_STORAGE_ACCOUNT_NAME     -- storage account created by Terraform
    AZURE_STORAGE_CONTAINER_BRONZE -- defaults to "bronze"
    DATABRICKS_CATALOG             -- defaults to "p2c_dev"
"""

import logging
import os

from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

load_dotenv()

_run_id = os.environ.get("DATABRICKS_JOB_RUN_ID", "local")
logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [%(levelname)s] run_id={_run_id} %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def build_source_path(account_name: str, container: str) -> str:
    return f"abfss://{container}@{account_name}.dfs.core.windows.net/"


def build_checkpoint_path(account_name: str, container: str) -> str:
    # Must be on durable ADLS storage — local paths are lost on cluster restart
    return (
        f"abfss://{container}@{account_name}.dfs.core.windows.net/" "_checkpoints/bronze_autoloader"
    )


def run(spark: SparkSession, catalog: str, account_name: str, container: str) -> None:
    source_path = build_source_path(account_name, container)
    checkpoint_path = build_checkpoint_path(account_name, container)
    target_table = f"{catalog}.bronze.sensor_events"

    log.info("Auto Loader start | source=%s | target=%s", source_path, target_table)

    (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", checkpoint_path + "/schema")
        # New columns in source JSON are added to the Delta table automatically
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(source_path)
        # Metadata columns for lineage and debugging
        .withColumn("_source_file", F.input_file_name())
        .withColumn("_ingestion_time", F.current_timestamp())
        .writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        # Required when schemaEvolutionMode adds new columns to the target table
        .option("mergeSchema", "true")
        # availableNow=True: process all new files then stop (cheaper than always-on)
        .trigger(availableNow=True)
        .toTable(target_table)
        .awaitTermination()
    )

    log.info("Auto Loader done | target=%s", target_table)


def main() -> None:
    account_name = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
    container = os.environ.get("AZURE_STORAGE_CONTAINER_BRONZE", "bronze")
    catalog = os.environ.get("DATABRICKS_CATALOG", "p2c_dev")

    spark = SparkSession.builder.getOrCreate()
    run(spark, catalog, account_name, container)


if __name__ == "__main__":
    main()
