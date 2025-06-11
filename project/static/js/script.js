// script.js (Re-introducing 2D/3D Toggle)
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {
  CSS2DRenderer,
  CSS2DObject,
} from 'three/addons/renderers/CSS2DRenderer.js';

const DEFAULT_PLANET_VISUAL_RADII = {
  Sun: 100.0,
  Mercury: 0.38,
  Venus: 0.95,
  Earth: 1.0,
  Mars: 0.53,
  Jupiter: 11.2,
  Saturn: 9.4,
  Uranus: 4.0,
  Neptune: 3.8,
  Moon: 0.27,
  Star: 100.0,
  StarA: 50.0,
  StarB: 40.0,
  StarC: 30.0,
  PlanetX: 0.3,
  Io: 0.36,
  Europa: 0.31,
  Ganymede: 0.52,
  Callisto: 0.48,
  MoonX1: 0.1,
  MoonX2: 0.12,
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
  StarA: '#FFDD33',
  StarB: '#FFAA33',
  StarC: '#FF7733',
  PlanetX: '#88CCFF',
  Io: '#F0E68C',
  Europa: '#B0E0E6',
  Ganymede: '#D2B48C',
  Callisto: '#A0522D',
  MoonX1: '#FFC0CB',
  MoonX2: '#ADD8E6',
  Body: '#FFFFFF',
};

const AU_PER_KM_JS = 1 / 1.495978707e8;
const YEARS_PER_SECOND_JS = 1 / 3.15576e7;
const AU_YEAR_PER_KM_S_JS = AU_PER_KM_JS / YEARS_PER_SECOND_JS;
const AU_YEAR_PER_AU_DAY_JS = 365.25;
const MAX_2D_TRAIL_LENGTH = 200;
const POSITION_TABLE_UPDATE_INTERVAL = 250;

let visualizationMode = '3D';
let scene, camera, renderer, labelRenderer, controls;
let canvas2D, ctx2D;
let planetObjects = [];
let current2DScale = 15,
  current2DOffsetX = 0,
  current2DOffsetY = 0;
let currentSimSessionId = null,
  currentSimConfigData = null;
let isPlayingGlobal = false,
  animationFrameId = null,
  originalSimulationNameForReset = '';
let lastPositionTableUpdateTime = 0;

function convertVelocityToAuYear(vx, vy, vz, unit) {
  if (isNaN(vx) || isNaN(vy) || isNaN(vz)) return {x: 0, y: 0, z: 0};
  if (unit === 'au_year') return {x: vx, y: vy, z: vz};
  if (unit === 'km_s')
    return {
      x: vx * AU_YEAR_PER_KM_S_JS,
      y: vy * AU_YEAR_PER_KM_S_JS,
      z: vz * AU_YEAR_PER_KM_S_JS,
    };
  if (unit === 'au_day')
    return {
      x: vx * AU_YEAR_PER_AU_DAY_JS,
      y: vy * AU_YEAR_PER_AU_DAY_JS,
      z: vz * AU_YEAR_PER_AU_DAY_JS,
    };
  return {x: vx, y: vy, z: vz};
}

