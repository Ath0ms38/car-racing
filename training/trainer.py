import os
import threading
import time

import neat
import numpy as np

from simulation.car import CarConfig
from simulation.track import Track
from simulation.world import World
from training.fitness_evaluator import FitnessEvaluator


def _to_native(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _to_native(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


class Trainer:
    """Runs NEAT evolution in a background thread."""

    def __init__(self):
        self.running = False
        self.paused = False
        self.generation = 0
        self.best_fitness = 0.0
        self.best_genome = None
        self.fitness_evaluator = FitnessEvaluator()
        self.history: list[dict] = []
        self.speed = 1  # Sim steps per frame (1-50)
        self.show_rays = True

        self._lock = threading.Lock()
        self._current_state: dict = {}
        self._thread: threading.Thread | None = None
        self._population = None
        self._neat_config = None
        self._world: World | None = None
        self._track: Track | None = None
        self._car_config: CarConfig | None = None
        self._neat_config_path: str = ""
        self._checkpoint_dir = "checkpoints"
        self._auto_checkpoint_interval = 10

    def start(self, track: Track, car_config: CarConfig, neat_config_path: str):
        """Start new training from scratch."""
        if self.running:
            return

        self._track = track
        self._car_config = car_config
        self._neat_config_path = neat_config_path

        # Load NEAT config
        self._neat_config = neat.Config(
            neat.DefaultGenome,
            neat.DefaultReproduction,
            neat.DefaultSpeciesSet,
            neat.DefaultStagnation,
            neat_config_path,
        )

        # Override num_inputs from car config
        self._neat_config.genome_config.num_inputs = car_config.num_inputs
        self._neat_config.genome_config.num_outputs = 2

        # Create population
        self._population = neat.Population(self._neat_config)
        self._population.add_reporter(neat.StdOutReporter(True))
        self._population.add_reporter(neat.StatisticsReporter())

        os.makedirs(self._checkpoint_dir, exist_ok=True)
        self._population.add_reporter(
            neat.Checkpointer(
                generation_interval=self._auto_checkpoint_interval,
                filename_prefix=os.path.join(self._checkpoint_dir, "neat-checkpoint-"),
            )
        )

        # Create world
        self._world = World(track, car_config)

        # Reset state
        self.generation = 0
        self.best_fitness = 0.0
        self.best_genome = None
        self.history = []
        self.running = True
        self.paused = False

        # Launch thread
        self._thread = threading.Thread(target=self._training_thread, daemon=True)
        self._thread.start()

    def resume(self, checkpoint_path: str, car_config: CarConfig, neat_config_path: str):
        """Resume training from a checkpoint."""
        if self.running:
            return

        self._car_config = car_config
        self._neat_config_path = neat_config_path

        # Restore checkpoint
        self._population = neat.Checkpointer.restore_checkpoint(checkpoint_path)

        # Load and override config
        self._neat_config = self._population.config
        self._neat_config.genome_config.num_inputs = car_config.num_inputs
        self._neat_config.genome_config.num_outputs = 2

        # Re-add reporters
        self._population.reporters.reporters.clear()
        self._population.add_reporter(neat.StdOutReporter(True))
        self._population.add_reporter(neat.StatisticsReporter())
        self._population.add_reporter(
            neat.Checkpointer(
                generation_interval=self._auto_checkpoint_interval,
                filename_prefix=os.path.join(self._checkpoint_dir, "neat-checkpoint-"),
            )
        )

        self._world = World(self._track, car_config)

        self.running = True
        self.paused = False

        self._thread = threading.Thread(target=self._training_thread, daemon=True)
        self._thread.start()

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def stop(self):
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None

    def _training_thread(self):
        """Main training loop."""
        try:
            while self.running:
                if self.paused:
                    time.sleep(0.1)
                    continue
                # Run one generation
                self._population.run(self._eval_genomes, 1)
                self.generation = self._population.generation

                # Update history
                if self._population.reporters.reporters:
                    for reporter in self._population.reporters.reporters:
                        if isinstance(reporter, neat.StatisticsReporter):
                            gen_stats = reporter.get_fitness_stat(max)
                            avg_stats = reporter.get_fitness_mean()
                            if gen_stats:
                                entry = {
                                    "gen": self.generation,
                                    "best": gen_stats[-1] if gen_stats else 0,
                                    "avg": avg_stats[-1] if avg_stats else 0,
                                }
                                self.history.append(entry)
        except Exception as e:
            print(f"Training error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False

    def _eval_genomes(self, genomes, config):
        """Called by NEAT per generation."""
        if not self.running:
            raise SystemExit("Training stopped")

        n = len(genomes)
        self._world.reset_generation(n)
        self._world.generation = self.generation

        # Create networks
        networks = []
        for genome_id, genome in genomes:
            net = neat.nn.FeedForwardNetwork.create(genome, config)
            networks.append(net)

        # Simulation loop
        tick = 0
        max_ticks = self._car_config.max_ticks

        while self.running and tick < max_ticks:
            if self.paused:
                time.sleep(0.1)
                continue

            # Run sim steps per frame
            still_alive = True
            for _ in range(self.speed):
                if not self._world.step(networks):
                    still_alive = False
                    break

            # Update state for JS polling
            with self._lock:
                world_state = self._world.get_state()
                self._current_state = _to_native({
                    "cars": world_state["positions"],
                    "angles": world_state["angles"],
                    "velocity_angles": world_state["velocity_angles"],
                    "speeds": world_state["speeds"],
                    "alive": world_state["alive"],
                    "fitness": world_state["fitness"],
                    "rays": world_state["rays"] if self.show_rays else None,
                    "generation": self.generation,
                    "alive_count": int(np.sum(self._world.cars.alive)),
                    "total_count": n,
                    "best_fitness": float(self.best_fitness),
                    "species_count": len(self._population.species.species)
                        if self._population and hasattr(self._population, 'species') else 0,
                    "tick": self._world.tick,
                    "max_ticks": max_ticks,
                    "history": self.history[-100:],
                })

            if not still_alive:
                break

            tick = self._world.tick
            time.sleep(1.0 / 60.0)  # ~60fps

        # Evaluate fitness for each genome
        car_stats = self._world.build_car_stats()
        for i, (genome_id, genome) in enumerate(genomes):
            genome.fitness = self.fitness_evaluator.evaluate(car_stats[i])

        # Track best
        for genome_id, genome in genomes:
            if genome.fitness is not None and genome.fitness > self.best_fitness:
                self.best_fitness = genome.fitness
                self.best_genome = genome

    def get_state(self) -> dict:
        """Thread-safe state for JS polling."""
        with self._lock:
            return self._current_state.copy()

    def save_checkpoint(self) -> str:
        """Manual checkpoint save."""
        if self._population is None:
            return ""
        os.makedirs(self._checkpoint_dir, exist_ok=True)
        filepath = os.path.join(
            self._checkpoint_dir, f"neat-checkpoint-manual-{self.generation}"
        )
        # Use NEAT's checkpointer
        for reporter in self._population.reporters.reporters:
            if isinstance(reporter, neat.Checkpointer):
                reporter.save_checkpoint(
                    self._population.config,
                    self._population.population,
                    self._population.species,
                    self.generation,
                )
                return filepath
        return ""
