# planetory_motion.py (Python Host Code with Scenarios)
import math
import os
import sys
import numpy as np
import logging 

# Ensure 'compiler' can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 
import compiler 
import ctypes
from config import SolarSystemConfig, BodyState 
import utils 
from typing import TextIO

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

LOMA_CODE_SUBDIR = 'loma_code'
COMPILED_CODE_SUBDIR = '_code' 
LOMA_CODE_3D_FILENAME = 'planetary_motion_3d_loma.py'
COMPILED_LIB_NAME_PREFIX_3D = 'n_planets_lib_3d_v2' 
MAX_N_BODIES_CONST = 20                    

G_val = (2.0 * math.pi)**2 
logging.info(f"Using G_val: {G_val:.4f} AU^3 M☉^-1 year^-2 (for Solar Masses, AU, Years)")

MASS_SUN_SOLAR = 1.0
MASS_MERCURY_SOLAR = 1.65e-7
MASS_VENUS_SOLAR = 2.45e-6
MASS_EARTH_SOLAR = 3.00e-6
MASS_MARS_SOLAR = 3.23e-7
MASS_JUPITER_SOLAR = 9.546e-4 
MASS_SATURN_SOLAR = 2.86e-4
MASS_URANUS_SOLAR = 4.37e-5
MASS_NEPTUNE_SOLAR = 5.15e-5
MASS_MOON_A_SOLAR = 5e-8 

def setup_solar_system_scenario() -> SolarSystemConfig:
    fps = 120 
    # Velocities are in AU/year
    planets = [ 
        BodyState(name="Mercury", mass=MASS_MERCURY_SOLAR,  pos=(-0.30078, 0.27911, -0.03169), vel=(-0.01756*365.25, -0.02108*365.25, 0.00089*365.25)),
        BodyState(name="Venus",   mass=MASS_VENUS_SOLAR,     pos=(-0.17612, -0.70403, 0.03379), vel=(0.01994*365.25, -0.00512*365.25, -0.00112*365.25)),
        BodyState(name="Earth",   mass=MASS_EARTH_SOLAR,     pos=(-0.15643, -0.99205, 0.00004), vel=(0.01705*365.25, -0.00285*365.25, -0.0000007*365.25)), 
        BodyState(name="Mars",    mass=MASS_MARS_SOLAR,      pos=(-1.30792, -0.83020, 0.03337), vel=(0.00919*365.25, -0.01177*365.25, -0.00048*365.25)),
        BodyState(name="Jupiter", mass=MASS_JUPITER_SOLAR,  pos=(4.56986, 2.33903, -0.10340), vel=(-0.00280*365.25, 0.00562*365.25, 0.00007*365.25)),
        BodyState(name="Saturn",  mass=MASS_SATURN_SOLAR,   pos=(8.62944, -4.61264, -0.28296), vel=(0.00243*365.25, 0.00447*365.25, -0.00009*365.25)),
        BodyState(name="Uranus",  mass=MASS_URANUS_SOLAR,   pos=(19.7987, 2.51304, -0.23738), vel=(-0.00052*365.25, 0.00367*365.25, 0.00003*365.25)),
        BodyState(name="Neptune", mass=MASS_NEPTUNE_SOLAR, pos=(29.6178, -5.11366, -0.68800), vel=(0.00053*365.25, 0.00303*365.25, -0.00008*365.25)),
    ]
    
    # Center-of-mass correction for stability
    total_momentum = np.array([0.0, 0.0, 0.0])
    for p in planets:
        total_momentum += p.mass * np.array(p.vel)
    
    sun_velocity = (-total_momentum / MASS_SUN_SOLAR).tolist()
    sun = BodyState(name="Sun", mass=MASS_SUN_SOLAR, pos=(0.0, 0.0, 0.0), vel=tuple(sun_velocity))
    
    initial_bodies = [sun] + planets
    logging.info(f"Setting up Solar System. Corrected Sun velocity to {sun_velocity} AU/year for stability.")

    system_config = SolarSystemConfig(
        name="Solar System (3D, Solar Masses)",
        current_n_bodies=len(initial_bodies),
        epsilon=0.005, 
        years_per_frame=0.01, 
        fps=fps,
        sim_steps_per_frame=1024, # Reduced for performance
        initial_bodies_data=initial_bodies,
        dimensions=3, 
        loma_code_file=LOMA_CODE_3D_FILENAME,
    )
    return system_config

