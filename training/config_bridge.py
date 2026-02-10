import configparser
import math
import os
import re


class ConfigBridge:
    """Translates between UI form values and .ini config files."""

    @staticmethod
    def read_car_config(filepath: str) -> dict:
        """INI -> dict for JS form."""
        config = configparser.ConfigParser()
        config.read(filepath)
        result = {}
        if "car" in config:
            sec = config["car"]
            result = {
                "name": sec.get("name", "MyCar"),
                "max_speed": sec.getfloat("max_speed", 10.0),
                "acceleration": sec.getfloat("acceleration", 0.5),
                "brake_force": sec.getfloat("brake_force", 0.8),
                "rotation_speed": sec.getfloat("rotation_speed", 4.0),
                "drift_enabled": sec.getboolean("drift_enabled", False),
                "grip": sec.getfloat("grip", 0.7),
                "ray_length": sec.getfloat("ray_length", 200.0),
                "car_image": sec.get("car_image", "assets/default_car.png"),
                "max_ticks": sec.getint("max_ticks", 2000),
                "stall_timeout": sec.getint("stall_timeout", 200),
            }
            # Read ray_angles (or fall back to ray_count/ray_spread_angle)
            if "ray_angles" in sec:
                result["ray_angles"] = sec.get("ray_angles")
            else:
                count = sec.getint("ray_count", 5)
                spread = sec.getfloat("ray_spread_angle", 180.0)
                half = spread / 2
                if count == 1:
                    angles = [0.0]
                else:
                    step = spread / (count - 1)
                    angles = [-half + i * step for i in range(count)]
                result["ray_angles"] = ", ".join(f"{a:.1f}" for a in angles)
        return result

    @staticmethod
    def write_car_config(filepath: str, values: dict):
        """JS form -> INI. Preserves comments by using regex replacement."""
        with open(filepath, "r") as f:
            content = f.read()

        for key, val in values.items():
            if isinstance(val, bool):
                val_str = str(val)
            else:
                val_str = str(val)
            # Try to replace existing key
            pattern = rf"(?m)^{re.escape(key)}\s*=\s*.*$"
            if re.search(pattern, content):
                content = re.sub(pattern, f"{key} = {val_str}", content)
            else:
                # Append under [car] section
                content = content.rstrip() + f"\n{key} = {val_str}\n"

        # Remove old ray_count/ray_spread_angle if ray_angles is now set
        if "ray_angles" in values:
            content = re.sub(r"(?m)^ray_count\s*=\s*.*\n?", "", content)
            content = re.sub(r"(?m)^ray_spread_angle\s*=\s*.*\n?", "", content)

        with open(filepath, "w") as f:
            f.write(content)

    @staticmethod
    def read_neat_config(filepath: str) -> dict:
        """INI -> dict for JS form."""
        config = configparser.ConfigParser()
        config.read(filepath)
        result = {}
        for section in config.sections():
            for key, value in config[section].items():
                result[f"{section}.{key}"] = value
        return result

    @staticmethod
    def write_neat_config(filepath: str, values: dict):
        """JS form -> INI. Values are keyed as 'Section.key'."""
        config = configparser.ConfigParser()
        # Read existing to preserve structure
        if os.path.exists(filepath):
            config.read(filepath)

        for key, value in values.items():
            if "." in key:
                section, param = key.split(".", 1)
            else:
                section = "NEAT"
                param = key

            if section not in config:
                config[section] = {}
            config[section][param] = str(value)

        with open(filepath, "w") as f:
            config.write(f)

    @staticmethod
    def get_editable_neat_params() -> list:
        """Returns metadata for each user-editable parameter."""
        return [
            # Car config params
            {"key": "name", "label": "Car Name", "type": "str", "default": "MyCar",
             "section": "car", "tooltip": "Name used in exports and race labels", "resume_safe": True},
            {"key": "max_speed", "label": "Max Speed", "type": "float",
             "default": 10.0, "section": "car",
             "tooltip": "Maximum speed of the car", "resume_safe": True},
            {"key": "acceleration", "label": "Acceleration", "type": "float",
             "default": 4.0, "section": "car",
             "tooltip": "Acceleration rate (speed units per second)", "resume_safe": True},
            {"key": "brake_force", "label": "Brake Force", "type": "float",
             "default": 6.0, "section": "car",
             "tooltip": "Braking deceleration rate", "resume_safe": True},
            {"key": "rotation_speed", "label": "Rotation Speed", "type": "float",
             "default": 5.0, "section": "car",
             "tooltip": "Turning rate in radians per second", "resume_safe": True},
            {"key": "drift_enabled", "label": "Drift", "type": "bool",
             "default": False, "section": "car",
             "tooltip": "Enable drift mechanics (adds drift angle input to network)",
             "resume_safe": False},
            {"key": "grip", "label": "Grip", "type": "float",
             "default": 0.7, "section": "car",
             "tooltip": "Grip level (only when drift enabled)", "resume_safe": True},
            {"key": "ray_length", "label": "Ray Length", "type": "float",
             "default": 200, "section": "car",
             "tooltip": "Maximum ray distance in pixels", "resume_safe": True,
             "warning": "Changing sensor range mid-training may degrade performance"},
            {"key": "max_ticks", "label": "Max Ticks", "type": "int",
             "default": 2000, "section": "car",
             "tooltip": "Maximum ticks per generation", "resume_safe": True},
            {"key": "stall_timeout", "label": "Stall Timeout", "type": "int",
             "default": 200, "section": "car",
             "tooltip": "Kill car after N ticks without checkpoint", "resume_safe": True},
            # NEAT config params
            {"key": "pop_size", "label": "Population Size", "type": "int",
             "default": 200, "section": "NEAT",
             "tooltip": "Number of genomes per generation", "resume_safe": True,
             "warning": "Changing population size will add/remove genomes"},
            {"key": "compatibility_threshold", "label": "Compat Threshold", "type": "float",
             "default": 3.0, "section": "DefaultSpeciesSet",
             "tooltip": "Species compatibility threshold", "resume_safe": True},
            {"key": "conn_add_prob", "label": "Conn Add Rate", "type": "float",
             "default": 0.5, "section": "DefaultGenome",
             "tooltip": "Probability of adding a connection", "resume_safe": True},
            {"key": "conn_delete_prob", "label": "Conn Delete Rate", "type": "float",
             "default": 0.3, "section": "DefaultGenome",
             "tooltip": "Probability of deleting a connection", "resume_safe": True},
            {"key": "node_add_prob", "label": "Node Add Rate", "type": "float",
             "default": 0.2, "section": "DefaultGenome",
             "tooltip": "Probability of adding a node", "resume_safe": True},
            {"key": "node_delete_prob", "label": "Node Delete Rate", "type": "float",
             "default": 0.1, "section": "DefaultGenome",
             "tooltip": "Probability of deleting a node", "resume_safe": True},
            {"key": "weight_mutate_rate", "label": "Weight Mutation", "type": "float",
             "default": 0.8, "section": "DefaultGenome",
             "tooltip": "Probability of weight mutation", "resume_safe": True},
            {"key": "survival_threshold", "label": "Survival Threshold", "type": "float",
             "default": 0.2, "section": "DefaultReproduction",
             "tooltip": "Fraction of species that survives", "resume_safe": True},
            {"key": "max_stagnation", "label": "Max Stagnation", "type": "int",
             "default": 20, "section": "DefaultStagnation",
             "tooltip": "Generations before stagnant species removed", "resume_safe": True},
            {"key": "elitism", "label": "Elitism", "type": "int",
             "default": 2, "section": "DefaultReproduction",
             "tooltip": "Top genomes preserved unchanged", "resume_safe": True},
        ]

    @staticmethod
    def validate_for_resume(new_config: dict, checkpoint_config: dict) -> dict:
        """Check if config changes are compatible with resume.
        Returns {"valid": True/False, "errors": [...], "warnings": [...]}
        """
        errors = []
        warnings = []

        # Topology-breaking changes (number of rays changes network inputs)
        def _count_angles(cfg):
            angles = cfg.get("ray_angles", "")
            if isinstance(angles, str) and angles:
                return len([a.strip() for a in angles.split(",") if a.strip()])
            return cfg.get("ray_count", 5)

        new_count = _count_angles(new_config)
        old_count = _count_angles(checkpoint_config)
        if new_count != old_count:
            errors.append(
                f"Number of rays changed from {old_count} to {new_count}"
            )
        if new_config.get("drift_enabled") != checkpoint_config.get("drift_enabled"):
            errors.append(
                f"drift_enabled changed from {checkpoint_config.get('drift_enabled')} to {new_config.get('drift_enabled')}"
            )

        # Warning-worthy changes
        if new_config.get("ray_length") != checkpoint_config.get("ray_length"):
            warnings.append("Changing sensor range mid-training may degrade performance")
        if new_config.get("ray_angles") != checkpoint_config.get("ray_angles"):
            warnings.append("Changing ray angles mid-training may degrade performance")
        if new_config.get("pop_size") != checkpoint_config.get("pop_size"):
            warnings.append("Changing population size will add/remove genomes")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
