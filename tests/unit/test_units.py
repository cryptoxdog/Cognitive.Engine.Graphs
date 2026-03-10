# ============================================================================
# tests/unit/test_units.py
# ============================================================================
"""
Unit tests for engine/config/units.py — UnitConverter.
Target Coverage: 85%+
"""

from __future__ import annotations

import pytest

from engine.config.units import UnitConverter, UnitDefinition

# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestUnitConverterDefaults:
    """Test default unit conversions."""

    def test_currency_passthrough(self) -> None:
        """Currency USD->USD is identity."""
        uc = UnitConverter()
        assert uc.convert_to_storage(100.0, "currency") == 100.0
        assert uc.convert_from_storage(100.0, "currency") == 100.0

    def test_percentage_to_decimal(self) -> None:
        """Percentage converts 50% -> 0.50 and back."""
        uc = UnitConverter()
        assert uc.convert_to_storage(50.0, "percentage") == pytest.approx(0.50)
        assert uc.convert_from_storage(0.50, "percentage") == pytest.approx(50.0)

    def test_distance_miles_to_meters(self) -> None:
        """Distance converts miles to meters."""
        uc = UnitConverter()
        result = uc.convert_to_storage(1.0, "distance")
        assert result == pytest.approx(1609.34, rel=1e-3)

    def test_distance_meters_to_miles(self) -> None:
        """Distance converts meters to miles."""
        uc = UnitConverter()
        result = uc.convert_from_storage(1609.34, "distance")
        assert result == pytest.approx(1.0, rel=1e-3)

    def test_weight_pounds_to_kg(self) -> None:
        """Weight converts pounds to kilograms."""
        uc = UnitConverter()
        result = uc.convert_to_storage(2.20462, "weight")
        assert result == pytest.approx(1.0, rel=1e-3)

    def test_weight_kg_to_pounds(self) -> None:
        """Weight converts kilograms to pounds."""
        uc = UnitConverter()
        result = uc.convert_from_storage(1.0, "weight")
        assert result == pytest.approx(2.20462, rel=1e-3)

    def test_time_passthrough(self) -> None:
        """Time days->days is identity."""
        uc = UnitConverter()
        assert uc.convert_to_storage(30.0, "time") == 30.0
        assert uc.convert_from_storage(30.0, "time") == 30.0

    def test_concentration_passthrough(self) -> None:
        """Concentration ppm->ppm is identity."""
        uc = UnitConverter()
        assert uc.convert_to_storage(500.0, "concentration") == 500.0

    def test_viscosity_passthrough(self) -> None:
        """Viscosity g/10min->g/10min is identity."""
        uc = UnitConverter()
        assert uc.convert_to_storage(12.5, "viscosity") == 12.5


@pytest.mark.unit
class TestTemperatureConversion:
    """Test formula-based temperature conversion."""

    def test_fahrenheit_to_celsius(self) -> None:
        """32°F -> 0°C."""
        uc = UnitConverter()
        result = uc.convert_to_storage(32.0, "temperature")
        assert result == pytest.approx(0.0, abs=0.01)

    def test_celsius_to_fahrenheit(self) -> None:
        """100°C -> 212°F."""
        uc = UnitConverter()
        result = uc.convert_from_storage(100.0, "temperature")
        assert result == pytest.approx(212.0, abs=0.01)

    def test_boiling_point_roundtrip(self) -> None:
        """212°F -> C -> F roundtrip."""
        uc = UnitConverter()
        celsius = uc.convert_to_storage(212.0, "temperature")
        back = uc.convert_from_storage(celsius, "temperature")
        assert back == pytest.approx(212.0, abs=0.01)

    def test_negative_temperature(self) -> None:
        """-40°F == -40°C (intersection point)."""
        uc = UnitConverter()
        result = uc.convert_to_storage(-40.0, "temperature")
        assert result == pytest.approx(-40.0, abs=0.01)


@pytest.mark.unit
class TestUnknownUnit:
    """Test unknown unit passthrough."""

    def test_unknown_unit_to_storage(self) -> None:
        """Unknown unit type returns value unchanged."""
        uc = UnitConverter()
        assert uc.convert_to_storage(42.0, "nonexistent") == 42.0

    def test_unknown_unit_from_storage(self) -> None:
        """Unknown unit type returns value unchanged."""
        uc = UnitConverter()
        assert uc.convert_from_storage(42.0, "nonexistent") == 42.0


@pytest.mark.unit
class TestCustomUnits:
    """Test custom unit registration."""

    def test_custom_unit_overrides_default(self) -> None:
        """Custom unit definitions override defaults."""
        custom = {
            "currency": UnitDefinition(
                display="EUR",
                storage="USD",
                to_storage=1.1,
                from_storage=0.909,
            )
        }
        uc = UnitConverter(unit_definitions=custom)
        assert uc.convert_to_storage(100.0, "currency") == pytest.approx(110.0)

    def test_register_new_unit(self) -> None:
        """register_unit adds a new unit at runtime."""
        uc = UnitConverter()
        uc.register_unit(
            "pressure",
            UnitDefinition(
                display="psi",
                storage="pascal",
                to_storage=6894.76,
                from_storage=0.000145038,
            ),
        )
        result = uc.convert_to_storage(1.0, "pressure")
        assert result == pytest.approx(6894.76, rel=1e-3)

    def test_get_unit_definition(self) -> None:
        """get_unit_definition returns UnitDefinition for known unit."""
        uc = UnitConverter()
        defn = uc.get_unit_definition("distance")
        assert defn is not None
        assert defn.display == "miles"
        assert defn.storage == "meters"

    def test_get_unit_definition_unknown(self) -> None:
        """get_unit_definition returns None for unknown unit."""
        uc = UnitConverter()
        assert uc.get_unit_definition("quantum_flux") is None


@pytest.mark.unit
class TestRatePerDistance:
    """Test rate_per_distance conversion."""

    def test_usd_per_mile_to_usd_per_meter(self) -> None:
        """1 USD/mile to USD/meter."""
        uc = UnitConverter()
        result = uc.convert_to_storage(1.0, "rate_per_distance")
        assert result == pytest.approx(0.000621371, rel=1e-3)

    def test_usd_per_meter_to_usd_per_mile(self) -> None:
        """USD/meter to USD/mile."""
        uc = UnitConverter()
        result = uc.convert_from_storage(0.000621371, "rate_per_distance")
        assert result == pytest.approx(1.0, rel=1e-2)
