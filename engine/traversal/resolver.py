"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [traversal, resolver]
owner: engine-team
status: active
--- /L9_META ---

Parameter resolver.
Resolves derived parameters from query fields.
"""

import logging
from typing import Any

from engine.config.schema import DomainSpec
from engine.utils.safe_eval import safe_eval

logger = logging.getLogger(__name__)


class ParameterResolutionError(Exception):
    """W1-05: Raised when a derived parameter fails to resolve in strict mode.

    Maps to HTTP 422 (Unprocessable Entity) in the handler layer.
    """


class ParameterResolver:
    """Resolves derived parameters from query input."""

    def __init__(self, domain_spec: DomainSpec):
        self.domain_spec = domain_spec

    def resolve_parameters(self, query_data: dict[str, Any]) -> dict[str, Any]:
        """
        Compute derived parameters from query fields.

        Args:
            query_data: Raw query input

        Returns:
            Query data with derived parameters added

        Raises:
            ParameterResolutionError: If PARAM_STRICT_MODE is enabled and
                a derived parameter expression fails to evaluate.
        """
        from engine.config.settings import settings

        resolved = query_data.copy()

        for param_spec in self.domain_spec.derivedparameters:
            try:
                value = self._evaluate_expression(param_spec.expression, resolved)
                resolved[param_spec.name] = value
                logger.debug("Resolved parameter '%s' = %s", param_spec.name, value)
            except Exception as exc:
                # W1-05: In strict mode, propagate the error instead of swallowing it.
                # This prevents downstream gates from silently evaluating against null.
                if settings.param_strict_mode:
                    msg = f"Failed to resolve derived parameter '{param_spec.name}': {exc}"
                    raise ParameterResolutionError(msg) from exc
                logger.error("Failed to resolve parameter '%s': %s", param_spec.name, exc)

        return resolved

    def _evaluate_expression(self, expression: str, context: dict[str, Any]) -> Any:
        """
        Safely evaluate derived parameter expression.

        Args:
            expression: Algebraic expression (e.g., "annualincomeusd / 12.0")
            context: Variable context

        Returns:
            Computed value
        """
        return safe_eval(expression, context)