const getRadius = (planetState, currentStateInFrame, systemName = '') => {
  if (planetState.radius) {
    return planetState.radius;
  }
  const name = planetState.name;
  let baseVisualSize =
    DEFAULT_PLANET_VISUAL_RADII[name] || DEFAULT_PLANET_VISUAL_RADII['Body'];
  let systemReferenceSize = 1.0;
  if (currentStateInFrame && currentStateInFrame.length > 0)
    systemReferenceSize = Math.max(
      ...currentStateInFrame.map(
        p => DEFAULT_PLANET_VISUAL_RADII[p.name] || 0.1,
      ),
      1.0,
    );
  let scaleFactor = 0.025,
    exponent = 0.65;
  if (systemName.toLowerCase().includes('solar system')) {
    scaleFactor = 0.08;
    exponent = 0.7;
    if (name === 'Sun')
      baseVisualSize = DEFAULT_PLANET_VISUAL_RADII['Sun'] * 0.3;
    else baseVisualSize *= 6;
  } else if (systemName.toLowerCase().includes('jupiter system')) {
    scaleFactor = 0.04;
    exponent = 0.7;
    if (name === 'Jupiter')
      baseVisualSize = DEFAULT_PLANET_VISUAL_RADII['Jupiter'] * 0.3;
    else baseVisualSize *= 3;
  } else if (systemName.toLowerCase().includes('chaotic')) {
    scaleFactor = 0.15;
    exponent = 0.6;
    baseVisualSize *= 2.0;
  }
  let scaledRadius =
    scaleFactor * Math.pow(baseVisualSize / systemReferenceSize, exponent);
  if (
    (name === 'Sun' || name.startsWith('Star')) &&
    !systemName.toLowerCase().includes('solar system')
  )
    scaledRadius = Math.max(scaledRadius, scaleFactor * 0.6);
  if (name === 'Sun' && systemName.toLowerCase().includes('solar system'))
    scaledRadius =
      scaleFactor * Math.pow(DEFAULT_PLANET_VISUAL_RADII['Sun'], 0.4) * 0.15;
  return Math.max(0.002, Math.min(scaledRadius, 3.0));
};

const getColor = name =>
  DEFAULT_PLANET_COLORS[name] || DEFAULT_PLANET_COLORS['Body'];

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
  const canvasParent = document.querySelector('#canvasparent');
  const parentRect = canvasParent.getBoundingClientRect();
  camera = new THREE.PerspectiveCamera(
    70,
    parentRect.width / parentRect.height,
    0.01,
    3000,
  );
  camera.position.set(0, -20, 10);
  camera.up.set(0, 0, 1);
  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(parentRect.width, parentRect.height);
  renderer.domElement.style.position = 'absolute';
  canvasParent.appendChild(renderer.domElement);
  labelRenderer = new CSS2DRenderer();
  labelRenderer.setSize(parentRect.width, parentRect.height);
  labelRenderer.domElement.style.position = 'absolute';
  labelRenderer.domElement.style.top = '0px';
  labelRenderer.domElement.style.left = '0px';
  labelRenderer.domElement.style.pointerEvents = 'none';
  canvasParent.appendChild(labelRenderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.screenSpacePanning = true;
  controls.minDistance = 0.01;
  controls.maxDistance = 1500;
  controls.object.up = new THREE.Vector3(0, 0, 1);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
  directionalLight.position.set(10, 10, 15);
  scene.add(directionalLight);
  const gridHelperXY = new THREE.GridHelper(200, 100, 0x666666, 0x333333);
  gridHelperXY.rotation.x = Math.PI / 2;
  scene.add(gridHelperXY);

  const loader = new THREE.TextureLoader();
  loader.load(
    '/static/jpg/lotsofstars.jpg',
    t => {
      const rt = new THREE.WebGLCubeRenderTarget(t.image.height);
      rt.fromEquirectangularTexture(renderer, t);
      scene.background = rt.texture;
      scene.environment = rt.texture;
    },
    _ => _,
    e => {
      scene.background = new THREE.Color(0x0a0f1a);
    },
  );
  window.addEventListener('resize', () => {
    const r = canvasParent.getBoundingClientRect();
    camera.aspect = r.width / r.height;
    camera.updateProjectionMatrix();
    renderer.setSize(r.width, r.height);
    labelRenderer.setSize(r.width, r.height);
    if (visualizationMode === '2D' && canvas2D) {
      canvas2D.width = r.width;
      canvas2D.height = r.height;
    }
  });
  return [scene, camera, renderer, labelRenderer, controls];
};

