import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {
  CSS2DRenderer,
  CSS2DObject,
} from 'three/addons/renderers/CSS2DRenderer.js';

const DEFAULT_PLANET_VISUAL_RADII = {
  Sun: 109.0,
  Mercury: 0.383,
  Venus: 0.949,
  Earth: 1.0,
  Mars: 0.532,
  Jupiter: 11.21,
  Saturn: 9.45,
  Uranus: 4.01,
  Neptune: 3.88,
  Moon: 0.27,
  Star: 200.0,
  MoonA: 0.5,
  MoonB: 0.4,
  MoonC: 0.6,
  MoonD: 0.3,
  Body: 0.5,
};

const DEFAULT_PLANET_COLORS = {
  Sun: '#FFD700',
  Mercury: '#B0AFAF',
  Venus: '#D4A373',
  Earth: '#6B93D6',
  Mars: '#C1440E',
  Jupiter: '#C4A484',
  Saturn: '#B8860B',
  Uranus: '#A4D8F0',
  Neptune: '#5B5DDF',
  Moon: 'lightgrey',
  Star: 'white',
  MoonA: '#E0E0E0',
  MoonB: '#A0A0A0',
  MoonC: '#C0C0C0',
  MoonD: '#808080',
  Body: 'white',
};

const getRadius = (name, currState) => {
  if (Object.hasOwn(DEFAULT_PLANET_VISUAL_RADII, name)) {
    let largestRad = -1;
    currState.forEach(state => {
      if (Object.hasOwn(DEFAULT_PLANET_VISUAL_RADII, state.name)) {
        if (DEFAULT_PLANET_VISUAL_RADII[state.name] > largestRad) {
          largestRad = DEFAULT_PLANET_VISUAL_RADII[state.name];
        }
      }
    });
    const r = DEFAULT_PLANET_VISUAL_RADII[name];
    if (largestRad <= 0) largestRad = r > 0 ? r : 1; // Avoid division by zero or negative
    return (0.01 * Math.pow(r, 1 / 2)) / Math.pow(largestRad, 1 / 2);
  }
  return 0.005;
};

const getColor = name => {
  if (Object.hasOwn(DEFAULT_PLANET_COLORS, name)) {
    return DEFAULT_PLANET_COLORS[name];
  }
  return '#ffffff';
};

let visualizationMode = '3D';
let scene, camera, renderer, labelRenderer, controls;
let canvas2D, ctx2D;
let planetObjects = []; // Stores {body: THREE.Mesh, name: string, trail_prev_pos: array, trail: LinkedList}

let current2DScale = 15;
let current2DOffsetX = 0;
let current2DOffsetY = 0;

function reset2DView() {
  if (!canvas2D) return;
  current2DScale = 15;
  current2DOffsetX = canvas2D.width / 2;
  current2DOffsetY = canvas2D.height / 2;
}

const worldToCanvas = (worldX, worldY) => {
  if (!canvas2D) return {x: 0, y: 0};
  return {
    x: current2DOffsetX + worldX * current2DScale,
    y: current2DOffsetY - worldY * current2DScale,
  };
};

const initThreeJSObjects = () => {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.01,
    1000,
  );
  camera.position.set(0, 0, 0.3);
  camera.up.set(0, 0, 1);

  const canvasParent = document.querySelector('#canvasparent');
  const parentRect = canvasParent.getBoundingClientRect();

  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(parentRect.width, parentRect.height);
  renderer.domElement.style.position = 'absolute';
  canvasParent.appendChild(renderer.domElement);

  labelRenderer = new CSS2DRenderer();
  labelRenderer.setSize(parentRect.width, parentRect.height);
  labelRenderer.domElement.style.position = 'absolute';
  labelRenderer.domElement.style.top = '0px';
  labelRenderer.domElement.style.left = '0px';
  canvasParent.appendChild(labelRenderer.domElement);

  controls = new OrbitControls(camera, labelRenderer.domElement);
  controls.target.set(0, 0, 0);
  controls.update();

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  directionalLight.position.set(5, 5, 5);
  scene.add(directionalLight);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
  scene.add(ambientLight);

  const axesHelper = new THREE.AxesHelper(1);
  scene.add(axesHelper);

  const loader = new THREE.TextureLoader();
  loader.load('/static/jpg/lotsofstars.jpg', milkyWayTexture => {
    const rt = new THREE.WebGLCubeRenderTarget(milkyWayTexture.image.height);
    rt.fromEquirectangularTexture(renderer, milkyWayTexture);
    scene.background = rt.texture;
    scene.environment = rt.texture;
  });
  return [scene, camera, renderer, labelRenderer, controls];
};

