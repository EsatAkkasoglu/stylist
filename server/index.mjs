// Stylist router MCP (stdio locally; api/mcp.mjs serves the same tools over HTTP). It runs no model and renders nothing: it routes.
// In: the user's request + the style they picked. Out: the skill to use, OUR style's rules (styles/),
// the production guides, matching sounds and the kit code. Claude on the user's machine does the work.
// Never write to stdout here except through the transport: it is the MCP channel.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { join, dirname, relative, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const STYLES = join(ROOT, "styles");            // our catalog, built by tools/import_styles.py
const KIT = join(ROOT, "kit");
const CATALOG = join(ROOT, "sfx_library", "sfx_catalog.json");
const GUIDES = ["creative", "music", "sound", "motion", "3d"];
const GENRES = ["auto", "none", "cinematic-pulse", "future-pop", "lofi-chill", "synthwave", "ambient-wonder", "chiptune", "jazz-combo", "hot-jazz",
  "minimal-pulse", "folk-acoustic", "chamber-march", "baroque-motor", "east-asian", "drone-sparse", "city-pop", "rock-opening"];   // kit/audio/score.py GENRES
const MOODS = ["auto", "bright", "playful", "warm", "calm", "wonder", "tense", "dark", "epic"];                                   // kit/audio/score.py MOODS
const ROLES = ["UI/CLICK", "WHOOSH/SWISH", "IMPACT/HIT", "DESIGNED/RISER", "DESIGNED/CHIME", "DESIGNED/ALERT",
  "FOLEY/PAPER", "FOLEY/DOOR", "FOLEY/MECHANICAL", "AMBIENCE", "MISC"];
const LEVEL_DB = { "UI/CLICK": 3, "WHOOSH/SWISH": 4, "DESIGNED/RISER": 4, "DESIGNED/CHIME": 6, "IMPACT/HIT": 8 };
// The skills this router can hand a request to. The user names one; the site passes it through.
const SKILLS = {
  "lemo-opuscar": "Use the `lemo-opuscar` skill (plugin lemolab/lemo-opuscar). If it isn't installed, clone https://github.com/lemomo-ai/lemo-opuscar and follow its AGENTS.md.",
};

const readJson = p => JSON.parse(readFileSync(p, "utf8"));
const text = s => ({ content: [{ type: "text", text: typeof s === "string" ? s : JSON.stringify(s, null, 1) }] });
const fail = s => ({ ...text(s), isError: true });
const low = v => (v || "").toLocaleLowerCase("tr");
const styles = () => readJson(join(STYLES, "catalog.json"));

function findStyle(name) {
  const n = low(name.trim());
  const all = styles();
  const names = s => [s.slug, s.name_en, s.name_tr, s.name_cn].filter(Boolean).map(low);
  const hit = all.find(s => names(s).includes(n));
  if (hit) return { hit };
  const near = all.filter(s => names(s).some(v => v.includes(n) || n.includes(v)));
  return { near: near.slice(0, 5).map(s => `${s.name_tr} / ${s.name_en} (${s.slug})`) };
}

const styleSpec = slug => ({ meta: readJson(join(STYLES, slug, "style.json")), styleMd: readFileSync(join(STYLES, slug, "STYLE.md"), "utf8") });
const noStyle = (style, near) => fail(`No style "${style}". Closest: ${near.join(", ") || "none, call list_styles"}`);