const getThreeJSPlanet = (
  planetState,
  currentStateInFrame,
  currentScene,
  systemName,
) => {
  const radius = getRadius(planetState, currentStateInFrame, systemName);
  const geometry = new THREE.SphereGeometry(radius, 32, 16);
  const material = new THREE.MeshStandardMaterial({
    color: planetState.color || getColor(planetState.name),
    metalness: 0.1,
    roughness: 0.7,
    envMap: currentScene.environment,
    emissive:
      planetState.name === 'Sun' || planetState.name.startsWith('Star')
        ? planetState.color || getColor(planetState.name)
        : 0x000000,
    emissiveIntensity:
      planetState.name === 'Sun' || planetState.name.startsWith('Star')
        ? 1.2
        : 0,
  });
  const sphere = new THREE.Mesh(geometry, material);
  let posArray = [0, 0, 0];
  if (Array.isArray(planetState.pos) && planetState.pos.length === 3)
    posArray = planetState.pos;
  else if (
    typeof planetState.pos === 'object' &&
    planetState.pos !== null &&
    'x' in planetState.pos
  )
    posArray = [
      planetState.pos.x || 0,
      planetState.pos.y || 0,
      planetState.pos.z || 0,
    ];
  sphere.position.set(posArray[0], posArray[1], posArray[2]);
  sphere.name = planetState.name;
  const labelDiv = document.createElement('div');
  labelDiv.className = 'planet-label';
  labelDiv.textContent = planetState.name;
  labelDiv.style.backgroundColor = 'rgba(0,0,0,0.6)';
  labelDiv.style.color = 'white';
  labelDiv.style.padding = '2px 5px';
  labelDiv.style.borderRadius = '3px';
  labelDiv.style.fontSize = '10px';
  const label = new CSS2DObject(labelDiv);
  label.position.set(0, radius * 1.2 + 0.02, 0);
  sphere.add(label);
  return sphere;
};