const getThreeJSPlanet = (planetState, currentStateInFrame, currentScene) => {
  const radius = getRadius(planetState.name, currentStateInFrame);
  const geometry = new THREE.SphereGeometry(radius, 32, 32);
  const material = new THREE.MeshStandardMaterial({
    color: getColor(planetState.name),
    metalness: 0.1,
    roughness: 0.7,
    envMap: currentScene.environment,
  });
  const sphere = new THREE.Mesh(geometry, material);
  sphere.position.set(
    planetState.pos[0],
    planetState.pos[1],
    planetState.pos[2],
  );
  sphere.name = planetState.name; // Store name on the mesh

  const labelDiv = document.createElement('div');
  labelDiv.textContent = planetState.name;
  labelDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
  labelDiv.style.color = 'white';
  labelDiv.style.padding = '2px 5px';
  labelDiv.style.borderRadius = '3px';
  const label = new CSS2DObject(labelDiv);
  label.position.set(radius * 1.1, radius * 1.1, 0);
  sphere.add(label);
  return sphere;
};

const initAnimation = (initialChronology, sessionCfg) => {
  if (!scene || !camera || !renderer || !labelRenderer || !controls) {
    [scene, camera, renderer, labelRenderer, controls] = initThreeJSObjects();
  } else {
    // Clear previous objects from scene if re-initializing
    planetObjects.forEach(pObj => {
      scene.remove(pObj.body);
      pObj.trail.forEach(trailLine => scene.remove(trailLine)); // Assuming trail stores THREE.Line
    });
  }
  planetObjects = []; // Reset planetObjects

  if (initialChronology.length > 0 && initialChronology[0]) {
    initialChronology[0].forEach(planetState => {
      const sphere = getThreeJSPlanet(planetState, initialChronology[0], scene);
      scene.add(sphere);
      planetObjects.push({
        body: sphere,
        name: planetState.name,
        trail_prev_pos: [
          planetState.pos[0],
          planetState.pos[1],
          planetState.pos[2],
        ],
        trail: new LinkedList(),
      });
    });
  }

  let chronology = [...initialChronology];
  let currentFrameIndex = 0;
  let yearsGoneBy = 0;
  let stateLock = false;
  let isPlaying = true;
  let cameraFollowing = false;

  const playButton = document.querySelector('#playButton');
  const pauseButton = document.querySelector('#pauseButton');
  const cameraFollowButton = document.querySelector('#cameraFollow');
  // const resetButton = document.querySelector('#resetButton'); // If reset logic is needed

  if (playButton)
    playButton.onclick = () => {
      isPlaying = true;
    };
  if (pauseButton)
    pauseButton.onclick = () => {
      isPlaying = false;
    };
  if (cameraFollowButton)
    cameraFollowButton.onclick = () => {
      cameraFollowing = !cameraFollowing;
      if (!cameraFollowing && controls) {
        controls.target.set(0, 0, 0);
      }
    };
  // if (resetButton) resetButton.onclick = () => { /* Call init with current sim name */ };

  function animateFrame() {
    if (isPlaying) {
      if (currentFrameIndex < chronology.length) {
        const currentFrameData = chronology[currentFrameIndex];
        if (currentFrameData) {
          currentFrameData.forEach((state, index) => {
            if (planetObjects[index]) {
              const planetObj = planetObjects[index];
              planetObj.body.position.set(
                state.pos[0],
                state.pos[1],
                state.pos[2],
              );

              if (planetObj.trail.size() > 100) {
                const oldTrailLine = planetObj.trail.popFront();
                scene.remove(oldTrailLine);
                oldTrailLine.geometry.dispose();
                oldTrailLine.material.dispose();
              }

              const trailStartPoint = planetObj.trail_prev_pos;
              const trailEndPoint = [state.pos[0], state.pos[1], state.pos[2]];
              const linePoints = [
                new THREE.Vector3(...trailStartPoint),
                new THREE.Vector3(...trailEndPoint),
              ];
              const geometry = new THREE.BufferGeometry().setFromPoints(
                linePoints,
              );
              const material = new THREE.LineBasicMaterial({
                color: getColor(state.name),
                opacity: 0.6,
                transparent: true,
              });
              const line = new THREE.Line(geometry, material);
              scene.add(line);
              planetObj.trail.pushBack(line);
              planetObj.trail_prev_pos = trailEndPoint;
            }
          });
          currentFrameIndex++;
          yearsGoneBy += sessionCfg.system_config.years_per_frame;
          const yearsElement = document.querySelector('#years');
          if (yearsElement) yearsElement.innerHTML = yearsGoneBy.toFixed(3);

          if (cameraFollowing && currentFrameData.length > 0 && controls) {
            let sumx = 0,
              sumy = 0,
              sumz = 0;
            const numBodies = currentFrameData.length;
            currentFrameData.forEach(state => {
              sumx += state.pos[0];
              sumy += state.pos[1];
              sumz += state.pos[2];
            });
            controls.target.set(
              sumx / numBodies,
              sumy / numBodies,
              sumz / numBodies,
            );
          }
        }
      }

      if (
        !stateLock &&
        (chronology.length - currentFrameIndex) / sessionCfg.system_config.fps <
          1
      ) {
        stateLock = true;
        getNextStatesChunk(sessionCfg.session_id)
          .then(nextChunk => {
            if (nextChunk && nextChunk.length > 0) {
              chronology.push(...nextChunk);
            }
            stateLock = false;
          })
          .catch(error => {
            console.error('Error fetching next states chunk:', error);
            stateLock = false;
          });
      }

      if (
        !stateLock &&
        currentFrameIndex > 500 &&
        chronology.length > currentFrameIndex + 100
      ) {
        stateLock = true;
        chronology = chronology.slice(currentFrameIndex);
        currentFrameIndex = 0;
        stateLock = false;
      }
    }

    if (visualizationMode === '2D') {
      render2D(planetObjects);
    } else if (renderer && scene && camera && labelRenderer && controls) {
      controls.update();
      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
    }
    requestAnimationFrame(animateFrame);
  }
  requestAnimationFrame(animateFrame);
};

