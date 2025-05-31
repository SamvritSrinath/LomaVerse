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
from config import SolarSystemConfig, PlotConfig, BodyConfig

# --- Global Constants ---
LOMA_CODE_FILENAME = 'planetary_motion_loma.py' # Loma physics code file (the one above)
LOMA_CODE_SUBDIR = 'loma_code'
COMPILED_CODE_SUBDIR = '_code'
COMPILED_LIB_NAME_PREFIX = 'n_planets_lib_dyn_v2' # Unique name for this library version
MAX_N_BODIES_CONST = 20                    # Max bodies Loma code is compiled for --> static

G_val = (2.0 * math.pi)**2 # Gravitational constant (AU^3 / (SolarMass * Year^2))

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

# --- Scenario Definition Functions ---
def setup_solar_system_scenario() -> SolarSystemConfig:
    """Defines parameters for the standard Solar System simulation."""
    n_bodies = 9
    real_time_seconds = 25.0 # Animation video length
    fps = 60                 # Animation frames per second
    animation_plot_duration_years = 75.0 # Simulated years to show
    
    num_frames = int(real_time_seconds * fps)
    
    initial_bodies = [ 
        {'name': "Sun", 'mass': 1.0, 'pos': (0,0), 'vel': (0,0)}, # vel can be non-zero if CoM is adjusted
        {'name': "Mercury", 'mass': 1.65e-7, 'pos': (0.39, 0), 'vel_r_parent': 0.39},
        {'name': "Venus", 'mass': 2.45e-6, 'pos': (0.72, 0), 'vel_r_parent': 0.72},
        {'name': "Earth", 'mass': 3.00e-6, 'pos': (1.0, 0), 'vel_r_parent': 1.0},
        {'name': "Mars", 'mass': 3.23e-7, 'pos': (1.52, 0), 'vel_r_parent': 1.52},
        {'name': "Jupiter", 'mass': 9.55e-4, 'pos': (5.20, 0), 'vel_r_parent': 5.20},
        {'name': "Saturn", 'mass': 2.86e-4, 'pos': (9.58, 0), 'vel_r_parent': 9.58},
        {'name': "Uranus", 'mass': 4.37e-5, 'pos': (19.22, 0), 'vel_r_parent': 19.22},
        {'name': "Neptune", 'mass': 5.15e-5, 'pos': (30.05, 0), 'vel_r_parent': 30.05},
    ]

    return {
        "name": "Solar System",
        "output_filename": "planetary_SS.mp4",
        "current_n_bodies": n_bodies,
        "time_step_years": 1e-3, # Physics time step
        "epsilon": 0.05,         # Gravitational softening
        "animation_plot_duration_years": animation_plot_duration_years,
        "real_time_animation_seconds": real_time_seconds,
        "fps": fps,
        "num_frames": num_frames,
        # show only trail long enough that it's visible
        "trail_length_frames": 400,
        "initial_bodies_data": initial_bodies,
        "plot_config": {
            "title_suffix": "Solar System (N-Body)",
            "limit_auto_scale": 1.2, 
            "limit_min_padding": 2.0,
            "marker_config": { # "sun_size" refers to the central/largest body visually
                "primary_body_size": 20.0, "base_size": 3.0, "min_size": 2.0, 
                "max_size": 11.0, "power_scale": 0.50 # Adjusted for less aggressive scaling
            },
            "trail_config": {
                "base_lw": 0.4, "max_lw": 1.8, "power_scale": 0.4, "primary_body_lw": 1.5
            },
            "label_font_size": 7,
            "label_offset_factor": 0.025 
        }
    }

