"""
--- L9_META ---
l9_schema: 1
origin: phase2-implementation
engine: graph
layer: [utils]
tags: [structlog, logging, json, observability]
owner: engine-team
status: active
--- /L9_META ---

engine/utils/logger.py

Structured Logging Setup.

Uses structlog for:
  - Consistent JSON output
  - Request tracing
  - Performance monitoring
  - Error correlation

All log calls use key-value pairs, never free-form strings.
"""
from __future__ import annotations

import logging

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the service.

    Output Format:
        JSON with timestamp, level, logger, event, and context fields.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Examples:
        >>> setup_logging("DEBUG")
        >>> logger = structlog.get_logger("test")
        >>> logger.info("event_name", key1="value1", key2=42)
        # Outputs: {"timestamp": "...", "level": "info", "event": "event_name", ...}
    """
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
