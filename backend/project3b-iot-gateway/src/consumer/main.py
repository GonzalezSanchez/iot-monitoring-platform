"""Consumer service — normalises gateway messages to the shared data contract.

Reads `sensor-events` in consumer group `gateway-normalizer`, writes the shared
prod-SensorEvents items + refreshes prod-RoomStatus, and produces anything that
fails normalisation to the DLQ topic with the original message and the reason
attached (never dropped, never half-written).

Offsets are committed manually after a message is either written or DLQ'd —
at-least-once delivery; the deterministic keys in normalizer.py make the
redelivery case idempotent.
"""

import asyncio
import json
import logging
import signal
import time
from typing import Any, Awaitable, Callable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from consumer import config, normalizer, writer

logger = logging.getLogger("consumer")

DlqSend = Callable[[bytes], Awaitable[None]]


async def handle_message(raw: bytes, dlq_send: DlqSend) -> str:
    """Process one raw Kafka record. Returns 'written' or 'dlq' (for logging/tests)."""
    try:
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise normalizer.NormalizationError("malformed: not a JSON object")
        items = normalizer.normalize(event)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        await dlq_send(_dlq_record(raw, f"malformed: invalid JSON ({exc})"))
        return "dlq"
    except normalizer.NormalizationError as exc:
        await dlq_send(_dlq_record(raw, str(exc)))
        return "dlq"

    await asyncio.to_thread(writer.write_events, items)
    await asyncio.to_thread(writer.refresh_room, items)
    return "written"


def _dlq_record(raw: bytes, error: str) -> bytes:
    return json.dumps(
        {
            "error": error,
            "original": raw.decode(errors="replace"),
            "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "consumer_group": config.CONSUMER_GROUP,
        }
    ).encode()


async def run() -> None:
    consumer = AIOKafkaConsumer(
        config.TOPIC_SENSOR_EVENTS,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        group_id=config.CONSUMER_GROUP,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS)
    await consumer.start()
    await producer.start()
    logger.info(
        "consuming %s as group %s (DLQ: %s)",
        config.TOPIC_SENSOR_EVENTS,
        config.CONSUMER_GROUP,
        config.TOPIC_DLQ,
    )

    async def dlq_send(record: bytes) -> None:
        await producer.send_and_wait(config.TOPIC_DLQ, record)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        while not stop.is_set():
            batches = await consumer.getmany(timeout_ms=1000)
            for _, records in batches.items():
                for record in records:
                    outcome = await handle_message(record.value, dlq_send)
                    logger.info(
                        "offset %d: %s (key=%s)",
                        record.offset,
                        outcome,
                        (record.key or b"").decode(errors="replace"),
                    )
            if batches:
                await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
        logger.info("consumer stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(run())
