from config import BodyState, SolarSystemConfig

def convert_ctype_state_to_body_state(ctype_state, cfg: SolarSystemConfig) -> list[BodyState]:
    body_configs = []
    for i in range(cfg.current_n_bodies):
        body_config = BodyState()
        body_state = ctype_state[i]
        body_config.name = cfg.initial_bodies_data[i].name
        body_config.mass = body_state.mass
        body_config.pos = (body_state.pos.x, body_state.pos.y)
        body_configs.append(body_config)
    return body_configs