# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [config]
# tags: [config, units]
# owner: engine-team
# status: active
# --- /L9_META ---
# engine/config/units.py
"""
Unit conversion system for cross-domain measurement normalization.
Handles currency, distance, weight, time, temperature, rates, etc.
"""

import logging
from dataclasses import dataclass

from engine.utils.safe_eval import safe_eval

logger = logging.getLogger(__name__)


@dataclass
class UnitDefinition:
    """Unit conversion definition."""

    display: str
    storage: str
    to_storage: float  # Multiplier to convert display → storage
    from_storage: float  # Multiplier to convert storage → display
    conversion_formula: dict[str, str] | None = None  # For non-linear conversions


class UnitConverter:
    """Domain-agnostic unit conversion engine."""

    # Default unit system (can be overridden by domain spec)
    DEFAULT_UNITS = {
        "currency": UnitDefinition(
            display="USD",
            storage="USD",
            to_storage=1.0,
            from_storage=1.0,
        ),
        "percentage": UnitDefinition(
            display="percent",
            storage="decimal",
            to_storage=0.01,
            from_storage=100.0,
        ),
        "time": UnitDefinition(
            display="days",
            storage="days",
            to_storage=1.0,
            from_storage=1.0,
        ),
        "distance": UnitDefinition(
            display="miles",
            storage="meters",
            to_storage=1609.34,
            from_storage=0.000621371,
        ),
        "weight": UnitDefinition(
            display="pounds",
            storage="kilograms",
            to_storage=0.453592,
            from_storage=2.20462,
        ),
        "temperature": UnitDefinition(
            display="fahrenheit",
            storage="celsius",
            to_storage=1.0,  # Placeholder (uses formula)
            from_storage=1.0,
            conversion_formula={
                "to_storage": "(value - 32.0) * 5.0 / 9.0",
                "from_storage": "value * 9.0 / 5.0 + 32.0",
            },
        ),
        "rate_per_distance": UnitDefinition(
            display="USD/mile",
            storage="USD_per_meter",
            to_storage=0.000621371,  # 1/meters_per_mile
            from_storage=1609.34,
        ),
        "concentration": UnitDefinition(
            display="ppm",
            storage="ppm",
            to_storage=1.0,
            from_storage=1.0,
        ),
        "viscosity": UnitDefinition(
            display="g_per_10min",
            storage="g_per_10min",
            to_storage=1.0,
            from_storage=1.0,
        ),
    }

    def __init__(self, unit_definitions: dict[str, UnitDefinition] | None = None):
        """
        Initialize converter.

        Args:
            unit_definitions: Custom unit definitions (overrides defaults)
        """
        self.units = {**self.DEFAULT_UNITS}
        if unit_definitions:
            self.units.update(unit_definitions)

    def convert_to_storage(self, value: float, unit: str) -> float:
        """
        Convert value from display units to storage units.

        Args:
            value: Value in display units
            unit: Unit type (e.g., "distance", "currency")

        Returns:
            Value in storage units
        """
        if unit not in self.units:
            logger.warning(f"Unknown unit type '{unit}', passing through unchanged")
            return value

        unit_def = self.units[unit]

        # Check for formula-based conversion
        if unit_def.conversion_formula and "to_storage" in unit_def.conversion_formula:
            formula = unit_def.conversion_formula["to_storage"]
            return self._eval_formula(formula, value)

        return value * unit_def.to_storage

    def convert_from_storage(self, value: float, unit: str) -> float:
        """
        Convert value from storage units to display units.

        Args:
            value: Value in storage units
            unit: Unit type

        Returns:
            Value in display units
        """
        if unit not in self.units:
            logger.warning(f"Unknown unit type '{unit}', passing through unchanged")
            return value

        unit_def = self.units[unit]

        # Check for formula-based conversion
        if unit_def.conversion_formula and "from_storage" in unit_def.conversion_formula:
            formula = unit_def.conversion_formula["from_storage"]
            return self._eval_formula(formula, value)

        return value * unit_def.from_storage

    def _eval_formula(self, formula: str, value: float) -> float:
        """
        Evaluate conversion formula (safe subset of Python expressions).

        Args:
            formula: Formula string with 'value' as variable
            value: Input value

        Returns:
            Computed result
        """
        try:
            return float(safe_eval(formula, {"value": value}))
        except Exception as e:
            logger.error(f"Formula evaluation failed: {formula}, error: {e}")
            return value

    def get_unit_definition(self, unit: str) -> UnitDefinition | None:
        """Get unit definition by name."""
        return self.units.get(unit)

    def register_unit(self, name: str, definition: UnitDefinition) -> None:
        """Register or override unit definition."""
        self.units[name] = definition
        logger.debug(f"Registered unit '{name}': {definition.display} → {definition.storage}")
