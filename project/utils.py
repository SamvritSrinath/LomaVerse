def convert_body_state_arrs_to_python(body_state_arrs, current_n_bodies):
    ret = []
    for body_state_arr in body_state_arrs:
        body_states = []
        for i in range(current_n_bodies):
            body_state = body_state_arr[i]
            body_states.append({
                "pos": {"x": body_state.pos.x, "y": body_state.pos.y},
                "mom": {"x": body_state.mom.x, "y": body_state.mom.y},
                "mass": body_state.mass,
                "inv_mass": body_state.inv_mass
            })
        ret.append(body_states)
    return ret