def setup_jupiter_system_scenario() -> SolarSystemConfig:
    fps = 120
    jupiter_mass_solar = MASS_JUPITER_SOLAR 
    moon_definitions = [ 
        {'name': "Io", 'mass_solar': 4.7e-5, 'pos_au': (0.0028, 0.0001, np.random.uniform(-0.0001,0.0001))},
        {'name': "Europa", 'mass_solar': 2.5e-5, 'pos_au': (-0.0045, 0.0001, np.random.uniform(-0.0001,0.0001))},
        {'name': "Ganymede", 'mass_solar': 7.8e-5, 'pos_au': (0.0001, 0.0071, np.random.uniform(-0.0001,0.0001))},
        {'name': "Callisto", 'mass_solar': 5.7e-5, 'pos_au': (0.0001, -0.0126, np.random.uniform(-0.0001,0.0001))},
        {'name': "MoonX1", 'mass_solar': 1e-10, 'pos_au': (np.random.uniform(0.015, 0.025), np.random.uniform(-0.01, 0.01), np.random.uniform(-0.002,0.002))},
        {'name': "MoonX2", 'mass_solar': 1e-10, 'pos_au': (np.random.uniform(-0.03, -0.02), np.random.uniform(0.005, 0.015), np.random.uniform(-0.002,0.002))},
    ]
    initial_bodies = [BodyState(name="Jupiter", mass=jupiter_mass_solar, pos=(0.0,0.0,0.0), vel=(0.0,0.0,0.0))]
    for moon_def in moon_definitions:
        pos_x, pos_y, pos_z = moon_def['pos_au']
        current_r_xy = math.sqrt(pos_x**2 + pos_y**2) 
        vx_init, vy_init, vz_init = 0.0, 0.0, 0.0 
        if current_r_xy > 1e-9: 
            v_mag_desired = math.sqrt(G_val * jupiter_mass_solar / current_r_xy) 
            vx_init = -pos_y / current_r_xy * v_mag_desired
            vy_init =  pos_x / current_r_xy * v_mag_desired
            vz_init = (np.random.rand() - 0.5) * 0.05 * v_mag_desired
        initial_bodies.append(BodyState(name=moon_def['name'], mass=moon_def['mass_solar'], pos=moon_def['pos_au'], vel=(vx_init, vy_init, vz_init)))
    logging.info(f"Setting up Jupiter System. Jupiter mass: {initial_bodies[0].mass:.2e} M☉. Bodies: {len(initial_bodies)}")
    system_config = SolarSystemConfig(
        name="Jupiter System (Solar Masses)", current_n_bodies=len(initial_bodies),
        epsilon=0.00005, years_per_frame=0.0005, fps=fps, sim_steps_per_frame=256,
        initial_bodies_data=initial_bodies, dimensions=3, loma_code_file=LOMA_CODE_3D_FILENAME,
    )
    return system_config

def setup_true_chaotic_scenario() -> SolarSystemConfig:
    n_bodies = 3 
    fps = 120
    initial_bodies = [
        BodyState(name="StarA", mass=1.1, pos=(0.9, 0.5, 0.05), vel=(0.12, 0.22, -0.03)),
        BodyState(name="StarB", mass=1.0, pos=(-0.7, -0.4, -0.02), vel=(-0.08, -0.15, 0.04)),
        BodyState(name="StarC", mass=0.9, pos=(0.2, -0.8, 0.1), vel=(0.18, 0.05, 0.08))
    ]
    n_bodies = len(initial_bodies)
    logging.info(f"Setting up True Chaotic Scenario with {n_bodies} bodies.")
    system_config = SolarSystemConfig(
        name=f"True Chaotic System ({n_bodies}-Body)", current_n_bodies=n_bodies,
        epsilon=0.02, years_per_frame=0.0015, fps=fps, sim_steps_per_frame=768,
        initial_bodies_data=initial_bodies, dimensions=3, loma_code_file=LOMA_CODE_3D_FILENAME,
    )
    return system_config

