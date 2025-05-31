from dataclasses import dataclass
from typing import Dict, Union, List

# Default visual parameters (can be overridden by scenarios)
DEFAULT_PLANET_VISUAL_RADII = { 
    "Sun": 109.0, "Mercury": 0.383, "Venus": 0.949, "Earth": 1.0, "Mars": 0.532,
    "Jupiter": 11.21, "Saturn": 9.45, "Uranus": 4.01, "Neptune": 3.88,
    "Moon": 0.27, "Star": 200.0, # Generic placeholders
    "MoonA": 0.5, "MoonB": 0.4, "MoonC": 0.6, "MoonD": 0.3, # Example sizes for chaotic system
    "Body": 0.5 # Default for unnamed
}
DEFAULT_PLANET_COLORS = {
    "Sun": '#FFD700', "Mercury": '#B0AFAF', "Venus": '#D4A373', "Earth": '#6B93D6',
    "Mars": '#C1440E', "Jupiter": '#C4A484', "Saturn": '#B8860B', "Uranus": '#A4D8F0',
    "Neptune": '#5B5DDF', "Moon": 'lightgrey', "Star": 'white',
    "MoonA": '#E0E0E0', "MoonB": '#A0A0A0', "MoonC": '#C0C0C0', "MoonD": '#808080',
    "Body": 'white'
}

@dataclass
class BodyConfig:
    name: str
    mass: float
    pos: tuple[float, float]
    vel: Union[tuple[float, float], float]

@dataclass
class SolarSystemConfig:
    name: str
    current_n_bodies: int
    epsilon: float
    animation_plot_duration_years: float
    real_time_animation_seconds: float
    fps: int
    initial_bodies_data: List[BodyConfig]