const initAnimation = (initialChronology, sessionData) => {
  currentSimConfigData = sessionData;
  const system_config = sessionData.system_config;

  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  isPlayingGlobal = false;
  if (planetObjects) {
    planetObjects.forEach(pObj => {
      if (pObj.body) {
        scene.remove(pObj.body);
        if (pObj.body.geometry) pObj.body.geometry.dispose();
        if (pObj.body.material) {
          if (Array.isArray(pObj.body.material))
            pObj.body.material.forEach(m => m.dispose());
          else pObj.body.material.dispose();
        }
        pObj.body.children.forEach(c => {
          if (c.isCSS2DObject) c.element.remove();
        });
      }
      if (pObj.trail) {
        let n = pObj.trail.head;
        while (n) {
          if (n.value) {
            scene.remove(n.value);
            if (n.value.geometry) n.value.geometry.dispose();
            if (n.value.material) n.value.material.dispose();
          }
          n = n.next;
        }
      }
    });
  }
  planetObjects = [];
  if (!scene) {
    [scene, camera, renderer, labelRenderer, controls] = initThreeJSObjects();
  } else {
    while (scene.children.length > 0) {
      const o = scene.children[0];
      if (
        o.isLight ||
        o.isGridHelper ||
        o.isAxesHelper ||
        o === scene.background
      ) {
        scene.remove(o);
        continue;
      }
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        if (Array.isArray(o.material)) o.material.forEach(m => m.dispose());
        else o.material.dispose();
      }
      o.children.forEach(c => {
        if (c.isCSS2DObject) c.element.remove();
      });
      scene.remove(o);
    }
    const al = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(al);
    const dl = new THREE.DirectionalLight(0xffffff, 1.0);
    dl.position.set(10, 10, 15);
    scene.add(dl);
    const gridHelperXY = new THREE.GridHelper(200, 100, 0x666666, 0x333333);
    gridHelperXY.rotation.x = Math.PI / 2;
    scene.add(gridHelperXY);
    const l = new THREE.TextureLoader();
    l.load(
      '/static/jpg/lotsofstars.jpg',
      t => {
        const rt = new THREE.WebGLCubeRenderTarget(t.image.height);
        rt.fromEquirectangularTexture(renderer, t);
        scene.background = rt.texture;
        scene.environment = rt.texture;
      },
      _ => _,
      e => {
        scene.background = new THREE.Color(0x0a0f1a);
      },
    );
  }

  if (camera && controls) {
    let d = 20;
    if (system_config.name.toLowerCase().includes('solar system')) d = 50;
    else if (system_config.name.toLowerCase().includes('jupiter system')) d = 5;
    else if (system_config.name.toLowerCase().includes('chaotic')) d = 10;
    camera.position.set(d / 1.5, -d, d / 1.2);
    camera.lookAt(0, 0, 0);
    controls.target.set(0, 0, 0);
    controls.update();
  }

  if (
    initialChronology &&
    initialChronology.length > 0 &&
    initialChronology[0]
  ) {
    initialChronology[0].forEach(planetState => {
      const sphere = getThreeJSPlanet(
        planetState,
        initialChronology[0],
        scene,
        system_config.name,
      );
      scene.add(sphere);
      let posArray = [0, 0, 0];
      if (Array.isArray(planetState.pos) && planetState.pos.length === 3)
        posArray = planetState.pos;
      else if (
        typeof planetState.pos === 'object' &&
        planetState.pos !== null &&
        'x' in planetState.pos
      )
        posArray = [planetState.pos.x, planetState.pos.y, planetState.pos.z];
      planetObjects.push({
        body: sphere,
        name: planetState.name,
        trail_prev_pos: [...posArray],
        trail: new LinkedList(),
        trail2D: new LinkedList(),
      });
    });
  }

  let chronology = [...initialChronology];
  let currentFrameIndex = 0;
  let yearsGoneBy = 0;
  document.getElementById('years').innerHTML = `${yearsGoneBy.toFixed(
    3,
  )} years`;
  let stateLock = false;
  let cameraFollowing = false;
  const playBtn = document.querySelector('#playButton'),
    pauseBtn = document.querySelector('#pauseButton'),
    camFollowBtn = document.querySelector('#cameraFollow');
  if (playBtn)
    playBtn.onclick = () => {
      isPlayingGlobal = true;
    };
  if (pauseBtn)
    pauseBtn.onclick = () => {
      isPlayingGlobal = false;
    };
  if (camFollowBtn)
    camFollowBtn.onclick = () => {
      cameraFollowing = !cameraFollowing;
      if (!cameraFollowing && controls) controls.target.set(0, 0, 0);
      camFollowBtn.textContent = cameraFollowing
        ? 'Unfollow Center'
        : 'Follow Center';
    };

  function animateFrame() {
    animationFrameId = requestAnimationFrame(animateFrame);
    const now = Date.now();

    if (isPlayingGlobal) {
      if (currentFrameIndex < chronology.length) {
        const currentFrameData = chronology[currentFrameIndex];
        if (currentFrameData) {
          let sumX = 0,
            sumY = 0,
            sumZ = 0,
            activeBodies = 0;
          currentFrameData.forEach((state, index) => {
            if (planetObjects[index] && planetObjects[index].body) {
              const planetObj = planetObjects[index];
              let currentPosArray = [0, 0, 0];
              if (Array.isArray(state.pos) && state.pos.length === 3)
                currentPosArray = state.pos;
              else if (typeof state.pos === 'object')
                currentPosArray = [state.pos.x, state.pos.y, state.pos.z];
              planetObj.body.position.set(
                currentPosArray[0],
                currentPosArray[1],
                currentPosArray[2],
              );
              sumX += currentPosArray[0];
              sumY += currentPosArray[1];
              sumZ += currentPosArray[2];
              activeBodies++;

              if (planetObj.trail.size() > 100) {
                const old = planetObj.trail.popFront();
                if (old) {
                  scene.remove(old);
                  old.geometry.dispose();
                  old.material.dispose();
                }
              }
              const tS = planetObj.trail_prev_pos,
                tE = [...currentPosArray];
              if (
                Math.hypot(tE[0] - tS[0], tE[1] - tS[1], tE[2] - tS[2]) > 1e-4
              ) {
                const lP = [new THREE.Vector3(...tS), new THREE.Vector3(...tE)];
                const g = new THREE.BufferGeometry().setFromPoints(lP);
                const m = new THREE.LineBasicMaterial({
                  color: state.color || getColor(state.name),
                  opacity: 0.5,
                  transparent: true,
                });
                const l = new THREE.Line(g, m);
                scene.add(l);
                planetObj.trail.pushBack(l);
                planetObj.trail_prev_pos = tE;
              }
              planetObj.trail2D.pushBack([
                currentPosArray[0],
                currentPosArray[1],
              ]);
              if (planetObj.trail2D.size() > MAX_2D_TRAIL_LENGTH)
                planetObj.trail2D.popFront();
            }
          });
          if (cameraFollowing && activeBodies > 0 && controls)
            controls.target.set(
              sumX / activeBodies,
              sumY / activeBodies,
              sumZ / activeBodies,
            );
          currentFrameIndex++;
          yearsGoneBy += system_config.years_per_frame;
          document.getElementById('years').innerHTML = `${yearsGoneBy.toFixed(
            3,
          )} years`;
        }
      }

      if (
        !stateLock &&
        currentSimSessionId &&
        system_config &&
        (chronology.length - currentFrameIndex) / system_config.fps < 5.0
      ) {
        stateLock = true;
        getNextStatesChunk(currentSimSessionId)
          .then(nC => {
            if (nC && nC.length > 0) chronology.push(...nC);
            stateLock = false;
          })
          .catch(e => {
            console.error('Err fetch states:', e);
            stateLock = false;
          });
      }
      if (
        !stateLock &&
        currentFrameIndex > 800 &&
        chronology.length > currentFrameIndex + 200
      ) {
        stateLock = true;
        chronology = chronology.slice(currentFrameIndex);
        currentFrameIndex = 0;
        stateLock = false;
      }
    }
    if (camera) {
      const camPosEl = document.getElementById('cameraPosition');
      if (camPosEl)
        camPosEl.textContent = `Cam: (X:${camera.position.x.toFixed(
          1,
        )},Y:${camera.position.y.toFixed(1)},Z:${camera.position.z.toFixed(
          1,
        )})`;
    }
    if (now - lastPositionTableUpdateTime > POSITION_TABLE_UPDATE_INTERVAL) {
      updatePositionTable(planetObjects);
      lastPositionTableUpdateTime = now;
    }

    if (visualizationMode === '2D') {
      if (canvas2D) render2D(planetObjects);
    } else {
      if (controls) controls.update();
      if (renderer && scene && camera) renderer.render(scene, camera);
      if (labelRenderer && scene && camera) labelRenderer.render(scene, camera);
    }
  }
  isPlayingGlobal = true;
  animateFrame();
};

