# Directions

Go to `project` to see ths source code for physics engine.

A standard Loma Installation is required to run the project (with any dependencies). Make sure you have also installed `ffmpeg` and `Flask` (refer to `project/requirements.txt` for current project dependencies).

To run the project, run the following commands:

```bash
cd project
python server.py
```

Then, open up the debug server in a web browser (`127.0.0.1:5555`)

## Running Basic Simulations

`cd project; python server.py`

Then, open up the debug server in a web browser.

## Basic Controls

The UI enables for you to click on basic scenarios:

1. `Solar System`
2. `Jupiter System`
3. `True Chaotic System`

We also allow for **User Specified Systems** to be created --> head to the `Scenario Builder` tab.

Following this, you can click on any of the _Saved Scenarios_ to load them into the simulation, these can be controlled via the play/pause button, but to reset the simulation for these Saved Scenarios, you need to re-click the Scenario.

## Visualization Toggle

Lomaverse supports both 2D and 3D visualizations.

To toggle between the two, click on the `View in 2D/3D` button. This simulates a view from the top(+Z axis) of the 3D scene.

## 3D Controls

In the 3D scene, you can click and drag to rotate the camera, and scroll to zoom in and out. Holding `Ctrl` while clicking and dragging will pan the camera.

## 2D Controls

In the 2D scene, you can click and drag to move the camera, and scroll to zoom in and out.

## Examples

Examples for 2D and 3D simulations can be found in `project/examples/` directory as `.mp4` files.

## Work to be done

- [x] Using a JS based Frontend
  - [x] Formatting User Input/Interface
  - [ ] Adding a Simulation Speed Control/Time step
  - [x] Pause/Resume Button
  - [x] Handling HTTP resp in chunks
  - [ ] User Canvas for Inputs?
  - [x] 3D Rendering Interface
- [x] Creating a 3D based Physics Engine
- [x] Different approximation methods (4th ODE Range Kutta)
- [ ] Timing/Improving export jobs
- [ ] Refine Simulation Config