def setup_jupiter_chaotic_scenario():
    """Defines parameters for a Jupiter-centered system with 8 other solar system planets."""
    n_bodies = 9 # Jupiter + the 8 planets
    real_time_seconds = 30.0
    fps = 60
    animation_plot_duration_years = 3.0 # Chaotic systems evolve or disperse quickly
    
    num_frames = int(real_time_seconds * fps)
    jupiter_mass = 0.000955 # Solar masses
    
    initial_bodies = [
        {'name': "Jupiter", 'mass': jupiter_mass, 'pos': (0,0), 'vel': (0,0)},
        {'name': "Mercury", 'mass': 1.65e-7, 'pos': (np.random.uniform(0.015, 0.025), np.random.uniform(-0.01, 0.01)), 'vel_r_parent': 0.02},
        {'name': "Venus",   'mass': 2.45e-6, 'pos': (np.random.uniform(-0.04, -0.03), np.random.uniform(0.00, 0.015)),  'vel_r_parent': 0.035},
        {'name': "Earth",   'mass': 3.00e-6, 'pos': (np.random.uniform(-0.055, -0.045), np.random.uniform(-0.015, 0.015)), 'vel_r_parent': 0.05},
        {'name': "Mars",    'mass': 3.23e-7, 'pos': (np.random.uniform(0.01, 0.02), np.random.uniform(0.06, 0.07)),'vel_r_parent': 0.065},
        {'name': "Saturn",  'mass': 2.86e-4, 'pos': (np.random.uniform(0.075, 0.085), np.random.uniform(-0.025, -0.015)), 'vel_r_parent': 0.08},
        {'name': "Uranus",  'mass': 4.37e-5, 'pos': (np.random.uniform(-0.105, -0.095), np.random.uniform(0, 0.01)),    'vel_r_parent': 0.1},
        {'name': "Neptune", 'mass': 5.15e-5, 'pos': (np.random.uniform(-0.01, 0.01), np.random.uniform(0.115, 0.125)),   'vel_r_parent': 0.12},
        # Add a smaller, faster "MoonA" for more chaos
        {'name': "MoonA",   'mass': 5e-8,    'pos': (0.005,0.005), 'vel_r_parent': math.sqrt(0.005**2+0.005**2)}
    ]
    initial_bodies = initial_bodies[:n_bodies] # Ensure correct number if list is longer

    return {
        "name": "Jupiter Chaotic System",
        "output_filename": "planetary_chaotic.mp4",
        "current_n_bodies": n_bodies,
        "time_step_years": 2e-6, # Very small dt
        "epsilon": 0.0001,       # Very small epsilon
        "animation_plot_duration_years": animation_plot_duration_years,
        "real_time_animation_seconds": real_time_seconds,
        "fps": fps,
        "num_frames": num_frames,
        "trail_length_frames": 400, # Full trails to see the chaos unfold
        "initial_bodies_data": initial_bodies,
        "plot_config": {
            "title_suffix": "Jupiter System (Chaotic)",
            "limit_fixed": 0.20, # Fixed small limit, e.g., 0.20 AU (adjust based on observations)
            "marker_config": { # Jupiter is the "sun_size" here
                "primary_body_size": 15.0, "base_size": 2.0, "min_size": 1.5, 
                "max_size": 7.0, "power_scale": 0.40
            },
            "trail_config": {
                "base_lw": 0.3, "max_lw": 1.2, "power_scale": 0.3, "primary_body_lw": 1.2
            },
            "label_font_size": 6,
            "label_offset_factor": 0.035
        }
    }