def compile_loma_code(loma_fp: str, output_lib_prefix: str):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    loma_source_full_path = os.path.join(script_dir, LOMA_CODE_SUBDIR, loma_fp)
    compiled_output_dir = os.path.join(script_dir, COMPILED_CODE_SUBDIR)
    if not os.path.exists(compiled_output_dir): os.makedirs(compiled_output_dir); logging.info(f"Created dir: {compiled_output_dir}")
    compiled_lib_path_prefix = os.path.join(compiled_output_dir, output_lib_prefix) 
    if not os.path.exists(loma_source_full_path): logging.error(f"Loma src not found: {loma_source_full_path}"); return None,None
    with open(loma_source_full_path, 'r') as f: loma_code_str = f.read()
    try:
        structs, lib = compiler.compile(loma_code_str,target='c',output_filename=compiled_lib_path_prefix)
        logging.info(f"Compiled: {loma_fp} to {compiled_lib_path_prefix}"); return structs,lib
    except Exception as e: logging.error(f"Compile error {loma_fp}: {e}",exc_info=True); return None,None

def get_simulation_runner(cfg: SolarSystemConfig):    
    structs, lib = compile_loma_code(cfg.loma_code_file, COMPILED_LIB_NAME_PREFIX_3D)
    if not structs or not lib: logging.error("Sim runner setup failed: no structs/lib."); return lambda _: [] 

    VecND = structs['Vec3']
    BodyStateLoma, SimConfigLoma = structs['BodyState'], structs['SimConfig']
    BodyStateArray = BodyStateLoma * MAX_N_BODIES_CONST 
    current_body_states, next_body_states_buffer = BodyStateArray(), BodyStateArray()

    for i in range(cfg.current_n_bodies):
        p_data = cfg.initial_bodies_data[i] 
        current_body_states[i].mass = p_data.mass 
        current_body_states[i].inv_mass = 1.0 / p_data.mass if p_data.mass > 1e-20 else 0.0
        pos_tuple, vel_tuple = p_data.pos, p_data.vel 
        if len(pos_tuple)<3 or len(vel_tuple)<3: logging.error(f"Body {p_data.name} bad pos/vel for 3D."); continue
        current_body_states[i].pos = VecND(x=pos_tuple[0], y=pos_tuple[1], z=pos_tuple[2])
        current_body_states[i].mom = VecND(x=vel_tuple[0]*p_data.mass, y=vel_tuple[1]*p_data.mass, z=vel_tuple[2]*p_data.mass)

    def get_next_states_closure(frames_to_generate_per_call):
        sim_conf_loma = SimConfigLoma(G=G_val, dt=(cfg.years_per_frame/cfg.sim_steps_per_frame), 
                                        epsilon_sq=cfg.epsilon**2, num_bodies=cfg.current_n_bodies)
        res_list = []
        for _ in range(frames_to_generate_per_call):
            for k_idx in range(cfg.current_n_bodies):
                cb_s=current_body_states[k_idx]; n="Unk"; hz_p=hasattr(cb_s.pos,'z'); hz_m=hasattr(cb_s.mom,'z')
                if k_idx < len(cfg.initial_bodies_data): n=cfg.initial_bodies_data[k_idx].name
                nan_p = math.isnan(cb_s.pos.x) or math.isnan(cb_s.pos.y) or (cfg.dimensions==3 and hz_p and math.isnan(cb_s.pos.z))
                nan_m = math.isnan(cb_s.mom.x) or math.isnan(cb_s.mom.y) or (cfg.dimensions==3 and hz_m and math.isnan(cb_s.mom.z))
                if nan_p or nan_m: logging.error(f"NaN in CTYPES {k_idx}({n}) P:({cb_s.pos.x:.2e},{cb_s.pos.y:.2e},{getattr(cb_s.pos,'z','N/A'):.2e}) M:({cb_s.mom.x:.2e},{cb_s.mom.y:.2e},{getattr(cb_s.mom,'z','N/A'):.2e})")
            
            res_list.append(utils.convert_ctype_state_to_body_state(current_body_states, cfg))
            for _s in range(cfg.sim_steps_per_frame):
                lib.time_step_system(current_body_states,sim_conf_loma,next_body_states_buffer)
                ctypes.memmove(ctypes.addressof(current_body_states),ctypes.addressof(next_body_states_buffer),ctypes.sizeof(BodyStateArray))
        return res_list
    return get_next_states_closure