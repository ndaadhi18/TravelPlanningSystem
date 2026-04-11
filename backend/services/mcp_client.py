"""
MCP client service for PLANIT agents.

M10 scope:
- Call running MCP server via httpx
- Provide typed wrappers for MCP tools
- Return structured schema-validated responses
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Mapping, Optional, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.core.settings import get_settings
from backend.schemas.accommodation import HotelOption, HotelSearchInput
from backend.schemas.itinerary import LocalInsight, WebSearchInput
from backend.schemas.transport import FlightOption, FlightSearchInput
from backend.utils.logger import get_logger

logger = get_logger("services.mcp_client")

TModel = TypeVar("TModel", bound=BaseModel)


class MCPClientError(Exception):
    """Structured exception for MCP client transport/protocol errors."""

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload = {"error": True, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class MCPClient:
    """Async client used by agents to call MCP tools over HTTP."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        timeout: float = 20.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        resolved_base_url = base_url or get_settings().mcp_server_url
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout = timeout
        self._client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> MCPClient:
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close owned httpx client resources."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _request_json(self, url: str, body: dict[str, Any]) -> Any:
        client = await self._get_client()
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        }
        try:
            response = await client.post(url, json=body, headers=headers)
        except httpx.RequestError as e:
            raise MCPClientError(
                f"Failed to reach MCP server at {url}: {e}",
                details={"url": url, "error_type": type(e).__name__},
            ) from e

        if response.status_code >= 400:
            raise MCPClientError(
                f"MCP server request failed with status {response.status_code}.",
                details={
                    "url": url,
                    "status_code": response.status_code,
                    "response_text": response.text[:500],
                },
            )

        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            parsed_event_payload = _parse_event_stream_payload(response.text)
            if parsed_event_payload is not None:
                return parsed_event_payload

        try:
            return response.json()
        except ValueError as e:
            parsed_event_payload = _parse_event_stream_payload(response.text)
            if parsed_event_payload is not None:
                return parsed_event_payload
            raise MCPClientError(
                "MCP server returned non-JSON response.",
                details={"url": url, "response_text": response.text[:500]},
            ) from e

    async def call_tool(self, tool_name: str, payload: Mapping[str, Any]) -> Any:
        """
        Call an MCP tool with protocol-aware fallback request shapes.
        """
        if not tool_name.strip():
            raise ValueError("tool_name must be non-empty.")

        logger.info(f"Calling MCP tool '{tool_name}'")
        attempts: list[str] = []
        for url, body in self._build_request_candidates(tool_name, dict(payload)):
            try:
                raw = await self._request_json(url, body)
                return self._extract_tool_result(raw, tool_name)
            except MCPClientError as e:
                if e.details.get("__tool_error__") is True:
                    # A valid MCP response reported a tool-level failure.
                    # Do not retry alternate endpoint shapes.
                    raise e
                logger.warning(f"MCP call attempt failed for '{tool_name}' at {url}: {e.message}")
                attempts.append(f"{url}: {e.message}")

        raise MCPClientError(
            f"All MCP call attempts failed for tool '{tool_name}'.",
            details={"attempts": attempts},
        )

    async def search_flights(
        self,
        params: FlightSearchInput | Mapping[str, Any],
    ) -> list[FlightOption]:
        request = (
            params if isinstance(params, FlightSearchInput) else FlightSearchInput.model_validate(params)
        )
        raw = await self.call_tool("search_flights", request.model_dump(mode="json"))
        return _parse_model_list(raw, FlightOption, "search_flights")

    async def search_hotels(
        self,
        params: HotelSearchInput | Mapping[str, Any],
    ) -> list[HotelOption]:
        request = params if isinstance(params, HotelSearchInput) else HotelSearchInput.model_validate(params)
        raw = await self.call_tool("search_hotels", request.model_dump(mode="json"))
        return _parse_model_list(raw, HotelOption, "search_hotels")

    async def web_search_places(
        self,
        params: WebSearchInput | Mapping[str, Any],
    ) -> list[LocalInsight]:
        request = params if isinstance(params, WebSearchInput) else WebSearchInput.model_validate(params)
        raw = await self.call_tool("web_search_places", request.model_dump(mode="json"))
        return _parse_model_list(raw, LocalInsight, "web_search_places")

    async def health_check(self) -> bool:
        """
        Best-effort MCP server health check.
        """
        client = await self._get_client()
        for endpoint in ("/health", "/"):
            try:
                response = await client.get(f"{self.base_url}{endpoint}")
                if response.status_code < 500:
                    logger.info(f"MCP health check passed on {endpoint}")
                    return True
            except httpx.RequestError:
                continue
        logger.warning("MCP health check failed on all endpoints")
        return False

    def _build_request_candidates(
        self, tool_name: str, payload: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any]]]:
        request_id = str(uuid.uuid4())
        return [
            (
                f"{self.base_url}/mcp",
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": payload},
                },
            ),
            (
                f"{self.base_url}/tools/call",
                {"name": tool_name, "arguments": payload},
            ),
            (
                f"{self.base_url}/tools/{tool_name}",
                payload,
            ),
            (
                f"{self.base_url}/{tool_name}",
                payload,
            ),
        ]

    def _extract_tool_result(self, raw: Any, tool_name: str) -> Any:
        if isinstance(raw, dict):
            if "error" in raw and raw["error"]:
                message, details = _unpack_error(raw["error"])
                details["__tool_error__"] = True
                raise MCPClientError(
                    f"MCP tool '{tool_name}' returned an error: {message}",
                    details=details,
                )

            if "result" in raw:
                return self._extract_from_result_container(raw["result"])

            if "data" in raw and isinstance(raw["data"], list):
                return raw["data"]

            return self._extract_from_result_container(raw)

        return raw

    def _extract_from_result_container(self, result: Any) -> Any:
        if isinstance(result, dict):
            if "structuredContent" in result:
                return result["structuredContent"]
            if "data" in result:
                return result["data"]
            if "content" in result and isinstance(result["content"], list):
                return _parse_content_items(result["content"])
            return result
        return result


