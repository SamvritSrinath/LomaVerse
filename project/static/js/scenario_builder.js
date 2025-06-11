import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {
  CSS2DRenderer,
  CSS2DObject,
} from 'three/addons/renderers/CSS2DRenderer.js';

// Velocity Unit Conversion Constants (scoped to this module if not globally needed)
const AU_PER_KM_JS_SCENARIO = 1 / 1.495978707e8;
const YEARS_PER_SECOND_JS_SCENARIO = 1 / 3.15576e7;
const AU_YEAR_PER_KM_S_JS_SCENARIO =
  AU_PER_KM_JS_SCENARIO / YEARS_PER_SECOND_JS_SCENARIO;
const AU_YEAR_PER_AU_DAY_JS_SCENARIO = 365.25;

let scene, camera, renderer, labelRenderer, controls;
let planets = []; // Local array for planets in the scenario being built

// Helper function to convert input velocity to AU/year for scenario builder
function convertVelocityToAuYearScenario(vx, vy, vz, unit) {
  if (isNaN(vx) || isNaN(vy) || isNaN(vz)) {
    return {x: 0, y: 0, z: 0};
  }
  if (unit === 'au_year') {
    return {x: vx, y: vy, z: vz};
  } else if (unit === 'km_s') {
    return {
      x: vx * AU_YEAR_PER_KM_S_JS_SCENARIO,
      y: vy * AU_YEAR_PER_KM_S_JS_SCENARIO,
      z: vz * AU_YEAR_PER_KM_S_JS_SCENARIO,
    };
  } else if (unit === 'au_day') {
    return {
      x: vx * AU_YEAR_PER_AU_DAY_JS_SCENARIO,
      y: vy * AU_YEAR_PER_AU_DAY_JS_SCENARIO,
      z: vz * AU_YEAR_PER_AU_DAY_JS_SCENARIO,
    };
  }
  console.warn('Unknown velocity unit for scenario conversion:', unit);
  return {x: vx, y: vy, z: vz};
}

const initThreeJS = () => {
  scene = new THREE.Scene();
  const canvasParent = document.getElementById('canvasparent');
  const parentRect = canvasParent.getBoundingClientRect();

  camera = new THREE.PerspectiveCamera(
    75,
    parentRect.width / parentRect.height,
    0.1,
    1000,
  );
  camera.position.set(0, 5, 10);

  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(parentRect.width, parentRect.height);
  canvasParent.appendChild(renderer.domElement);

  labelRenderer = new CSS2DRenderer();
  labelRenderer.setSize(parentRect.width, parentRect.height);
  labelRenderer.domElement.style.position = 'absolute';
  labelRenderer.domElement.style.top = '0px';
  labelRenderer.domElement.style.pointerEvents = 'none';
  canvasParent.appendChild(labelRenderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 0, 0);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
  directionalLight.position.set(5, 10, 7.5);
  scene.add(directionalLight);
  const gridHelper = new THREE.GridHelper(20, 20);
  scene.add(gridHelper);

  window.addEventListener('resize', () => {
    const newRect = canvasParent.getBoundingClientRect();
    camera.aspect = newRect.width / newRect.height;
    camera.updateProjectionMatrix();
    renderer.setSize(newRect.width, newRect.height);
    labelRenderer.setSize(newRect.width, newRect.height);
  });
};

