from dataclasses import dataclass
from typing import Dict, Union, List

@dataclass
class BodyState:
    name: str = ""
    mass: float = 0
    pos: tuple[float, float] = (0, 0)
    vel: Union[tuple[float, float], float] = 0

@dataclass
class SolarSystemConfig:
    name: str
    current_n_bodies: int
    epsilon: float
    # In every frame, how many years go by
    years_per_frame: float
    fps: int
    # Between frames, how many precision steps to take
    sim_steps_per_frame: int
    initial_bodies_data: List[BodyState]
