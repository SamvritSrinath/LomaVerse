# utils.py
from config import BodyState, SolarSystemConfig

def convert_ctype_state_to_body_state(ctype_state_array, cfg: SolarSystemConfig) -> list[BodyState]:
    body_configs_list = []
    for i in range(cfg.current_n_bodies):
        py_body_state = BodyState()
        loma_body_state = ctype_state_array[i]
        
        if i < len(cfg.initial_bodies_data):
            py_body_state.name = cfg.initial_bodies_data[i].name
        else:
            py_body_state.name = f"Body {i+1}"

        py_body_state.mass = loma_body_state.mass
        
        py_body_state.pos = (loma_body_state.pos.x, loma_body_state.pos.y, loma_body_state.pos.z)
        
        # Velocity is not directly used by the frontend rendering, which relies on .pos
        # Leaving it as default to avoid unnecessary computation.

        body_configs_list.append(py_body_state)
    return body_configs_list