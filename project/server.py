from flask import Flask, render_template, jsonify, request
import uuid
from planetary_motion import setup_jupiter_system_scenario, setup_true_chaotic_scenario, setup_solar_system_scenario, get_simulation_runner, LOMA_CODE_2D_FILENAME, LOMA_CODE_3D_FILENAME
import random
import os
import json
import logging
import math

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

current_session = None
sessions = {}

@app.route("/")
def index(): return render_template("index.html")

@app.route("/scenario-builder")
def scenario_builder(): return render_template("scenario_builder.html")

@app.route("/conversions") 
def conversions(): return render_template("conversions.html")

@app.route("/init_session", methods=['POST'])
def init_session():
    global current_session 
    try:
        data = request.get_json()
        simulation_name = data['simulation_name']
        app.logger.info(f"init_session: Initializing: {simulation_name}")
        cfg = None
        if simulation_name == "jupiterchaotic":
            cfg = setup_jupiter_system_scenario() 
        elif simulation_name == "solarsys":
            cfg = setup_solar_system_scenario()
        elif simulation_name == "trulychaotic":
            cfg = setup_true_chaotic_scenario()
        else:
            app.logger.error(f"init_session: Unknown simulation: {simulation_name}")
            return jsonify({"error": f"Unknown simulation: {simulation_name}"}), 400

        if not cfg: return jsonify({"error": "Failed to setup config"}), 500
        new_id = str(uuid.uuid4())
        sim_runner = get_simulation_runner(cfg)
        if not sim_runner or sim_runner == (lambda _: []): 
            return jsonify({"error": "Failed to init sim runner"}), 500
        sessions[new_id] = sim_runner
        current_session = sim_runner
        return jsonify({"session_id": new_id, "system_config": cfg})
    except Exception as e:
        app.logger.exception("Error in init_session")
        return jsonify({"error": str(e)}), 500

@app.get("/state/<session_id>")
def get_state(session_id):
    try:
        if session_id not in sessions:
            app.logger.warning(f"get_state: Invalid session ID: {session_id}")
            return jsonify({"error": "Invalid session ID"}), 404
            
        sim_runner = sessions[session_id]
        if not sim_runner:
            app.logger.error(f"get_state: Invalid simulation runner for session ID: {session_id}")
            return jsonify({"error": "Invalid simulation runner"}), 500
            
        new_states = sim_runner(256)
        
        for frame_idx, frame_data in enumerate(new_states):
            if not isinstance(frame_data, list):
                app.logger.error(f"get_state: Frame {frame_idx} is not a list for session {session_id}.")
                return jsonify({"error": "Malformed frame data from simulation."}), 500
            for body_idx, body_state_obj in enumerate(frame_data):
                if not hasattr(body_state_obj, 'pos') or not isinstance(body_state_obj.pos, tuple):
                    app.logger.error(f"get_state: Body {body_idx} in frame {frame_idx} has malformed position for session {session_id}.")
                    return jsonify({"error": "Malformed body state data from simulation."}), 500
                if any(math.isnan(p_comp) for p_comp in body_state_obj.pos):
                    body_name = getattr(body_state_obj, 'name', f'UnknownBody{body_idx}')
                    error_msg = f"NaN detected in position for body '{body_name}' in frame {frame_idx}. Position: {body_state_obj.pos}"
                    app.logger.error(f"get_state: {error_msg} for session {session_id}")
                    return jsonify({"error": "Simulation produced NaN values.", "details": error_msg}), 500
            
        return jsonify(new_states)
    except Exception as e:
        app.logger.exception(f"get_state: An error occurred for session ID: {session_id}")
        return jsonify({"error": str(e)}), 500

@app.route('/add_planet', methods=['POST'])
def add_planet():
    data = request.get_json()
    app.logger.info(f"Conceptual add_planet: {data.get('name')}, mass {data.get('mass')} M☉")
    return jsonify({'message': 'Planet data received (conceptual). Re-init for changes.'}), 200

@app.route('/save_scenario', methods=['POST'])
def save_scenario():
    data = request.get_json()
    if not data or 'name' not in data or 'planets' not in data:
        return jsonify({'error': 'Missing fields'}), 400
    for p in data['planets']:
        if 'mass' not in p or float(p['mass']) <= 0:
            return jsonify({'error': f"Invalid mass for planet {p.get('name')}"}), 400
            
    scenario_dir = 'scenarios'
    if not os.path.exists(scenario_dir): os.makedirs(scenario_dir)
    sane_name = "".join(c for c in data['name'] if c.isalnum() or c in (' ', '_', '-')).strip()
    if not sane_name: return jsonify({'error': 'Invalid scenario name'}), 400
    scenario_file = os.path.join(scenario_dir, f"{sane_name}.json")
    with open(scenario_file, 'w') as f: json.dump(data, f, indent=2)
    app.logger.info(f"Scenario '{sane_name}' saved with mass in Solar Masses.")
    return jsonify({'message': 'Scenario saved successfully'}), 200

@app.route('/list_scenarios')
def list_scenarios():
    scenario_dir = 'scenarios'
    scenarios = []
    if os.path.exists(scenario_dir):
        for fn in os.listdir(scenario_dir):
            if fn.endswith('.json'):
                try:
                    with open(os.path.join(scenario_dir, fn), 'r') as f: 
                        data = json.load(f)
                        if 'name' in data and 'planets' in data:
                            scenarios.append({
                                'name': data['name'],
                                'planet_count': len(data['planets'])
                            })
                except Exception as e:
                    app.logger.error(f"Err processing {fn}: {e}")
    return jsonify(scenarios)

@app.route('/load_scenario/<name>')
def load_scenario(name):
    global current_session
    sane_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
    if not sane_name: return jsonify({'error': 'Invalid scenario name'}), 400
    scenario_file = os.path.join('scenarios', f"{sane_name}.json")
    if not os.path.exists(scenario_file): return jsonify({'error': 'Scenario not found'}), 404

    try:
        with open(scenario_file, 'r') as f: scenario_data = json.load(f)
        initial_bodies = [BodyState(**p) for p in scenario_data.get('planets', [])]
        
        loaded_cfg_dict = {
            'name': f"Loaded: {scenario_data.get('name', 'Unnamed')}",
            'current_n_bodies': len(initial_bodies),
            'epsilon': scenario_data.get('epsilon', 0.005),
            'years_per_frame': scenario_data.get('years_per_frame', 0.005),
            'fps': scenario_data.get('fps', 60),
            'sim_steps_per_frame': scenario_data.get('sim_steps_per_frame', 512),
            'initial_bodies_data': initial_bodies,
            'dimensions': scenario_data.get('dimensions', 3),
            'loma_code_file': LOMA_CODE_3D_FILENAME if scenario_data.get('dimensions', 3) == 3 else LOMA_CODE_2D_FILENAME,
        }
        loaded_cfg = SolarSystemConfig(**loaded_cfg_dict)
        
        new_id = str(uuid.uuid4())
        sim_runner = get_simulation_runner(loaded_cfg)
        if not sim_runner or sim_runner == (lambda _: []):
            return jsonify({'error': 'Failed to init runner for loaded scenario'}), 500
        
        sessions[new_id] = sim_runner
        current_session = sim_runner
        app.logger.info(f"Loaded scenario '{sane_name}' into session {new_id}.")
        return jsonify({'session_id': new_id, 'system_config': loaded_cfg_dict})
    except Exception as e:
        app.logger.exception(f"Error loading scenario {name}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)