def _parse_content_items(content_items: list[Any]) -> Any:
    if len(content_items) == 1 and isinstance(content_items[0], dict):
        text = content_items[0].get("text")
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return content_items


def _parse_event_stream_payload(text: str) -> Optional[Any]:
    """
    Parse JSON payload from a text/event-stream body.
    """
    data_chunks: list[str] = []
    current_chunk: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if line.startswith("data:"):
            current_chunk.append(line[5:].lstrip())
            continue
        if line.strip() == "" and current_chunk:
            data_chunks.append("\n".join(current_chunk))
            current_chunk = []

    if current_chunk:
        data_chunks.append("\n".join(current_chunk))

    for chunk in reversed(data_chunks):
        if not chunk or chunk == "[DONE]":
            continue
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue

    return None


def _parse_model_list(raw: Any, model_cls: type[TModel], tool_name: str) -> list[TModel]:
    if isinstance(raw, dict):
        if "results" in raw and isinstance(raw["results"], list):
            raw = raw["results"]
        elif "items" in raw and isinstance(raw["items"], list):
            raw = raw["items"]

    if not isinstance(raw, list):
        raise MCPClientError(
            f"MCP tool '{tool_name}' returned unexpected response shape.",
            details={"response_type": type(raw).__name__, "response_preview": str(raw)[:400]},
        )

    parsed: list[TModel] = []
    for index, item in enumerate(raw):
        try:
            parsed.append(model_cls.model_validate(item))
        except ValidationError as e:
            raise MCPClientError(
                f"Failed to parse item {index} from tool '{tool_name}' into {model_cls.__name__}.",
                details={"item_index": index, "item_preview": str(item)[:400]},
            ) from e
    return parsed


def _unpack_error(error: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(error, dict):
        message = str(error.get("message", "Unknown MCP error"))
        return message, error
    return str(error), {"raw_error": str(error)}


__all__ = [
    "MCPClient",
    "MCPClientError",
]
