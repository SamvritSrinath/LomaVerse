# --- Struct Definitions ---
class Vec3: 
    x: float
    y: float
    z: float 

class BodyState:
    pos: Vec3 # Uses Vec3
    mom: Vec3 # Uses Vec3
    mass: float
    inv_mass: float

class SimConfig:
    G: float
    dt: float
    epsilon_sq: float
    num_bodies: int

# --- Hamiltonian Function (3D) ---
def n_body_hamiltonian(states: In[Array[BodyState, 20]], 
                       config: In[SimConfig]) -> float:
    total_kinetic_energy: float = 0.0
    total_potential_energy: float = 0.0
    i: int = 0
    j: int = 0
    
    dx: float; dy: float; dz: float; # Added dz
    dist_sq: float; inv_dist_soft: float
    s_i_pos_x: float; s_i_pos_y: float; s_i_pos_z: float; 
    s_j_pos_x: float; s_j_pos_y: float; s_j_pos_z: float; 
    s_i_mom_x: float; s_i_mom_y: float; s_i_mom_z: float; 
    s_i_inv_mass: float; s_i_mass: float; s_j_mass: float

    # Kinetic Energy (includes z-component of momentum)
    i = 0
    while (i < config.num_bodies, max_iter := 20):
        s_i_mom_x = states[i].mom.x
        s_i_mom_y = states[i].mom.y
        s_i_mom_z = states[i].mom.z # Added
        s_i_inv_mass = states[i].inv_mass
        total_kinetic_energy = total_kinetic_energy + \
            (s_i_mom_x*s_i_mom_x + s_i_mom_y*s_i_mom_y + s_i_mom_z*s_i_mom_z) * \
            s_i_inv_mass * 0.5
        i = i + 1
    
    # Potential Energy (distance calculation includes z)
    i = 0
    while (i < config.num_bodies, max_iter := 20):
        s_i_pos_x = states[i].pos.x
        s_i_pos_y = states[i].pos.y
        s_i_pos_z = states[i].pos.z # Added
        s_i_mass = states[i].mass
        
        j = i + 1
        while (j < config.num_bodies, max_iter := 20):
            s_j_pos_x = states[j].pos.x
            s_j_pos_y = states[j].pos.y
            s_j_pos_z = states[j].pos.z # Added
            s_j_mass = states[j].mass
            
            dx = s_j_pos_x - s_i_pos_x
            dy = s_j_pos_y - s_i_pos_y
            dz = s_j_pos_z - s_i_pos_z # Added
            dist_sq = dx*dx + dy*dy + dz*dz # Updated distance squared
            
            inv_dist_soft = 1.0 / sqrt(dist_sq + config.epsilon_sq)
            total_potential_energy = total_potential_energy - \
                config.G * s_i_mass * s_j_mass * inv_dist_soft
            j = j + 1
        i = i + 1
        
    return total_kinetic_energy + total_potential_energy

# --- Differentiated Hamiltonian ---
d_n_body_hamiltonian = fwd_diff(n_body_hamiltonian)

# --- Functions to compute partial derivatives of H (3D) ---
# alpha: 0 for x, 1 for y, 2 for z
def get_dH_dr_k_alpha(states_val: In[Array[BodyState, 20]], 
                        config_val: In[SimConfig],
                        k: In[int], 
                        alpha: In[int]
                        ) -> float:
    d_states: Array[Diff[BodyState], 20] 
    d_config: Diff[SimConfig]
    idx: int = 0

    while(idx < 20, max_iter := 20): 
        if idx < config_val.num_bodies:
            d_states[idx].pos.x.val = states_val[idx].pos.x
            d_states[idx].pos.y.val = states_val[idx].pos.y
            d_states[idx].pos.z.val = states_val[idx].pos.z # Added
            d_states[idx].mom.x.val = states_val[idx].mom.x
            d_states[idx].mom.y.val = states_val[idx].mom.y
            d_states[idx].mom.z.val = states_val[idx].mom.z # Added
            d_states[idx].mass.val = states_val[idx].mass
            d_states[idx].inv_mass.val = states_val[idx].inv_mass
        else: 
            d_states[idx].pos.x.val = 0.0; d_states[idx].pos.y.val = 0.0; d_states[idx].pos.z.val = 0.0 
            d_states[idx].mom.x.val = 0.0; d_states[idx].mom.y.val = 0.0; d_states[idx].mom.z.val = 0.0 
            d_states[idx].mass.val = 1.0 
            d_states[idx].inv_mass.val = 1.0

        d_states[idx].pos.x.dval = 0.0; d_states[idx].pos.y.dval = 0.0; d_states[idx].pos.z.dval = 0.0 
        d_states[idx].mom.x.dval = 0.0; d_states[idx].mom.y.dval = 0.0; d_states[idx].mom.z.dval = 0.0 
        d_states[idx].mass.dval = 0.0      
        d_states[idx].inv_mass.dval = 0.0  
        idx = idx + 1
    
    d_config.G.val = config_val.G; d_config.G.dval = 0.0      
    d_config.dt.val = config_val.dt; d_config.dt.dval = 0.0       
    d_config.epsilon_sq.val = config_val.epsilon_sq; d_config.epsilon_sq.dval = 0.0
    d_config.num_bodies = config_val.num_bodies 

    if k < config_val.num_bodies: 
        if alpha == 0: 
            d_states[k].pos.x.dval = 1.0
        elif alpha == 1: 
            d_states[k].pos.y.dval = 1.0
        else: # alpha == 2 for z
            d_states[k].pos.z.dval = 1.0 
        
    return d_n_body_hamiltonian(d_states, d_config).dval

