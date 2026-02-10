import json
import os
import glob as glob_module

import webview

from simulation.car import CarConfig
from simulation.track import Track
from training.config_bridge import ConfigBridge
from training.exporter import Exporter
from training.fitness_evaluator import FitnessEvaluator
from training.trainer import Trainer
from race.race_manager import RaceManager


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAR_CONFIG_PATH = os.path.join(BASE_DIR, "config", "car_config.ini")
NEAT_CONFIG_PATH = os.path.join(BASE_DIR, "config", "neat_config.ini")
TRACKS_DIR = os.path.join(BASE_DIR, "tracks")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
CHECKPOINTS_DIR = os.path.join(BASE_DIR, "checkpoints")


class Api:
    """Exposed to JavaScript via pywebview.api."""

    def __init__(self):
        self._window = None
        self._trainer = Trainer()
        self._race_manager = RaceManager()
        self._car_config = CarConfig.from_ini(CAR_CONFIG_PATH)
        self._current_track: Track | None = None
        self._current_track_name: str = ""

    # === Track Editor ===

    def save_track(self, track_json: str) -> dict:
        """Save track to .track file."""
        try:
            data = json.loads(track_json) if isinstance(track_json, str) else track_json
            track = Track.from_json(data)

            # Use file dialog
            os.makedirs(TRACKS_DIR, exist_ok=True)
            result = self._window.create_file_dialog(
                webview.FileDialog.SAVE,
                directory=TRACKS_DIR,
                save_filename="track.track",
                file_types=("Track Files (*.track)",),
            )
            if result:
                filepath = result if isinstance(result, str) else result[0]
                if not filepath.endswith(".track"):
                    filepath += ".track"
                track.save(filepath)
                return {"success": True, "path": filepath}
            return {"success": False, "error": "Cancelled"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_track_data(self, track_json: str, filename: str) -> dict:
        """Save track data directly without file dialog."""
        try:
            data = json.loads(track_json) if isinstance(track_json, str) else track_json
            track = Track.from_json(data)
            os.makedirs(TRACKS_DIR, exist_ok=True)
            filepath = os.path.join(TRACKS_DIR, filename)
            if not filepath.endswith(".track"):
                filepath += ".track"
            track.save(filepath)
            return {"success": True, "path": filepath}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_track(self, filepath: str = None) -> dict:
        """Load track from .track file."""
        try:
            if filepath is None:
                result = self._window.create_file_dialog(
                    webview.FileDialog.OPEN,
                    directory=TRACKS_DIR,
                    file_types=("Track Files (*.track)",),
                )
                if not result:
                    return {"success": False, "error": "Cancelled"}
                filepath = result[0] if isinstance(result, (list, tuple)) else result

            track = Track.load(filepath)
            self._current_track = track
            self._current_track_name = os.path.basename(filepath)
            return {"success": True, "data": track.to_json()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_tracks(self) -> list:
        """List saved tracks."""
        os.makedirs(TRACKS_DIR, exist_ok=True)
        tracks = glob_module.glob(os.path.join(TRACKS_DIR, "*.track"))
        return [{"name": os.path.basename(t), "path": t} for t in sorted(tracks)]

    def delete_track(self, filepath: str) -> bool:
        try:
            os.remove(filepath)
            return True
        except Exception:
            return False

    # === Config ===

    def get_car_config(self) -> dict:
        return ConfigBridge.read_car_config(CAR_CONFIG_PATH)

    def set_car_config(self, config: dict) -> bool:
        try:
            ConfigBridge.write_car_config(CAR_CONFIG_PATH, config)
            new_config = CarConfig.from_ini(CAR_CONFIG_PATH)
            # Update existing object in-place so trainer/world see changes live
            for attr in vars(new_config):
                setattr(self._car_config, attr, getattr(new_config, attr))
            return True
        except Exception:
            return False

    def get_neat_config(self) -> dict:
        return ConfigBridge.read_neat_config(NEAT_CONFIG_PATH)

    def set_neat_config(self, config: dict) -> bool:
        try:
            ConfigBridge.write_neat_config(NEAT_CONFIG_PATH, config)
            return True
        except Exception:
            return False

    def get_editable_params(self) -> list:
        return ConfigBridge.get_editable_neat_params()

    def validate_config_for_resume(self, config: dict) -> dict:
        checkpoint_config = self._car_config.to_dict()
        return ConfigBridge.validate_for_resume(config, checkpoint_config)

    # === Fitness Function ===

    def get_fitness_code(self) -> str:
        return self._trainer.fitness_evaluator.get_code()

    def get_fitness_file_path(self) -> str:
        return self._trainer.fitness_evaluator.get_file_path()

    def reload_fitness(self) -> dict:
        """Reload fitness function from config/fitness.py."""
        return self._trainer.fitness_evaluator.load_from_file()

    # === Training ===

    def start_training(self, track_json: str) -> dict:
        """Start NEAT training."""
        try:
            data = json.loads(track_json) if isinstance(track_json, str) else track_json
            track = Track.from_json(data)

            # Validation
            if not track.checkpoints:
                return {"success": False, "error": "Place at least one checkpoint"}
            if track.start_pos is None:
                return {"success": False, "error": "Place a start position"}
            if track.is_grass(int(track.start_pos[0]), int(track.start_pos[1])):
                return {"success": False, "error": "Start position is on grass"}

            self._current_track = track
            self._car_config = CarConfig.from_ini(CAR_CONFIG_PATH)

            # Update NEAT config num_inputs
            self._update_neat_num_inputs()

            self._trainer.start(track, self._car_config, NEAT_CONFIG_PATH, window=self._window)
            self._trainer._track = track
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_neat_num_inputs(self):
        """Update num_inputs in neat config based on car config (preserves comments)."""
        import re
        with open(NEAT_CONFIG_PATH, "r") as f:
            content = f.read()
        content = re.sub(
            r"(?m)^num_inputs\s*=\s*\d+",
            f"num_inputs = {self._car_config.num_inputs}",
            content,
        )
        with open(NEAT_CONFIG_PATH, "w") as f:
            f.write(content)

    def resume_training(self, checkpoint_path: str, track_json: str = None) -> dict:
        """Resume from checkpoint."""
        try:
            if track_json:
                data = json.loads(track_json) if isinstance(track_json, str) else track_json
                track = Track.from_json(data)
                self._current_track = track
            if self._current_track is None:
                return {"success": False, "error": "Load a track before resuming training"}
            self._car_config = CarConfig.from_ini(CAR_CONFIG_PATH)
            self._update_neat_num_inputs()
            self._trainer._track = self._current_track
            self._trainer.resume(checkpoint_path, self._car_config, NEAT_CONFIG_PATH, window=self._window)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pause_training(self) -> bool:
        self._trainer.pause()
        return True

    def unpause_training(self) -> bool:
        self._trainer.unpause()
        return True

    def stop_training(self) -> bool:
        self._trainer.stop()
        return True

    def set_speed(self, steps_per_frame: int) -> bool:
        self._trainer.speed = max(1, min(50, steps_per_frame))
        return True

    def get_training_state(self) -> dict:
        return self._trainer.get_state()

    def toggle_rays(self, visible: bool) -> bool:
        self._trainer.show_rays = visible
        return True

    def save_checkpoint(self) -> str:
        return self._trainer.save_checkpoint()

    def list_checkpoints(self) -> list:
        """List available checkpoints."""
        os.makedirs(CHECKPOINTS_DIR, exist_ok=True)
        # Match both old format (neat-checkpoint-*) and new format (CarName-gen-*)
        files = glob_module.glob(os.path.join(CHECKPOINTS_DIR, "*-gen-*"))
        files += glob_module.glob(os.path.join(CHECKPOINTS_DIR, "neat-checkpoint-*"))
        files = list(set(files))  # deduplicate
        result = []
        for f in sorted(files, key=os.path.getmtime, reverse=True):
            name = os.path.basename(f)
            result.append({
                "name": name,
                "path": f,
                "modified": os.path.getmtime(f),
            })
        return result

    # === Export ===

    def export_best_racer(self, name: str = None) -> dict:
        """Export best genome as .racer."""
        try:
            if self._trainer.best_genome is None:
                return {"success": False, "error": "No trained genome available"}

            filepath = Exporter.export_racer(
                genome=self._trainer.best_genome,
                car_config=self._car_config,
                neat_config=self._trainer._neat_config,
                generation=self._trainer.generation,
                species_count=len(self._trainer._population.species.species)
                    if self._trainer._population else 0,
                track_name=self._current_track_name,
                fitness_code=self._trainer.fitness_evaluator.get_code(),
                name=name,
            )
            return {"success": True, "path": filepath}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_racers(self) -> list:
        """List exported racers."""
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        files = glob_module.glob(os.path.join(EXPORTS_DIR, "*.racer"))
        result = []
        for f in sorted(files, key=os.path.getmtime, reverse=True):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                result.append({
                    "name": data.get("name", os.path.basename(f)),
                    "path": f,
                    "generation": data.get("generation"),
                    "fitness": data.get("genome", {}).get("fitness"),
                    "car_config": data.get("car_config", {}),
                })
            except Exception:
                result.append({"name": os.path.basename(f), "path": f})
        return result

    # === Race ===

    def start_race(self, track_json: str, racer_paths: list, num_laps: int = 3) -> dict:
        """Start a race."""
        try:
            data = json.loads(track_json) if isinstance(track_json, str) else track_json
            track = Track.from_json(data)
            result = self._race_manager.load_race(track, racer_paths, num_laps)
            if result.get("success"):
                self._race_manager.start()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_race_state(self) -> dict:
        return self._race_manager.get_state()

    def stop_race(self) -> bool:
        self._race_manager.stop()
        return True

    # === File Dialogs ===

    def open_file_dialog(self, filetypes: list = None) -> str:
        """Native file picker."""
        ft = tuple(filetypes) if filetypes else ("All Files (*.*)",)
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=ft,
        )
        if result:
            return result[0] if isinstance(result, (list, tuple)) else result
        return ""

    def save_file_dialog(self, filename: str = "") -> str:
        """Native save dialog."""
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=filename,
        )
        if result:
            return result if isinstance(result, str) else result[0]
        return ""
