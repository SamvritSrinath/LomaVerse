# planetary_motion.py (Loma code for N-Body simulation)

# --- Struct Definitions ---
class Vec2:
    x: float
    y: float

class BodyState:
    pos: Vec2     # Position (q_i)
    mom: Vec2     # Momentum (p_i)
    mass: float   # Mass of the body
    inv_mass: float # Inverse mass (1.0 / mass)

class SimConfig:
    G: float            # Gravitational constant
    dt: float           # Time step for integration
    epsilon_sq: float   # Softening factor squared (epsilon^2)
    num_bodies: int # Actual number of bodies to simulate

# --- Hamiltonian Function ---
# Calculates the total energy of the N-body system.
# H(q,p) = sum_i ||p_i||^2 / (2*m_i) - sum_{i<j} G * m_i * m_j / ||r_j - r_i||_soft
def n_body_hamiltonian(states: In[Array[BodyState, 20]], 
                       config: In[SimConfig]) -> float:
    total_kinetic_energy: float = 0.0
    total_potential_energy: float = 0.0
    i: int = 0
    j: int = 0
    
    # Local variables for calculations
    dx: float; dy: float; dist_sq: float; inv_dist_soft: float
    s_i_pos_x: float; s_i_pos_y: float; s_j_pos_x: float; s_j_pos_y: float
    s_i_mom_x: float; s_i_mom_y: float; s_i_inv_mass: float; s_i_mass: float; s_j_mass: float

    # Calculate Kinetic Energy
    i = 0
    while (i < config.num_bodies, max_iter := 20):
        s_i_mom_x = states[i].mom.x
        s_i_mom_y = states[i].mom.y
        s_i_inv_mass = states[i].inv_mass
        total_kinetic_energy = total_kinetic_energy + (s_i_mom_x * s_i_mom_x + s_i_mom_y * s_i_mom_y) * s_i_inv_mass * 0.5
        i = i + 1
    
    # Calculate Potential Energy
    i = 0
    while (i < config.num_bodies, max_iter := 20):
        s_i_pos_x = states[i].pos.x
        s_i_pos_y = states[i].pos.y
        s_i_mass = states[i].mass
        
        j = i + 1 # Sum over unique pairs (j > i)
        while (j < config.num_bodies, max_iter := 20):
            s_j_pos_x = states[j].pos.x
            s_j_pos_y = states[j].pos.y
            s_j_mass = states[j].mass
            
            dx = s_j_pos_x - s_i_pos_x
            dy = s_j_pos_y - s_i_pos_y
            dist_sq = dx * dx + dy * dy
            
            # Softened distance to prevent singularity
            inv_dist_soft = 1.0 / sqrt(dist_sq + config.epsilon_sq)
            total_potential_energy = total_potential_energy - config.G * s_i_mass * s_j_mass * inv_dist_soft
            j = j + 1
        i = i + 1
        
    return total_kinetic_energy + total_potential_energy

# --- Differentiated Hamiltonian ---
# This creates d_n_body_hamiltonian, used by helper functions to get specific partial derivatives.
d_n_body_hamiltonian = fwd_diff(n_body_hamiltonian)

# --- Functions to compute partial derivatives of H ---
# Computes dH / d(states[k].pos.alpha), where alpha=0 for x, alpha=1 for y.
def get_dH_dr_k_alpha(states_val: In[Array[BodyState, 20]], 
                        config_val: In[SimConfig],
                        k: In[int], 
                        alpha: In[int]
                        ) -> float:
    # Local variable for holding primal and dual values for AD.
    # Type is Array of (Differential of BodyState), sized to max bodies.
    d_states: Array[Diff[BodyState], 20] 
    d_config: Diff[SimConfig] # For config parameters
    idx: int = 0

    # Initialize all elements of d_states.
    # Active bodies (idx < config_val.num_bodies) get values from states_val.
    # Inactive bodies get benign default values. All dvals are zeroed initially.
    while(idx < 20, max_iter := 20): 
        if idx < config_val.num_bodies: # Active body
            d_states[idx].pos.x.val = states_val[idx].pos.x
            d_states[idx].pos.y.val = states_val[idx].pos.y
            d_states[idx].mom.x.val = states_val[idx].mom.x
            d_states[idx].mom.y.val = states_val[idx].mom.y
            d_states[idx].mass.val = states_val[idx].mass
            d_states[idx].inv_mass.val = states_val[idx].inv_mass
        else: # Inactive body - set to benign defaults
            d_states[idx].pos.x.val = 0.0 
            d_states[idx].pos.y.val = 0.0
            d_states[idx].mom.x.val = 0.0
            d_states[idx].mom.y.val = 0.0
            d_states[idx].mass.val = 1.0 # Avoid div by zero if inv_mass used
            d_states[idx].inv_mass.val = 1.0

        # Initialize all differential parts to zero
        d_states[idx].pos.x.dval = 0.0
        d_states[idx].pos.y.dval = 0.0
        d_states[idx].mom.x.dval = 0.0
        d_states[idx].mom.y.dval = 0.0
        d_states[idx].mass.dval = 0.0 # Mass is a parameter for this differentiation      
        d_states[idx].inv_mass.dval = 0.0 # Inverse mass is also a parameter
        idx = idx + 1
    
    # Initialize d_config
    d_config.G.val = config_val.G
    d_config.dt.val = config_val.dt 
    d_config.epsilon_sq.val = config_val.epsilon_sq
    d_config.num_bodies = config_val.num_bodies # int members assigned directly
    
    d_config.G.dval = 0.0           
    d_config.dt.dval = 0.0          
    d_config.epsilon_sq.dval = 0.0
    # No .dval for d_config.num_bodies (it's an int, not a _dfloat)

    # Set the specific .dval to 1.0 for the variable we are differentiating with respect to.
    # Ensure k is within the bounds of active bodies.
    if k < config_val.num_bodies: 
        if alpha == 0: # dH/dr_kx
            d_states[k].pos.x.dval = 1.0
        else: # dH/dr_ky (alpha == 1)
            d_states[k].pos.y.dval = 1.0
    # If k is out of bounds, all dvals remain 0, so derivative will be appropriately zero.
        
    return d_n_body_hamiltonian(d_states, d_config).dval

