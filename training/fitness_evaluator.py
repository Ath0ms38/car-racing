import os
from dataclasses import dataclass


@dataclass
class CarStats:
    """Read-only snapshot of car state, passed to fitness function as `car`."""
    checkpoints_reached: int
    total_checkpoints: int
    laps: int
    time_alive: int
    total_time: int
    total_distance: float
    average_speed: float
    max_speed_reached: float
    current_speed: float
    distance_to_next_cp: float
    drift_count: int
    is_alive: bool
    crashed: bool
    timed_out: bool
    wall_hits: int
    min_wall_distance: float
    avg_wall_distance: float


FITNESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "fitness.py")


class FitnessEvaluator:
    """Loads and runs fitness function from config/fitness.py."""

    def __init__(self):
        self.code = ""
        self._compiled = None
        self._file_path = os.path.normpath(FITNESS_FILE)
        self.load_from_file()

    def load_from_file(self) -> dict:
        """Load fitness function from config/fitness.py.
        Returns {"valid": True} or {"valid": False, "error": "..."}
        """
        try:
            with open(self._file_path, "r") as f:
                code = f.read()
            return self._validate_and_set(code)
        except FileNotFoundError:
            return {"valid": False, "error": f"File not found: {self._file_path}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_and_set(self, code: str) -> dict:
        """Validate code and set as active fitness function."""
        try:
            compile(code, "<fitness>", "exec")

            namespace = {
                "abs": abs, "min": min, "max": max,
                "pow": pow, "round": round,
                "__builtins__": {},
            }
            exec(code, namespace)

            if "fitness" not in namespace:
                return {"valid": False, "error": "File must define a 'fitness(car)' function"}

            func = namespace["fitness"]

            # Test with dummy CarStats
            dummy = CarStats(
                checkpoints_reached=0, total_checkpoints=0, laps=0,
                time_alive=100, total_time=2000, total_distance=50.0,
                average_speed=5.0, max_speed_reached=8.0, current_speed=3.0,
                distance_to_next_cp=0.5, drift_count=0, is_alive=False,
                crashed=True, timed_out=False, wall_hits=5,
                min_wall_distance=3.0, avg_wall_distance=10.0,
            )
            result = func(dummy)
            if not isinstance(result, (int, float)):
                return {"valid": False, "error": f"Must return a number, got {type(result).__name__}"}

            self.code = code
            self._compiled = func
            return {"valid": True}

        except SyntaxError as e:
            return {"valid": False, "error": f"Syntax error on line {e.lineno}: {e.msg}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def evaluate(self, car_stats: CarStats) -> float:
        """Evaluate fitness for a single car."""
        try:
            result = self._compiled(car_stats)
            return float(result)
        except Exception:
            return 0.0

    def get_code(self) -> str:
        """Return current code (re-reads from file)."""
        try:
            with open(self._file_path, "r") as f:
                return f.read()
        except Exception:
            return self.code

    def get_file_path(self) -> str:
        return self._file_path
