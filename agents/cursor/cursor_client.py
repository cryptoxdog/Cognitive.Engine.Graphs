"""
L9 Cursor Client
HTTP client wrapper for Cursor remote API.
Simple POST wrapper with timeout and error handling.
"""

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Client",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2025-12-09T01:02:49Z",
    "updated_at": "2026-01-14T15:24:45Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "cursor_client",
    "type": "adapter",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": ["HTTP API"],
        "memory_layers": [],
        "imported_by": ["agents.cursor.__init__"],
    },
}
# ============================================================================

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class CursorClient:
    """Client for Cursor remote API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 3000, timeout: int = 30):
        """
        Initialize Cursor remote API client.

        Args:
            host: Cursor API host address.
            port: Cursor API port number.
            timeout: Request timeout in seconds.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"

    def _request(self, endpoint: str, method: str = "POST", data: dict | None = None) -> dict[str, Any]:
        """Make HTTP request to Cursor API."""
        url = f"{self.base_url}{endpoint}"

        try:
            if method == "POST":
                response = httpx.post(url, json=data, timeout=self.timeout)
            elif method == "GET":
                response = httpx.get(url, timeout=self.timeout)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            response.raise_for_status()

            return {
                "success": True,
                "response": response.json() if response.content else {},
                "status_code": response.status_code,
            }

        except httpx.TimeoutException:
            logger.error("Cursor API timeout", url=url)
            return {"success": False, "error": "Request timeout"}
        except httpx.ConnectError:
            logger.error("Cursor API connection error", url=url)
            return {"success": False, "error": "Connection failed"}
        except httpx.HTTPStatusError as e:
            logger.error("Cursor API error", url=url, exc_info=True)
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error("Unexpected error in Cursor API", url=url, exc_info=True)
            return {"success": False, "error": str(e)}

    def send_code(self, code: str) -> dict[str, Any]:
        """
        Send code to Cursor.
        Returns: {success: bool, response: Dict, error: str}
        """
        return self._request("/api/code", data={"code": code})

    def send_command(self, command: str) -> dict[str, Any]:
        """
        Send command to Cursor.
        Returns: {success: bool, response: Dict, error: str}
        """
        return self._request("/api/command", data={"command": command})

    def health_check(self) -> dict[str, Any]:
        """
        Check Cursor API health.
        Returns: {success: bool, response: Dict}
        """
        return self._request("/health", method="GET")


# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-018",
    "governance_level": "critical",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [],
    "tags": ["adapter", "agent-execution", "api", "client", "intelligence", "logging"],
    "keywords": ["check", "client", "command", "cursor", "health", "send", "wrapper"],
    "business_value": "Implements CursorClient for cursor client functionality",
    "last_modified": "2026-01-14T15:24:45Z",
    "modified_by": "L9_Codegen_Engine",
    "change_summary": "Initial generation with DORA compliance",
}
# ============================================================================
# L9 DORA BLOCK - AUTO-UPDATED - DO NOT EDIT
# Runtime execution trace - updated automatically on every execution
# ============================================================================
__l9_trace__ = {
    "trace_id": "",
    "task": "",
    "timestamp": "",
    "patterns_used": [],
    "graph": {"nodes": [], "edges": []},
    "inputs": {},
    "outputs": {},
    "metrics": {"confidence": "", "errors_detected": [], "stability_score": ""},
}
# ============================================================================
# END L9 DORA BLOCK
# ============================================================================
