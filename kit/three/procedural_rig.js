// 3D without skinning (guide "3d"): nothing here has bone weights that can break. Three.js (MIT), pure functions of t.
//   import * as THREE from "three"; import { SVGExtrudeHero, HierarchicalRigidJoints, SkeletonlessShaderRig } from "./tools/procedural_rig.js";
import * as THREE from "three";

/** Mode A: 2D outlines → 3D objects. `shapes` = THREE.Shape[] (e.g. from SVGLoader: data.paths.flatMap(p => SVGLoader.createShapes(p))). */
export function SVGExtrudeHero(shapes, { depth = 20, bevel = 2, color = 0xdddddd, metalness = 0.3, roughness = 0.4 } = {}) {
  const geo = new THREE.ExtrudeGeometry(shapes, { depth, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 3, curveSegments: 24 });
  geo.center();
  geo.rotateX(Math.PI);                      // SVG y points down
  return new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color, metalness, roughness }));
}

/** From SVG text, in the browser (SVGLoader needs DOMParser). */
export async function svgToShapes(svgText) {
  const { SVGLoader } = await import("three/examples/jsm/loaders/SVGLoader.js");
  return new SVGLoader().parse(svgText).paths.flatMap(p => SVGLoader.createShapes(p));
}

/** Mode B (rigid joints): a stylised biped, each limb its own mesh under an Object3D pivot. pose(t) = walk cycle. */
export function HierarchicalRigidJoints({ color = 0x88aaff, height = 1.8 } = {}) {
  const u = height / 1.8, mat = new THREE.MeshStandardMaterial({ color, roughness: 0.6 });
  const box = (w, h, d) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w * u, h * u, d * u), mat); m.position.y = -h * u / 2; return m; };
  const joint = (parent, x, y, child) => { const j = new THREE.Object3D(); j.position.set(x * u, y * u, 0); j.add(child); parent.add(j); return j; };
  const root = new THREE.Group(), hips = new THREE.Object3D();
  hips.position.y = 0.95 * u; root.add(hips);
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.4 * u, 0.6 * u, 0.22 * u), mat); torso.position.y = 0.3 * u; hips.add(torso);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.13 * u, 16, 12), mat); head.position.y = 0.75 * u; hips.add(head);
  const J = {};
  for (const [side, s] of [["L", 1], ["R", -1]]) {
    J["thigh" + side] = joint(hips, 0.1 * s, 0, box(0.14, 0.45, 0.14));
    J["shin" + side] = joint(J["thigh" + side], 0, -0.45, box(0.12, 0.45, 0.12));
    J["arm" + side] = joint(hips, 0.27 * s, 0.58, box(0.1, 0.35, 0.1));
    J["fore" + side] = joint(J["arm" + side], 0, -0.35, box(0.09, 0.32, 0.09));
  }
  function pose(t, { speed = 1, stride = 0.5 } = {}) {
    const p = t * speed * Math.PI * 2;
    for (const [side, ph] of [["L", 0], ["R", Math.PI]]) {
      const s = Math.sin(p + ph);
      J["thigh" + side].rotation.x = stride * s;
      J["shin" + side].rotation.x = Math.max(0, -stride * 1.2 * Math.cos(p + ph));   // knee only bends one way
      J["arm" + side].rotation.x = -stride * 0.8 * s;                                  // arms swing against legs
      J["fore" + side].rotation.x = -0.3 - 0.2 * Math.max(0, s);
    }
    hips.position.y = (0.95 + 0.03 * Math.abs(Math.sin(p))) * u;                       // bob twice per cycle
    torso.rotation.y = 0.08 * Math.sin(p);
    return J;
  }
  return { root, joints: J, pose };
}

// Mode B (shader): one pose function shared by GLSL and JS. JS twin is for tests and for placing props on the body.
export const POSE_GLSL = /* glsl */ `
uniform float uTime, uBreath, uSway, uBend, uHeight;
vec3 posePos(vec3 p) {
  float h = clamp(p.y / uHeight, 0.0, 1.0);                       // 0 at the feet, 1 at the top
  p.xz *= 1.0 + uBreath * 0.04 * sin(uTime * 1.6) * smoothstep(0.3, 0.7, h) * (1.0 - smoothstep(0.7, 1.0, h));
  p.x += uSway * 0.06 * uHeight * sin(uTime * 3.0) * h * h;       // feet stay planted, top sways
  float a = uBend * 0.35 * sin(uTime * 0.8) * h;
  p.xy = mat2(cos(a), sin(a), -sin(a), cos(a)) * p.xy;            // lean from the base
  return p;
}`;
export function posePos([x, y, z], { t, breath = 1, sway = 1, bend = 0, height = 1 }) {
  const ss = (a, b, v) => { const k = Math.min(1, Math.max(0, (v - a) / (b - a))); return k * k * (3 - 2 * k); };
  const h = Math.min(1, Math.max(0, y / height));
  const s = 1 + breath * 0.04 * Math.sin(t * 1.6) * ss(0.3, 0.7, h) * (1 - ss(0.7, 1, h));
  x *= s; z *= s;
  x += sway * 0.06 * height * Math.sin(t * 3) * h * h;
  const a = bend * 0.35 * Math.sin(t * 0.8) * h, c = Math.cos(a), sn = Math.sin(a);
  return [c * x - sn * y, sn * x + c * y, z];
}

/** Any mesh (geometry base at y=0) becomes a breathing, swaying character with no skeleton. update(t) each frame. */
export function SkeletonlessShaderRig(mesh, { breath = 1, sway = 1, bend = 0 } = {}) {
  mesh.geometry.computeBoundingBox();
  const uniforms = { uTime: { value: 0 }, uBreath: { value: breath }, uSway: { value: sway }, uBend: { value: bend },
    uHeight: { value: mesh.geometry.boundingBox.max.y || 1 } };
  mesh.material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = POSE_GLSL + shader.vertexShader.replace("#include <begin_vertex>", "vec3 transformed = posePos(position);");
  };
  mesh.material.needsUpdate = true;
  return { mesh, uniforms, update: t => { uniforms.uTime.value = t; } };
}
