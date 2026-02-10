import configparser
import math

import numpy as np


class CarConfig:
    """Loaded from car_config.ini."""

    CAR_WIDTH: int = 30
    CAR_HEIGHT: int = 15

    def __init__(self):
        self.name = "MyCar"
        self.max_speed = 10.0
        self.acceleration = 0.5
        self.brake_force = 0.8
        self.rotation_speed = 4.0
        self.drift_enabled = False
        self.grip = 0.7
        self.ray_count = 5
        self.ray_length = 200.0
        self.ray_spread_angle = 180.0
        self.ray_angles: np.ndarray = np.array([])
        self.car_image = "assets/default_car.png"
        self.max_ticks = 2000
        self.stall_timeout = 200
        self._compute_ray_angles()

    def _compute_ray_angles(self):
        """Compute ray angles from count and spread."""
        if self.ray_count == 1:
            self.ray_angles = np.array([0.0])
        else:
            half = math.radians(self.ray_spread_angle) / 2
            self.ray_angles = np.linspace(-half, half, self.ray_count)

    @property
    def num_inputs(self) -> int:
        """Neural network input count."""
        base = self.ray_count + 3  # rays + speed + heading + accel_state
        if self.drift_enabled:
            base += 1  # + drift_angle
        return base

    @classmethod
    def from_ini(cls, filepath: str) -> "CarConfig":
        config = configparser.ConfigParser()
        config.read(filepath)
        c = cls()
        if "car" in config:
            sec = config["car"]
            c.name = sec.get("name", "MyCar")
            c.max_speed = sec.getfloat("max_speed", 10.0)
            c.acceleration = sec.getfloat("acceleration", 0.5)
            c.brake_force = sec.getfloat("brake_force", 0.8)
            c.rotation_speed = sec.getfloat("rotation_speed", 4.0)
            c.drift_enabled = sec.getboolean("drift_enabled", False)
            c.grip = sec.getfloat("grip", 0.7)
            c.ray_count = sec.getint("ray_count", 5)
            c.ray_length = sec.getfloat("ray_length", 200.0)
            c.ray_spread_angle = sec.getfloat("ray_spread_angle", 180.0)
            c.car_image = sec.get("car_image", "assets/default_car.png")
            c.max_ticks = sec.getint("max_ticks", 2000)
            c.stall_timeout = sec.getint("stall_timeout", 200)

            # Check for manual ray angles
            if "ray_angles" in sec:
                angles_str = sec.get("ray_angles")
                angles = [float(a.strip()) for a in angles_str.split(",")]
                c.ray_angles = np.radians(np.array(angles))
                c.ray_count = len(c.ray_angles)
            else:
                c._compute_ray_angles()
        return c

    @classmethod
    def from_dict(cls, d: dict) -> "CarConfig":
        c = cls()
        c.name = d.get("name", "MyCar")
        c.max_speed = float(d.get("max_speed", 10.0))
        c.acceleration = float(d.get("acceleration", 0.5))
        c.brake_force = float(d.get("brake_force", 0.8))
        c.rotation_speed = float(d.get("rotation_speed", 4.0))
        c.drift_enabled = bool(d.get("drift_enabled", False))
        c.grip = float(d.get("grip", 0.7))
        c.ray_length = float(d.get("ray_length", 200.0))
        c.car_image = d.get("car_image", "assets/default_car.png")
        c.max_ticks = int(d.get("max_ticks", 2000))
        c.stall_timeout = int(d.get("stall_timeout", 200))

        if "ray_angles" in d:
            angles_str = d["ray_angles"]
            if isinstance(angles_str, str):
                angles = [float(a.strip()) for a in angles_str.split(",")]
            else:
                angles = [float(a) for a in angles_str]
            c.ray_angles = np.radians(np.array(angles))
            c.ray_count = len(c.ray_angles)
        else:
            c.ray_count = int(d.get("ray_count", 5))
            c.ray_spread_angle = float(d.get("ray_spread_angle", 180.0))
            c._compute_ray_angles()
        return c

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "max_speed": self.max_speed,
            "acceleration": self.acceleration,
            "brake_force": self.brake_force,
            "rotation_speed": self.rotation_speed,
            "drift_enabled": self.drift_enabled,
            "grip": self.grip,
            "ray_count": self.ray_count,
            "ray_length": self.ray_length,
            "ray_angles": ", ".join(f"{math.degrees(a):.1f}" for a in self.ray_angles),
            "car_image": self.car_image,
            "max_ticks": self.max_ticks,
            "stall_timeout": self.stall_timeout,
        }

    def is_topology_compatible(self, other: "CarConfig") -> bool:
        """Check if ray_count and drift_enabled match (required for resume)."""
        return self.ray_count == other.ray_count and self.drift_enabled == other.drift_enabled


