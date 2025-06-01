# config.py
from dataclasses import dataclass
from typing import Dict, Union, List

@dataclass
class BodyState:
    name: str = ""
    mass: float = 0
    pos: tuple[float, float, float] = (0, 0, 0)
    vel: Union[tuple[float, float, float], float] = 0.0 

@dataclass
class SolarSystemConfig:
    name: str
    current_n_bodies: int
    epsilon: float
    # How many years go by in each frame
    years_per_frame: float
    fps: int
    sim_steps_per_frame: int
    initial_bodies_data: List[BodyState]
    loma_code_file: str = "planetary_motion_3d_loma.py"
    dimensions: int = 3 # 2 for 2D, 3 for 3D