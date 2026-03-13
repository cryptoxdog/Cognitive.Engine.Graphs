"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [kge, transformations]
owner: engine-team
status: active
--- /L9_META ---

3D Transformation Primitives for CompoundE3D.

Defines the geometric operations used in knowledge graph embedding space:
rotation, scaling, translation, reflection (flip), and hyperplane projection.

Each transformation implements __call__ for direct application to embedding
tensors and to_dict()/from_dict() for serialization in PacketEnvelope payloads.

**Invariants:**
- All transformations are invertible (required for link prediction)
- Parameter ranges validated on construction
- Deterministic: same params → same output (no RNG)
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt


class Transformation3D(ABC):
    """Abstract base for 3D embedding transformations."""

    @abstractmethod
    def apply(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Apply this transformation to an embedding composed of consecutive 3-element (x, y, z) components.
        
        Returns:
            npt.NDArray[np.float64]: Embedding with the same shape as the input where each 3-element block has been transformed.
        """

    @abstractmethod
    def inverse(self) -> Transformation3D:
        """Return inverse transformation."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """
        Return a JSON-serializable dictionary representing this transformation for inclusion in a PacketEnvelope or audit trail.
        
        Returns:
            dict[str, Any]: Serialized transformation fields (including "type" and parameter values) suitable for storage or transmission.
        """

    def __call__(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Apply the transformation to an embedding vector.
        
        Parameters:
            embedding (npt.NDArray[np.float64]): 1-D array of concatenated 3D coordinates (length should be a multiple of 3).
        
        Returns:
            npt.NDArray[np.float64]: Transformed embedding array with the same shape and dtype as the input.
        """
        return self.apply(embedding)


@dataclass(frozen=True)
class Rotation(Transformation3D):
    """Rotation in 3D embedding space around an arbitrary axis.

    Args:
        angle: Rotation angle in degrees.
        axis: Unit axis tuple (x, y, z).  Normalized on construction.
    """

    angle: float
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)

    def apply(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Rotate each consecutive 3-element block of the flattened embedding by the instance's angle around the instance's axis.
        
        Parameters:
            embedding (npt.NDArray[np.float64]): 1-D array of float64 containing concatenated 3D vectors (x, y, z). If the array length is not a multiple of 3, any trailing 1–2 elements are left unchanged.
        
        Returns:
            npt.NDArray[np.float64]: A new array with the same shape as `embedding` where each complete 3-element block has been rotated; if the rotation axis has near-zero length, the original `embedding` is returned unchanged.
        """
        rad = math.radians(self.angle)
        ax = np.array(self.axis, dtype=np.float64)
        norm = np.linalg.norm(ax)
        if norm < 1e-9:
            return embedding
        ax = ax / norm

        cos_a, sin_a = math.cos(rad), math.sin(rad)
        # Rodrigues' rotation applied per 3-element chunk
        out = np.copy(embedding)
        for i in range(0, len(embedding) - 2, 3):
            v = embedding[i : i + 3]
            out[i : i + 3] = v * cos_a + np.cross(ax, v) * sin_a + ax * np.dot(ax, v) * (1 - cos_a)
        return out

    def inverse(self) -> Rotation:
        return Rotation(angle=-self.angle, axis=self.axis)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "rotation", "angle": self.angle, "axis": list(self.axis)}


@dataclass(frozen=True)
class Scale(Transformation3D):
    """Uniform scaling of embedding magnitude.

    Args:
        factor: Scale factor.  Must be > 0.
    """

    factor: float = 1.0

    def __post_init__(self) -> None:
        """
        Validate that the scale factor is greater than zero.
        
        Raises:
            ValueError: If `self.factor` is less than or equal to 0.
        """
        if self.factor <= 0:
            raise ValueError(f"Scale factor must be > 0, got {self.factor}")

    def apply(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Scale the embedding by this Scale's factor.
        
        Returns:
            npt.NDArray[np.float64]: The input embedding multiplied elementwise by the scale factor.
        """
        return embedding * self.factor

    def inverse(self) -> Scale:
        """
        Create the inverse Scale transformation.
        
        Returns:
            Scale: A new Scale whose factor is 1.0 divided by this Scale's factor.
        """
        return Scale(factor=1.0 / self.factor)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "scale", "factor": self.factor}


