import * as THREE from "three";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";

const sceneState = { renderer: null, labelRenderer: null, frame: 0, root: null };

function labelFor(node, isMe) {
  const element = document.createElement("div");
  element.className = `org-scene-label${isMe ? " org-scene-me" : ""}`;
  const name = document.createElement("strong");
  name.textContent = node.name || "";
  const role = document.createElement("span");
  role.textContent = node.role_title || node.department || "";
  element.append(name, role);
  return new CSS2DObject(element);
}

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose();
    if (Array.isArray(child.material)) child.material.forEach((material) => material.dispose());
    else child.material?.dispose();
    if (child.element?.parentNode) child.element.parentNode.removeChild(child.element);
  });
}

function positionNodes(nodes, radius, y) {
  const count = Math.max(nodes.length, 1);
  return nodes.map((node, index) => {
    const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
    return { node, position: new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius) };
  });
}

function buildScene(data, myId, container) {
  if (sceneState.root) {
    sceneState.scene.remove(sceneState.root);
    disposeObject(sceneState.root);
  }
  sceneState.root = new THREE.Group();
  const rootNode = data.roots[0];
  if (!rootNode) return;

  const authored = new THREE.Mesh(
    new THREE.SphereGeometry(0.34, 24, 16),
    new THREE.MeshStandardMaterial({ color: 0x6d4dff, roughness: 0.42 })
  );
  authored.add(labelFor(rootNode, rootNode.id === myId));
  sceneState.root.add(authored);

  const children = positionNodes(rootNode.children, 4.6, 0);
  children.forEach(({ node, position }) => {
    const area = new THREE.Mesh(
      new THREE.BoxGeometry(0.58, 0.58, 0.58),
      new THREE.MeshStandardMaterial({ color: 0x2aa198, roughness: 0.48 })
    );
    area.position.copy(position);
    area.userData.node = node;
    area.userData.detail = false;
    area.add(labelFor(node, node.id === myId));
    sceneState.root.add(area);
    const link = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), position]),
      new THREE.LineBasicMaterial({ color: 0xc8c3d8 })
    );
    sceneState.root.add(link);
  });
  sceneState.root.userData.source = data;
  sceneState.root.userData.myId = myId;
  sceneState.scene.add(sceneState.root);
  container.replaceChildren();
  container.appendChild(sceneState.renderer.domElement);
  container.appendChild(sceneState.labelRenderer.domElement);
  container.appendChild(Object.assign(document.createElement("div"), { className: "org-scene-hint", textContent: "Select an area node to reveal its reporting detail." }));
  sceneState.root.children.filter((child) => child.userData.node).forEach((child) => {
    child.userData.onSelect = () => revealDetail(child.userData.node, container);
  });
  if (!sceneState.pointerBound) {
    container.addEventListener("click", (event) => {
      const bounds = sceneState.renderer.domElement.getBoundingClientRect();
      sceneState.pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      sceneState.pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      sceneState.raycaster.setFromCamera(sceneState.pointer, sceneState.camera);
      const hit = sceneState.raycaster.intersectObjects(sceneState.root.children, false).find((item) => item.object.userData.onSelect);
      hit?.object.userData.onSelect();
    });
    sceneState.pointerBound = true;
  }
}

function revealDetail(node, container) {
  const children = node.children || [];
  const detail = positionNodes(children, 2.2, -1.8);
  const group = new THREE.Group();
  detail.forEach(({ node: child, position }) => {
    const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.18, 16, 12), new THREE.MeshStandardMaterial({ color: 0xf08a5d }));
    leaf.position.copy(position);
    leaf.add(labelFor(child, child.id === sceneState.root.userData.myId));
    group.add(leaf);
  });
  sceneState.root.children.filter((child) => child.userData.detail).forEach((child) => {
    sceneState.root.remove(child);
    disposeObject(child);
  });
  group.userData.detail = true;
  sceneState.root.add(group);
}

function animate() {
  sceneState.frame = requestAnimationFrame(animate);
  if (!sceneState.renderer || !sceneState.root) return;
  sceneState.root.rotation.y += 0.0007;
  sceneState.renderer.render(sceneState.scene, sceneState.camera);
  sceneState.labelRenderer.render(sceneState.scene, sceneState.camera);
}

function resizeScene(container) {
  if (!sceneState.renderer) return;
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 620;
  sceneState.camera.aspect = width / height;
  sceneState.camera.updateProjectionMatrix();
  sceneState.renderer.setSize(width, height, false);
  sceneState.labelRenderer.setSize(width, height);
}

export function mountOrgScene(data, myId, container) {
  if (!sceneState.renderer) {
    sceneState.scene = new THREE.Scene();
    sceneState.scene.background = new THREE.Color(0xf7f5fb);
    sceneState.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    sceneState.camera.position.set(0, 2.4, 11);
    sceneState.scene.add(new THREE.HemisphereLight(0xffffff, 0x6b637c, 2.2));
    sceneState.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    sceneState.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    sceneState.renderer.domElement.className = "org-scene-canvas";
    sceneState.labelRenderer = new CSS2DRenderer();
    sceneState.labelRenderer.domElement.style.position = "absolute";
    sceneState.labelRenderer.domElement.style.inset = "0";
    sceneState.labelRenderer.domElement.style.pointerEvents = "none";
    sceneState.pointer = new THREE.Vector2();
    sceneState.raycaster = new THREE.Raycaster();
    window.addEventListener("resize", () => resizeScene(document.querySelector("#org-scene")));
    animate();
  }
  resizeScene(container);
  buildScene(data, myId, container);
}

window.mountOrgScene = mountOrgScene;