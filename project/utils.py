# utils.py
from config import BodyState, SolarSystemConfig # SolarSystemConfig carries dimension info

def convert_ctype_state_to_body_state(ctype_state_array, cfg: SolarSystemConfig) -> list[BodyState]:
    body_configs_list = [] # Renamed for clarity
    for i in range(cfg.current_n_bodies):
        py_body_state = BodyState() # Create a new Python BodyState instance
        loma_body_state = ctype_state_array[i] # Access the i-th element of the CTYPES array
        
        # Copy name and mass
        # Ensure initial_bodies_data is available and has enough elements
        if i < len(cfg.initial_bodies_data):
            py_body_state.name = cfg.initial_bodies_data[i].name
        else:
            py_body_state.name = f"Body {i+1}" # Fallback name

        py_body_state.mass = loma_body_state.mass # Mass comes from the simulated Loma state
        
        # Position: convert Loma's Vec2/Vec3 to Python 3-tuple (x,y,z)
        if cfg.dimensions == 3:
            py_body_state.pos = (loma_body_state.pos.x, loma_body_state.pos.y, loma_body_state.pos.z)
        else: # dimensions == 2
            py_body_state.pos = (loma_body_state.pos.x, loma_body_state.pos.y, 0.0) # z is 0.0 for 2D
        
        # Velocity is not directly part of the Loma BodyState (it uses momentum).
        # If velocity is needed by the frontend, it should be calculated here:
        # mom_x = loma_body_state.mom.x
        # mom_y = loma_body_state.mom.y
        # if py_body_state.mass > 1e-20:
        #     if cfg.dimensions == 3:
        #         mom_z = loma_body_state.mom.z
        #         py_body_state.vel = (mom_x / py_body_state.mass, mom_y / py_body_state.mass, mom_z / py_body_state.mass)
        #     else:
        #         py_body_state.vel = (mom_x / py_body_state.mass, mom_y / py_body_state.mass, 0.0)
        # else:
        #     py_body_state.vel = (0.0, 0.0, 0.0)
        # However, config.BodyState.vel is Union[tuple[float,float,float], float], so better to stick to tuple for consistency if filled.
        # For now, as JS only uses .pos from this conversion, .vel is left as its default from BodyState().

        body_configs_list.append(py_body_state)
    return body_configs_list