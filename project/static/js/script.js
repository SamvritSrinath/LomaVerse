DEFAULT_PLANET_VISUAL_RADII = { 
    "Sun": 109.0, "Mercury": 0.383, "Venus": 0.949, "Earth": 1.0, "Mars": 0.532,
    "Jupiter": 11.21, "Saturn": 9.45, "Uranus": 4.01, "Neptune": 3.88,
    "Moon": 0.27, "Star": 200.0,
    "MoonA": 0.5, "MoonB": 0.4, "MoonC": 0.6, "MoonD": 0.3,
    "Body": 0.5
}

DEFAULT_PLANET_COLORS = {
    "Sun": '#FFD700', "Mercury": '#B0AFAF', "Venus": '#D4A373', "Earth": '#6B93D6',
    "Mars": '#C1440E', "Jupiter": '#C4A484', "Saturn": '#B8860B', "Uranus": '#A4D8F0',
    "Neptune": '#5B5DDF', "Moon": 'lightgrey', "Star": 'white',
    "MoonA": '#E0E0E0', "MoonB": '#A0A0A0', "MoonC": '#C0C0C0', "MoonD": '#808080',
    "Body": 'white'
}

const getRadius = (name, currState) => {
  if (Object.hasOwn(DEFAULT_PLANET_VISUAL_RADII, name)) {
    let largestRad = -1;
    for (const state in currState) {
      if (Object.hasOwn(DEFAULT_PLANET_VISUAL_RADII, state.name)) {
        if (DEFAULT_PLANET_VISUAL_RADII[state.name] > largestRad)
          largestRad = Math.pow(DEFAULT_PLANET_VISUAL_RADII[state.name], 1/4);
      }
    }
    const r = Math.pow(DEFAULT_PLANET_VISUAL_RADII[name], 1/4)
    return 0.01 * (r / largestRad);
  }
  return 1;
}

const getColor = (name) => {
  if (Object.hasOwn(DEFAULT_PLANET_COLORS, name)) {
    return DEFAULT_PLANET_COLORS[name];
  }
  return '#ffffff';
}

const initAnimation = (chronology, sessionCfg) => {
  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.01,
    1000
  );
  camera.position.set(0, 0, 0.3);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth * 0.7, window.innerHeight * 0.7);
  document.body.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);

  const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
  directionalLight.position.set(5, 10, 7.5);
  scene.add(directionalLight);

  const light = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(light);

  const planetObjects = [];
  chronology[0].forEach((state) => {
    const geometry = new THREE.SphereGeometry(getRadius(state.name, chronology[0]), 32, 32);
    const material = new THREE.MeshStandardMaterial({ color: getColor(state.name), metalness: 0.1, roughness: 0.2 });
    const sphere = new THREE.Mesh(geometry, material);
    sphere.position.set(state.pos[0], state.pos[1], 0);
    scene.add(sphere);
    planetObjects.push({
      "body": sphere, 
      "trail_prev_pos": [state.pos[0], state.pos[1]],
      "trail": new LinkedList(),
    });
  });

  let currentFrame = 0;
  let yearsGoneBy = 0;
  // stateLock is to ensure that only one request for more chunks is out at a time
  let stateLock = false;
  // this is for the pause/play functionality
  let isUpdatingPositions = true;

  document.querySelector("#playButton").onclick = () => {
    isUpdatingPositions = true;
  }
  document.querySelector("#pauseButton").onclick = () => {
    isUpdatingPositions = false;
  }

  function animate() {
    if (isUpdatingPositions) {
      // First, check there still states left to render
      if (currentFrame < chronology.length) {
        chronology[currentFrame].forEach((state, index) => {
          const sphere = planetObjects[index].body;
          sphere.position.set(state.pos[0], state.pos[1], 0);
          // Remove oldest trail
          if (planetObjects[index].trail.size() > 100) {
            const oldTrailLine = planetObjects[index].trail.popFront();
            scene.remove(oldTrailLine);
          }
          // Add new trail
          const oldTrailPos = planetObjects[index].trail_prev_pos;
          const newLinePoints = [
            new THREE.Vector3(oldTrailPos[0], oldTrailPos[1], 0),
            new THREE.Vector3(state.pos[0], state.pos[1], 0),
          ]
          const geometry = new THREE.BufferGeometry().setFromPoints(newLinePoints);
          const material = new THREE.LineBasicMaterial({ color: 0xffffff });
          const line = new THREE.Line(geometry, material);
          scene.add(line);
          planetObjects[index].trail.pushBack(line);
          planetObjects[index].trail_prev_pos = [state.pos[0], state.pos[1]];
        });
        currentFrame++;
        yearsGoneBy += sessionCfg.system_config.years_per_frame;
        document.querySelector("#years").innerHTML = yearsGoneBy.toFixed(3);
      }
      // Now, if there is less than 1 second of footage left, then will get next chunks
      if (!stateLock && (chronology.length - currentFrame) / sessionCfg.system_config.fps < 1) {
        stateLock = true;
        getNextStatesChunk(sessionCfg.session_id).then(nextChunk => {
          chronology.push(...nextChunk)
          stateLock = false;
        })
      }
      // Here, remove old states
      if (!stateLock && currentFrame > 500) {
        stateLock = true;
        console.log("Garbage Collection");
        chronology = chronology.slice(currentFrame);
        currentFrame = 0;
        stateLock = false;
      }
    }
    renderer.render(scene, camera);
    setTimeout(() => {
      animate();
    }, 1000 / sessionCfg.system_config.fps);
  }
  animate();
}

const getSessionCfg = async (simulationName) => {
  let resp = await fetch("/state?simulationName=" + simulationName);
  let data = await resp.json();
  return data;
}

const getNextStatesChunk = async (session_id) => {
  let resp = await fetch("/state/" + session_id);
  let data = await resp.json();
  return data;
}

const init = async (simulationName) => {
  let sessionCfg = await getSessionCfg(simulationName);
  document.querySelector("#simName").innerHTML = sessionCfg.system_config.name;
  const sessionId = sessionCfg.session_id;
  let initialStates = await getNextStatesChunk(sessionId);
  initAnimation(initialStates, sessionCfg);
}

window.onload = async () => {
  document.querySelector("#solarsysButton").onclick = async () => {
    document.querySelector('#menu').style.display = 'none';
    document.querySelector("#controls").style.display = 'block';
    await init("solarsys");
  }
  document.querySelector("#jupiterchaoticButton").onclick = async () => {
    document.querySelector('#menu').style.display = 'none';
    document.querySelector("#controls").style.display = 'block';
    await init("jupiterchaotic");
  }
}