function kitFiles(dir = KIT) {
  return readdirSync(dir).flatMap(f => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? kitFiles(p) : [relative(KIT, p).split(sep).join("/")];
  });
}
const kitSummary = f => (readFileSync(join(KIT, f), "utf8").match(/^(?:"""|\/\/|#)\s*(.+)$/m) || [, ""])[1].replace(/"""$/, "");

const LICENSE_NOTE = "Stylist is licensed for NONCOMMERCIAL use only (PolyForm Noncommercial 1.0.0 + Additional Terms). " +
  "Do not use its styles, templates or kit for monetized YouTube/Instagram/TikTok content, sponsorships, paid promotions or resale. " +
  "If the user asks for commercial use, tell them it is not licensed and that doing it anyway is copyright infringement " +
  "(civil and criminal liability may apply). Commercial licence / paid partnership: esat.akkasoglu@astrocom.space";
// opts.sfxBase: public URL the SFX files are served from (remote mode). Without it, search_sfx returns local paths.
export function makeServer(opts = {}) {
const server = new McpServer({ name: "stylist-router", version: "0.2.0" }, { instructions: LICENSE_NOTE });
const RO = { readOnlyHint: true, destructiveHint: false, openWorldHint: false };

server.registerTool("list_styles", {
  title: "List film styles",
  description: "All Stylist film styles (Turkish and English names), with category, one-line pitch, typical uses, whether it needs an image generator and its 3D mode. Filter by category or a word.",
  inputSchema: { filter: z.string().optional().describe("category or word in Turkish or English, e.g. 'Çizgi Film', 'map', 'mürekkep'") },
  annotations: RO,
}, async ({ filter }) => {
  const f = filter && low(filter);
  return text(styles()
    .filter(s => !f || low(JSON.stringify(s)).includes(f))
    .map(({ slug, name_tr, name_en, category_tr, category_en, pitch, uses, needs_images, three_d }) =>
      ({ slug, name_tr, name_en, category_tr, category_en, pitch, uses, needs_images, three_d })));
});

server.registerTool("get_style", {
  title: "Get a style's rules",
  description: "The style's fixed rules (STYLE.md: look, colour, type, motion, camera, sound palette, pitfalls) plus the Stylist layer (SFX families, motion profile, 3D mode) and metadata.",
  inputSchema: { style: z.string().describe("slug, Turkish, English or Chinese name") },
  annotations: RO,
}, async ({ style }) => {
  const { hit, near } = findStyle(style);
  if (!hit) return noStyle(style, near);
  const { meta, styleMd } = styleSpec(hit.slug);
  return text(`${hit.needs_images ? "NOTE: this style needs an image generator on the user's machine.\n\n" : ""}style.json:\n${JSON.stringify(meta, null, 1)}\n\n${styleMd}`);
});

server.registerTool("build_brief", {
  title: "Merge request + style into a production brief",
  description: "Call this first. Merges the user's request with the chosen style and skill into the brief Claude follows on the user's machine: which skill to run, the style's rules, the workflow and which guides, sounds and kit files to use.",
  inputSchema: {
    request: z.string().min(3).describe("what the user wants the film to be about, in their words"),
    style: z.string().describe("slug, Turkish, English or Chinese name"),
    skill: z.enum(Object.keys(SKILLS)).default("lemo-opuscar"),
    duration_s: z.number().positive().max(600).optional(),
    aspect: z.enum(["16:9", "9:16", "1:1"]).optional(),
    language: z.string().optional().describe("film language; default: the language the request is written in"),
    music: z.enum(GENRES).default("auto").describe("music genre the customer picked; auto = the style's own band (always made unless the customer says none)"),
    mood: z.enum(MOODS).default("auto").describe("the topic's feeling for the score; auto = read it from the request"),
  },
  annotations: RO,
}, async ({ request, style, skill, duration_s, aspect, language, music, mood }) => {
  const { hit, near } = findStyle(style);
  if (!hit) return noStyle(style, near);
  const { meta, styleMd } = styleSpec(hit.slug);
  const size = { "9:16": "1080x1920", "1:1": "1080x1080" }[aspect];
  const band = meta.stylist?.score ?? { genre: meta.stylist?.music ?? "cinematic-pulse" };
  const genre = music === "none" ? "none (the customer asked for no music)"
    : music === "auto" ? `the style's own band, made by default: \`${JSON.stringify(band.render ?? band)}\``
    : `\`${music}\` groove (customer's choice) played by the style's band: \`${JSON.stringify({ ...(band.render ?? band), groove: music })}\``;
  const engine = band.render?.engine === "synth" ? "`audio/synth.py` (Surge XT)" : "`audio/notes.py` (MusicXML + General MIDI)";
  const feel = mood === "auto" ? "read the topic's feeling from the request (bright, playful, warm, calm, wonder, tense, dark, epic)" : `\`${mood}\``;
  const demo = meta.lemo_slug
    ? `\nTechniques from the library's demo: \`sh "<skill dir>/scripts/setup.sh" demo ${meta.lemo_slug}\`, only after TREATMENT.md is written.` : "";
  return text(`# Production brief

## The user's request (topic and story are theirs; never bend it toward the style's demo)
${request}

## Skill
${SKILLS[skill]}
Follow its workflow: brief → one round of questions → TREATMENT.md → style frames → produce → self-check → deliver.

## Style: ${hit.name_tr} / ${hit.name_en} (${hit.slug}) — ${hit.category_tr}
${hit.needs_images ? "**Needs an image generator** on the user's machine. Check it before anything else; without one, offer other styles.\n" : ""}STYLE.md is fixed for the look: keep every rule on palette, type, drawing and materials. Camera, motion and pacing follow the Stylist cinematic standard (its "Stylist layer" at the end, guide "motion"), which also gives the SFX families to search.${demo}

${styleMd}

## Format
- Length: ${duration_s ? `${duration_s} s` : "what the style suggests"}
- Frame: ${size ? `${aspect} → render with --size ${size}` : "16:9, 1920x1080 (library default)"}
- Language: ${language || "the language of the request"}
- Music: ${genre}; topic mood: ${feel}. Written by you as notes, played by kit ${engine}; guide "music". Original; never generic piano-and-strings.

## How to produce it (router rules on top of the skill)
STYLE.md wins on the look and the foley materials; its camera grammar runs on the Stylist camera rig (guide "motion": never-resting camera, camera-based transitions, idle life, three depth layers, staggered spring entrances). The music genre comes from the customer or the Stylist layer, the music level from guide "music".
0. **Clear the creative bar** (guide "creative"): three concepts, pick the most surprising; hook in frame 1; checks C1–C11 on the contact sheet. A plain literal walkthrough is not acceptable.
0. **Content first, then the cut**: write the film as numbered beats (one plain voice line + what must be seen + a label each), call \`plan_edit\` with them to get the shot-by-shot edit in this style's own language, and show that table to the user for approval before recording voice or animating.
0. **Build on the style's own engine**: after TREATMENT.md, \`setup.sh demo <slug>\`, read DEMO.md, copy its engine into the project.
1. In the one round of questions, if the film needs 3D objects or characters, ask the 3D question from guide "3d" (this style's default: ${meta.stylist?.three_d ?? "none"}).
2. Before the full render: one style frame + a 15–30 s demo, and pass gates G0–G6 (guide "motion", kit \`gates/gates.py\`). Never start a long render untested.
3. Music first: write the cue as notes (cue.json: the style's band, the topic's mood, sections with an energy arc, a motif and its answer, one silence before the payoff) → kit ${engine} → check it with \`audio/audio_report.py\`; cut the picture on its bar grid.
4. Sound: voice → word timings (kit \`audio/beats.py\`) → cue sheet → \`search_sfx\` per cue with the style's SFX families → kit \`audio/mix_pro.py\` (music ~10 dB under the voice, ~20 dB under speech; check \`measured\`) → kit \`audio/verify_mix.py\` and \`audio/audio_report.py\` → mux.sh (guides "music", "sound").
5. Never ask the user for keys to outside 3D or stock sites. Everything is drawn in code.

Call \`get_guide\` with "creative", "music", "sound", "motion" and "3d" (only if needed), and \`get_kit\` for each kit file you use (save it into the project's \`tools/\` folder), before production.`);
});

// ---------- plan_edit: the same content steps, edited in each style's own language ----------
// Content is style-independent (what must be seen and said); the cut (camera, transitions, labels, rhythm) comes from the
// style's STYLE.md, parsed into style.json stylist.edit by tools/import_styles.py. Like a brand lock: the steps stay fixed.
const ROLE_KW = {
  hook: "opening establish reveal wonder scale arrival first waking whole strike lights up",
  step: "how it works cause effect mechanism detail part inside process stages sequence explaining heart hidden cutaway attention",
  result: "result change after transformation turn reveal two states before",
  payoff: "ending verdict whole closing context scale everything return arrival lamp keepsake",
  bridge: "journey travel route flow path distance carried along timeline",
};
const TRANS_KINDS = ["match cut", "dissolve", "iris", "wipe", "curtain", "light off/on", "fig-number", "whip", "hard cut", "cut on", "cuts land on beats", "split"];
const HARD = new Set(["hard cut", "cut on", "cuts land on beats"]);   // never a plain cut: the rig's camera move carries it
// Stylist cinematic standard (kit motion/motion_pro.js RIGS): same numbers as the kit, in words for the table
const RIG_TR = {
  calm: { name: "sakin", drift: "yumuşak sürüklenme", push: "çekim boyu %4 yavaş push", trans: "push-through + odak kayması", shake: "çok hafif" },
  editorial: { name: "editoryal", drift: "hafif sürüklenme", push: "çekim boyu %6 push", trans: "kamera kaydırma (slide)", shake: "hafif" },
  punchy: { name: "enerjik", drift: "kısa sürüklenme", push: "çekim boyu %10 push", trans: "snap zoom", shake: "belirgin" },
};
const words = s => (s || "").toLowerCase().match(/[a-zçğıöşü0-9/]+/g) || [];

function planEdit(meta, beats, wps) {
  const ed = meta.stylist?.edit || {};
  const cams = ed.camera?.length ? ed.camera : [{ move: "Locked medium", expresses: "reading time", serves: "" }];
  const transText = (ed.transitions || []).join(" ").toLowerCase();
  const kinds = TRANS_KINDS.filter(k => transText.includes(k));
  const used = new Map(), usedNative = new Set(); let prev = null;
  const rigKey = meta.stylist?.motion?.rig || "editorial", rig = { ...RIG_TR[rigKey], reveal: meta.stylist?.motion?.reveal || "rise", mblur: meta.stylist?.motion?.mblur !== false };
  const nSteps = beats.filter(b => b.role === "step").length; let stepNo = 0;
  const shots = beats.map((b, i) => {
    const want = new Set([...words(ROLE_KW[b.role] || ""), ...words(b.intent)]);
    let best = null, bestScore = -1e9;
    cams.forEach((c, ci) => {
      const hay = words(`${c.move} ${c.expresses} ${c.serves}`);
      let s = hay.filter(w => want.has(w)).length - (c.move === prev ? 3 : 0) - (used.get(c.move) || 0) * 1.2 - ci * 0.01;
      if (s > bestScore) { bestScore = s; best = c; }
    });
    used.set(best.move, (used.get(best.move) || 0) + 1); prev = best.move;
    // the medium's own move for this beat, when one fits (e.g. two states → "Alternate circuits"); each used once
    let native = null, ns = 0;
    for (const n of ed.native_moves || []) {
      if (usedNative.has(n.name)) continue;
      const s = words(`${n.name} ${n.does} ${n.fits}`).filter(x => want.has(x)).length;
      if (s > ns) { ns = s; native = n; }
    }
    if (native && ns >= 2) usedNative.add(native.name); else native = null;
    const w = words(b.vo).length, dur = Math.max(b.role === "hook" ? 3 : 2.5, +(w / wps + 1.2 + (b.role === "hook" ? .5 : 0)).toFixed(1));
    if (b.role === "step") stepNo++;
    return {
      n: i + 1, role: b.role, step: b.role === "step" ? `${stepNo}/${nSteps}` : null, duration_s: dur,
      show: b.show, label: b.label || null, vo: b.vo,
      camera: best.move, why: [best.expresses, best.serves].filter(Boolean).join(" — "), native: native ? native.name : null,
      transition_in: i === 0 ? "film opens (hook in frame 1)" : (k => !k || HARD.has(k) ? rig.trans : `${k} + ${rig.trans}`)(kinds.length ? kinds[(i - 1) % kinds.length] : null),
      shake: b.label ? `"${b.label}" söylendiği karede, 5 kare` : b.role === "hook" || b.role === "payoff" ? "hero indiği karede, 5 kare" : null,
      accents: Array.from({ length: Math.max(0, Math.floor((dur - .8) / 2.75)) }, (_, j) => +(1.65 + j * 2.75).toFixed(1)).filter(a => a < dur - .4),
    };
  });
  return { shots, total_s: +shots.reduce((a, s) => a + s.duration_s, 0).toFixed(1), ed, moves: new Set(shots.map(s => s.camera)).size, rigKey, rig };
}

server.registerTool("plan_edit", {
  title: "Edit content steps in a style's own language",
  description: "Turns style-independent content beats (what must be seen, said and labelled, step by step) into a shot-by-shot edit in the chosen style: camera move and why (from the style's camera grammar), transition in, how labels look in this medium, motion rule, durations from the voice line, step counter, a native move for the signature beat. Call after writing the beats and BEFORE recording voice or animating; show the result to the user for approval.",
  inputSchema: {
    style: z.string().describe("slug, Turkish, English or Chinese name"),
    beats: z.array(z.object({
      role: z.enum(["hook", "step", "result", "bridge", "payoff"]),
      vo: z.string().describe("the voice line for this beat: one plain fact"),
      show: z.string().describe("what the viewer must see happen in this shot (the hero), concretely"),
      label: z.string().optional().describe("on-screen label naming what is shown, e.g. ELEKTRON"),
      intent: z.string().optional().describe("optional English keywords to steer the camera, e.g. 'inside, detail' or 'journey'"),
    })).min(1).max(20),
    words_per_second: z.number().min(1.5).max(4).default(2.4),
  },
  annotations: RO,
}, async ({ style, beats, words_per_second }) => {
  const { hit, near } = findStyle(style);
  if (!hit) return noStyle(style, near);
  const { meta } = styleSpec(hit.slug);
  const p = planEdit(meta, beats, words_per_second);
  const native = (p.ed.native_moves || [])[0];
  const row = s => `| ${s.n} | ${s.step ?? s.role} | ${s.duration_s} s | ${s.show} | ${s.label ?? "—"} | ${s.camera} | ${s.native ?? "—"} | ${s.transition_in} | ${s.shake ?? "—"} | ${s.accents.length ? s.accents.map(a => `${a} s`).join(", ") : "—"} | ${s.vo} |`;
  return text(`# Kurgu planı — ${hit.name_tr} / ${hit.name_en}

Toplam ≈ ${p.total_s} s · ${p.shots.length} çekim · ${p.moves} farklı kamera hareketi${p.moves < Math.min(4, p.shots.length) ? " (az: en az 4 hedefle, guide \"creative\" C6)" : ""}

| # | Adım | Süre | Ekranda görülen (hero) | Etiket | Kamera (bu stilin dili) | Stile özgü hareket | Giriş geçişi (kamera ile) | Darbe (micro-shake) | Mikro-aksiyon (çekim içi) | Seslendirme |
|---|---|---|---|---|---|---|---|---|---|---|
${p.shots.map(row).join("\n")}

## Bu stilde nasıl kurgulanır
- **Geçişler**: ${(p.ed.transitions || []).join(" ")}
- **Etiketler bu ortamda şöyle görünür**: ${(p.ed.labels || []).slice(0, 2).join(" ")}
- **Hareket kuralı**: ${(p.ed.motion || [])[0] || "—"}
- **İmza anı** (final/doruk için önerilen stile özgü hareket): ${native ? `${native.name} — ${native.does}` : "—"}${(p.ed.native_moves || []).length > 1 ? `\n- Diğer seçenekler: ${p.ed.native_moves.slice(1, 5).map(n => n.name).join(" · ")}` : ""}

## Sinematik hareket standardı (görünüş stilin, kamera ve tempo bu)
Kamera rig'i: **${p.rig.name}** (\`${p.rigKey}\`, kit \`motion/motion_pro.js\` \`rig()\`, \`RIGS.${p.rigKey}\`).
1. **Sanal kamera hiç durmaz**: ${p.rig.drift} + ${p.rig.push}; çekime giriş ${p.rig.trans} (düz kesme yok); tablodaki darbe karelerinde ${p.rig.shake} micro-shake (\`shake()\`, 4–5 kare). Yukarıdaki kamera hareketi bu rig'in üstünde çalışır.
2. **Sıfır ölü kare**: girişi biten her nesne \`idle()\` ile nefes alır / süzülür; tablodaki zamanlarda (~2.75 s'de bir) hero'yu vurgulayan ikincil mikro-aksiyon (parıltı, nabız, arka katman değişimi). Yeni bir özne ekleme, hero'yu vurgula.
3. **Üç katman + paralaks**: arka = stilin dokusu/ışığı (×0.25 hız) · orta = hero ve etiket (×1) · ön = stilin malzemesinden kameraya yakın, bulanık ışık/partikül (×1.8). Ön katman etiketin üstünden geçmez.
4. **Koreografi**: lineer hareket yok (\`softLand\`, \`spring\`, \`snapSettle\`); bir gruptaki öğeler 4–6 kare arayla (\`stagger()\`); vurucu kelime stilin vurgu rengi / alt çizgiyle (\`emphasis()\`), karta koymadan. Konuşmaya bağlı etiket kendi kelimesinde kalır; gecikmeyi ikincil öğeler alır.
5. **Kinetik tipografi**: yazılar bu stilin açılışıyla gelir: \`${p.rig.reveal}\` (\`reveal(t, stagger(t0, i), "${p.rig.reveal}")\`, kelime kelime, stilin malzemesiyle); çıkış tersine ve hızlanarak (\`{ out: true }\`); kısa satır indikten sonra en az 1.5 s kalır. Hızlı kamera hareketlerinde hareket bulanıklığı: ${p.rig.mblur ? "açık (\`rig().mb\`)" : "kapalı, bu görünüm keskin kalır"}.
6. **Netlik önce**: altyazı ve adım sayacı rig'in dışında (sarsılmaz); etiketler sadece çok hafif idle alır. Gate G6 (canlılık) duran saniyeleri ve vurgusuz >3.5 s aralıkları listeler.

## Kamera seçimlerinin nedeni
${p.shots.map(s => `${s.n}. **${s.camera}** — ${s.why}`).join("\n")}

## Netlik kuralları (guide "creative" §0)
- Her çekimde tek bir hero; etiket hero'nun yanında, olduğu anda çıkar; adım sayacı (${p.shots.find(s => s.step)?.step?.split("/")[1] ?? 0} adım) ekranın sabit bir köşesinde.
- Bir adımın sonucu ~1.2 s görünmeden sonraki başlamaz (süreler buna göre hesaplandı).
- Etiket ve sayaç bu stilin kendi malzemesiyle yapılır (yukarıdaki etiket kuralı), düz bir altyazı katmanıyla değil.

**Onay noktası**: bu tabloyu kullanıcıya göster; onaylanmadan seslendirme kaydetme, animasyona başlama.

\`\`\`json
${JSON.stringify(p.shots, null, 1)}
\`\`\``);
});

server.registerTool("get_guide", {
  title: "Production guide",
  description: "Router rules Claude follows while producing: 'creative' (concepts, hook, checks C1–C11 against simple films), 'music' (genres, energy arc, level against the voice), 'sound' (SFX choice, frame placement, ducking, loudness, checks), 'motion' (cinematic standard: camera rig, motion blur, idle life, depth layers, stagger, kinetic type; easing; gates G0–G6), '3d' (code-only 3D, skeletonless rigs, optional Blender).",
  inputSchema: { topic: z.enum(GUIDES) },
  annotations: RO,
}, async ({ topic }) => text(readFileSync(join(ROOT, "guides", `${topic}.md`), "utf8")));

server.registerTool("get_kit", {
  title: "Production kit code",
  description: "Ready, tested helper code Claude saves into the user's project and runs there: frame-locked SFX mix with ducking, word beats, mix verification, quality gates G0–G6, camera rig + motion blur + idle + stagger + kinetic type reveals + deterministic easing, skeletonless 3D rigs, optional Blender auto-weights. No file: lists them.",
  inputSchema: { file: z.string().optional().describe("path from the list, e.g. 'audio/mix_pro.py'") },
  annotations: RO,
}, async ({ file }) => {
  const files = kitFiles();
  if (!file) return text(files.map(f => `${f} — ${kitSummary(f)}`).join("\n"));
  if (!files.includes(file)) return fail(`No kit file "${file}". Available: ${files.join(", ")}`);   // also blocks ../ escapes
  return text(`// kit/${file}\n${readFileSync(join(KIT, file), "utf8")}`);
});

server.registerTool("search_sfx", {
  title: "Find sound effects by character",
  description: "Search the local CC0 SFX library by role, brightness, onset and length. Returns a local file path (or, on the hosted router, a download `url`: fetch it into the project before mixing), the acoustic numbers (centroid, attack, duration), the suggested level over the music bed, licence and attribution.",
  inputSchema: {
    role: z.enum(ROLES).optional(),
    query: z.string().optional().describe("words matched against title, tags and description, e.g. 'paper', 'metal'"),
    brightness: z.enum(["dark/sub", "warm", "bright"]).optional(),
    onset: z.enum(["sharp", "soft", "swell"]).optional().describe("sharp < 20 ms attack < soft < 150 ms < swell"),
    max_ms: z.number().positive().optional(),
    min_ms: z.number().nonnegative().optional(),
    exclude_ids: z.array(z.string()).optional().describe("ids already used, so the same file isn't repeated"),
    limit: z.number().int().min(1).max(30).default(5),
  },
  annotations: RO,
}, async ({ role, query, brightness, onset, max_ms, min_ms, exclude_ids = [], limit }) => {
  if (!existsSync(CATALOG)) return fail("The SFX library is empty. Run in the router folder: uv run --no-project python tools/sfx_library.py fetch");
  const words = query?.toLowerCase().split(/\s+/).filter(Boolean) || [];
  const onsetOf = a => (a < 20 ? "sharp" : a < 150 ? "soft" : "swell");
  const rows = readJson(CATALOG)
    .filter(s => (!role || s.role === role) && (!brightness || s.brightness === brightness)
      && (!onset || onsetOf(s.attack_ms) === onset) && (!max_ms || s.duration_ms <= max_ms)
      && (!min_ms || s.duration_ms >= min_ms) && !exclude_ids.includes(s.id))
    .map(s => ({ s, score: words.filter(w => `${s.title} ${s.description} ${s.tags.join(" ")}`.toLowerCase().includes(w)).length }))
    .filter(r => !words.length || r.score > 0)
    .sort((a, b) => b.score - a.score || (a.s.clipped ?? false) - (b.s.clipped ?? false) || (a.s.license === "cc0" ? -1 : 1))   // clipped last, then prefer CC0: no credit needed
    .slice(0, limit)
    .map(({ s: { path, ...s } }) => ({ ...s, ...(opts.sfxBase ? { url: `${opts.sfxBase}/sfx_library/${path}` } : { path: join(ROOT, "sfx_library", path) }), level_db_over_music: LEVEL_DB[s.role] ?? 3 }));
  return rows.length ? text(rows) : fail("No match. Loosen a filter, or use a \"synth\" cue in mix_pro.py (lemo core/audio/sfx.py; guide 'sound').");
});

return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await makeServer().connect(new StdioServerTransport());
