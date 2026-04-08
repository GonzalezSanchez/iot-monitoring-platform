"""
HTTP Response utilities for Lambda handlers
"""
import json
from typing import Any, Dict, Optional


def success_response(
    data: Any, status_code: int = 200, headers: Optional[Dict] = None
) -> Dict:
    """Create successful HTTP response"""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Credentials": True,
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(data, default=str),
    }


def error_response(
    message: str, status_code: int = 400, error_code: Optional[str] = None
) -> Dict:
    """Create error HTTP response with consistent CORS headers"""
    body = {"error": message, "code": error_code or f"ERROR_{status_code}"}

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body),
    }
