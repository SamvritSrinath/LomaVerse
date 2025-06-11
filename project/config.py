# config.py
from dataclasses import dataclass
from typing import Dict, Union, List, Optional, Literal

@dataclass
class BodyState:
    name: str = ""
    mass: float = 0  # Mass in Solar Masses (M☉)
    pos: tuple[float, float, float] = (0, 0, 0)  # Position in Astronomical Units (AU)
    vel: Union[tuple[float, float, float], float] = (0.0, 0.0, 0.0) # Velocity in AU/year
    color: Optional[str] = None # Visual color
    radius: Optional[float] = None # Visual radius, not used in physics

@dataclass
class SolarSystemConfig:
    name: str
    current_n_bodies: int
    epsilon: float # Softening factor
    years_per_frame: float # Simulation time (years) per display frame
    fps: int # Target FPS for visualization
    sim_steps_per_frame: int # Simulation steps per display frame (dt_loma = years_per_frame / sim_steps_per_frame)
    initial_bodies_data: List[BodyState]
    loma_code_file: str = "planetary_motion_3d_loma.py" 
    dimensions: int = 3
    integrator: Literal['symplectic_euler', 'rk4'] = 'symplectic_euler'