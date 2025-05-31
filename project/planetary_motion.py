# planetory_motion.py (Python Host Code with Scenarios)

import matplotlib.pyplot as plt
from matplotlib import animation
import math
import os
import sys
import numpy as np
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(os.path.dirname(current))
sys.path.append(parent)
import compiler
import ctypes
from config import SolarSystemConfig, BodyConfig, DEFAULT_PLANET_VISUAL_RADII, DEFAULT_PLANET_COLORS

# --- Global Constants ---
LOMA_CODE_FILENAME = 'planetary_motion_loma.py' # Loma physics code file (the one above)
LOMA_CODE_SUBDIR = 'loma_code'
COMPILED_CODE_SUBDIR = '_code'
COMPILED_LIB_NAME_PREFIX = 'n_planets_lib_dyn_v2' # Unique name for this library version
MAX_N_BODIES_CONST = 20                    # Max bodies Loma code is compiled for --> static

G_val = (2.0 * math.pi)**2 # Gravitational constant (AU^3 / (SolarMass * Year^2))

# --- Scenario Definition Functions ---
# def setup_solar_system_scenario() -> SolarSystemConfig:
#     """Defines parameters for the standard Solar System simulation."""
#     n_bodies = 9
#     real_time_seconds = 25.0 # Animation video length
#     fps = 60                 # Animation frames per second
#     animation_plot_duration_years = 75.0 # Simulated years to show
    
#     num_frames = int(real_time_seconds * fps)
    
#     initial_bodies = [ 
#         {'name': "Sun", 'mass': 1.0, 'pos': (0,0), 'vel': (0,0)}, # vel can be non-zero if CoM is adjusted
#         {'name': "Mercury", 'mass': 1.65e-7, 'pos': (0.39, 0), 'vel_r_parent': 0.39},
#         {'name': "Venus", 'mass': 2.45e-6, 'pos': (0.72, 0), 'vel_r_parent': 0.72},
#         {'name': "Earth", 'mass': 3.00e-6, 'pos': (1.0, 0), 'vel_r_parent': 1.0},
#         {'name': "Mars", 'mass': 3.23e-7, 'pos': (1.52, 0), 'vel_r_parent': 1.52},
#         {'name': "Jupiter", 'mass': 9.55e-4, 'pos': (5.20, 0), 'vel_r_parent': 5.20},
#         {'name': "Saturn", 'mass': 2.86e-4, 'pos': (9.58, 0), 'vel_r_parent': 9.58},
#         {'name': "Uranus", 'mass': 4.37e-5, 'pos': (19.22, 0), 'vel_r_parent': 19.22},
#         {'name': "Neptune", 'mass': 5.15e-5, 'pos': (30.05, 0), 'vel_r_parent': 30.05},
#     ]

#     return {
#         "name": "Solar System",
#         "output_filename": "planetary_SS.mp4",
#         "current_n_bodies": n_bodies,
#         "time_step_years": 1e-3, # Physics time step
#         "epsilon": 0.05,         # Gravitational softening
#         "animation_plot_duration_years": animation_plot_duration_years,
#         "real_time_animation_seconds": real_time_seconds,
#         "fps": fps,
#         "num_frames": num_frames,
#         # show only trail long enough that it's visible
#         "trail_length_frames": 400,
#         "initial_bodies_data": initial_bodies,
#         "plot_config": {
#             "title_suffix": "Solar System (N-Body)",
#             "limit_auto_scale": 1.2, 
#             "limit_min_padding": 2.0,
#             "marker_config": { # "sun_size" refers to the central/largest body visually
#                 "primary_body_size": 20.0, "base_size": 3.0, "min_size": 2.0, 
#                 "max_size": 11.0, "power_scale": 0.50 # Adjusted for less aggressive scaling
#             },
#             "trail_config": {
#                 "base_lw": 0.4, "max_lw": 1.8, "power_scale": 0.4, "primary_body_lw": 1.5
#             },
#             "label_font_size": 7,
#             "label_offset_factor": 0.025 
#         }
#     }

def setup_jupiter_chaotic_scenario():
    """Defines parameters for a Jupiter-centered system with 8 other solar system planets."""
    n_bodies = 9 # Jupiter + the 8 planets
    real_time_seconds = 30.0
    fps = 60
    animation_plot_duration_years = 3.0 # Chaotic systems evolve or disperse quickly
    
    initial_bodies = [
        BodyConfig(name="Jupiter", mass=0.000955, pos=(0, 0), vel=(0, 0)),
        BodyConfig(name="Mercury", mass=1.65e-7, pos=(np.random.uniform(0.015, 0.025), np.random.uniform(-0.01, 0.01)), vel=0.02),
        BodyConfig(name="Venus", mass=2.45e-6, pos=(np.random.uniform(-0.04, -0.03), np.random.uniform(0.00, 0.015)), vel=0.035),
        BodyConfig(name="Earth", mass=3.00e-6, pos=(np.random.uniform(-0.055, -0.045), np.random.uniform(-0.015, 0.015)), vel=0.05),
        BodyConfig(name="Mars", mass=3.23e-7, pos=(np.random.uniform(0.01, 0.02), np.random.uniform(0.06, 0.07)), vel=0.065),
        BodyConfig(name="Saturn", mass=2.86e-4, pos=(np.random.uniform(0.075, 0.085), np.random.uniform(-0.025, -0.015)), vel=0.08),
        BodyConfig(name="Uranus", mass=4.37e-5, pos=(np.random.uniform(-0.105, -0.095), np.random.uniform(0, 0.01)), vel=0.1),
        BodyConfig(name="Neptune", mass=5.15e-5, pos=(np.random.uniform(-0.01, 0.01), np.random.uniform(0.115, 0.125)), vel=0.12),
        BodyConfig(name="MoonA", mass=5e-8, pos=(0.005, 0.005), vel=math.sqrt(0.005**2 + 0.005**2))
    ]

    system_config = SolarSystemConfig(
        name="Jupiter Chaotic System",
        current_n_bodies=n_bodies,
        epsilon=0.0001,  # Very small epsilon for softening
        animation_plot_duration_years=animation_plot_duration_years,
        real_time_animation_seconds=real_time_seconds,
        fps=fps,
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

# --- Main Simulation Runner ---
def run_simulation_scenario(cfg: SolarSystemConfig):
    """Runs a complete simulation and animation for a given scenario."""
    
    NUM_FRAMES = int(cfg.real_time_animation_seconds * cfg.fps)
    TIME_PER_FRAME_FOR_ANIM = cfg.animation_plot_duration_years / NUM_FRAMES

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

    sim_config_obj = SimConfig(
        G=G_val, 
        dt=TIME_PER_FRAME_FOR_ANIM,
        epsilon_sq=cfg.epsilon**2,
        num_bodies=cfg.current_n_bodies
    )
    for i in range(1000):
        lib.time_step_system(current_body_states, sim_config_obj, next_body_states_buffer)
        ctypes.memmove(ctypes.addressof(current_body_states),
                        ctypes.addressof(next_body_states_buffer),
                        ctypes.sizeof(BodyStateArray)) 
        print(current_body_states[0].pos.x, current_body_states[0].pos.y)

if __name__ == '__main__':
    # Run Solar System Scenario
    # ss_params = setup_solar_system_scenario()
    # run_simulation_scenario(ss_params)

    # Run Jupiter Chaotic Scenario
    jc_params = setup_jupiter_chaotic_scenario()
    run_simulation_scenario(jc_params)