# Computes dH / d(states[k].mom.alpha), where alpha=0 for x, alpha=1 for y.
def get_dH_dp_k_alpha(states_val: In[Array[BodyState, 20]], 
                        config_val: In[SimConfig],
                        k: In[int],
                        alpha: In[int]
                        ) -> float:
    d_states: Array[Diff[BodyState], 20] 
    d_config: Diff[SimConfig]
    idx: int = 0

    # Initialize d_states (similar to get_dH_dr_k_alpha)
    while(idx < 20, max_iter := 20): 
        if idx < config_val.num_bodies:
            d_states[idx].pos.x.val = states_val[idx].pos.x
            d_states[idx].pos.y.val = states_val[idx].pos.y
            d_states[idx].mom.x.val = states_val[idx].mom.x
            d_states[idx].mom.y.val = states_val[idx].mom.y
            d_states[idx].mass.val = states_val[idx].mass
            d_states[idx].inv_mass.val = states_val[idx].inv_mass
        else: 
            d_states[idx].pos.x.val = 0.0; d_states[idx].pos.y.val = 0.0
            d_states[idx].mom.x.val = 0.0; d_states[idx].mom.y.val = 0.0
            d_states[idx].mass.val = 1.0; d_states[idx].inv_mass.val = 1.0

        d_states[idx].pos.x.dval = 0.0
        d_states[idx].pos.y.dval = 0.0
        d_states[idx].mom.x.dval = 0.0
        d_states[idx].mom.y.dval = 0.0
        d_states[idx].mass.dval = 0.0
        d_states[idx].inv_mass.dval = 0.0
        idx = idx + 1
    
    # Initialize d_config
    d_config.G.val = config_val.G
    d_config.dt.val = config_val.dt
    d_config.epsilon_sq.val = config_val.epsilon_sq
    d_config.num_bodies = config_val.num_bodies # int member

    d_config.G.dval = 0.0
    d_config.dt.dval = 0.0
    d_config.epsilon_sq.dval = 0.0
    # No .dval for d_config.num_bodies

    # Set the specific .dval for momentum component.
    if k < config_val.num_bodies: 
        if alpha == 0: # dH/dp_kx
            d_states[k].mom.x.dval = 1.0
        else: # dH/dp_ky (alpha == 1)
            d_states[k].mom.y.dval = 1.0
        
    return d_n_body_hamiltonian(d_states, d_config).dval

# --- Time Stepping Function (Symplectic Euler) ---
# Updates current_states to next_states over one time step config.dt.
def time_step_system(current_states: In[Array[BodyState, 20]], 
                     config: In[SimConfig],
                     next_states: Out[Array[BodyState, 20]]): 
    k: int = 0
    dH_dr_kx: float; dH_dr_ky: float # Partial derivatives of H w.r.t position
    dH_dp_kx: float; dH_dp_ky: float # Partial derivatives of H w.r.t momentum

    # Pass 1: Update momenta (p_new = p_old - dt * dH/dr(r_old, p_old))
    # Also copy r_old and mass properties to next_states to prepare for Pass 2.
    k = 0
    while(k < config.num_bodies, max_iter := 20): 
        # Calculate derivatives using current (old) state
        dH_dr_kx = get_dH_dr_k_alpha(current_states, config, k, 0)
        dH_dr_ky = get_dH_dr_k_alpha(current_states, config, k, 1)
        
        # Update momentum
        next_states[k].mom.x = current_states[k].mom.x - config.dt * dH_dr_kx
        next_states[k].mom.y = current_states[k].mom.y - config.dt * dH_dr_ky
        
        # Copy old position for use in Pass 2 (dH/dp is evaluated at r_old, p_new)
        next_states[k].pos.x = current_states[k].pos.x 
        next_states[k].pos.y = current_states[k].pos.y
        
        # Pass mass and inv_mass through (they don't change in this step)
        next_states[k].mass = current_states[k].mass
        next_states[k].inv_mass = current_states[k].inv_mass
        k = k + 1

    # Pass 2: Update positions (r_new = r_old + dt * dH/dp(r_old, p_new))
    # next_states currently holds (r_old, p_new) from Pass 1.
    k = 0
    while(k < config.num_bodies, max_iter := 20): 
        # Calculate derivatives using r_old (from next_states.pos) and p_new (from next_states.mom)
        dH_dp_kx = get_dH_dp_k_alpha(next_states, config, k, 0) 
        dH_dp_ky = get_dH_dp_k_alpha(next_states, config, k, 1)
        
        # Update position using the dH/dp calculated with new momenta
        next_states[k].pos.x = next_states[k].pos.x + config.dt * dH_dp_kx
        next_states[k].pos.y = next_states[k].pos.y + config.dt * dH_dp_ky
        # Momenta, mass, and inv_mass in next_states are already correctly set from Pass 1.
        k = k + 1