const createPlanetMesh = planet => {
  const radius = 0.2;
  const geometry = new THREE.SphereGeometry(radius, 16, 16);
  const material = new THREE.MeshStandardMaterial({
    color:
      planet.color ||
      `#${Math.floor(Math.random() * 16777215)
        .toString(16)
        .padStart(6, '0')}`,
    roughness: 0.5,
    metalness: 0.1,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(planet.position.x, planet.position.y, planet.position.z);

  const labelDiv = document.createElement('div');
  labelDiv.className = 'planet-label-builder';
  labelDiv.textContent = planet.name;
  labelDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
  labelDiv.style.color = 'white';
  labelDiv.style.padding = '2px 5px';
  labelDiv.style.borderRadius = '3px';
  labelDiv.style.fontSize = '12px';
  const label = new CSS2DObject(labelDiv);
  label.position.set(0, radius + 0.1, 0);
  mesh.add(label);
  return mesh;
};

const updatePlanetList = () => {
  const planetListEl = document.getElementById('planetList');
  planetListEl.innerHTML = '';

  planets.forEach((planet, index) => {
    const planetItem = document.createElement('div');
    planetItem.className = 'planet-item';
    const colorIndicator = document.createElement('div');
    colorIndicator.className = 'planet-color';
    colorIndicator.style.backgroundColor = planet.color || '#FFFFFF';
    const nameSpan = document.createElement('span');
    const massDisplay = isNaN(parseFloat(planet.mass))
      ? 'N/A'
      : parseFloat(planet.mass).toExponential(2);
    nameSpan.textContent = `${planet.name} (m: ${massDisplay} kg)`;
    const deleteButton = document.createElement('button');
    deleteButton.className = 'button secondary small-delete-button';
    deleteButton.textContent = '×';
    deleteButton.onclick = e => {
      e.stopPropagation();
      removePlanet(index);
    };
    planetItem.appendChild(colorIndicator);
    planetItem.appendChild(nameSpan);
    planetItem.appendChild(deleteButton);
    planetListEl.appendChild(planetItem);
  });
  document.getElementById(
    'planetCount',
  ).textContent = `${planets.length} planets`;
};

const removePlanet = index => {
  if (planets[index] && planets[index].mesh) {
    scene.remove(planets[index].mesh);
    if (planets[index].mesh.geometry) planets[index].mesh.geometry.dispose();
    if (planets[index].mesh.material) planets[index].mesh.material.dispose();
    planets[index].mesh.children.forEach(child => {
      if (child.isCSS2DObject) child.element.remove();
    });
  }
  planets.splice(index, 1);
  updatePlanetList();
};

const animate = () => {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
};

const planetForm = document.getElementById('planetForm');
planetForm.addEventListener('submit', e => {
  e.preventDefault();

  const rawVelX = parseFloat(document.getElementById('velX').value) || 0;
  const rawVelY = parseFloat(document.getElementById('velY').value) || 0;
  const rawVelZ = parseFloat(document.getElementById('velZ').value) || 0;
  const selectedUnit = document.getElementById('velocityUnitScenario').value;
  const convertedVelocity = convertVelocityToAuYearScenario(
    rawVelX,
    rawVelY,
    rawVelZ,
    selectedUnit,
  );

  const newPlanet = {
    name: document.getElementById('planetName').value.trim(),
    position: {
      x: parseFloat(document.getElementById('posX').value) || 0,
      y: parseFloat(document.getElementById('posY').value) || 0,
      z: parseFloat(document.getElementById('posZ').value) || 0,
    },
    velocity: convertedVelocity, // Already in AU/year
    mass: parseFloat(document.getElementById('mass').value),
    color:
      document.getElementById('color').value ||
      `#${Math.floor(Math.random() * 16777215)
        .toString(16)
        .padStart(6, '0')}`,
  };

  if (!newPlanet.name) {
    alert('Please enter a planet name.');
    return;
  }
  if (isNaN(newPlanet.mass)) {
    alert('Please enter a valid mass (in kg).');
    return;
  }
  if (Object.values(newPlanet.position).some(isNaN)) {
    alert('Position components must be valid numbers.');
    return;
  }
  if (Object.values(newPlanet.velocity).some(isNaN)) {
    alert('Velocity components resulted in NaN. Check inputs.');
    return;
  }

  const mesh = createPlanetMesh(newPlanet);
  scene.add(mesh);
  newPlanet.mesh = mesh;

  planets.push(newPlanet);
  updatePlanetList();
  planetForm.reset();
  document.getElementById('posZ').value = '0';
  document.getElementById('velX').value = '0';
  document.getElementById('velY').value = '0';
  document.getElementById('velZ').value = '0';
  document.getElementById('velocityUnitScenario').value = 'au_year';
  document.getElementById('color').value = '';
});

document.getElementById('saveScenario').addEventListener('click', async () => {
  const scenarioName = document.getElementById('scenarioName').value.trim();
  if (!scenarioName) {
    alert('Please enter a scenario name.');
    return;
  }
  if (planets.length === 0) {
    alert('Please add at least one planet.');
    return;
  }

  const planetsToSave = planets.map(p => ({
    name: p.name,
    position: p.position, // AU
    velocity: p.velocity, // AU/year (already converted)
    mass: p.mass, // kg
    color: p.color,
  }));

  try {
    const response = await fetch('/save_scenario', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: scenarioName, planets: planetsToSave}),
    });
    const responseData = await response.json();
    if (!response.ok)
      throw new Error(responseData.error || 'Failed to save scenario.');
    alert(responseData.message || 'Scenario saved successfully!');
  } catch (error) {
    console.error('Error saving scenario:', error);
    alert(`Failed to save scenario: ${error.message}`);
  }
});

document.getElementById('clearScenario').addEventListener('click', () => {
  if (
    confirm('Are you sure you want to clear all planets from this scenario?')
  ) {
    planets.forEach(planet => {
      if (planet.mesh) {
        scene.remove(planet.mesh);
        if (planet.mesh.geometry) planet.mesh.geometry.dispose();
        if (planet.mesh.material) planet.mesh.material.dispose();
        planet.mesh.children.forEach(child => {
          if (child.isCSS2DObject) child.element.remove();
        });
      }
    });
    planets = [];
    updatePlanetList();
    document.getElementById('scenarioName').value = '';
    document.getElementById('scenarioStatus').textContent = 'Scenario cleared';
  }
});

window.onload = () => {
  initThreeJS();
  animate();
  updatePlanetList();
  document.getElementById(
    'planetCount',
  ).textContent = `${planets.length} planets`;
  document.getElementById('scenarioStatus').textContent =
    'Define your scenario';
};