const getNextStatesChunk = async sessionId => {
  if (!sessionId) return [];
  try {
    const r = await fetch(`/state/${sessionId}`);
    if (!r.ok) {
      const eD = await r.json().catch(() => ({e: `Server error: ${r.status}`}));
      throw new Error(eD.error || `Server error: ${r.status}`);
    }
    const d = await r.json();
    if (!d || !Array.isArray(d)) return [];
    return d;
  } catch (e) {
    console.error('Err fetch chunk:', e);
    return [];
  }
};

const init2DCanvas = () => {
  const cP = document.querySelector('#canvasparent');
  if (!cP) return;
  let eC = cP.querySelector('canvas#simCanvas2D');
  if (eC) {
    canvas2D = eC;
  } else {
    canvas2D = document.createElement('canvas');
    canvas2D.id = 'simCanvas2D';
    cP.appendChild(canvas2D);
  }
  const pR = cP.getBoundingClientRect();
  canvas2D.width = pR.width;
  canvas2D.height = pR.height;
  canvas2D.style.position = 'absolute';
  canvas2D.style.top = '0px';
  canvas2D.style.left = '0px';
  canvas2D.style.display = visualizationMode === '2D' ? 'block' : 'none';
  ctx2D = canvas2D.getContext('2d');
  reset2DView();
  let iP = false,
    lPX,
    lPY;
  canvas2D.addEventListener('mousedown', e => {
    iP = true;
    lPX = e.clientX;
    lPY = e.clientY;
    canvas2D.style.cursor = 'grabbing';
  });
  canvas2D.addEventListener('mousemove', e => {
    if (iP) {
      current2DOffsetX += e.clientX - lPX;
      current2DOffsetY += e.clientY - lPY;
      lPX = e.clientX;
      lPY = e.clientY;
    }
  });
  const sP = () => {
    if (iP) {
      iP = false;
      canvas2D.style.cursor = 'grab';
    }
  };
  canvas2D.addEventListener('mouseup', sP);
  canvas2D.addEventListener('mouseleave', sP);
  canvas2D.addEventListener('wheel', e => {
    e.preventDefault();
    const zF = 1.1;
    const r = canvas2D.getBoundingClientRect();
    const mX = e.clientX - r.left;
    const mY = e.clientY - r.top;
    const wMXB = (mX - current2DOffsetX) / current2DScale;
    const wMYB = (current2DOffsetY - mY) / current2DScale;
    current2DScale *= e.deltaY < 0 ? zF : 1 / zF;
    current2DScale = Math.max(0.01, Math.min(current2DScale, 5000));
    current2DOffsetX = mX - wMXB * current2DScale;
    current2DOffsetY = mY + wMYB * current2DScale;
  });
  canvas2D.style.cursor = 'grab';
};

