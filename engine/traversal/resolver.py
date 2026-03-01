"""
Parameter resolver.
Resolves derived parameters from query fields.
"""

import logging
from typing import Any

from engine.config.schema import DomainSpec

logger = logging.getLogger(__name__)


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
        """
        resolved = query_data.copy()

        for param_spec in self.domain_spec.derivedparameters:
            try:
                value = self._evaluate_expression(param_spec.expression, resolved)
                resolved[param_spec.name] = value
                logger.debug(f"Resolved parameter '{param_spec.name}' = {value}")
            except Exception as e:
                logger.error(f"Failed to resolve parameter '{param_spec.name}': {e}")

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
        # Safe eval with restricted namespace
        namespace = {**context, "__builtins__": {}}
        return eval(expression, namespace)
