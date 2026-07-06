"""Devices table access (p3-{env}-Devices, docs/project3b-iot-gateway.md schema).

boto3 is synchronous — routes call these functions via asyncio.to_thread so the
event loop never blocks. Registration/auth are low-frequency; the message hot
path only reads through a short TTL cache (see main.py).
"""

import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from gateway import config


class DeviceAlreadyExists(Exception):
    pass


def _table():
    return boto3.resource("dynamodb", region_name=config.AWS_REGION).Table(config.DEVICES_TABLE)


def create_device(device_id: str, device_type: str, api_key_hash: str, metadata: Dict[str, str]) -> None:
    try:
        _table().put_item(
            Item={
                "device_id": device_id,
                "device_type": device_type,
                "api_key_hash": api_key_hash,
                "status": "registered",
                "metadata": metadata,
                "registered_at": _now_iso(),
                "last_seen": None,
            },
            ConditionExpression="attribute_not_exists(device_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise DeviceAlreadyExists(device_id) from e
        raise


def get_device(device_id: str) -> Optional[Dict[str, Any]]:
    resp = _table().get_item(Key={"device_id": device_id})
    return resp.get("Item")


def touch_device(device_id: str, status: str = "online") -> None:
    _table().update_item(
        Key={"device_id": device_id},
        UpdateExpression="SET #s = :s, last_seen = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status, ":t": _now_iso()},
    )


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
