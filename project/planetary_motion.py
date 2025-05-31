# planetory_motion.py (Python Host Code with Scenarios)

import matplotlib.pyplot as plt
from matplotlib import animation
import math
import os
import sys
import numpy as np
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import compiler
import ctypes
from config import SolarSystemConfig, BodyState
import utils
from typing import List

# --- Global Constants ---
LOMA_CODE_FILENAME = 'planetary_motion_loma.py' # Loma physics code file (the one above)
LOMA_CODE_SUBDIR = 'loma_code'
COMPILED_CODE_SUBDIR = '_code'
COMPILED_LIB_NAME_PREFIX = 'n_planets_lib_dyn_v2' # Unique name for this library version
MAX_N_BODIES_CONST = 20                    # Max bodies Loma code is compiled for --> static

G_val = (2.0 * math.pi)**2 # Gravitational constant (AU^3 / (SolarMass * Year^2))

def setup_solar_system_scenario() -> SolarSystemConfig:
    """Defines parameters for the standard Solar System simulation."""
    n_bodies = 9
    fps = 60                 # Animation frames per second

    initial_bodies = [
        BodyState(name="Sun", mass=1.0, pos=(0, 0), vel=(0, 0)),
        BodyState(name="Mercury", mass=1.65e-7, pos=(0.39, 0), vel=0.39),
        BodyState(name="Venus", mass=2.45e-6, pos=(0.72, 0), vel=0.72),
        BodyState(name="Earth", mass=3.00e-6, pos=(1.0, 0), vel=1.0),
        BodyState(name="Mars", mass=3.23e-7, pos=(1.52, 0), vel=1.52),
        BodyState(name="Jupiter", mass=9.55e-4, pos=(5.20, 0), vel=5.20),
        BodyState(name="Saturn", mass=2.86e-4, pos=(9.58, 0), vel=9.58),
        BodyState(name="Uranus", mass=4.37e-5, pos=(19.22, 0), vel=19.22),
        BodyState(name="Neptune", mass=5.15e-5, pos=(30.05, 0), vel=30.05),
    ]

    system_config = SolarSystemConfig(
        name="Solar System",
        current_n_bodies=n_bodies,
        epsilon=0.05,
        years_per_frame=0.001,
        fps=fps,
        sim_steps_per_frame=64,
        initial_bodies_data=initial_bodies,
    )

    return system_config

def setup_jupiter_chaotic_scenario():
    """Defines parameters for a Jupiter-centered system with 8 other solar system planets."""
    n_bodies = 9 # Jupiter + the 8 planets
    fps = 60
    
    initial_bodies = [
        BodyState(name="Jupiter", mass=0.000955, pos=(0, 0), vel=(0, 0)),
        BodyState(name="Mercury", mass=1.65e-7, pos=(np.random.uniform(0.015, 0.025), np.random.uniform(-0.01, 0.01)), vel=0.02),
        BodyState(name="Venus", mass=2.45e-6, pos=(np.random.uniform(-0.04, -0.03), np.random.uniform(0.00, 0.015)), vel=0.035),
        BodyState(name="Earth", mass=3.00e-6, pos=(np.random.uniform(-0.055, -0.045), np.random.uniform(-0.015, 0.015)), vel=0.05),
        BodyState(name="Mars", mass=3.23e-7, pos=(np.random.uniform(0.01, 0.02), np.random.uniform(0.06, 0.07)), vel=0.065),
        BodyState(name="Saturn", mass=2.86e-4, pos=(np.random.uniform(0.075, 0.085), np.random.uniform(-0.025, -0.015)), vel=0.08),
        BodyState(name="Uranus", mass=4.37e-5, pos=(np.random.uniform(-0.105, -0.095), np.random.uniform(0, 0.01)), vel=0.1),
        BodyState(name="Neptune", mass=5.15e-5, pos=(np.random.uniform(-0.01, 0.01), np.random.uniform(0.115, 0.125)), vel=0.12),
        BodyState(name="MoonA", mass=5e-8, pos=(0.005, 0.005), vel=math.sqrt(0.005**2 + 0.005**2))
    ]

    system_config = SolarSystemConfig(
        name="Jupiter Chaotic System",
        current_n_bodies=n_bodies,
        epsilon=0.0001,  # Very small epsilon for softening
        years_per_frame=0.001,
        fps=fps,
        sim_steps_per_frame=64,
        initial_bodies_data=initial_bodies,
    )

    return system_config

