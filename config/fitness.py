def fitness(car):
    score = 0.0

    # Reward checkpoint progress (main signal)
    score += car.total_checkpoints * 1000

    # Reward getting closer to next checkpoint
    score += (1.0 - car.distance_to_next_cp) * 500

    # Reward completing laps
    score += car.laps * 10000

    # Reward average speed
    score += car.average_speed * 10

    # Reward staying away from walls (safer driving)
    score += car.avg_wall_distance * 2

    return score


# ──────────────────────────────────────────────────────────
# Available car attributes:
#
#   car.checkpoints_reached   int    Checkpoints passed in current lap
#   car.total_checkpoints     int    Total checkpoints crossed (all laps)
#   car.laps                  int    Full laps completed
#   car.time_alive            int    Ticks survived
#   car.total_time            int    Max ticks allowed per generation
#   car.total_distance        float  Total distance traveled (odometer)
#   car.average_speed         float  Mean speed over lifetime
#   car.max_speed_reached     float  Peak speed achieved
#   car.current_speed         float  Speed at death/end
#   car.distance_to_next_cp   float  Normalized [0,1] distance to next checkpoint
#   car.drift_count           int    Ticks spent drifting (0 if drift OFF)
#   car.is_alive              bool   Still alive at end of generation
#   car.crashed               bool   Died by hitting grass
#   car.timed_out             bool   Killed by stall timeout
#   car.wall_hits             int    Ticks spent grazing grass edge
#   car.min_wall_distance     float  Closest approach to grass (0 = touching)
#   car.avg_wall_distance     float  Average distance to nearest grass
#
# Available math: abs, min, max, pow, round
# ──────────────────────────────────────────────────────────
