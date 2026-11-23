// Kit JS: motion_pro.js and procedural_rig.js.  node test/test_kit.mjs
import assert from "node:assert/strict";
import * as THREE from "three";
import * as M from "../kit/motion/motion_pro.js";
import { SVGExtrudeHero, HierarchicalRigidJoints, SkeletonlessShaderRig, posePos } from "../kit/three/procedural_rig.js";

for (const [name, f] of Object.entries(M.ease)) {
  assert.ok(Math.abs(f(0)) < 1e-9 && Math.abs(f(1) - 1) < 1e-9, `${name} goes 0 → 1`);
  assert.equal(f(-5), f(0)); assert.equal(f(5), f(1));
}
assert.ok(M.ease.softLand(0.25) > 0.5 && M.ease.accelExit(0.75) < 0.5, "asymmetric");
assert.ok(Math.max(...Array.from({ length: 101 }, (_, i) => M.ease.snapSettle(i / 100))) > 1.05, "snapSettle overshoots");
const keys = [[0, 0], [1, 100, "linear"], [2, 50]];
assert.equal(M.tween(-1, keys), 0); assert.equal(M.tween(0.5, keys), 50); assert.equal(M.tween(3, keys), 50);
assert.deepEqual(M.drift(3.7, 2, 0.3, 4), M.drift(3.7, 2, 0.3, 4), "deterministic");
assert.ok(Math.abs(M.drift(1, 1).x - M.drift(1 + 1 / 24, 1).x) > 0, "moves every frame");
const e0 = M.enter(1, 1), e1 = M.enter(2, 1);
assert.ok(e0.scale > 1.1 && e0.opacity === 0 && e1.scale === 1 && e1.opacity === 1, "enters from a scale");
assert.deepEqual(M.shot(3, [0, 2.5, 4]), { index: 1, local: 0.5 });
assert.equal(M.onFrame(1.01, 24), 24 / 24);
// cinematic standard: spring overshoots, shake lasts 5 frames, rig is deterministic and never rests, camera-based shot entry
const sp = Array.from({ length: 101 }, (_, i) => M.ease.spring(i / 100));
assert.ok(Math.max(...sp) > 1.05 && Math.max(...sp) < 1.15, "spring overshoots ~10 %");
assert.ok(M.shake(1 + 2 / 24, [1]).x !== 0 && M.shake(1 + 5 / 24, [1]).x === 0 && M.shake(.9, [1]).x === 0, "shake: 5 frames after the hit");
const cuts = [0, 4, 8];
assert.deepEqual(M.rig(5.3, cuts, M.RIGS.calm, { hits: [5.3] }), M.rig(5.3, cuts, M.RIGS.calm, { hits: [5.3] }), "rig deterministic");
for (let t = 0; t < 12; t += 1 / 24) { const a = M.rig(t, cuts), b = M.rig(t + 1 / 24, cuts); assert.ok(a.x !== b.x || a.zoom !== b.zoom, `camera rests at ${t}`); }
assert.ok(M.rig(4.01, cuts, M.RIGS.punchy).zoom > 1.2 && M.rig(4.01, cuts, M.RIGS.calm).blur > .9, "shot entry is a camera move");
assert.equal(M.stagger(2, 3, 5, 30), 2.5);
assert.deepEqual(M.accents(0, 8), [1.65, 4.4, 7.15]);
assert.ok(M.emphasis(1.2, 1).k > .5 && M.emphasis(.9, 1).underline === 0, "emphasis");
// motion blur: on fast camera moves only, never on shake, 0 at rest
assert.ok(M.rig(4 + 1 / 24, cuts, M.RIGS.punchy).mb.x > 0, "snap zoom blurs");
assert.deepEqual(M.rig(2, cuts, M.RIGS.calm).mb, { x: 0, y: 0 }, "drift stays crisp");
assert.deepEqual(M.rig(2, cuts, M.RIGS.punchy, { hits: [2 - 1 / 24] }).mb, M.rig(2, cuts, M.RIGS.punchy).mb, "shake not blurred");
// kinetic type: every kind starts hidden/offset and lands clean; exits run backwards
for (const kind of M.REVEALS) {
  const a = M.reveal(1, 1, kind), b = M.reveal(2, 1, kind);
  assert.deepEqual(b, { clip: kind === "wipe" ? "inset(-10% 0.00% -10% 0)" : "none", y: 0, tracking: 0, blur: 0, opacity: 1, frac: 1 }, `${kind} lands`);
  assert.notDeepEqual(a, b, `${kind} starts different`);
  assert.deepEqual(M.reveal(1, 1, kind, { out: true }), b, `${kind} exit starts from the landed state`);
}
assert.equal(M.reveal(1.5, 1, "draw", { frames: 24 }).frac, .5, "draw at a steady rate");
assert.ok(M.reveal(1.1, 1, "rise", { out: true }).y < M.reveal(1.3, 1, "rise", { out: true }).y, "exit accelerates out");

// Mode A
const sq = new THREE.Shape().moveTo(0, 0).lineTo(100, 0).lineTo(100, 50).lineTo(0, 50).lineTo(0, 0);
const hero = SVGExtrudeHero([sq], { depth: 10 });
hero.geometry.computeBoundingBox();
const sz = hero.geometry.boundingBox.getSize(new THREE.Vector3());
assert.ok(Math.abs(sz.x - 104) < 0.5 && Math.abs(sz.z - 14) < 0.5, `extruded size ${sz.toArray()}`);

// Mode B rigid joints: legs in antiphase, knees bend one way, same t → same pose
const rig = HierarchicalRigidJoints();
const J = rig.pose(0.25);
assert.ok(J.thighL.rotation.x > 0.4 && J.thighR.rotation.x < -0.4, "legs opposite");
for (let t = 0; t < 1; t += 0.05) { rig.pose(t); assert.ok(rig.joints.shinL.rotation.x >= 0 && rig.joints.shinR.rotation.x >= 0); }
rig.pose(0.25); assert.equal(rig.joints.thighL.rotation.x, J.thighL.rotation.x);
assert.ok(!rig.root.getObjectByProperty("type", "SkinnedMesh"), "no skinning anywhere");

// Mode B shader: feet planted, top moves; GLSL gets injected
for (const t of [0, 0.7, 2.3]) assert.deepEqual(posePos([0.2, 0, 0.1], { t, bend: 1 }), [0.2, 0, 0.1]);
const top = posePos([0, 1, 0], { t: 0.5, bend: 1 });
assert.ok(Math.abs(top[0]) > 0.01, "top sways/leans");
const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 2, 1).translate(0, 1, 0), new THREE.MeshStandardMaterial());
const sr = SkeletonlessShaderRig(mesh, { bend: 1 });
const shader = { uniforms: {}, vertexShader: "void main(){\n#include <begin_vertex>\n}" };
mesh.material.onBeforeCompile(shader);
assert.ok(shader.vertexShader.includes("posePos(position)") && shader.uniforms.uHeight.value === 2);
sr.update(3.5); assert.equal(shader.uniforms.uTime.value, 3.5);

console.log("ok: motion_pro, procedural_rig");