# --- Main Simulation Runner ---
def run_simulation_scenario(scenario_params):
    """Runs a complete simulation and animation for a given scenario."""
    
    CURRENT_N_BODIES = scenario_params["current_n_bodies"]
    initial_states_list = scenario_params["initial_bodies_data"]
    
    NUM_FRAMES = scenario_params["num_frames"]
    if NUM_FRAMES <= 0: # Should not happen with current setup, but defensive
        print(f"Scenario '{scenario_params['name']}' has zero frames. Skipping.")
        return
    TIME_PER_FRAME_FOR_ANIM = scenario_params["animation_plot_duration_years"] / NUM_FRAMES

    TRAIL_LENGTH = scenario_params["trail_length_frames"]
    
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
    print(f"Compiling Loma code for scenario: {scenario_params['name']} (if not already compiled with this name/content)")
    structs, lib = compiler.compile(loma_code_str,
                                    target='c', 
                                    output_filename=compiled_lib_path_prefix)
    print("Compilation successful for Loma code.")

    Vec2 = structs['Vec2']
    BodyState = structs['BodyState']
    SimConfig = structs['SimConfig']
    BodyStateArray = BodyState * MAX_N_BODIES_CONST 

    current_body_states = BodyStateArray() # Zero-initialized by ctypes
    next_body_states_buffer = BodyStateArray() # Zero-initialized

    total_momentum_x: float = 0.0
    total_momentum_y: float = 0.0
    max_initial_coord = 0.001 

    central_body_mass = initial_states_list[0]['mass']
    for i in range(CURRENT_N_BODIES):
        p_data = initial_states_list[i]
        current_body_states[i].mass = p_data['mass']
        current_body_states[i].inv_mass = 1.0 / p_data['mass'] if p_data['mass'] > 1e-20 else 0.0 # Avoid div by zero for tiny/zero mass
        
        pos_x, pos_y = p_data['pos']
        current_body_states[i].pos = Vec2(x=pos_x, y=pos_y)
        max_initial_coord = max(max_initial_coord, abs(pos_x), abs(pos_y))
        
        vx_init, vy_init = 0.0, 0.0
        if 'vel' in p_data: 
             vel_x_abs, vel_y_abs = p_data['vel']
             vx_init, vy_init = vel_x_abs, vel_y_abs
        elif 'vel_r_parent' in p_data and i > 0: # Only for orbiting bodies
            r_orbit = p_data['vel_r_parent']
            # Use mass of the actual central body for this scenario
            v_mag = math.sqrt(G_val * central_body_mass / r_orbit) if r_orbit > 1e-9 else 0.0
            if r_orbit > 1e-9:
                vx_init = -pos_y / r_orbit * v_mag
                vy_init = pos_x / r_orbit * v_mag
                if scenario_params["name"] == "Jupiter Chaotic System": # Add specific perturbations for chaos
                    angle_perturb = np.random.uniform(-0.3, 0.3) 
                    v_mag_perturb = np.random.uniform(0.85, 1.15) # More aggressive velocity perturbation
                    
                    c, s = math.cos(angle_perturb), math.sin(angle_perturb)
                    vx_new_perturb = vx_init * c - vy_init * s
                    vy_new_perturb = vx_init * s + vy_init * c
                    vx_init = vx_new_perturb * v_mag_perturb
                    vy_init = vy_new_perturb * v_mag_perturb
            
        current_body_states[i].mom = Vec2(x=p_data['mass'] * vx_init, y=p_data['mass'] * vy_init)
        total_momentum_x += current_body_states[i].mom.x
        total_momentum_y += current_body_states[i].mom.y
    
    if CURRENT_N_BODIES > 0 and initial_states_list[0].get('vel', None) is not None : 
        if current_body_states[0].mass > 1e-20 :
            current_body_states[0].mom.x -= total_momentum_x 
            current_body_states[0].mom.y -= total_momentum_y

    sim_config_obj = SimConfig(
        G=G_val, 
        dt=scenario_params["time_step_years"], 
        epsilon_sq=scenario_params["epsilon"]**2, 
        num_bodies=CURRENT_N_BODIES
    )

    fig, ax = plt.subplots(figsize=(14, 14))
    ax.set_aspect('equal')
    p_cfg = scenario_params["plot_config"]
    if "limit_fixed" in p_cfg:
        plot_limit = p_cfg["limit_fixed"]
    else:
        plot_limit = max_initial_coord * p_cfg.get("limit_auto_scale", 1.3) + p_cfg.get("limit_min_padding", 2.0)
    ax.set_xlim(-plot_limit, plot_limit)
    ax.set_ylim(-plot_limit, plot_limit)
    ax.set_title(f'N-Body: {p_cfg["title_suffix"]} ({CURRENT_N_BODIES} bodies) - {scenario_params["animation_plot_duration_years"]:.1f} yrs', color='white', fontsize=16)
    ax.set_xlabel('X (AU)', color='white', fontsize=12)
    ax.set_ylabel('Y (AU)', color='white', fontsize=12)
    ax.grid(True, linestyle=':', alpha=0.4, color='gray')
    fig.patch.set_facecolor('#101018') 
    ax.set_facecolor('#0B0B12') 
    ax.tick_params(axis='x', colors='lightgrey'); ax.tick_params(axis='y', colors='lightgrey')
    for spine in ax.spines.values(): spine.set_edgecolor('lightgrey')

    planet_plots = [ax.plot([], [], 'o', zorder=5)[0] for _ in range(CURRENT_N_BODIES)]
    trajectory_plots = [ax.plot([], [], '-', zorder=4)[0] for _ in range(CURRENT_N_BODIES)]
    planet_labels = [ax.text(0, 0, '', fontsize=p_cfg["label_font_size"], color='white', ha='left', va='bottom',zorder=10) for _ in range(CURRENT_N_BODIES)]
    
    trajectories_data = [[([], []) for _ in range(MAX_N_BODIES_CONST)]] # Use a list wrapper for nonlocal modification
    trajectories_data[0] = [ ([], []) for _ in range(CURRENT_N_BODIES) ]


    scenario_body_names = [p['name'] for p in initial_states_list]
    mkr_cfg = p_cfg["marker_config"]
    trl_cfg = p_cfg["trail_config"]

    for i in range(CURRENT_N_BODIES):
        body_name = scenario_body_names[i]
        color = DEFAULT_PLANET_COLORS.get(body_name, DEFAULT_PLANET_COLORS["Body"])
        
        planet_plots[i].set_color(color)
        planet_plots[i].set_markeredgecolor('#202020')
        
        trajectory_plots[i].set_color(color)
        trajectory_plots[i].set_alpha(0.65)
        
        planet_labels[i].set_text(body_name)
        
        relative_radius = DEFAULT_PLANET_VISUAL_RADII.get(body_name, DEFAULT_PLANET_VISUAL_RADII["Body"])
        is_primary_body = (i == 0) 

        if is_primary_body: 
            planet_plots[i].set_markersize(mkr_cfg["primary_body_size"])
            trajectory_plots[i].set_linewidth(trl_cfg.get("primary_body_lw", trl_cfg["base_lw"] + 0.5))
        else:
            marker_sz = mkr_cfg["base_size"] * (relative_radius ** mkr_cfg["power_scale"])
            planet_plots[i].set_markersize(min(max(mkr_cfg["min_size"], marker_sz), mkr_cfg["max_size"]))
            trail_lw = trl_cfg["base_lw"] + (relative_radius ** trl_cfg["power_scale"]) * 0.7 
            trajectory_plots[i].set_linewidth(min(max(0.4, trail_lw), trl_cfg["max_lw"]))

    def animate(frame_num):
        steps_per_frame = int(TIME_PER_FRAME_FOR_ANIM / scenario_params["time_step_years"]) if scenario_params["time_step_years"] > 0 else 1
        
        for _ in range(steps_per_frame):
            lib.time_step_system(current_body_states, sim_config_obj, next_body_states_buffer)
            ctypes.memmove(ctypes.addressof(current_body_states),
                           ctypes.addressof(next_body_states_buffer),
                           ctypes.sizeof(BodyStateArray)) 
        
        if TRAIL_LENGTH > 0:
            for i in range(CURRENT_N_BODIES):
                trajectories_data[0][i][0].append(current_body_states[i].pos.x)
                trajectories_data[0][i][1].append(current_body_states[i].pos.y)
                
                if len(trajectories_data[0][i][0]) > TRAIL_LENGTH:
                    trajectories_data[0][i][0].pop(0)
                    trajectories_data[0][i][1].pop(0)
        
        updated_artists = []
        current_plot_xlim = ax.get_xlim() # Use full tuple for consistent indexing
        label_x_offset_data = (current_plot_xlim[1] - current_plot_xlim[0]) * p_cfg["label_offset_factor"] * 0.2  # Smaller offset
        label_y_offset_data = label_x_offset_data # Keep it symmetric for now

        for i in range(CURRENT_N_BODIES):
            x_pos, y_pos = current_body_states[i].pos.x, current_body_states[i].pos.y
            planet_plots[i].set_data([x_pos], [y_pos])
            updated_artists.append(planet_plots[i])
            
            if TRAIL_LENGTH > 0:
                trajectory_plots[i].set_data(trajectories_data[0][i][0], trajectories_data[0][i][1])
                updated_artists.append(trajectory_plots[i])
            
            planet_labels[i].set_position((x_pos + label_x_offset_data, y_pos + label_y_offset_data))
            updated_artists.append(planet_labels[i])
            
        if frame_num % (scenario_params["fps"] // 2) == 0: 
            print(f"Scenario '{scenario_params['name']}': Frame {frame_num}/{NUM_FRAMES}, Sim Time: {frame_num * TIME_PER_FRAME_FOR_ANIM:.2f} Years")

        return updated_artists

    print(f"\n--- Running Scenario: {scenario_params['name']} ---")
    print(f"Animation: {NUM_FRAMES} frames, plotting {scenario_params['animation_plot_duration_years']:.1f} simulated years.")
    print(f"Time per frame: {TIME_PER_FRAME_FOR_ANIM:.4f} years. Steps per frame: {int(TIME_PER_FRAME_FOR_ANIM / scenario_params['time_step_years']) if scenario_params['time_step_years'] > 0 else 1}")

    ani = animation.FuncAnimation(fig, animate, frames=NUM_FRAMES,
                                  interval=1000.0/scenario_params["fps"], blit=True, repeat=False)
    
    plt.show(block=False) 

    save_opt = scenario_params.get("save_animation", True) # Default to save
    if save_opt:
        output_file = scenario_params["output_filename"]
        print(f"Saving animation to {output_file}...")
        try:
            ani.save(output_file, writer='ffmpeg', fps=scenario_params["fps"], dpi=150, 
                     progress_callback=lambda i, n: print(f'Saving {output_file} frame {i+1}/{n}', end='\r'))
            print(f"\nAnimation saved as {output_file}")
        except Exception as e:
            print(f"\nError saving animation {output_file}: {e}")
            print("Ensure ffmpeg is installed and in your system PATH.")
    
    plt.close(fig)
    print(f"--- Scenario '{scenario_params['name']}' Finished ---")


if __name__ == '__main__':
    # Run Solar System Scenario
    # ss_params = setup_solar_system_scenario()
    # run_simulation_scenario(ss_params)

    # Run Jupiter Chaotic Scenario
    jc_params = setup_jupiter_chaotic_scenario()
    run_simulation_scenario(jc_params)

    print("\nAll scenarios complete. You may need to close Matplotlib windows manually if any persist.")