const getNextStatesChunk = async sessionId => {
  try {
    const response = await fetch(`/state/${sessionId}`);
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `Server error: ${response.status}`);
    }
    const data = await response.json();
    if (!data || !Array.isArray(data)) {
      throw new Error('Invalid response format from server');
    }
    return data;
  } catch (error) {
    console.error('Error fetching next states:', error);
    return [];
  }
};

const init2DCanvas = () => {
  const canvasParent = document.querySelector('#canvasparent');
  if (!canvasParent) return;

  const existingCanvas = canvasParent.querySelector('canvas#simCanvas2D');
  if (existingCanvas) {
    canvas2D = existingCanvas;
  } else {
    canvas2D = document.createElement('canvas');
    canvas2D.id = 'simCanvas2D';
    canvasParent.appendChild(canvas2D);
  }

  const parentRect = canvasParent.getBoundingClientRect();
  canvas2D.width = parentRect.width;
  canvas2D.height = parentRect.height;
  canvas2D.style.position = 'absolute';
  canvas2D.style.top = '0px';
  canvas2D.style.left = '0px';
  canvas2D.style.display = 'none';
  ctx2D = canvas2D.getContext('2d');
  reset2DView();

  let isPanning = false;
  let lastPanX, lastPanY;

  canvas2D.addEventListener('mousedown', e => {
    isPanning = true;
    lastPanX = e.clientX;
    lastPanY = e.clientY;
    canvas2D.style.cursor = 'grabbing';
  });

  canvas2D.addEventListener('mousemove', e => {
    if (isPanning) {
      const dx = e.clientX - lastPanX;
      const dy = e.clientY - lastPanY;
      current2DOffsetX += dx;
      current2DOffsetY += dy;
      lastPanX = e.clientX;
      lastPanY = e.clientY;
    }
  });

  const stopPanning = () => {
    if (isPanning) {
      isPanning = false;
      canvas2D.style.cursor = 'grab';
    }
  };
  canvas2D.addEventListener('mouseup', stopPanning);
  canvas2D.addEventListener('mouseleave', stopPanning);

  canvas2D.addEventListener('wheel', e => {
    e.preventDefault();
    const zoomFactor = 1.1;
    const rect = canvas2D.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const worldMouseXBefore = (mouseX - current2DOffsetX) / current2DScale;
    const worldMouseYBefore = (current2DOffsetY - mouseY) / current2DScale;

    if (e.deltaY < 0) {
      current2DScale *= zoomFactor;
    } else {
      current2DScale /= zoomFactor;
    }
    current2DScale = Math.max(0.1, Math.min(current2DScale, 1000));

    current2DOffsetX = mouseX - worldMouseXBefore * current2DScale;
    current2DOffsetY = mouseY + worldMouseYBefore * current2DScale;
  });
  canvas2D.style.cursor = 'grab';
};

