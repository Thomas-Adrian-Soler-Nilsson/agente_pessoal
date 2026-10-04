"""Shared browser bridge message and result contract."""
from __future__ import annotations

import uuid

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 1_000_000
OPERATIONS = {
    "list_tabs", "inspect", "click", "fill", "select", "press", "navigate",
    "open_tab", "wait", "back", "screenshot", "click_at", "download", "search_site",
}
STATUSES = {"success", "failure", "uncertain", "confirmation_required", "setup_needed"}


def request(operation: str, arguments: dict | None = None) -> dict:
    if operation not in OPERATIONS:
        raise ValueError("unsupported_operation")
    return {
        "version": PROTOCOL_VERSION,
        "type": "request",
        "request_id": str(uuid.uuid4()),
        "operation": operation,
        "arguments": arguments or {},
    }


def result(operation: str, status: str, *, request_id: str = "", tab=None,
           before=None, after=None, observation: str = "", error_code: str = "",
           retry_hint: str = "", data=None) -> dict:
    if status not in STATUSES:
        status = "failure"
        error_code = error_code or "invalid_result_status"
    return {
        "status": status,
        "request_id": request_id,
        "operation": operation,
        "tab": tab or {},
        "before": before or {},
        "after": after or {},
        "observation": observation[:4000],
        "error_code": error_code,
        "retry_hint": retry_hint,
        "data": data,
    }


def normalize_response(message: dict, expected: dict) -> dict:
    if not isinstance(message, dict) or message.get("request_id") != expected["request_id"]:
        return result(expected["operation"], "failure", request_id=expected["request_id"], error_code="response_mismatch", retry_hint="browser_list_tabs")
    status = message.get("status")
    if status not in STATUSES:
        return result(expected["operation"], "failure", request_id=expected["request_id"], error_code="invalid_response", retry_hint="browser_inspect")
    return result(
        expected["operation"], status, request_id=expected["request_id"],
        tab=message.get("tab"), before=message.get("before"), after=message.get("after"),
        observation=message.get("observation", ""), error_code=message.get("error_code", ""),
        retry_hint=message.get("retry_hint", ""), data=message.get("data"),
    )
