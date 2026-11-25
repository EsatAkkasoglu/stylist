// Spawns the router over stdio like Claude Code does and calls every tool.  node test/roundtrip.mjs
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

import { fileURLToPath } from "node:url";
const cfg = { command: "node", args: [fileURLToPath(new URL("../server/index.mjs", import.meta.url))] };
const client = new Client({ name: "roundtrip", version: "0" });
await client.connect(new StdioClientTransport({ command: cfg.command, args: cfg.args, env: { ...process.env, ...cfg.env } }));
const call = async (name, args = {}) => {
  const r = await client.callTool({ name, arguments: args });
  return { err: !!r.isError, t: r.content[0].text };
};

const { tools } = await client.listTools();
assert.deepEqual(tools.map(t => t.name).sort(), ["build_brief", "get_guide", "get_kit", "get_style", "list_styles", "plan_edit", "search_sfx"]);

const all = JSON.parse((await call("list_styles")).t);
assert.ok(all.length >= 99, `styles: ${all.length}`);
assert.ok(JSON.parse((await call("list_styles", { filter: "Cartoons" })).t).length >= 6);
assert.ok(JSON.parse((await call("list_styles", { filter: "çizgi film" })).t).length >= 6, "Turkish category filter");
assert.ok(all.every(s => s.name_tr && s.category_tr), "every style has Turkish names");
const tr = await call("get_style", { style: "mühendislik planı" });
assert.ok(!tr.err && tr.t.includes("## Stylist layer") && tr.t.includes("FOLEY/PAPER"), "found by Turkish name, carries our layer");

const st = await call("get_style", { style: "工程蓝图" });
assert.ok(!st.err && st.t.includes("# Blueprint"));
const bad = await call("get_style", { style: "blue" });
assert.ok(bad.err && bad.t.includes("blueprint"), "unknown style suggests close ones");
assert.ok((await call("get_style", { style: "Manga Panels" })).t.startsWith("NOTE: this style needs an image generator"));

const brief = await call("build_brief", { request: "Güneş panelinin nasıl çalıştığını anlatan 30 sn'lik video", style: "blueprint", duration_s: 30, aspect: "9:16" });
assert.ok(!brief.err);
for (const s of ["Güneş panelinin", "baroque-motor", "harpsichord", "audio/notes.py", "topic mood", "creative", "lemo-opuscar", "# Blueprint", "Mühendislik Planı", "Stylist layer", "setup.sh\" demo blueprint", "--size 1080x1920", "search_sfx", "G0–G6", "audio/mix_pro.py"]) assert.ok(brief.t.includes(s), `brief lacks ${s}`);
assert.ok((await call("build_brief", { request: "test film", style: "blueprint", skill: "nope" })).err, "unknown skill rejected");
const quiet = await call("build_brief", { request: "sessiz bir film", style: "ukiyoe", music: "none", mood: "calm" });
assert.ok(quiet.t.includes("no music") && !quiet.t.includes("shamisen\"") , "customer can turn music off");
assert.ok((await call("build_brief", { request: "neşeli bir film", style: "ukiyoe", mood: "playful" })).t.includes("pluck:shamisen"), "style band in the brief");

assert.ok((await call("get_guide", { topic: "sound" })).t.includes("mean_volume − 15"));
assert.ok((await call("get_guide", { topic: "blender" })).t.includes("character_check.py") && (await call("get_guide", { topic: "operator" })).t.includes("Gates"));
assert.ok((await call("get_kit", { file: "blender/character_blockout.py" })).t.includes("def build("), "character proxy in the kit");
assert.ok((await call("build_brief", { request: "bir robot karakterin hikayesi", style: "comic-teardown" })).t.includes("character_check.py"), "brief routes characters to the Blender guide");

const w = JSON.parse((await call("search_sfx", { role: "WHOOSH/SWISH", limit: 3 })).t);
assert.ok(w.length >= 1 && w.every(s => s.role === "WHOOSH/SWISH" && existsSync(s.path) && s.level_db_over_music === 4));
const again = JSON.parse((await call("search_sfx", { role: "WHOOSH/SWISH", limit: 3, exclude_ids: [w[0].id] })).t);
assert.ok(!again.some(s => s.id === w[0].id), "exclude_ids respected");
const sharp = JSON.parse((await call("search_sfx", { onset: "sharp", max_ms: 400 })).t);
assert.ok(sharp.every(s => s.attack_ms < 20 && s.duration_ms <= 400));
assert.ok((await call("search_sfx", { query: "zzzqqq" })).err, "no match is an error with a fallback hint");