const toggleVisualizationMode = () => {
  visualizationMode = visualizationMode === '3D' ? '2D' : '3D';
  const canvasParent = document.querySelector('#canvasparent');
  if (!canvasParent) return;
  const parentRect = canvasParent.getBoundingClientRect();

  if (visualizationMode === '2D') {
    if (renderer) renderer.domElement.style.display = 'none';
    if (labelRenderer) labelRenderer.domElement.style.display = 'none';
    if (!canvas2D) init2DCanvas(); // Ensure canvas exists

    if (canvas2D) {
      canvas2D.width = parentRect.width;
      canvas2D.height = parentRect.height;
      canvas2D.style.display = 'block';
      reset2DView();
    }
  } else {
    if (renderer) {
      renderer.setSize(parentRect.width, parentRect.height); // Ensure 3D renderer resizes too
      renderer.domElement.style.display = 'block';
    }
    if (labelRenderer) {
      labelRenderer.setSize(parentRect.width, parentRect.height);
      labelRenderer.domElement.style.display = 'block';
    }
    if (canvas2D) canvas2D.style.display = 'none';
  }
};

const render2D = currentPlanetObjects => {
  if (!ctx2D || !canvas2D) return;

  ctx2D.clearRect(0, 0, canvas2D.width, canvas2D.height);
  ctx2D.fillStyle = '#000000';
  ctx2D.fillRect(0, 0, canvas2D.width, canvas2D.height);

  currentPlanetObjects.forEach(obj => {
    const planetColor = getColor(obj.name);

    if (obj.trail.size() > 0) {
      ctx2D.beginPath();
      ctx2D.strokeStyle = planetColor;
      ctx2D.lineWidth = 1;
      let currentSegmentNode = obj.trail.head;
      while (currentSegmentNode) {
        const trailLineMesh = currentSegmentNode.value;
        const points = trailLineMesh.geometry.attributes.position.array;
        const startCanvas = worldToCanvas(points[0], points[1]);
        const endCanvas = worldToCanvas(points[3], points[4]);
        ctx2D.moveTo(startCanvas.x, startCanvas.y);
        ctx2D.lineTo(endCanvas.x, endCanvas.y);
        currentSegmentNode = currentSegmentNode.next;
      }
      ctx2D.stroke();
    }

    const planetPosWorld = obj.body.position;
    let planetCanvasRadius = 5;
    if (obj.name === 'Sun' || obj.name === 'Star') planetCanvasRadius = 10;
    else if (obj.name === 'Jupiter' || obj.name === 'Saturn')
      planetCanvasRadius = 7;

    const planetCanvasPos = worldToCanvas(planetPosWorld.x, planetPosWorld.y);
    ctx2D.beginPath();
    ctx2D.arc(
      planetCanvasPos.x,
      planetCanvasPos.y,
      Math.max(1, planetCanvasRadius),
      0,
      Math.PI * 2,
    );
    ctx2D.fillStyle = planetColor;
    ctx2D.fill();

    ctx2D.fillStyle = 'white';
    ctx2D.font = '10px Arial';
    ctx2D.textAlign = 'left';
    ctx2D.fillText(
      obj.name,
      planetCanvasPos.x + planetCanvasRadius + 5,
      planetCanvasPos.y + 3,
    );
  });
};

const planetForm = document.getElementById('planetForm');
const planetListEl = document.getElementById('planetList'); // Renamed to avoid conflict

function updatePlanetListDisplay(bodiesToShow) {
  if (!planetListEl) return;
  planetListEl.innerHTML = '';
  if (!bodiesToShow || bodiesToShow.length === 0) return;

  bodiesToShow.forEach((bodyData, index) => {
    const planetItem = document.createElement('div');
    planetItem.className = 'planet-item';

    const colorIndicator = document.createElement('div');
    colorIndicator.className = 'planet-color'; // Match CSS
    colorIndicator.style.backgroundColor =
      bodyData.color || getColor(bodyData.name) || '#FFFFFF';

    const nameSpan = document.createElement('span');
    nameSpan.textContent = bodyData.name || `Planet ${index + 1}`;

    planetItem.appendChild(colorIndicator);
    planetItem.appendChild(nameSpan);
    planetListEl.appendChild(planetItem);
  });
}

