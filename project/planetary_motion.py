# planetory_motion.py (Python Host Code with Scenarios)
import math
import os
import sys
import numpy as np # Make sure numpy is imported
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
import compiler
import ctypes
from config import SolarSystemConfig, BodyState
import utils
from typing import TextIO

# --- Global Constants ---
LOMA_CODE_2D_FILENAME = 'planetary_motion_loma.py' # Loma physics code file
LOMA_CODE_3D_FILENAME = 'planetary_motion_3d_loma.py' # Loma 3d Engine
LOMA_CODE_SUBDIR = 'loma_code'
COMPILED_CODE_SUBDIR = '_code'
COMPILED_LIB_NAME_PREFIX_2D = 'n_planets_lib_2d_v2'
COMPILED_LIB_NAME_PREFIX_3D = 'n_planets_lib_3d_v2'
MAX_N_BODIES_CONST = 20                    # Max bodies Loma code is compiled for --> static

G_val = (2.0 * math.pi)**2 # Gravitational constant (AU^3 / (SolarMass * Year^2))

def setup_solar_system_scenario() -> SolarSystemConfig:
    """Defines parameters for the standard Solar System simulation (2D)."""
    n_bodies = 9
    fps = 120

    initial_bodies = [
        BodyState(name="Sun",     mass=1.0,     pos=(0.0, 0.0, 0.0), vel=(0.0, 0.0, 0.0)), # vel as tuple
        BodyState(name="Mercury", mass=1.65e-7, pos=(0.39, 0.0, 0.0), vel=0.39),
        BodyState(name="Venus",   mass=2.45e-6, pos=(0.72, 0.0, 0.0), vel=0.72),
        BodyState(name="Earth",   mass=3.00e-6, pos=(1.0, 0.0, 0.0), vel=1.0),
        BodyState(name="Mars",    mass=3.23e-7, pos=(1.52, 0.0, 0.0), vel=1.52),
        BodyState(name="Jupiter", mass=9.55e-4, pos=(5.20, 0.0, 0.0), vel=5.20),
        BodyState(name="Saturn",  mass=2.86e-4, pos=(9.58, 0.0, 0.0), vel=9.58),
        BodyState(name="Uranus",  mass=4.37e-5, pos=(19.22, 0.0, 0.0), vel=19.22),
        BodyState(name="Neptune", mass=5.15e-5, pos=(30.05, 0.0, 0.0), vel=30.05),
    ]

    system_config = SolarSystemConfig(
        name="Solar System (2D)",
        current_n_bodies=n_bodies,
        epsilon=0.05,
        years_per_frame=0.01,
        fps=fps,
        sim_steps_per_frame=128,
        initial_bodies_data=initial_bodies,
        dimensions=2, # Explicitly 2D
        loma_code_file=LOMA_CODE_2D_FILENAME,
    )
    return system_config

def setup_jupiter_chaotic_scenario() -> SolarSystemConfig:
    """Defines parameters for a Jupiter-centered system (3D)."""
    n_bodies = 9 # Jupiter + 7 planets + MoonA
    fps = 120
    
    # Ensure positions are 3-tuples (x, y, z)
    # For this scenario, we'll keep initial z positions at 0.0 for simplicity,
    # but the simulation will evolve in 3D.
    initial_bodies = [
        BodyState(name="Jupiter", mass=0.000955, pos=(0.0, 0.0, 0.0), vel=(0.0, 0.0, 0.0)), # vel as tuple
        BodyState(name="Mercury", mass=1.65e-7, pos=(np.random.uniform(0.015, 0.025), np.random.uniform(-0.01, 0.01), 0.0), vel=0.02),
        BodyState(name="Venus",   mass=2.45e-6, pos=(np.random.uniform(-0.04, -0.03), np.random.uniform(0.00, 0.015), 0.0), vel=0.035),
        BodyState(name="Earth",   mass=3.00e-6, pos=(np.random.uniform(-0.055, -0.045), np.random.uniform(-0.015, 0.015), 0.0), vel=0.05),
        BodyState(name="Mars",    mass=3.23e-7, pos=(np.random.uniform(0.01, 0.02), np.random.uniform(0.06, 0.07), 0.0), vel=0.065),
        BodyState(name="Saturn",  mass=2.86e-4, pos=(np.random.uniform(0.075, 0.085), np.random.uniform(-0.025, -0.015), 0.0), vel=0.08),
        BodyState(name="Uranus",  mass=4.37e-5, pos=(np.random.uniform(-0.105, -0.095), np.random.uniform(0, 0.01), 0.0), vel=0.1),
        BodyState(name="Neptune", mass=5.15e-5, pos=(np.random.uniform(-0.01, 0.01), np.random.uniform(0.115, 0.125), 0.0), vel=0.12),
        BodyState(name="MoonA",   mass=5e-8,    pos=(0.005, 0.005, 0.0), vel=math.sqrt(0.005**2 + 0.005**2)) # vel is r_orbit
    ]

    system_config = SolarSystemConfig(
        name="Jupiter Chaotic System (3D)",
        current_n_bodies=n_bodies,
        epsilon=0.0001,
        years_per_frame=0.001,
        fps=fps,
        sim_steps_per_frame=64, # Reduced for potentially more complex 3D
        initial_bodies_data=initial_bodies,
        dimensions=3, # Explicitly 3D
        loma_code_file=LOMA_CODE_3D_FILENAME,
    )
    return system_config

