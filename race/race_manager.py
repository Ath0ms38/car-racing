import threading
import time

import numpy as np

from simulation.car import CarBatch, CarConfig
from simulation.track import Track
from training.exporter import Exporter


RACER_COLORS = [
    "#FF4444", "#4488FF", "#44CC44", "#FFAA00", "#CC44CC",
    "#44CCCC", "#FF8844", "#8844FF", "#CCCC44", "#FF44AA",
]


class RaceManager:
    """Manages a race between exported models."""

    def __init__(self):
        self.track: Track | None = None
        self.racers: list[dict] = []
        self.networks: list = []
        self.car_configs: list[CarConfig] = []
        self.car_batches: list[CarBatch] = []
        self.colors: list[str] = []
        self.num_laps = 3
        self.results: list[dict] = []
        self.running = False
        self.finished = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._current_state: dict = {}
        self._tick = 0
        self._finish_times: dict[int, float] = {}

    def load_race(self, track: Track, racer_paths: list, num_laps: int = 3) -> dict:
        """Load track and racers for a race."""
        try:
            self.track = track
            self.num_laps = num_laps
            self.racers = []
            self.networks = []
            self.car_configs = []
            self.car_batches = []
            self.colors = []
            self.results = []
            self.finished = False
            self._tick = 0
            self._finish_times = {}

            for i, path in enumerate(racer_paths):
                racer = Exporter.import_racer(path)
                self.racers.append(racer)
                self.networks.append(racer["network"])
                self.car_configs.append(racer["car_config"])

                batch = CarBatch()
                batch.reset(1, track.start_pos, track.start_angle)
                self.car_batches.append(batch)

                self.colors.append(RACER_COLORS[i % len(RACER_COLORS)])

            return {
                "success": True,
                "racers": [
                    {
                        "name": r["name"],
                        "color": self.colors[i],
                        "car_config": r["car_config"].to_dict(),
                        "generation": r["metadata"].get("generation"),
                    }
                    for i, r in enumerate(self.racers)
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start(self):
        """Launch race in thread."""
        self.running = True
        self.finished = False
        self._thread = threading.Thread(target=self._race_thread, daemon=True)
        self._thread.start()

    def _race_thread(self):
        """Main race loop."""
        try:
            num_cps = len(self.track.checkpoints) if self.track.checkpoints else 1

            while self.running and not self.finished:
                self._tick += 1

                # Update each racer independently
                for i in range(len(self.racers)):
                    batch = self.car_batches[i]
                    config = self.car_configs[i]

                    if not batch.alive[0]:
                        continue

                    # Get NN inputs
                    inputs = batch.get_nn_inputs(self.track, config)
                    output = self.networks[i].activate(inputs[0].tolist())

                    steering = np.array([np.tanh(output[0])])
                    throttle = np.array([np.tanh(output[1])])

                    batch.update(steering, throttle, config)
                    batch.check_grass(self.track)
                    batch.check_checkpoints(self.track.checkpoints)

                # Check for race completion
                all_done = True
                for i, batch in enumerate(self.car_batches):
                    if batch.alive[0] and batch.laps[0] >= self.num_laps:
                        if i not in self._finish_times:
                            self._finish_times[i] = self._tick / 60.0  # Approximate seconds
                    if batch.alive[0] and i not in self._finish_times:
                        all_done = False

                if not any(b.alive[0] for b in self.car_batches):
                    all_done = True

                # Update state
                with self._lock:
                    self._current_state = self._build_state()

                if all_done:
                    self.finished = True
                    with self._lock:
                        self._current_state = self._build_state()
                    break

                time.sleep(1.0 / 60.0)

        except Exception as e:
            print(f"Race error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False

    def _build_state(self) -> dict:
        cars = []
        for i in range(len(self.racers)):
            batch = self.car_batches[i]
            cars.append({
                "name": self.racers[i]["name"],
                "x": float(batch.positions[0, 0]),
                "y": float(batch.positions[0, 1]),
                "angle": float(batch.angles[0]),
                "velocity_angle": float(batch.velocity_angles[0]),
                "drift_enabled": self.car_configs[i].drift_enabled,
                "color": self.colors[i],
                "alive": bool(batch.alive[0]),
                "lap": int(batch.laps[0]),
                "checkpoint": int(batch.checkpoint_progress[0]),
                "total_checkpoints": int(batch.total_checkpoints[0]),
            })

        # Build rankings
        rankings = []
        for i in range(len(self.racers)):
            batch = self.car_batches[i]
            dnf = not batch.alive[0] and i not in self._finish_times
            rankings.append({
                "name": self.racers[i]["name"],
                "color": self.colors[i],
                "lap": int(batch.laps[0]),
                "checkpoint": int(batch.total_checkpoints[0]),
                "time": self._finish_times.get(i, 0),
                "dnf": dnf,
                "finished": i in self._finish_times,
            })

        # Sort: finished first (by time), then by progress
        rankings.sort(
            key=lambda r: (
                not r["finished"],  # Finished first
                r["time"] if r["finished"] else 0,
                -r["checkpoint"],   # More checkpoints = better
                r["dnf"],           # DNF last
            )
        )

        return {
            "cars": cars,
            "rankings": rankings,
            "finished": self.finished,
            "tick": self._tick,
        }

    def get_state(self) -> dict:
        with self._lock:
            return self._current_state.copy()

    def stop(self):
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def reset(self):
        self.stop()
        for i, batch in enumerate(self.car_batches):
            batch.reset(1, self.track.start_pos, self.track.start_angle)
        self.finished = False
        self._tick = 0
        self._finish_times = {}