const kit = (await call("get_kit")).t;
for (const f of ["audio/mix_pro.py", "audio/verify_mix.py", "audio/beats.py", "gates/gates.py", "motion/motion_pro.js", "three/procedural_rig.js", "blender/blender_autoweight.py"])
  assert.ok(kit.includes(f + " — "), `kit lists ${f}`);
assert.ok((await call("get_kit", { file: "motion/motion_pro.js" })).t.includes("export const ease"));
assert.ok((await call("get_kit", { file: "../server/index.mjs" })).err, "no path escape");

// plan_edit: the same beats come back edited in each style's own language
const beats = [
  { role: "hook", vo: "Güneş paneli ışığı nasıl elektriğe çevirir?", show: "Çatıda panel", intent: "opening whole" },
  { role: "step", vo: "Fotonlar silisyum hücreye çarpar.", show: "Foton hücreye çarpar", label: "SİLİSYUM", intent: "inside detail" },
  { role: "step", vo: "İnverter akımı alternatif akıma çevirir.", show: "Düz çizgi girer, dalgalı çıkar", label: "İNVERTER", intent: "two states before after" },
  { role: "payoff", vo: "Ve güneş evinin lambasında yanar.", show: "Lamba yanar", intent: "ending whole" }];
const plan = async st => { const r = await call("plan_edit", { style: st, beats }); assert.ok(!r.err, r.t); return { t: r.t, shots: JSON.parse(r.t.split("```json")[1].split("```")[0]) }; };
const neon = await plan("neon-tubes"), box = await plan("Kâğıt Kesme Işık Kutusu");
assert.equal(neon.shots.length, 4); assert.equal(neon.shots[1].step, "1/2"); assert.equal(neon.shots[2].step, "2/2");
assert.ok(neon.shots.every(s => s.duration_s >= 2.5), "every beat holds long enough to be seen");
assert.notDeepEqual(neon.shots.map(s => s.camera), box.shots.map(s => s.camera), "different styles cut differently");
assert.equal(neon.shots[2].native, "Alternate circuits", "two states -> the medium's own two-state move");
assert.ok(neon.t.includes("Words are tubes") && box.t.includes("cut strips"), "labels follow each medium");
assert.ok(box.t.includes("Onay noktası"), "approval checkpoint");
// cinematic standard: rig from the style's category, no plain cut, shake on labelled beats, accents inside long shots
assert.ok(box.t.includes("Sinematik hareket standardı") && box.t.includes("RIGS.calm"), "paper lightbox runs the calm rig");
assert.ok([...neon.shots, ...box.shots].every(s => !/^(hard cut|cut on)/.test(s.transition_in)), "shots join with a camera move");
assert.ok(box.shots[1].shake.includes("SİLİSYUM") && box.shots[0].shake, "micro-shake on the label word and the hook");
assert.ok(box.shots.every(s => s.accents.every(a => a < s.duration_s)), "accents inside the shot");
// kinetic type + motion blur: from each style's profile (neon draws on light, paper lightbox focuses; pixel RPG stays crisp)
assert.ok(neon.t.includes('"draw"') && box.t.includes('"focus"') && neon.t.includes("rig().mb"), "reveal per style");
assert.ok((await plan("pixel-rpg")).t.includes("keskin kalır"), "pixel look: no motion blur");
const REV = ["wipe", "rise", "focus", "track", "draw"];
for (const s of all) {
  const m = JSON.parse(readFileSync(new URL(`../styles/${s.slug}/style.json`, import.meta.url))).stylist.motion;
  assert.ok(REV.includes(m.reveal) && typeof m.mblur === "boolean" && m.rig, `${s.slug} has the full motion profile`);
}
// music: every style carries its own band, read from its sound palette (kit/audio/score.py ensemble)
for (const s of all) {
  const st = JSON.parse(readFileSync(new URL(`../styles/${s.slug}/style.json`, import.meta.url))).stylist;
  assert.ok(st.score && st.score.genre && st.music === st.score.genre && st.score.note, `${s.slug} has a music band`);
}

await client.close();
console.log(`ok: ${tools.length} tools, ${all.length} styles, brief ${brief.t.length} chars, ${w.length} whooshes`);
