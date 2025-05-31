from dataclasses import dataclass
from typing import Dict, Union, List

@dataclass
class PlotConfig:
    title_suffix: str
    limit_auto_scale: float
    limit_min_padding: float
    marker_config: Dict[str, float]
    trail_config: Dict[str, float]
    label_font_size: int
    label_offset_factor: float

@dataclass
class BodyConfig:
    name: str
    mass: float
    pos: tuple[float, float]
    vel: Union[tuple[float, float], float]

@dataclass
class SolarSystemConfig:
    name: str
    output_filename: str
    current_n_bodies: int
    time_step_years: float
    epsilon: float
    animation_plot_duration_years: float
    real_time_animation_seconds: float
    fps: int
    num_frames: int
    trail_length_frames: int
    initial_bodies_data: List[BodyConfig]
    plot_config: PlotConfig
