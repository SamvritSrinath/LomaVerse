document.addEventListener("DOMContentLoaded", () => {
  function visualizePlanetMovement(planetStates, frameRate = 60) {
    const scene = new THREE.Scene();

    // Camera with some initial position so we see the scene
    const camera = new THREE.PerspectiveCamera(
      75,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0, 10);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);

    const light = new THREE.AmbientLight(0xffffff, 1);
    scene.add(light);

    function radiusFromMass(mass) {
      return 0.1;
    }

    const planetObjects = [];

    // Create spheres for each planet at initial frame
    planetStates[0].forEach((state) => {
      const radius = radiusFromMass(state.mass);
      const geometry = new THREE.SphereGeometry(radius, 32, 32);
      const material = new THREE.MeshStandardMaterial({ color: 0x0077ff });
      const sphere = new THREE.Mesh(geometry, material);
      sphere.position.set(state.pos.x, state.pos.y, 0);
      scene.add(sphere);
      planetObjects.push(sphere);
    });

    let currentFrame = 0;

    function animate() {
      setTimeout(() => {
        requestAnimationFrame(animate);

        // Update planet positions and scale for each frame
        if (currentFrame < planetStates.length) {
          planetStates[currentFrame].forEach((state, index) => {
            const sphere = planetObjects[index];
            sphere.position.set(state.pos.x, state.pos.y, 0);

            // If mass changes per frame, update scale accordingly (optional)
            const newRadius = radiusFromMass(state.mass);
            sphere.scale.set(newRadius, newRadius, newRadius);
          });
          currentFrame++;
        }

        // controls.update(); // update controls (for damping)
        renderer.render(scene, camera);
      }, 1000 / frameRate);
    }

    window.addEventListener("resize", () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });

    animate();
  }

  // Example data (replace with your actual frames)
//   const planetStates = [
//     [
//       { pos: { x: 0, y: 0 }, mass: 1 },
//       { pos: { x: 2, y: 1 }, mass: 8 },
//       { pos: { x: -1, y: -2 }, mass: 0.5 },
//     ],
//     [
//       { pos: { x: 0.1, y: 0.1 }, mass: 1 },
//       { pos: { x: 2.1, y: 1.2 }, mass: 8 },
//       { pos: { x: -0.9, y: -1.9 }, mass: 0.5 },
//     ],
//     [
//       { pos: { x: 0.3, y: 0.15 }, mass: 1 },
//       { pos: { x: 2.3, y: 1.3 }, mass: 8 },
//       { pos: { x: -0.7, y: -1.7 }, mass: 0.5 },
//     ],
//   ];

  fetch("/state")
    .then(response => response.json())
    .then(data => {
        session_id = data.session_id;
        fetch("/state/" + session_id)
        .then(response => response.json())
        .then(data => {
            console.log(data);
            visualizePlanetMovement(data, 30);
        })
    })

});