@dataclass(frozen=True)
class Translation(Transformation3D):
    """Translation (shift) of embedding vector.

    Args:
        offset: Tuple (dx, dy, dz) applied cyclically across dimensions.
    """

    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def apply(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Translate the embedding by adding the instance offset tiled across its dimensions.
        
        The offset (dx, dy, dz) is repeated to form a shift vector that is truncated or extended to match the input length and added elementwise to the input embedding.
        
        Parameters:
            embedding (npt.NDArray[np.float64]): 1-D embedding vector interpreted as consecutive 3-element (x, y, z) blocks.
        
        Returns:
            npt.NDArray[np.float64]: The translated embedding with the same shape as the input.
        """
        shift = np.tile(np.array(self.offset, dtype=np.float64), int(np.ceil(len(embedding) / 3)))[: len(embedding)]
        result: npt.NDArray[np.float64] = embedding + shift
        return result

    def inverse(self) -> Translation:
        """
        Compute the inverse translation.
        
        Returns:
            Translation: A Translation whose offset is the elementwise negation of this translation's offset, such that applying it reverses the original translation.
        """
        neg = tuple(-x for x in self.offset)
        return Translation(offset=(neg[0], neg[1], neg[2]))

    def to_dict(self) -> dict[str, Any]:
        return {"type": "translation", "offset": list(self.offset)}


@dataclass(frozen=True)
class Flip(Transformation3D):
    """Reflection across a coordinate axis.

    Args:
        axis: 0 = x, 1 = y, 2 = z.
    """

    axis: int = 0

    def apply(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Reflect the embedding across the specified coordinate axis by negating that axis in every 3-element block.
        
        Returns:
            npt.NDArray[np.float64]: The transformed embedding where elements at positions self.axis, self.axis+3, self.axis+6, ... are multiplied by -1.
        """
        out = np.copy(embedding)
        out[self.axis :: 3] *= -1
        return out

    def inverse(self) -> Flip:
        return Flip(axis=self.axis)  # self-inverse

    def to_dict(self) -> dict[str, Any]:
        return {"type": "flip", "axis": self.axis}


@dataclass(frozen=True)
class Hyperplane(Transformation3D):
    """Projection onto / reflection through a hyperplane ax+by+cz=d.

    Args:
        normal: (a, b, c) — plane normal.
        d: Plane offset.
    """

    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
    d: float = 0.0

    def apply(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Project each contiguous 3-element block of `embedding` across the plane defined by `normal · x = d`.
        
        Parameters:
            embedding (npt.NDArray[np.float64]): 1D array whose length is a multiple of 3 (or trailing elements ignored); interpreted as a sequence of 3D vectors [x, y, z, x, y, z, ...].
        
        Returns:
            npt.NDArray[np.float64]: A copy of `embedding` with each 3-element block reflected across the plane `normal · x = d`. If the provided normal has near-zero magnitude, the original `embedding` is returned unchanged.
        """
        n = np.array(self.normal, dtype=np.float64)
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            return embedding
        n = n / norm
        out = np.copy(embedding)
        for i in range(0, len(embedding) - 2, 3):
            v = embedding[i : i + 3]
            dist = np.dot(v, n) - self.d
            out[i : i + 3] = v - 2 * dist * n  # reflection
        return out

    def inverse(self) -> Hyperplane:
        return Hyperplane(normal=self.normal, d=self.d)  # self-inverse

    def to_dict(self) -> dict[str, Any]:
        return {"type": "hyperplane", "normal": list(self.normal), "d": self.d}


@dataclass(frozen=True)
class Shear(Transformation3D):
    """Shear transformation in 3D embedding space.

    Shear matrix: [[1, shxy, shxz], [shyx, 1, shyz], [shzx, shzy, 1]]
    Applied per 3-element block of the embedding vector.

    Shear is the 5th CompoundE3D primitive (H) and captures
    asymmetric relational patterns (e.g., hypernymy, causality).
    """

    shxy: float = 0.0
    shxz: float = 0.0
    shyx: float = 0.0
    shyz: float = 0.0
    shzx: float = 0.0
    shzy: float = 0.0

    def _matrix(self) -> npt.NDArray[np.float64]:
        """
        Constructs the 3x3 shear matrix from the instance's shear components.
        
        Returns:
            npt.NDArray[np.float64]: 3x3 NumPy array (dtype float64) representing the shear matrix
            [[1.0, shxy, shxz],
             [shyx, 1.0, shyz],
             [shzx, shzy, 1.0]] where the `sh*` entries are the corresponding instance attributes.
        """
        return np.array(
            [
                [1.0, self.shxy, self.shxz],
                [self.shyx, 1.0, self.shyz],
                [self.shzx, self.shzy, 1.0],
            ],
            dtype=np.float64,
        )

    def apply(self, embedding: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Apply a 3D shear to an embedding by transforming each consecutive 3-element block.
        
        Parameters:
            embedding (npt.NDArray[np.float64]): Flattened embedding whose coordinates are grouped as (x, y, z) blocks. Length need not be a multiple of 3; trailing elements (if any) are left unchanged.
        
        Returns:
            npt.NDArray[np.float64]: A new array with each 3-element block replaced by the shear-transformed block.
        """
        mat = self._matrix()
        out = np.copy(embedding)
        for i in range(0, len(embedding) - 2, 3):
            out[i : i + 3] = mat @ embedding[i : i + 3]
        return out

    def inverse(self) -> Shear:
        """Inverse shear via matrix inverse (exists if det != 0)."""
        mat_inv = np.linalg.inv(self._matrix())
        return Shear(
            shxy=-mat_inv[0, 1],
            shxz=-mat_inv[0, 2],
            shyx=-mat_inv[1, 0],
            shyz=-mat_inv[1, 2],
            shzx=-mat_inv[2, 0],
            shzy=-mat_inv[2, 1],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "shear",
            "shxy": self.shxy,
            "shxz": self.shxz,
            "shyx": self.shyx,
            "shyz": self.shyz,
            "shzx": self.shzx,
            "shzy": self.shzy,
        }
