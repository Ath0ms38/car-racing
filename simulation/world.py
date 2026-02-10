import math

import numpy as np

from simulation.car import CarBatch, CarConfig
from simulation.track import Track


class World:
    """Manages one generation of cars on a track."""

    def __init__(self, track: Track, car_config: CarConfig):
        self.track = track
        self.car_config = car_config
        self.cars = CarBatch()
        self.generation = 0
        self.tick = 0
        self._last_ray_distances: np.ndarray | None = None

    def reset_generation(self, count: int):
        """Reset all cars to start position."""
        self.cars.reset(count, self.track.start_pos, self.track.start_angle)
        self.tick = 0
        self._last_ray_distances = None

    def step(self, networks: list) -> bool:
        """Execute one simulation step. Returns False when all dead or timeout."""
        if self.all_dead() or self.tick >= self.car_config.max_ticks:
            return False

        # 1. Get NN inputs
        inputs = self.cars.get_nn_inputs(self.track, self.car_config)

        # 2. Feed through networks, get outputs
        n = self.cars.count
        steering = np.zeros(n, dtype=np.float64)
        throttle = np.zeros(n, dtype=np.float64)

        for i in range(n):
            if self.cars.alive[i]:
                output = networks[i].activate(inputs[i].tolist())
                steering[i] = np.tanh(output[0])  # [-1, 1]
                throttle[i] = np.tanh(output[1])  # [-1, 1]

        # 3. Update physics
        self.cars.update(steering, throttle, self.car_config)

        # 4. Check grass collision
        self.cars.check_grass(self.track)

        # 5. Check checkpoints
        self.cars.check_checkpoints(self.track.checkpoints)

        # 6. Update wall stats (need ray distances)
        ray_distances = self.track.raycast_batch(
            self.cars.positions, self.cars.angles,
            self.car_config.ray_angles, self.car_config.ray_length
        )
        self._last_ray_distances = ray_distances
        self.cars.update_wall_stats(self.track, ray_distances, self.car_config.ray_length)

        # 7. Update distance to next checkpoint
        self.cars.update_distance_to_cp(self.track.checkpoints)

        # 8. Check stall
        self.cars.check_stall(self.car_config.stall_timeout)

        # 9. Increment tick
        self.tick += 1

        return not self.all_dead()

    def all_dead(self) -> bool:
        return not np.any(self.cars.alive)

    def get_state(self) -> dict:
        """For JS rendering."""
        state = self.cars.get_state_dict()
        state["tick"] = self.tick
        state["max_ticks"] = self.car_config.max_ticks

        # Include ray endpoints if available
        if self._last_ray_distances is not None:
            rays = []
            for i in range(self.cars.count):
                if self.cars.alive[i]:
                    car_rays = []
                    for j, offset in enumerate(self.car_config.ray_angles):
                        angle = self.cars.angles[i] + offset
                        dist = self._last_ray_distances[i, j] * self.car_config.ray_length
                        x1 = self.cars.positions[i, 0]
                        y1 = self.cars.positions[i, 1]
                        x2 = x1 + math.cos(angle) * dist
                        y2 = y1 + math.sin(angle) * dist
                        car_rays.append([x1, y1, x2, y2, self._last_ray_distances[i, j]])
                    rays.append(car_rays)
                else:
                    rays.append(None)
            state["rays"] = rays
        else:
            state["rays"] = None

        return state

    def build_car_stats(self) -> list:
        """Build CarStats list from CarBatch arrays for FitnessEvaluator."""
        from training.fitness_evaluator import CarStats

        stats = []
        for i in range(self.cars.count):
            time_alive = max(int(self.cars.time_alive[i]), 1)
            avg_speed = float(self.cars.speed_accumulator[i]) / time_alive
            avg_wall_dist = float(self.cars.wall_distance_accumulator[i]) / time_alive

            # Normalize distance_to_next_cp to [0, 1] range
            max_dist = max(self.track.width, self.track.height)
            dist_norm = min(float(self.cars.distance_to_next_cp[i]) / max_dist, 1.0)

            stats.append(CarStats(
                checkpoints_reached=int(self.cars.checkpoint_progress[i]),
                total_checkpoints=int(self.cars.total_checkpoints[i]),
                laps=int(self.cars.laps[i]),
                time_alive=int(self.cars.time_alive[i]),
                total_time=self.car_config.max_ticks,
                total_distance=float(self.cars.total_distance[i]),
                average_speed=avg_speed,
                max_speed_reached=float(self.cars.max_speed_reached[i]),
                current_speed=float(self.cars.speeds[i]),
                distance_to_next_cp=dist_norm,
                drift_count=int(self.cars.drift_count[i]),
                is_alive=bool(self.cars.alive[i]),
                crashed=bool(self.cars.crashed[i]),
                timed_out=bool(self.cars.timed_out[i]),
                wall_hits=int(self.cars.wall_hits[i]),
                min_wall_distance=float(
                    self.cars.min_wall_distance[i]
                    if self.cars.min_wall_distance[i] != np.inf else 0.0
                ),
                avg_wall_distance=avg_wall_dist,
            ))

        return stats
