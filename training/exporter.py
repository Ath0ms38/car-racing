import json
import os
from datetime import datetime, timezone

import neat

from simulation.car import CarConfig


class Exporter:

    @staticmethod
    def export_racer(
        genome: neat.DefaultGenome,
        car_config: CarConfig,
        neat_config: neat.Config,
        generation: int,
        species_count: int,
        track_name: str,
        fitness_code: str = "",
        name: str = None,
    ) -> str:
        """Export best genome as .racer JSON file. Returns filepath."""
        if name is None:
            name = f"{car_config.name}_Gen{generation}"

        racer_data = {
            "version": 1,
            "name": name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "car_config": car_config.to_dict(),
            "genome": Exporter.genome_to_dict(genome),
            "generation": generation,
            "species_count": species_count,
            "training_track": track_name,
            "fitness_code": fitness_code,
        }

        os.makedirs("exports", exist_ok=True)
        filepath = os.path.join("exports", f"{name}.racer")
        with open(filepath, "w") as f:
            json.dump(racer_data, f, indent=2)
        return filepath

    @staticmethod
    def import_racer(filepath: str) -> dict:
        """Load a .racer file. Returns dict with name, car_config, network, genome_data, metadata."""
        with open(filepath, "r") as f:
            data = json.load(f)

        car_config = CarConfig.from_dict(data["car_config"])

        # Rebuild NEAT config for network creation
        config_path = os.path.join("config", "neat_config.ini")
        neat_config = neat.Config(
            neat.DefaultGenome,
            neat.DefaultReproduction,
            neat.DefaultSpeciesSet,
            neat.DefaultStagnation,
            config_path,
        )
        neat_config.genome_config.num_inputs = car_config.num_inputs
        neat_config.genome_config.num_outputs = 2

        genome = Exporter.dict_to_genome(data["genome"], neat_config)
        network = neat.nn.FeedForwardNetwork.create(genome, neat_config)

        return {
            "name": data["name"],
            "car_config": car_config,
            "network": network,
            "genome_data": data["genome"],
            "metadata": {
                "exported_at": data.get("exported_at"),
                "generation": data.get("generation"),
                "species_count": data.get("species_count"),
                "training_track": data.get("training_track"),
                "fitness_code": data.get("fitness_code", ""),
            },
        }

    @staticmethod
    def genome_to_dict(genome: neat.DefaultGenome) -> dict:
        """Serialize a NEAT genome to a JSON-compatible dict."""
        nodes = []
        for key, node in genome.nodes.items():
            nodes.append({
                "key": key,
                "bias": node.bias,
                "activation": node.activation,
                "response": node.response,
                "aggregation": node.aggregation,
            })

        connections = []
        for key, conn in genome.connections.items():
            connections.append({
                "key": list(key),
                "weight": conn.weight,
                "enabled": conn.enabled,
                "innovation": conn.innovation,
            })

        return {
            "key": genome.key,
            "fitness": genome.fitness,
            "nodes": nodes,
            "connections": connections,
        }

    @staticmethod
    def dict_to_genome(data: dict, config: neat.Config) -> neat.DefaultGenome:
        """Deserialize a genome from dict."""
        genome = neat.DefaultGenome(data["key"])
        genome.fitness = data.get("fitness")

        for node_data in data["nodes"]:
            node = genome.create_node(config.genome_config, node_data["key"])
            node.bias = node_data["bias"]
            node.activation = node_data["activation"]
            node.response = node_data["response"]
            node.aggregation = node_data.get("aggregation", "sum")
            genome.nodes[node_data["key"]] = node

        for i, conn_data in enumerate(data["connections"]):
            key = tuple(conn_data["key"])
            innovation = conn_data.get("innovation", i)
            conn = neat.genome.DefaultConnectionGene(key, innovation)
            conn.weight = conn_data["weight"]
            conn.enabled = conn_data["enabled"]
            genome.connections[key] = conn

        return genome