if (planetForm) {
  planetForm.addEventListener('submit', async e => {
    e.preventDefault();
    const newPlanet = {
      name: document.getElementById('planetName').value,
      position: {
        x: parseFloat(document.getElementById('posX').value),
        y: parseFloat(document.getElementById('posY').value),
        z: parseFloat(document.getElementById('posZ').value),
      },
      velocity: {
        x: parseFloat(document.getElementById('velX').value),
        y: parseFloat(document.getElementById('velY').value),
        z: parseFloat(document.getElementById('velZ').value),
      },
      mass: parseFloat(document.getElementById('mass').value),
      color: document.getElementById('color').value,
    };

    try {
      const response = await fetch('/add_planet', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(newPlanet),
      });
      if (!response.ok) throw new Error('Failed to add planet');
      planetForm.reset();
      // To see the new planet, the simulation usually needs to be re-initialized.
      // For now, just alerting. A full re-init might be too disruptive without user confirmation.
      alert(
        'Planet data sent. Re-select simulation to see changes if supported by backend.',
      );
      // Or, if the backend supports dynamic addition and provides updated config:
      // const currentSimName = document.getElementById('simName').textContent;
      // if (currentSimName && currentSimName !== 'Select a simulation' && currentSimName.indexOf('Error') === -1) {
      //   init(currentSimName);
      // }
    } catch (error) {
      console.error('Error adding planet:', error);
      alert('Failed to add planet. Please try again.');
    }
  });
}

async function init(simulationName) {
  const simNameElement = document.getElementById('simName');
  if (simNameElement) simNameElement.textContent = 'Loading...';

  try {
    const response = await fetch('/init_session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({simulation_name: simulationName}),
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(
        'Failed to initialize session:',
        response.status,
        errorBody,
      );
      throw new Error(`Failed to initialize session: ${response.status}`);
    }
    const sessionCfg = await response.json();

    if (simNameElement) {
      if (sessionCfg.system_config && sessionCfg.system_config.name) {
        simNameElement.textContent = sessionCfg.system_config.name;
      } else {
        simNameElement.textContent = simulationName;
      }
    }

    const initialStates = await getNextStatesChunk(sessionCfg.session_id);
    if (!initialStates || initialStates.length === 0) {
      throw new Error('Failed to get initial simulation states');
    }

    initAnimation(initialStates, sessionCfg);
    const bodiesForList =
      sessionCfg.system_config.initial_bodies_data ||
      sessionCfg.system_config.bodies;
    updatePlanetListDisplay(bodiesForList);
  } catch (error) {
    console.error('Error initializing simulation:', error);
    if (simNameElement) simNameElement.textContent = 'Error: ' + error.message;
  }
}

window.onload = async () => {
  init2DCanvas(); // Initialize 2D canvas elements and listeners
  const solarsysButton = document.querySelector('#solarsysButton');
  const jupiterchaoticButton = document.querySelector('#jupiterchaoticButton');
  const toggleViewButton = document.querySelector('#toggleViewButton');

  if (solarsysButton) solarsysButton.onclick = () => init('solarsys');
  if (jupiterchaoticButton)
    jupiterchaoticButton.onclick = () => init('jupiterchaotic');
  if (toggleViewButton) toggleViewButton.onclick = toggleVisualizationMode;

  // Handle window resize to keep canvas sizes correct
  window.addEventListener('resize', () => {
    const canvasParent = document.querySelector('#canvasparent');
    if (!canvasParent) return;
    const parentRect = canvasParent.getBoundingClientRect();

    if (camera && renderer) {
      // 3D
      camera.aspect = parentRect.width / parentRect.height;
      camera.updateProjectionMatrix();
      renderer.setSize(parentRect.width, parentRect.height);
      if (labelRenderer)
        labelRenderer.setSize(parentRect.width, parentRect.height);
    }
    if (canvas2D) {
      // 2D
      canvas2D.width = parentRect.width;
      canvas2D.height = parentRect.height;
      // Optionally call reset2DView() or adjust offsets/scale if needed after resize
      // For now, just resizing, existing offsets/scale will apply to new size
    }
  });
};