def compile_loma_code():
    # --- Compile Loma Code ---
    script_dir = os.path.dirname(os.path.realpath(__file__))
    loma_source_full_path = os.path.join(script_dir, LOMA_CODE_SUBDIR, LOMA_CODE_FILENAME)
    compiled_output_dir = os.path.join(script_dir, COMPILED_CODE_SUBDIR)
    if not os.path.exists(compiled_output_dir):
        os.makedirs(compiled_output_dir)
    compiled_lib_path_prefix = os.path.join(compiled_output_dir, COMPILED_LIB_NAME_PREFIX) 

    if not os.path.exists(loma_source_full_path):
        print(f"ERROR: Loma source file not found at {loma_source_full_path}")
        return # Exit this scenario run
    with open(loma_source_full_path) as f:
        loma_code_str = f.read()
    structs, lib = compiler.compile(loma_code_str,
                                    target='c', 
                                    output_filename=compiled_lib_path_prefix)
    print("Compilation successful for Loma code.")
    return structs, lib

def get_simulation_runner(cfg: SolarSystemConfig):    
    structs, lib = compile_loma_code()
    Vec2 = structs['Vec2']
    BodyState = structs['BodyState']
    SimConfig = structs['SimConfig']
    BodyStateArray = BodyState * MAX_N_BODIES_CONST 

    current_body_states = BodyStateArray() # Zero-initialized by ctypes
    next_body_states_buffer = BodyStateArray() # Zero-initialized

    total_momentum_x: float = 0.0
    total_momentum_y: float = 0.0

    for i in range(cfg.current_n_bodies):
        p_data = cfg.initial_bodies_data[i]
        current_body_states[i].mass = p_data.mass
        current_body_states[i].inv_mass = 1.0 / p_data.mass if p_data.mass > 1e-20 else 0.0 # Avoid div by zero for tiny/zero mass
        
        pos_x, pos_y = p_data.pos
        current_body_states[i].pos = Vec2(x=pos_x, y=pos_y)
        
        vx_init, vy_init = 0.0, 0.0
        if isinstance(p_data.vel, tuple):
             vx_init, vy_init = p_data.vel
        elif isinstance(p_data.vel, float): # Only for orbiting bodies
            central_body_mass = cfg.initial_bodies_data[0].mass
            r_orbit = p_data.vel
            # Use mass of the actual central body for this scenario
            v_mag = math.sqrt(G_val * central_body_mass / r_orbit) if r_orbit > 1e-9 else 0.0
            if r_orbit > 1e-9:
                vx_init = -pos_y / r_orbit * v_mag
                vy_init = pos_x / r_orbit * v_mag
            
        current_body_states[i].mom = Vec2(x=p_data.mass * vx_init, y=p_data.mass * vy_init)
        total_momentum_x += current_body_states[i].mom.x
        total_momentum_y += current_body_states[i].mom.y
    
    # if cfg.current_n_bodies > 0 and cfg.initial_bodies_data[0].get('vel', None) is not None : 
    #     if current_body_states[0].mass > 1e-20 :
    #         current_body_states[0].mom.x -= total_momentum_x 
    #         current_body_states[0].mom.y -= total_momentum_y

    def get_get_next_states():
        sim_config_obj = SimConfig(
            G=G_val,
            dt=cfg.years_per_frame / cfg.sim_steps_per_frame,
            epsilon_sq=cfg.epsilon**2,
            num_bodies=cfg.current_n_bodies
        )
        body_states = []
        for _ in range(256):
            body_states.append(utils.convert_ctype_state_to_body_state(current_body_states, cfg))
            for _ in range(cfg.sim_steps_per_frame):
                lib.time_step_system(current_body_states, sim_config_obj, next_body_states_buffer)
                ctypes.memmove(ctypes.addressof(current_body_states),
                                ctypes.addressof(next_body_states_buffer),
                                ctypes.sizeof(BodyStateArray)) 
        return body_states
    return get_get_next_states
