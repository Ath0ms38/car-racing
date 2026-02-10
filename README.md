# NEAT Car AI Trainer

Application desktop pour entraîner des voitures autonomes par neuroévolution (NEAT). Dessinez un circuit, configurez la physique et les capteurs, lancez l'entraînement et observez les IA apprendre à conduire en temps réel.

## Fonctionnalités

- **Éditeur de circuit** — Peignez la route au pinceau, placez les checkpoints et le point de départ
- **Entraînement NEAT** — Neuroévolution avec visualisation temps réel des voitures, rayons et graphe de fitness
- **Mode Course** — Importez plusieurs modèles entraînés et faites-les s'affronter sur un circuit
- **Configuration complète** — Physique, capteurs, réseau de neurones et fonction de fitness entièrement paramétrables
- **Modifications en direct** — Les changements de config s'appliquent immédiatement pendant l'entraînement

## Installation

### Prérequis

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets)

### Étapes

```bash
# Fork et cloner le dépôt
# 1. Cliquez "Fork" sur https://github.com/Ath0ms38/car-racing
# 2. Clonez votre fork :
git clone https://github.com/<votre-username>/car-racing.git
cd car-racing

# Installer les dépendances avec uv
uv sync

# Lancer l'application
uv run python main.py
```

### Dépendances

| Paquet | Rôle |
|---|---|
| `pywebview` | Fenêtre desktop avec webview intégrée |
| `neat-python` | Algorithme NEAT (neuroévolution) |
| `numpy` | Calculs vectorisés (physique, raycasting) |
| `PyQt6` + `PyQt6-WebEngine` | Backend graphique Qt |

## Utilisation

### 1. Éditeur de circuit