const toggleVisualizationMode = () => {
  visualizationMode = visualizationMode === '3D' ? '2D' : '3D';
  const cP = document.querySelector('#canvasparent');
  if (!cP) return;
  const pR = cP.getBoundingClientRect();
  if (visualizationMode === '2D') {
    if (renderer) renderer.domElement.style.display = 'none';
    if (labelRenderer) labelRenderer.domElement.style.display = 'none';
    if (!canvas2D) init2DCanvas();
    else {
      canvas2D.width = pR.width;
      canvas2D.height = pR.height;
      canvas2D.style.display = 'block';
      reset2DView();
    }
  } else {
    if (renderer) {
      renderer.setSize(pR.width, pR.height);
      renderer.domElement.style.display = 'block';
    }
    if (labelRenderer) {
      labelRenderer.setSize(pR.width, pR.height);
      labelRenderer.domElement.style.display = 'block';
    }
    if (canvas2D) canvas2D.style.display = 'none';
  }
  const tB = document.getElementById('toggleViewButton');
  if (tB)
    tB.textContent = `View in ${visualizationMode === '3D' ? '2D' : '3D'}`;
};

const render2D = currentPlanetObjs => {
  if (!ctx2D || !canvas2D) return;
  ctx2D.fillStyle = '#000000';
  ctx2D.fillRect(0, 0, canvas2D.width, canvas2D.height);

  currentPlanetObjs.forEach(obj => {
    if (!obj.body || !obj.trail2D) return;
    const planetColor = obj.body.material.color.getStyle();

    if (obj.trail2D.size() > 1) {
      ctx2D.beginPath();
      ctx2D.strokeStyle = planetColor;
      ctx2D.lineWidth = 1.5;
      ctx2D.globalAlpha = 0.5;
      let node = obj.trail2D.head;
      let firstCanvasPoint = worldToCanvas(node.value[0], node.value[1]);
      ctx2D.moveTo(firstCanvasPoint.x, firstCanvasPoint.y);
      node = node.next;
      while (node) {
        const canvasPoint = worldToCanvas(node.value[0], node.value[1]);
        ctx2D.lineTo(canvasPoint.x, canvasPoint.y);
        node = node.next;
      }
      const currentPlanetCanvasPos = worldToCanvas(
        obj.body.position.x,
        obj.body.position.y,
      );
      ctx2D.lineTo(currentPlanetCanvasPos.x, currentPlanetCanvasPos.y);
      ctx2D.stroke();
      ctx2D.globalAlpha = 1.0;
    }

    const planetPosWorld = obj.body.position;
    const baseSize =
      DEFAULT_PLANET_VISUAL_RADII[obj.name] ||
      DEFAULT_PLANET_VISUAL_RADII['Body'];
    let planetCanvasRadius = Math.max(
      2,
      Math.min(baseSize * 0.6, 12) * Math.sqrt(current2DScale / 15),
    );
    if (obj.name === 'Sun' || obj.name.startsWith('Star'))
      planetCanvasRadius = Math.max(
        5,
        Math.min(baseSize * 0.15, 18) * Math.sqrt(current2DScale / 15),
      );

    const planetCanvasPos = worldToCanvas(planetPosWorld.x, planetPosWorld.y);
    ctx2D.beginPath();
    ctx2D.arc(
      planetCanvasPos.x,
      planetCanvasPos.y,
      planetCanvasRadius,
      0,
      Math.PI * 2,
    );
    ctx2D.fillStyle = planetColor;
    ctx2D.fill();

    const nameScaleThreshold = 2.0;
    if (current2DScale > nameScaleThreshold) {
      ctx2D.fillStyle = 'white';
      const fontSize = Math.max(
        9,
        Math.min(12, Math.floor((current2DScale / nameScaleThreshold) * 6)),
      );
      ctx2D.font = `bold ${fontSize}px Arial`;
      ctx2D.textAlign = 'center';
      ctx2D.fillText(
        obj.name,
        planetCanvasPos.x,
        planetCanvasPos.y - planetCanvasRadius - fontSize * 0.6,
      );
    }
  });
};

