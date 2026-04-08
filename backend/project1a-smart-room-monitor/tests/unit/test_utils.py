"""
Unit tests for response utilities
"""

import json

from utils.response import error_response, success_response


class TestSuccessResponse:
    """Test success_response utility"""

    def test_default_status_code(self):
        response = success_response(data={"key": "value"})
        assert response["statusCode"] == 200

    def test_custom_status_code(self):
        response = success_response(data={"key": "value"}, status_code=201)
        assert response["statusCode"] == 201

    def test_body_is_json_string(self):
        response = success_response(data={"key": "value"})
        body = json.loads(response["body"])
        assert body["key"] == "value"

    def test_cors_header_present(self):
        response = success_response(data={})
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_content_type_header(self):
        response = success_response(data={})
        assert response["headers"]["Content-Type"] == "application/json"

    def test_custom_headers_merged(self):
        response = success_response(data={}, headers={"X-Custom": "test"})
        assert response["headers"]["X-Custom"] == "test"
        assert response["headers"]["Content-Type"] == "application/json"

    def test_data_serialized_with_str_fallback(self):
        """Non-serializable types (datetime) should not raise"""
        from datetime import datetime

        response = success_response(data={"ts": datetime(2026, 1, 1)})
        body = json.loads(response["body"])
        assert "ts" in body


class TestErrorResponse:
    """Test error_response utility"""

    def test_default_status_code(self):
        response = error_response("something went wrong")
        assert response["statusCode"] == 400

    def test_custom_status_code(self):
        response = error_response("not found", status_code=404)
        assert response["statusCode"] == 404

    def test_body_contains_error_message(self):
        response = error_response("bad request")
        body = json.loads(response["body"])
        assert body["error"] == "bad request"

    def test_default_error_code(self):
        response = error_response("bad request", status_code=400)
        body = json.loads(response["body"])
        assert body["code"] == "ERROR_400"

    def test_custom_error_code(self):
        response = error_response("bad request", error_code="INVALID_SENSOR")
        body = json.loads(response["body"])
        assert body["code"] == "INVALID_SENSOR"

    def test_cors_header_present(self):
        response = error_response("error")
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_500_error(self):
        response = error_response("internal error", status_code=500)
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["code"] == "ERROR_500"
