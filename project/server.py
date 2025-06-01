from flask import Flask, render_template, jsonify, request
import uuid
from planetary_motion import setup_jupiter_chaotic_scenario, setup_solar_system_scenario, get_simulation_runner

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

sessions = {}
@app.get("/state")
def init_session():
    simulation_name = request.args.get('simulationName')
    cfg = None
    if simulation_name == "jupiterchaotic":
        cfg = setup_jupiter_chaotic_scenario()
    elif simulation_name == "solarsys":
        cfg = setup_solar_system_scenario()
    new_session_id = str(uuid.uuid4())
    sim_runner = get_simulation_runner(cfg)
    sessions[new_session_id] = sim_runner
    return jsonify({"session_id": new_session_id, "system_config": cfg})

@app.get("/state/<session_id>")
def get_state(session_id):
    new_states = sessions[session_id](256)
    return jsonify(new_states)

if __name__ == '__main__':
    app.run(debug=True)