function updatePositionTable(currentPlanetObjs) {
  const tableBody = document.getElementById('positionTableBody');
  if (!tableBody) return;
  let tableHTML = '';
  currentPlanetObjs.forEach(obj => {
    if (!obj.body) return;
    const pos = obj.body.position;
    tableHTML += `<tr><td>${obj.name}</td><td>${pos.x.toFixed(
      3,
    )}</td><td>${pos.y.toFixed(3)}</td><td>${pos.z.toFixed(3)}</td></tr>`;
  });
  tableBody.innerHTML = tableHTML;
}

const planetForm = document.getElementById('planetForm');
const planetListEl = document.getElementById('planetList');
function updatePlanetListDisplay(bodiesToShow) {
  if (!planetListEl) return;
  planetListEl.innerHTML = '';
  if (!bodiesToShow || bodiesToShow.length === 0) {
    planetListEl.innerHTML = '<li>No bodies.</li>';
    return;
  }
  bodiesToShow.forEach(bodyData => {
    const pI = document.createElement('div');
    pI.className = 'planet-item';
    const cI = document.createElement('div');
    cI.className = 'planet-color';
    cI.style.backgroundColor =
      bodyData.color || getColor(bodyData.name) || '#FFF';
    const nS = document.createElement('span');
    const m = parseFloat(bodyData.mass);
    nS.textContent = `${bodyData.name} (${m.toExponential(2)} M☉)`;
    pI.appendChild(cI);
    pI.appendChild(nS);
    planetListEl.appendChild(pI);
  });
}

if (planetForm) {
  planetForm.addEventListener('submit', async e => {
    e.preventDefault();
    const rawVelX = parseFloat(document.getElementById('velX').value) || 0;
    const rawVelY = parseFloat(document.getElementById('velY').value) || 0;
    const rawVelZ = parseFloat(document.getElementById('velZ').value) || 0;
    const selectedUnit = document.getElementById('velocityUnit').value;
    const convertedVelocity = convertVelocityToAuYear(
      rawVelX,
      rawVelY,
      rawVelZ,
      selectedUnit,
    );
    const newPlanet = {
      name: document.getElementById('planetName').value.trim(),
      position: {
        x: parseFloat(document.getElementById('posX').value),
        y: parseFloat(document.getElementById('posY').value),
        z: parseFloat(document.getElementById('posZ').value),
      },
      velocity: convertedVelocity,
      mass: parseFloat(document.getElementById('mass').value),
      color: document.getElementById('color').value,
    };
    if (
      !newPlanet.name ||
      Object.values(newPlanet.position).some(isNaN) ||
      isNaN(newPlanet.mass)
    ) {
      alert('Fill name, position (AU), and mass (M☉).');
      return;
    }
    if (!currentSimSessionId) {
      alert('No active simulation.');
      return;
    }
    try {
      const r = await fetch('/add_planet', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(newPlanet),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Failed.');
      alert(d.message || 'Planet sent.');
      planetForm.reset();
      document.getElementById('velocityUnit').value = 'au_year';
    } catch (err) {
      console.error('Add planet err:', err);
      alert(`Failed: ${err.message}`);
    }
  });
}

async function startSimulation(url, isScenario = false, scenarioName = '') {
  const simName = scenarioName;
  originalSimulationNameForReset = isScenario ? '' : simName;
  const simNameEl = document.getElementById('simName');
  if (simNameEl) simNameEl.textContent = `Loading ${simName}...`;
  isPlayingGlobal = false;
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  animationFrameId = null;
  const tableBody = document.getElementById('positionTableBody');
  if (tableBody) tableBody.innerHTML = '';

  const fetchOptions = isScenario
    ? {}
    : {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({simulation_name: simName}),
      };

  try {
    const response = await fetch(url, fetchOptions);
    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({error: response.statusText}));
      throw new Error(errorData.error || `Server error ${response.status}`);
    }
    const sessionData = await response.json();
    currentSimSessionId = sessionData.session_id;
    currentSimConfigData = sessionData;
    if (simNameEl && sessionData.system_config) {
      simNameEl.textContent = sessionData.system_config.name;
      if (isScenario) {
        originalSimulationNameForReset = sessionData.system_config.name;
      } else {
        originalSimulationNameForReset = simName;
      }
    }
    const initialStates = await getNextStatesChunk(currentSimSessionId);
    initAnimation(initialStates, sessionData);
    if (sessionData.system_config)
      updatePlanetListDisplay(
        sessionData.system_config.initial_bodies_data ||
          sessionData.system_config.bodies,
      );
  } catch (e) {
    console.error(`Init error:`, e);
    if (simNameEl)
      simNameEl.textContent = `Error: ${e.message.substring(0, 100)}`;
    currentSimSessionId = null;
    currentSimConfigData = null;
  }
}