def compile_loma_code(loma_fp: str, output_lib_prefix: str):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    loma_source_full_path = os.path.join(script_dir, LOMA_CODE_SUBDIR, loma_fp)
    compiled_output_dir = os.path.join(script_dir, COMPILED_CODE_SUBDIR)
    if not os.path.exists(compiled_output_dir):
        os.makedirs(compiled_output_dir)
    compiled_lib_path_prefix = os.path.join(compiled_output_dir, output_lib_prefix) 

    if not os.path.exists(loma_source_full_path):
        print(f"ERROR: Loma source file not found at {loma_source_full_path}")
        return None, None 
    with open(loma_source_full_path) as f:
        loma_code_str = f.read()
    try:
        structs, lib = compiler.compile(loma_code_str,
                                        target='c', 
                                        output_filename=compiled_lib_path_prefix)
        print(f"Compilation successful for Loma code: {loma_fp}")
        return structs, lib
    except Exception as e:
        print(f"ERROR compiling Loma code {loma_fp}: {e}")
        return None, None

def get_simulation_runner(cfg: SolarSystemConfig):    
    lib_prefix = COMPILED_LIB_NAME_PREFIX_2D if cfg.dimensions == 2 else COMPILED_LIB_NAME_PREFIX_3D
    structs, lib = compile_loma_code(cfg.loma_code_file, lib_prefix)

    if not structs or not lib:
        print("Failed to compile or load simulation library. Exiting runner setup.")
        return lambda _: [] # Return a dummy runner

    VecND = structs['Vec2'] if cfg.dimensions == 2 else structs['Vec3']
    BodyStateLoma = structs['BodyState'] # Renamed to avoid conflict with config.BodyState
    SimConfigLoma = structs['SimConfig']
    BodyStateArray = BodyStateLoma * MAX_N_BODIES_CONST 

    current_body_states = BodyStateArray() 
    next_body_states_buffer = BodyStateArray()

    # For potential momentum conservation (currently commented out in original)
    # total_momentum_x: float = 0.0
    # total_momentum_y: float = 0.0
    # total_momentum_z: float = 0.0 # Added for 3D

    for i in range(cfg.current_n_bodies):
        p_data = cfg.initial_bodies_data[i] # This is config.BodyState instance
        
        current_body_states[i].mass = p_data.mass
        current_body_states[i].inv_mass = 1.0 / p_data.mass if p_data.mass > 1e-20 else 0.0
        
        # p_data.pos is now always a 3-tuple (x,y,z)
        if cfg.dimensions == 2:
            current_body_states[i].pos = VecND(x=p_data.pos[0], y=p_data.pos[1])
        else: # dimensions == 3
            current_body_states[i].pos = VecND(x=p_data.pos[0], y=p_data.pos[1], z=p_data.pos[2])
        
        # Initialize velocities
        vx_init, vy_init, vz_init = 0.0, 0.0, 0.0
        
        # Extract position components for clarity in velocity calculations
        # p_data.pos is guaranteed to be a 3-tuple
        pos_x, pos_y, pos_z = p_data.pos[0], p_data.pos[1], p_data.pos[2]

        if isinstance(p_data.vel, tuple):
            vx_init = p_data.vel[0]
            vy_init = p_data.vel[1]
            if len(p_data.vel) == 3: # If (vx, vy, vz) is provided
                vz_init = p_data.vel[2]
            # If only (vx, vy) provided for a 3D sim, vz_init remains 0.0
            # For a 2D sim, vz_init also remains 0.0 (and is effectively ignored)
        elif isinstance(p_data.vel, float): # p_data.vel is interpreted as orbital radius parameter
            if i == 0: # Central body, typically has explicit velocity or is static
                pass # vx, vy, vz remain 0 unless set by tuple above
            else:
                central_body_mass = cfg.initial_bodies_data[0].mass
                r_orbit_param = p_data.vel # This is the parameter defining orbital distance
                
                v_mag = 0.0
                if r_orbit_param > 1e-9: # Avoid division by zero
                    v_mag = math.sqrt(G_val * central_body_mass / r_orbit_param)
                
                # Calculate velocity direction for circular orbit in xy-plane based on current position
                # Assumes central body is at origin for this simplified calculation
                current_r_xy = math.sqrt(pos_x**2 + pos_y**2)
                if current_r_xy > 1e-9:
                    vx_init = -pos_y / current_r_xy * v_mag
                    vy_init =  pos_x / current_r_xy * v_mag
                # vz_init remains 0.0 (orbit in xy-plane for this simplified setup)
        
        # Set momentum in the CTYPES structure (Loma's BodyState uses momentum)
        body_mass = p_data.mass
        if cfg.dimensions == 2:
            current_body_states[i].mom = VecND(x=vx_init * body_mass, y=vy_init * body_mass)
        else: # dimensions == 3
            current_body_states[i].mom = VecND(x=vx_init * body_mass, y=vy_init * body_mass, z=vz_init * body_mass)

        # Accumulate momentum (if conservation logic is to be used)
        # total_momentum_x += current_body_states[i].mom.x
        # total_momentum_y += current_body_states[i].mom.y
        # if cfg.dimensions == 3:
        #     total_momentum_z += current_body_states[i].mom.z


    # --- Center of Mass Momentum Adjustment (optional, currently commented out in original) ---
    # if cfg.current_n_bodies > 0 and cfg.initial_bodies_data[0].vel is None : # Example condition
    #     # This part would also need to be dimension-aware for total_momentum_z
    #     # if current_body_states[0].mass > 1e-20 :
    #     #     current_body_states[0].mom.x -= total_momentum_x 
    #     #     current_body_states[0].mom.y -= total_momentum_y
    #     #     if cfg.dimensions == 3:
    #     #          current_body_states[0].mom.z -= total_momentum_z

    def get_next_states_closure(simulation_steps_per_call):
        sim_config_loma_obj = SimConfigLoma(
            G=G_val,
            dt=cfg.years_per_frame / cfg.sim_steps_per_frame,
            epsilon_sq=cfg.epsilon**2,
            num_bodies=cfg.current_n_bodies
        )
        
        # Buffer for states to be returned for one call to the closure
        returned_body_states_list = [] 

        for _ in range(simulation_steps_per_call): # e.g., 256 steps per API call
            # Convert current CTYPES state to Python list[BodyState] for this frame/step
            # utils.convert_ctype_state_to_body_state expects cfg (SolarSystemConfig)
            returned_body_states_list.append(utils.convert_ctype_state_to_body_state(current_body_states, cfg))
            
            # Advance simulation by one frame (which includes multiple sim_steps_per_frame)
            for _ in range(cfg.sim_steps_per_frame):
                lib.time_step_system(current_body_states, sim_config_loma_obj, next_body_states_buffer)
                # Copy data from next_states_buffer back to current_states for the next step
                ctypes.memmove(ctypes.addressof(current_body_states),
                                ctypes.addressof(next_body_states_buffer),
                                ctypes.sizeof(BodyStateArray)) 
        return returned_body_states_list
        
    return get_next_states_closure