- **Road** — Peindre la route (la zone verte est l'herbe = mort)
- **Erase** — Effacer de la route
- **Checkpoint** — Placer des portes de checkpoint (les voitures doivent les traverser dans l'ordre)
- **Start** — Placer le point de départ et l'orientation initiale
- **Save / Load** — Sauvegarder et charger des circuits (fichiers `.track`)

### 2. Entraînement

1. Dessinez un circuit avec au moins 2 checkpoints et un point de départ
2. Allez dans l'onglet **Training**
3. Configurez les paramètres (voir section Configuration)
4. Cliquez **Start**
5. Utilisez le slider **Speed** pour accélérer la simulation (x1 à x50)
6. **Export Best** pour sauvegarder le meilleur modèle en `.racer`

### 3. Mode Course

1. Allez dans l'onglet **Race**
2. Chargez un circuit
3. Ajoutez des racers (fichiers `.racer` exportés depuis l'entraînement)
4. Configurez le nombre de tours
5. Lancez la course

## Configuration

### Physique de la voiture (`config/car_config.ini`)

```ini
[car]
name = MyCar

# Physique
max_speed = 10.0        # Vitesse max (unités abstraites, speed 10 ≈ 200 px/sec)
acceleration = 4.0      # Taux d'accélération (unités de vitesse par seconde)
brake_force = 6.0       # Force de freinage
rotation_speed = 5.0    # Vitesse de rotation (radians par seconde)

# Drift
drift_enabled = False   # Activer la mécanique de drift
grip = 0.7              # Adhérence (0.0 = glisse totale, 1.0 = aucun drift)

# Capteurs (raycasts)
ray_angles = -90, -45, 0, 45, 90   # Angles des rayons en degrés (0 = devant)
ray_length = 200                     # Portée max des rayons en pixels

# Timing
max_ticks = 2000        # Durée max d'une génération (en ticks)
stall_timeout = 200     # Mort si aucun checkpoint atteint pendant N ticks
```

Tous les paramètres sont modifiables sans limite depuis l'interface. Les changements s'appliquent en temps réel pendant l'entraînement.

#### Angles des rayons

Les rayons sont les capteurs de la voiture. Chaque rayon mesure la distance jusqu'au bord de la route dans une direction donnée.

- `0` = droit devant
- `-90` = gauche (perpendiculaire)
- `90` = droite (perpendiculaire)
- `-180` / `180` = derrière

L'interface propose des presets (5 wide, 5 narrow, 7 wide, 5 front) et un aperçu visuel des rayons sur la voiture.

> **Attention** : Changer le nombre de rayons modifie la topologie du réseau de neurones. Il est impossible de reprendre un entraînement avec un nombre de rayons différent.

#### Drift

Quand `drift_enabled = True`, la voiture peut déraper. Le paramètre `grip` contrôle l'adhérence :
- `1.0` = la voiture suit parfaitement sa direction
- `0.1` = la voiture glisse beaucoup

Le drift ajoute une entrée supplémentaire au réseau de neurones (angle de drift).

### Configuration NEAT (`config/neat_config.ini`)

Paramètres principaux modifiables depuis l'interface :

| Paramètre | Description |
|---|---|
| `pop_size` | Nombre de génomes par génération |
| `compatibility_threshold` | Seuil de compatibilité pour la spéciation |
| `conn_add_prob` | Probabilité d'ajouter une connexion |
| `conn_delete_prob` | Probabilité de supprimer une connexion |
| `node_add_prob` | Probabilité d'ajouter un noeud |
| `node_delete_prob` | Probabilité de supprimer un noeud |
| `weight_mutate_rate` | Probabilité de mutation des poids |
| `survival_threshold` | Fraction de l'espèce qui survit |
| `max_stagnation` | Générations avant suppression d'une espèce stagnante |
| `elitism` | Nombre de meilleurs génomes préservés tels quels |

Le fichier complet `config/neat_config.ini` contient tous les paramètres NEAT avancés (biais, poids, activation, etc.) modifiables directement dans le fichier.

### Fonction de fitness (`config/fitness.py`)

La fonction de fitness détermine comment les voitures sont évaluées. Elle est définie dans le fichier `config/fitness.py`, modifiable avec votre éditeur de code.

```python
def fitness(car):
    score = 0.0
    score += car.total_checkpoints * 1000
    score += (1.0 - car.distance_to_next_cp) * 500
    score += car.laps * 10000
    return score
```

#### Attributs disponibles

| Attribut | Type | Description |
|---|---|---|
| `car.checkpoints_reached` | int | Checkpoints passés dans le tour actuel |
| `car.total_checkpoints` | int | Total de checkpoints traversés (tous tours) |
| `car.laps` | int | Tours complets |
| `car.time_alive` | int | Ticks survécus |
| `car.total_time` | int | Ticks max autorisés par génération |
| `car.total_distance` | float | Distance totale parcourue |
| `car.average_speed` | float | Vitesse moyenne sur la durée de vie |
| `car.max_speed_reached` | float | Vitesse max atteinte |
| `car.current_speed` | float | Vitesse au moment de la mort/fin |
| `car.distance_to_next_cp` | float | Distance au prochain checkpoint (normalisée 0-1) |
| `car.drift_count` | int | Ticks passés en drift (0 si drift désactivé) |
| `car.is_alive` | bool | Encore en vie à la fin de la génération |
| `car.crashed` | bool | Mort en touchant l'herbe |
| `car.timed_out` | bool | Tué par le stall timeout |
| `car.wall_hits` | int | Ticks passés à frôler le bord |
| `car.min_wall_distance` | float | Distance min au bord (0 = touché) |
| `car.avg_wall_distance` | float | Distance moyenne au bord |

L'aperçu en lecture seule est visible dans l'interface. Cliquez **Reload** après avoir modifié le fichier.

## Réseau de neurones

Chaque voiture possède un réseau de neurones feed-forward :

- **Entrées** : distances des rayons (normalisées 0-1) + vitesse + cap + état d'accélération (+ angle de drift si activé)
- **Sorties** : direction (`-1` = gauche, `+1` = droite) et accélération (`-1` = frein, `+1` = gaz)
- **Activation** : `tanh`

Le nombre d'entrées est calculé automatiquement : `nombre_de_rayons + 3` (ou `+4` avec drift).

## Structure du projet

```
car-racing/
├── main.py                  # Point d'entrée
├── api.py                   # Bridge Python <-> JS (PyWebView)
├── config/
│   ├── car_config.ini       # Configuration physique de la voiture
│   ├── neat_config.ini      # Configuration NEAT
│   └── fitness.py           # Fonction de fitness (modifiable)
├── simulation/
│   ├── car.py               # CarConfig + CarBatch (physique vectorisée)
│   ├── track.py             # Circuit (masque, raycasting, PNG)
│   ├── checkpoint.py        # Portes de checkpoint
│   └── world.py             # Orchestrateur simulation
├── training/
│   ├── trainer.py           # Boucle NEAT en thread
│   ├── fitness_evaluator.py # Charge et exécute fitness.py
│   ├── config_bridge.py     # Traduction INI <-> UI
│   └── exporter.py          # Export génomes en .racer
├── race/
│   └── race_manager.py      # Gestion des courses
└── web/
    ├── index.html
    ├── style.css
    └── js/
        ├── app.js           # Contrôleur principal
        ├── canvas.js        # Rendu canvas
        ├── editor.js        # Éditeur de circuit
        ├── training.js      # Interface entraînement
        ├── race.js          # Interface course
        ├── config_panel.js  # Panneau de configuration
        ├── fitness_editor.js # Aperçu fitness
        └── chart.js         # Graphe de fitness
```

## Technologies

- **Python** — Backend, simulation, NEAT
- **neat-python** — Implémentation de l'algorithme NEAT
- **NumPy** — Physique vectorisée (tous les véhicules simulés en parallèle)
- **PyWebView** — Fenêtre desktop native avec webview
- **PyQt6** — Backend graphique
- **HTML5 Canvas + JS** — Interface utilisateur
