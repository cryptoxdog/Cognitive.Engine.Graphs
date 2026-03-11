"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, kge]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine/kge/transformations.py — 3D transformations.
Target Coverage: 85%+
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.kge.transformations import (
    Flip,
    Hyperplane,
    Rotation,
    Scale,
    Translation,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def embedding_6d() -> np.ndarray:
    """6D embedding vector (2 chunks of 3)."""
    return np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


@pytest.fixture
def embedding_3d() -> np.ndarray:
    """3D embedding vector."""
    return np.array([1.0, 0.0, 0.0])


# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestRotation:
    """Test Rotation transformation."""

    def test_identity_rotation(self, embedding_3d: np.ndarray) -> None:
        """0-degree rotation is identity."""
        rot = Rotation(angle=0.0, axis=(0.0, 0.0, 1.0))
        result = rot.apply(embedding_3d)
        np.testing.assert_allclose(result, embedding_3d, atol=1e-9)

    def test_90_degree_z_axis(self, embedding_3d: np.ndarray) -> None:
        """90° rotation around z-axis: (1,0,0) -> (0,1,0)."""
        rot = Rotation(angle=90.0, axis=(0.0, 0.0, 1.0))
        result = rot.apply(embedding_3d)
        np.testing.assert_allclose(result, [0.0, 1.0, 0.0], atol=1e-9)

    def test_180_degree_z_axis(self, embedding_3d: np.ndarray) -> None:
        """180° rotation around z-axis: (1,0,0) -> (-1,0,0)."""
        rot = Rotation(angle=180.0, axis=(0.0, 0.0, 1.0))
        result = rot.apply(embedding_3d)
        np.testing.assert_allclose(result, [-1.0, 0.0, 0.0], atol=1e-9)

    def test_inverse_rotation(self, embedding_3d: np.ndarray) -> None:
        """Inverse rotation restores original vector."""
        rot = Rotation(angle=45.0, axis=(1.0, 0.0, 0.0))
        transformed = rot.apply(embedding_3d)
        restored = rot.inverse().apply(transformed)
        np.testing.assert_allclose(restored, embedding_3d, atol=1e-9)

    def test_zero_axis_norm_passthrough(self) -> None:
        """Zero-norm axis returns embedding unchanged."""
        rot = Rotation(angle=90.0, axis=(0.0, 0.0, 0.0))
        v = np.array([1.0, 2.0, 3.0])
        result = rot.apply(v)
        np.testing.assert_allclose(result, v)

    def test_to_dict(self) -> None:
        """to_dict serializes correctly."""
        rot = Rotation(angle=30.0, axis=(1.0, 0.0, 0.0))
        d = rot.to_dict()
        assert d["type"] == "rotation"
        assert d["angle"] == 30.0
        assert d["axis"] == [1.0, 0.0, 0.0]

    def test_callable_interface(self, embedding_3d: np.ndarray) -> None:
        """Rotation is callable via __call__."""
        rot = Rotation(angle=90.0, axis=(0.0, 0.0, 1.0))
        result = rot(embedding_3d)
        np.testing.assert_allclose(result, [0.0, 1.0, 0.0], atol=1e-9)

    def test_6d_rotation(self, embedding_6d: np.ndarray) -> None:
        """Rotation applies to multi-chunk embeddings."""
        rot = Rotation(angle=90.0, axis=(0.0, 0.0, 1.0))
        result = rot.apply(embedding_6d)
        assert result.shape == embedding_6d.shape


@pytest.mark.unit
class TestScale:
    """Test Scale transformation."""

    def test_identity_scale(self, embedding_3d: np.ndarray) -> None:
        """Scale factor 1.0 is identity."""
        s = Scale(factor=1.0)
        result = s.apply(embedding_3d)
        np.testing.assert_allclose(result, embedding_3d)

    def test_double_scale(self, embedding_3d: np.ndarray) -> None:
        """Scale factor 2.0 doubles all components."""
        s = Scale(factor=2.0)
        result = s.apply(embedding_3d)
        np.testing.assert_allclose(result, embedding_3d * 2.0)

    def test_inverse_scale(self, embedding_3d: np.ndarray) -> None:
        """Inverse scale restores original."""
        s = Scale(factor=3.0)
        transformed = s.apply(embedding_3d)
        restored = s.inverse().apply(transformed)
        np.testing.assert_allclose(restored, embedding_3d, atol=1e-9)

    def test_zero_factor_raises(self) -> None:
        """Scale factor <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="must be > 0"):
            Scale(factor=0.0)

    def test_negative_factor_raises(self) -> None:
        """Negative scale factor raises ValueError."""
        with pytest.raises(ValueError, match="must be > 0"):
            Scale(factor=-1.0)

    def test_to_dict(self) -> None:
        """to_dict serializes correctly."""
        s = Scale(factor=1.5)
        d = s.to_dict()
        assert d["type"] == "scale"
        assert d["factor"] == 1.5


@pytest.mark.unit
class TestTranslation:
    """Test Translation transformation."""

    def test_zero_translation(self, embedding_3d: np.ndarray) -> None:
        """Zero offset is identity."""
        t = Translation(offset=(0.0, 0.0, 0.0))
        result = t.apply(embedding_3d)
        np.testing.assert_allclose(result, embedding_3d)

    def test_positive_translation(self, embedding_3d: np.ndarray) -> None:
        """Positive offset shifts vector."""
        t = Translation(offset=(1.0, 1.0, 1.0))
        result = t.apply(embedding_3d)
        np.testing.assert_allclose(result, [2.0, 1.0, 1.0])

    def test_inverse_translation(self, embedding_3d: np.ndarray) -> None:
        """Inverse translation restores original."""
        t = Translation(offset=(0.5, -0.3, 1.2))
        transformed = t.apply(embedding_3d)
        restored = t.inverse().apply(transformed)
        np.testing.assert_allclose(restored, embedding_3d, atol=1e-9)

    def test_cyclic_on_6d(self, embedding_6d: np.ndarray) -> None:
        """Translation cycles offset across 6D vector."""
        t = Translation(offset=(10.0, 20.0, 30.0))
        result = t.apply(embedding_6d)
        expected = embedding_6d + np.array([10.0, 20.0, 30.0, 10.0, 20.0, 30.0])
        np.testing.assert_allclose(result, expected)

    def test_to_dict(self) -> None:
        """to_dict serializes correctly."""
        t = Translation(offset=(1.0, 2.0, 3.0))
        d = t.to_dict()
        assert d["type"] == "translation"
        assert d["offset"] == [1.0, 2.0, 3.0]


@pytest.mark.unit
class TestFlip:
    """Test Flip (reflection) transformation."""

    def test_x_axis_flip(self) -> None:
        """Flip axis=0 negates x components."""
        f = Flip(axis=0)
        v = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        result = f.apply(v)
        np.testing.assert_allclose(result, [-1.0, 2.0, 3.0, -4.0, 5.0, 6.0])

    def test_y_axis_flip(self) -> None:
        """Flip axis=1 negates y components."""
        f = Flip(axis=1)
        v = np.array([1.0, 2.0, 3.0])
        result = f.apply(v)
        np.testing.assert_allclose(result, [1.0, -2.0, 3.0])

    def test_z_axis_flip(self) -> None:
        """Flip axis=2 negates z components."""
        f = Flip(axis=2)
        v = np.array([1.0, 2.0, 3.0])
        result = f.apply(v)
        np.testing.assert_allclose(result, [1.0, 2.0, -3.0])

    def test_flip_is_self_inverse(self) -> None:
        """Double flip restores original."""
        f = Flip(axis=0)
        v = np.array([1.0, 2.0, 3.0])
        result = f.apply(f.apply(v))
        np.testing.assert_allclose(result, v)

    def test_inverse_returns_same(self) -> None:
        """Flip.inverse() returns same axis (self-inverse)."""
        f = Flip(axis=1)
        inv = f.inverse()
        assert inv.axis == 1

    def test_to_dict(self) -> None:
        """to_dict serializes correctly."""
        f = Flip(axis=2)
        d = f.to_dict()
        assert d["type"] == "flip"
        assert d["axis"] == 2


@pytest.mark.unit
class TestHyperplane:
    """Test Hyperplane (reflection through plane) transformation."""

    def test_xy_plane_reflection(self) -> None:
        """Reflection through z=0 plane negates z component."""
        hp = Hyperplane(normal=(0.0, 0.0, 1.0), d=0.0)
        v = np.array([1.0, 2.0, 3.0])
        result = hp.apply(v)
        np.testing.assert_allclose(result, [1.0, 2.0, -3.0], atol=1e-9)

    def test_reflection_is_self_inverse(self) -> None:
        """Double hyperplane reflection restores original."""
        hp = Hyperplane(normal=(1.0, 1.0, 0.0), d=0.5)
        v = np.array([1.0, 2.0, 3.0])
        result = hp.apply(hp.apply(v))
        np.testing.assert_allclose(result, v, atol=1e-9)

    def test_zero_normal_passthrough(self) -> None:
        """Zero normal vector returns embedding unchanged."""
        hp = Hyperplane(normal=(0.0, 0.0, 0.0), d=0.0)
        v = np.array([1.0, 2.0, 3.0])
        result = hp.apply(v)
        np.testing.assert_allclose(result, v)

    def test_inverse_returns_same(self) -> None:
        """Hyperplane.inverse() returns same (self-inverse)."""
        hp = Hyperplane(normal=(1.0, 0.0, 0.0), d=1.0)
        inv = hp.inverse()
        assert inv.normal == hp.normal
        assert inv.d == hp.d

    def test_6d_reflection(self, embedding_6d: np.ndarray) -> None:
        """Hyperplane applies to multi-chunk embeddings."""
        hp = Hyperplane(normal=(0.0, 0.0, 1.0), d=0.0)
        result = hp.apply(embedding_6d)
        assert result.shape == embedding_6d.shape

    def test_to_dict(self) -> None:
        """to_dict serializes correctly."""
        hp = Hyperplane(normal=(1.0, 0.0, 0.0), d=0.5)
        d = hp.to_dict()
        assert d["type"] == "hyperplane"
        assert d["normal"] == [1.0, 0.0, 0.0]
        assert d["d"] == 0.5