def get_dH_dp_k_alpha(states_val: In[Array[BodyState, 20]], 
                        config_val: In[SimConfig],
                        k: In[int],
                        alpha: In[int]
                        ) -> float:
    d_states: Array[Diff[BodyState], 20] 
    d_config: Diff[SimConfig]
    idx: int = 0

    while(idx < 20, max_iter := 20): 
        if idx < config_val.num_bodies:
            d_states[idx].pos.x.val = states_val[idx].pos.x 
            d_states[idx].pos.y.val = states_val[idx].pos.y
            d_states[idx].pos.z.val = states_val[idx].pos.z # Added
            d_states[idx].mom.x.val = states_val[idx].mom.x
            d_states[idx].mom.y.val = states_val[idx].mom.y
            d_states[idx].mom.z.val = states_val[idx].mom.z # Added
            d_states[idx].mass.val = states_val[idx].mass
            d_states[idx].inv_mass.val = states_val[idx].inv_mass
        else: 
            d_states[idx].pos.x.val = 0.0; d_states[idx].pos.y.val = 0.0; d_states[idx].pos.z.val = 0.0 
            d_states[idx].mom.x.val = 0.0; d_states[idx].mom.y.val = 0.0; d_states[idx].mom.z.val = 0.0 
            d_states[idx].mass.val = 1.0; d_states[idx].inv_mass.val = 1.0

        d_states[idx].pos.x.dval = 0.0; d_states[idx].pos.y.dval = 0.0; d_states[idx].pos.z.dval = 0.0 
        d_states[idx].mom.x.dval = 0.0; d_states[idx].mom.y.dval = 0.0; d_states[idx].mom.z.dval = 0.0 
        d_states[idx].mass.dval = 0.0
        d_states[idx].inv_mass.dval = 0.0
        idx = idx + 1
    
    d_config.G.val = config_val.G; d_config.G.dval = 0.0
    d_config.dt.val = config_val.dt; d_config.dt.dval = 0.0
    d_config.epsilon_sq.val = config_val.epsilon_sq; d_config.epsilon_sq.dval = 0.0
    d_config.num_bodies = config_val.num_bodies

    if k < config_val.num_bodies: 
        if alpha == 0: 
            d_states[k].mom.x.dval = 1.0
        elif alpha == 1: 
            d_states[k].mom.y.dval = 1.0
        else: # alpha == 2 for z
            d_states[k].mom.z.dval = 1.0
        
    return d_n_body_hamiltonian(d_states, d_config).dval

# --- Time Stepping Function (Symplectic Euler - 3D) ---
def time_step_system(current_states: In[Array[BodyState, 20]], 
                     config: In[SimConfig],
                     next_states: Out[Array[BodyState, 20]]): 
    k: int = 0
    dH_dr_kx: float; dH_dr_ky: float; dH_dr_kz: float 
    dH_dp_kx: float; dH_dp_ky: float; dH_dp_kz: float 

    k = 0
    while(k < config.num_bodies, max_iter := 20): 
        dH_dr_kx = get_dH_dr_k_alpha(current_states, config, k, 0)
        dH_dr_ky = get_dH_dr_k_alpha(current_states, config, k, 1)
        dH_dr_kz = get_dH_dr_k_alpha(current_states, config, k, 2) 
        
        next_states[k].mom.x = current_states[k].mom.x - config.dt * dH_dr_kx
        next_states[k].mom.y = current_states[k].mom.y - config.dt * dH_dr_ky
        next_states[k].mom.z = current_states[k].mom.z - config.dt * dH_dr_kz 
        
        next_states[k].pos.x = current_states[k].pos.x 
        next_states[k].pos.y = current_states[k].pos.y
        next_states[k].pos.z = current_states[k].pos.z 
        
        next_states[k].mass = current_states[k].mass
        next_states[k].inv_mass = current_states[k].inv_mass
        k = k + 1

    k = 0
    while(k < config.num_bodies, max_iter := 20): 
        dH_dp_kx = get_dH_dp_k_alpha(next_states, config, k, 0) 
        dH_dp_ky = get_dH_dp_k_alpha(next_states, config, k, 1)
        dH_dp_kz = get_dH_dp_k_alpha(next_states, config, k, 2) 
        
        next_states[k].pos.x = next_states[k].pos.x + config.dt * dH_dp_kx
        next_states[k].pos.y = next_states[k].pos.y + config.dt * dH_dp_ky
        next_states[k].pos.z = next_states[k].pos.z + config.dt * dH_dp_kz 
        k = k + 1