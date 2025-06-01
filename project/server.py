from flask import Flask, render_template, jsonify, request
import uuid
from planetary_motion import setup_jupiter_chaotic_scenario, setup_solar_system_scenario, get_simulation_runner
import random
import os
import json

app = Flask(__name__)
current_session = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/scenario-builder")
def scenario_builder():
    return render_template("scenario_builder.html")

sessions = {}

@app.route("/init_session", methods=['POST'])
def init_session():
    try:
        data = request.get_json()
        if not data or 'simulation_name' not in data:
            return jsonify({"error": "No simulation name provided"}), 400
            
        simulation_name = data['simulation_name']
        cfg = None
        if simulation_name == "jupiterchaotic":
            cfg = setup_jupiter_chaotic_scenario()
        elif simulation_name == "solarsys":
            cfg = setup_solar_system_scenario()
        else:
            return jsonify({"error": f"Unknown simulation: {simulation_name}"}), 400
            
        if not cfg:
            return jsonify({"error": "Failed to setup simulation configuration"}), 500
            
        new_session_id = str(uuid.uuid4())
        sim_runner = get_simulation_runner(cfg)
        
        if not sim_runner:
            return jsonify({"error": "Failed to initialize simulation runner"}), 500
            
        sessions[new_session_id] = sim_runner
        global current_session
        current_session = sim_runner
        return jsonify({"session_id": new_session_id, "system_config": cfg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/state/<session_id>")
def get_state(session_id):
    try:
        if session_id not in sessions:
            return jsonify({"error": "Invalid session ID"}), 404
            
        sim_runner = sessions[session_id]
        if not sim_runner:
            return jsonify({"error": "Invalid simulation runner"}), 500
            
        new_states = sim_runner(256)
        if not new_states:
            return jsonify({"error": "Failed to generate new states"}), 500
            
        return jsonify(new_states)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_planet', methods=['POST'])
def add_planet():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['name', 'position', 'mass']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Create new body state with default values for optional fields
        new_body = {
            'name': data['name'],
            'position': {
                'x': float(data['position']['x']),
                'y': float(data['position']['y']),
                'z': float(data['position'].get('z', 0))
            },
            'velocity': {
                'x': float(data.get('velocity', {}).get('x', 0)),
                'y': float(data.get('velocity', {}).get('y', 0)),
                'z': float(data.get('velocity', {}).get('z', 0))
            },
            'mass': float(data['mass']),
            'color': data.get('color') or f'#{random.randint(0, 0xFFFFFF):06x}'
        }

        # Add the new body to the current simulation
        if 'current_session' not in globals() or not current_session:
            return jsonify({'error': 'No active simulation session'}), 400

        # Add the new body to the simulation runner
        current_session.add_body(new_body)

        return jsonify({'message': 'Planet added successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_scenario', methods=['POST'])
def save_scenario():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        if 'name' not in data or 'planets' not in data:
            return jsonify({'error': 'Missing required fields: name and planets'}), 400

        # Validate planets data
        for planet in data['planets']:
            required_fields = ['name', 'position', 'mass']
            for field in required_fields:
                if field not in planet:
                    return jsonify({'error': f'Missing required field in planet: {field}'}), 400

        # Save scenario to a file
        scenario_dir = 'scenarios'
        if not os.path.exists(scenario_dir):
            os.makedirs(scenario_dir)

        scenario_file = os.path.join(scenario_dir, f"{data['name']}.json")
        with open(scenario_file, 'w') as f:
            json.dump(data, f, indent=2)

        return jsonify({'message': 'Scenario saved successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/list_scenarios')
def list_scenarios():
    try:
        scenario_dir = 'scenarios'
        if not os.path.exists(scenario_dir):
            return jsonify([])
            
        scenarios = []
        for file in os.listdir(scenario_dir):
            if file.endswith('.json'):
                with open(os.path.join(scenario_dir, file), 'r') as f:
                    scenario_data = json.load(f)
                    scenarios.append({
                        'name': scenario_data['name'],
                        'planet_count': len(scenario_data['planets'])
                    })
        return jsonify(scenarios)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/load_scenario/<name>')
def load_scenario(name):
    try:
        scenario_file = os.path.join('scenarios', f"{name}.json")
        if not os.path.exists(scenario_file):
            return jsonify({'error': 'Scenario not found'}), 404
            
        with open(scenario_file, 'r') as f:
            scenario_data = json.load(f)
            
        # Create a new session for this scenario
        new_session_id = str(uuid.uuid4())
        sim_runner = get_simulation_runner({
            'name': scenario_data['name'],
            'bodies': scenario_data['planets']
        })
        
        if not sim_runner:
            return jsonify({'error': 'Failed to initialize simulation runner'}), 500
            
        sessions[new_session_id] = sim_runner
        return jsonify({
            'session_id': new_session_id,
            'system_config': {
                'name': scenario_data['name'],
                'bodies': scenario_data['planets']
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)