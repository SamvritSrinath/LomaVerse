import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {
  CSS2DRenderer,
  CSS2DObject,
} from 'three/addons/renderers/CSS2DRenderer.js';

// Scene setup
let scene, camera, renderer, labelRenderer, controls;
let planets = [];

const initThreeJS = () => {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.1,
    1000,
  );
  camera.position.set(0, 0, 5);

  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(window.innerWidth * 0.7, window.innerHeight * 0.7);
  document.getElementById('canvasparent').appendChild(renderer.domElement);

  labelRenderer = new CSS2DRenderer();
  labelRenderer.setSize(window.innerWidth * 0.7, window.innerHeight * 0.7);
  document.getElementById('canvasparent').appendChild(labelRenderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  // Add lights
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  directionalLight.position.set(5, 5, 5);
  scene.add(directionalLight);

  // Add grid helper
  const gridHelper = new THREE.GridHelper(10, 10);
  scene.add(gridHelper);
};

const createPlanetMesh = planet => {
  const geometry = new THREE.SphereGeometry(0.2, 32, 32);
  const material = new THREE.MeshStandardMaterial({
    color: planet.color || 0xffffff,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(planet.position.x, planet.position.y, planet.position.z);

  // Add label
  const labelDiv = document.createElement('div');
  labelDiv.textContent = planet.name;
  labelDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
  labelDiv.style.color = 'white';
  labelDiv.style.padding = '2px 5px';
  labelDiv.style.borderRadius = '3px';
  const label = new CSS2DObject(labelDiv);
  label.position.set(0.3, 0.3, 0);
  mesh.add(label);

  return mesh;
};

const updatePlanetList = () => {
  const planetList = document.getElementById('planetList');
  planetList.innerHTML = '';

  planets.forEach((planet, index) => {
    const planetItem = document.createElement('div');
    planetItem.className = 'planet-item';

    const colorIndicator = document.createElement('div');
    colorIndicator.className = 'color-indicator';
    colorIndicator.style.backgroundColor = planet.color || '#ffffff';

    const nameSpan = document.createElement('span');
    nameSpan.textContent = planet.name;

    const deleteButton = document.createElement('button');
    deleteButton.className = 'button secondary';
    deleteButton.textContent = '×';
    deleteButton.onclick = () => removePlanet(index);

    planetItem.appendChild(colorIndicator);
    planetItem.appendChild(nameSpan);
    planetItem.appendChild(deleteButton);
    planetList.appendChild(planetItem);
  });

  document.getElementById(
    'planetCount',
  ).textContent = `${planets.length} planets`;
};

const removePlanet = index => {
  if (planets[index].mesh) {
    scene.remove(planets[index].mesh);
  }
  planets.splice(index, 1);
  updatePlanetList();
  updateScene();
};

const updateScene = () => {
  planets.forEach(planet => {
    if (planet.mesh) {
      planet.mesh.position.set(
        planet.position.x,
        planet.position.y,
        planet.position.z,
      );
    }
  });
};

const animate = () => {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
};

// Form handling
const planetForm = document.getElementById('planetForm');
planetForm.addEventListener('submit', e => {
  e.preventDefault();

  const newPlanet = {
    name: document.getElementById('planetName').value,
    position: {
      x: parseFloat(document.getElementById('posX').value),
      y: parseFloat(document.getElementById('posY').value),
      z: parseFloat(document.getElementById('posZ').value),
    },
    velocity: {
      x: parseFloat(document.getElementById('velX').value) || 0,
      y: parseFloat(document.getElementById('velY').value) || 0,
      z: parseFloat(document.getElementById('velZ').value) || 0,
    },
    mass: parseFloat(document.getElementById('mass').value),
    color: document.getElementById('color').value || undefined,
  };

  const mesh = createPlanetMesh(newPlanet);
  scene.add(mesh);
  newPlanet.mesh = mesh;

  planets.push(newPlanet);
  updatePlanetList();
  planetForm.reset();
});

// Save scenario
document.getElementById('saveScenario').addEventListener('click', async () => {
  const scenarioName = document.getElementById('scenarioName').value;
  if (!scenarioName) {
    alert('Please enter a scenario name');
    return;
  }

  if (planets.length === 0) {
    alert('Please add at least one planet');
    return;
  }

  try {
    const response = await fetch('/save_scenario', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: scenarioName,
        planets: planets.map(p => ({
          name: p.name,
          position: p.position,
          velocity: p.velocity,
          mass: p.mass,
          color: p.color,
        })),
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to save scenario');
    }

    alert('Scenario saved successfully!');
  } catch (error) {
    console.error('Error saving scenario:', error);
    alert('Failed to save scenario. Please try again.');
  }
});

// Clear scenario
document.getElementById('clearScenario').addEventListener('click', () => {
  if (confirm('Are you sure you want to clear all planets?')) {
    planets.forEach(planet => {
      if (planet.mesh) {
        scene.remove(planet.mesh);
      }
    });
    planets = [];
    updatePlanetList();
    document.getElementById('scenarioName').value = '';
  }
});

// Initialize
window.onload = () => {
  initThreeJS();
  animate();
};
