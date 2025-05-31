from flask import Flask, render_template, jsonify
import uuid
from planetary_motion import setup_jupiter_chaotic_scenario, get_simulation_runner

app = Flask(__name__)

@app.route("/")
def hello_world():
    return render_template("index.html")


sessions = {}
@app.get("/state")
def init_session():    
    new_session_id = str(uuid.uuid4())
    cfg = setup_jupiter_chaotic_scenario()
    sim_runner = get_simulation_runner(cfg)
    sessions[new_session_id] = sim_runner
    return jsonify({"session_id": new_session_id})

@app.get("/state/<session_id>")
def get_state(session_id):
    new_states = sessions[session_id]()
    return jsonify(new_states)

if __name__ == '__main__':
    app.run(debug=True)