async function populateSavedScenarios() {
  const listEl = document.getElementById('savedScenariosList');
  try {
    const response = await fetch('/list_scenarios');
    const scenarios = await response.json();
    if (scenarios.length === 0) {
      listEl.innerHTML = '<p>No saved scenarios found.</p>';
      return;
    }
    listEl.innerHTML = '';
    scenarios.forEach(scenario => {
      const btn = document.createElement('button');
      btn.className = 'button secondary scenario-button';
      btn.textContent = `${scenario.name} (${scenario.planet_count} bodies)`;
      btn.onclick = () => {
        startSimulation(
          `/load_scenario/${scenario.filename}`,
          true,
          scenario.name,
        );
      };
      listEl.appendChild(btn);
    });
  } catch (error) {
    console.error('Failed to load scenarios:', error);
    listEl.innerHTML = '<p>Error loading scenarios.</p>';
  }
}

window.onload = async () => {
  init2DCanvas();
  if (!scene) {
    initThreeJSObjects();
    function dA() {
      if (!currentSimSessionId) {
        requestAnimationFrame(dA);
        if (controls) controls.update();
        if (renderer && scene && camera) renderer.render(scene, camera);
        if (labelRenderer && scene && camera)
          labelRenderer.render(scene, camera);
      }
    }
    dA();
  }
  const solBtn = document.querySelector('#solarsysButton'),
    jupBtn = document.querySelector('#jupiterchaoticButton'),
    chaBtn = document.querySelector('#trulychaoticButton'),
    toggleBtn = document.querySelector('#toggleViewButton'),
    resBtn = document.querySelector('#resetButton');

  if (solBtn)
    solBtn.onclick = () => startSimulation('/init_session', false, 'solarsys');
  if (jupBtn)
    jupBtn.onclick = () =>
      startSimulation('/init_session', false, 'jupiterchaotic');
  if (chaBtn)
    chaBtn.onclick = () =>
      startSimulation('/init_session', false, 'trulychaotic');
  if (toggleBtn) toggleBtn.onclick = toggleVisualizationMode;

  if (resBtn) {
    resBtn.onclick = () => {
      if (
        originalSimulationNameForReset &&
        originalSimulationNameForReset.startsWith('Loaded:')
      ) {
        const scenarioName = originalSimulationNameForReset
          .replace('Loaded: ', '')
          .trim();
        alert(
          `To reload '${scenarioName}', please click its button in the 'Saved Scenarios' list.`,
        );
      } else if (originalSimulationNameForReset) {
        startSimulation('/init_session', false, originalSimulationNameForReset);
      } else {
        alert('No simulation active to reset. Please select a simulation.');
      }
    };
  }

  populateSavedScenarios();
};
