#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Loopback-only, read-only HTTP boundary for the compact Ksoloti AI core."""

from __future__ import annotations

import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Tuple
from urllib.parse import parse_qs, urlsplit


MAX_REQUEST_BYTES = 1024 * 1024


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class ReadOnlyAPI:
    """Pure request dispatcher; every operation returns data and writes nothing."""

    def __init__(
        self,
        catalog: Dict[str, Any],
        *,
        search: Callable[[Dict[str, Any], str, int], Dict[str, Any]],
        inspect: Callable[[Dict[str, Any], str], Dict[str, Any]],
        validate_text: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        explain: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        self.catalog = catalog
        self.search = search
        self.inspect = inspect
        self.validate_text = validate_text
        self.explain = explain

    def dispatch(
        self, method: str, target: str, body: bytes = b""
    ) -> Tuple[int, Dict[str, Any]]:
        parsed = urlsplit(target)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if method == "GET" and parsed.path == "/v1/health":
            return 200, {
                "ok": True,
                "service": "ksai-read-only",
                "version": 1,
                "object_count": len(self.catalog.get("objects", [])),
                "mutation": "disabled",
                "device_access": "disabled",
            }
        if method == "GET" and parsed.path == "/v1/catalog/search":
            term = query.get("q", [""])[0]
            try:
                limit = int(query.get("limit", ["10"])[0])
            except ValueError:
                return self._error(400, "E_LIMIT", "limit must be an integer")
            if not 1 <= limit <= 100:
                return self._error(400, "E_LIMIT", "limit must be between 1 and 100")
            return 200, self.search(self.catalog, term, limit)
        if method == "GET" and parsed.path == "/v1/catalog/inspect":
            requested = query.get("object", [""])[0]
            if not requested:
                return self._error(400, "E_OBJECT", "object is required")
            result = self.inspect(self.catalog, requested)
            return (200 if result.get("ok") else 404), result
        if method == "POST" and parsed.path in ("/v1/patch/validate", "/v1/patch/explain"):
            request, error = self._json_request(body)
            if error is not None:
                return error
            source = request.get("source")
            if not isinstance(source, str):
                return self._error(400, "E_SOURCE", "source must be a string")
            validated = self.validate_text(source, self.catalog)
            result = (
                self.explain(validated, self.catalog)
                if parsed.path.endswith("/explain")
                else validated
            )
            return (200 if result.get("ok") else 422), result
        return self._error(404, "E_ROUTE", "read-only route not found")

    @staticmethod
    def _json_request(
        body: bytes,
    ) -> Tuple[Dict[str, Any], Tuple[int, Dict[str, Any]] | None]:
        if len(body) > MAX_REQUEST_BYTES:
            return {}, ReadOnlyAPI._error(413, "E_BODY_SIZE", "request body is too large")
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}, ReadOnlyAPI._error(400, "E_JSON", "request body must be a JSON object")
        if not isinstance(value, dict):
            return {}, ReadOnlyAPI._error(400, "E_JSON", "request body must be a JSON object")
        return value, None

    @staticmethod
    def _error(status: int, code: str, message: str) -> Tuple[int, Dict[str, Any]]:
        return status, {
            "ok": False,
            "diagnostics": [{"severity": "error", "code": code, "message": message}],
        }


def serve(api: ReadOnlyAPI, host: str, port: int) -> None:
    if not is_loopback_host(host):
        raise ValueError("the AI service only binds to a loopback address")

    class Handler(BaseHTTPRequestHandler):
        server_version = "ksai-read-only/1"

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch(b"")

        def do_POST(self) -> None:  # noqa: N802
            content_length = self.headers.get("Content-Length", "0")
            try:
                length = int(content_length)
            except ValueError:
                self._respond(*ReadOnlyAPI._error(400, "E_BODY_SIZE", "invalid content length"))
                return
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._respond(*ReadOnlyAPI._error(413, "E_BODY_SIZE", "request body is too large"))
                return
            self._dispatch(self.rfile.read(length))

        def _dispatch(self, body: bytes) -> None:
            self._respond(*api.dispatch(self.command, self.path, body))

        def _respond(self, status: int, payload: Dict[str, Any]) -> None:
            encoded = json.dumps(
                payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        server.server_close()
