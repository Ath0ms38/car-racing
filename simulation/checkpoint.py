import numpy as np


class Checkpoint:
    """A gate defined by two endpoints (a line segment)."""

    def __init__(self, x1: float, y1: float, x2: float, y2: float, index: int = 0):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.index = index

    def intersects_segment(self, px: float, py: float, qx: float, qy: float) -> bool:
        """Check if movement segment (p->q) crosses this gate."""
        return _segments_intersect(self.x1, self.y1, self.x2, self.y2, px, py, qx, qy)

    def intersects_batch(
        self, old_positions: np.ndarray, new_positions: np.ndarray
    ) -> np.ndarray:
        """Vectorized: check all cars against this checkpoint.
        old_positions: (N, 2), new_positions: (N, 2)
        Returns: (N,) bool array
        """
        return _segments_intersect_batch(
            self.x1, self.y1, self.x2, self.y2,
            old_positions[:, 0], old_positions[:, 1],
            new_positions[:, 0], new_positions[:, 1],
        )

    def midpoint(self) -> tuple:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def to_dict(self) -> dict:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, data: dict, index: int = 0) -> "Checkpoint":
        return cls(data["x1"], data["y1"], data["x2"], data["y2"], index)


def _cross(ax, ay, bx, by):
    """2D cross product of vectors a and b."""
    return ax * by - ay * bx


def _segments_intersect(
    ax1, ay1, ax2, ay2, bx1, by1, bx2, by2
) -> bool:
    """Check if line segment A (ax1,ay1)-(ax2,ay2) intersects B (bx1,by1)-(bx2,by2)."""
    dx_a = ax2 - ax1
    dy_a = ay2 - ay1
    dx_b = bx2 - bx1
    dy_b = by2 - by1

    denom = _cross(dx_a, dy_a, dx_b, dy_b)
    if abs(denom) < 1e-10:
        return False

    dx_ab = bx1 - ax1
    dy_ab = by1 - ay1

    t = _cross(dx_ab, dy_ab, dx_b, dy_b) / denom
    u = _cross(dx_ab, dy_ab, dx_a, dy_a) / denom

    return 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0


def _segments_intersect_batch(
    ax1, ay1, ax2, ay2,
    bx1: np.ndarray, by1: np.ndarray,
    bx2: np.ndarray, by2: np.ndarray,
) -> np.ndarray:
    """Vectorized segment intersection. Gate A is scalar, segments B are arrays."""
    dx_a = ax2 - ax1
    dy_a = ay2 - ay1
    dx_b = bx2 - bx1
    dy_b = by2 - by1

    denom = dx_a * dy_b - dy_a * dx_b

    safe_denom = np.where(np.abs(denom) < 1e-10, 1.0, denom)

    dx_ab = bx1 - ax1
    dy_ab = by1 - ay1

    t = (dx_ab * dy_b - dy_ab * dx_b) / safe_denom
    u = (dx_ab * dy_a - dy_ab * dx_a) / safe_denom

    valid = np.abs(denom) >= 1e-10
    return valid & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