class CarBatch:
    """Vectorized state for ALL cars in a generation."""

    def __init__(self, count: int = 0):
        self.count = count
        if count > 0:
            self._init_arrays(count)

    def _init_arrays(self, count: int):
        self.count = count
        self.positions = np.zeros((count, 2), dtype=np.float64)
        self.angles = np.zeros(count, dtype=np.float64)
        self.velocity_angles = np.zeros(count, dtype=np.float64)
        self.speeds = np.zeros(count, dtype=np.float64)
        self.prev_speeds = np.zeros(count, dtype=np.float64)
        self.alive = np.ones(count, dtype=bool)
        self.fitness = np.zeros(count, dtype=np.float64)
        self.checkpoint_progress = np.zeros(count, dtype=np.int32)
        self.total_checkpoints = np.zeros(count, dtype=np.int32)
        self.laps = np.zeros(count, dtype=np.int32)
        self.time_alive = np.zeros(count, dtype=np.int32)
        self.stall_timer = np.zeros(count, dtype=np.int32)
        self.total_distance = np.zeros(count, dtype=np.float64)
        self.max_speed_reached = np.zeros(count, dtype=np.float64)
        self.speed_accumulator = np.zeros(count, dtype=np.float64)
        self.drift_count = np.zeros(count, dtype=np.int32)
        self.crashed = np.zeros(count, dtype=bool)
        self.timed_out = np.zeros(count, dtype=bool)
        self.wall_hits = np.zeros(count, dtype=np.int32)
        self.min_wall_distance = np.full(count, np.inf, dtype=np.float64)
        self.wall_distance_accumulator = np.zeros(count, dtype=np.float64)
        self.distance_to_next_cp = np.zeros(count, dtype=np.float64)

    def reset(self, count: int, start_pos: tuple, start_angle: float):
        """Reset all cars to start."""
        self._init_arrays(count)
        self.positions[:, 0] = start_pos[0]
        self.positions[:, 1] = start_pos[1]
        self.angles[:] = start_angle
        self.velocity_angles[:] = start_angle

    # Fixed timestep. With dt applied to both acceleration and movement,
    # max_speed becomes "pixels per second" and acceleration "pixels/sec^2".
    # max_speed=10 → 10px/sec → crosses 1200px canvas in ~2 min.
    # To get a good visual pace, we scale so max_speed=10 → ~200px/sec.
    SPEED_SCALE = 20.0  # multiplier: config speed 10 → 200 px/sec effective
    DT = 1.0 / 60.0     # 60 ticks per second

    def update(
        self,
        steering: np.ndarray,
        throttle: np.ndarray,
        config: CarConfig,
        track=None,
    ):
        """Vectorized physics update for all cars."""
        dt = self.DT
        scale = self.SPEED_SCALE
        alive_mask = self.alive.astype(np.float64)

        # Store previous speeds
        self.prev_speeds = self.speeds.copy()

        # Apply steering (radians per second * dt)
        self.angles += steering * config.rotation_speed * alive_mask * dt

        # Apply throttle: acceleration is in speed-units per second
        accel = np.where(throttle > 0, throttle * config.acceleration, 0.0)
        brake = np.where(throttle < 0, throttle * config.brake_force, 0.0)
        self.speeds += (accel + brake) * alive_mask * dt
        self.speeds = np.clip(self.speeds, 0.0, config.max_speed)

        # Movement: speed * scale gives pixels/sec, * dt gives pixels/tick
        if config.drift_enabled:
            angle_diff = self.angles - self.velocity_angles
            self.velocity_angles += angle_diff * config.grip
            move_angles = self.velocity_angles
            drift_active = np.abs(angle_diff) > 0.05
            self.drift_count += (drift_active & self.alive).astype(np.int32)
        else:
            self.velocity_angles = self.angles.copy()
            move_angles = self.angles

        px_per_tick = self.speeds * scale * dt  # pixels this tick

        dir_x = np.cos(move_angles)
        dir_y = np.sin(move_angles)

        if track is not None:
            # Subdivide movement to prevent tunneling through grass.
            # Checkpoint intersection uses start->end segment, no substeps needed.
            MAX_STEP_PX = 8.0
            max_px = np.max(px_per_tick * alive_mask) if np.any(self.alive) else 0.0
            substeps = max(1, int(np.ceil(max_px / MAX_STEP_PX)))

            step_dx = dir_x * px_per_tick / substeps
            step_dy = dir_y * px_per_tick / substeps

            # Save positions before movement for checkpoint detection
            old_positions = self.positions.copy()

            for _ in range(substeps):
                alive_f = self.alive.astype(np.float64)
                self.positions[:, 0] += step_dx * alive_f
                self.positions[:, 1] += step_dy * alive_f
                self.check_grass(track)

            # Check checkpoints once using full start->end path
            self.check_checkpoints_sweep(track.checkpoints, old_positions)
        else:
            # No track: simple movement, no collision
            self.positions[:, 0] += dir_x * px_per_tick * alive_mask
            self.positions[:, 1] += dir_y * px_per_tick * alive_mask

        dx = dir_x * px_per_tick * alive_mask
        dy = dir_y * px_per_tick * alive_mask

        # Update tracking stats
        dist = np.sqrt(dx * dx + dy * dy)
        self.total_distance += dist
        self.max_speed_reached = np.maximum(self.max_speed_reached, self.speeds * alive_mask)
        self.speed_accumulator += self.speeds * alive_mask
        self.time_alive += self.alive.astype(np.int32)
        self.stall_timer += self.alive.astype(np.int32)

    def check_grass(self, track):
        """Kill cars that touch grass."""
        on_grass = track.is_grass_batch(self.positions[:, 0], self.positions[:, 1])
        newly_dead = on_grass & self.alive
        self.alive &= ~on_grass
        self.crashed |= newly_dead

    def check_checkpoints(self, checkpoints: list):
        """Update checkpoint progress, laps, total_checkpoints."""
        if not checkpoints:
            return

        num_cps = len(checkpoints)
        old_pos = self.positions - np.stack(
            [np.cos(self.angles) * self.speeds, np.sin(self.angles) * self.speeds], axis=1
        )

        for i, cp in enumerate(checkpoints):
            # Only check cars that need this checkpoint next
            needs_this = (self.checkpoint_progress == i) & self.alive
            if not np.any(needs_this):
                continue

            crossed = cp.intersects_batch(old_pos, self.positions)
            advanced = crossed & needs_this

            if np.any(advanced):
                self.total_checkpoints += advanced.astype(np.int32)
                self.checkpoint_progress = np.where(
                    advanced,
                    (self.checkpoint_progress + 1) % num_cps,
                    self.checkpoint_progress,
                )
                # Check for lap completion
                lap_done = advanced & (self.checkpoint_progress == 0)
                self.laps += lap_done.astype(np.int32)
                # Reset stall timer on checkpoint
                self.stall_timer = np.where(advanced, 0, self.stall_timer)

    def check_checkpoints_sweep(self, checkpoints: list, old_positions: np.ndarray):
        """Check checkpoints using explicit old->new position sweep."""
        if not checkpoints:
            return

        num_cps = len(checkpoints)

        for i, cp in enumerate(checkpoints):
            needs_this = (self.checkpoint_progress == i) & self.alive
            if not np.any(needs_this):
                continue

            crossed = cp.intersects_batch(old_positions, self.positions)
            advanced = crossed & needs_this

            if np.any(advanced):
                self.total_checkpoints += advanced.astype(np.int32)
                self.checkpoint_progress = np.where(
                    advanced,
                    (self.checkpoint_progress + 1) % num_cps,
                    self.checkpoint_progress,
                )
                lap_done = advanced & (self.checkpoint_progress == 0)
                self.laps += lap_done.astype(np.int32)
                self.stall_timer = np.where(advanced, 0, self.stall_timer)

    def check_stall(self, max_stall: int):
        """Kill cars stalled too long."""
        stalled = (self.stall_timer >= max_stall) & self.alive
        self.alive &= ~stalled
        self.timed_out |= stalled

    def update_wall_stats(self, track, ray_distances: np.ndarray = None, ray_length: float = 200.0):
        """Track min/avg wall distance, wall_hits per tick.
        Uses shortest ray distance as proxy for wall distance.
        """
        if ray_distances is None:
            return

        alive_mask = self.alive
        # ray_distances: (N, R), normalized 0-1. Multiply by ray_length for pixels.
        min_ray = np.min(ray_distances, axis=1) * ray_length  # (N,) in pixels

        # Wall hit = any ray < 5px
        hit = (min_ray < 5.0) & alive_mask
        self.wall_hits += hit.astype(np.int32)

        # Min wall distance
        alive_min_ray = np.where(alive_mask, min_ray, np.inf)
        self.min_wall_distance = np.minimum(self.min_wall_distance, alive_min_ray)

        # Accumulate for average
        self.wall_distance_accumulator += np.where(alive_mask, min_ray, 0.0)

    def update_distance_to_cp(self, checkpoints: list):
        """Update distance to next checkpoint center."""
        if not checkpoints:
            self.distance_to_next_cp[:] = 0.0
            return

        for i in range(self.count):
            if not self.alive[i]:
                continue
            cp_idx = self.checkpoint_progress[i]
            cp = checkpoints[cp_idx]
            mx, my = cp.midpoint()
            dx = self.positions[i, 0] - mx
            dy = self.positions[i, 1] - my
            self.distance_to_next_cp[i] = math.sqrt(dx * dx + dy * dy)

    def get_nn_inputs(self, track, config: CarConfig) -> np.ndarray:
        """Build neural network inputs for all cars. Returns (N, num_inputs)."""
        # Raycast (cached for reuse by wall stats)
        ray_distances = track.raycast_batch(
            self.positions, self.angles, config.ray_angles, config.ray_length
        )
        self._last_ray_distances = ray_distances

        # Normalize speed: [0, 1]
        speed_norm = (self.speeds / config.max_speed).reshape(-1, 1)

        # Normalize heading: [-1, 1]
        heading_norm = (self.angles / math.pi).reshape(-1, 1)

        # Acceleration state: (speed - prev_speed) / acceleration, clamped [-1, 1]
        accel_state = np.clip(
            (self.speeds - self.prev_speeds) / max(config.acceleration, 1e-6),
            -1.0, 1.0
        ).reshape(-1, 1)

        inputs = [ray_distances, speed_norm, heading_norm, accel_state]

        if config.drift_enabled:
            drift_angle = np.clip(
                (self.angles - self.velocity_angles) / math.pi,
                -1.0, 1.0
            ).reshape(-1, 1)
            inputs.append(drift_angle)

        return np.hstack(inputs).astype(np.float32)

    def get_state_dict(self) -> dict:
        """Compact dict for JS rendering."""
        return {
            "positions": self.positions.tolist(),
            "angles": self.angles.tolist(),
            "velocity_angles": self.velocity_angles.tolist(),
            "speeds": self.speeds.tolist(),
            "alive": self.alive.tolist(),
            "fitness": self.fitness.tolist(),
            "checkpoint_progress": self.checkpoint_progress.tolist(),
            "total_checkpoints": self.total_checkpoints.tolist(),
            "laps": self.laps.tolist(),
        }
