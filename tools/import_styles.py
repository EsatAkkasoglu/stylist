"""Build OUR style catalog (styles/) from the lemo-opuscar library, customised for Stylist.

  python tools/import_styles.py            # LEMO_OPUSCAR_HOME or ~/lemo-opuscar
  python tools/import_styles.py --relayer  # no library needed: re-apply profiles + Stylist layer to styles/

For every lemo style it writes styles/<slug>/:
  STYLE.md     the original rules (MIT, credited) + a "Stylist layer": our SFX families, motion profile, 3D mode
  style.json   lemo metadata + Turkish names + the "stylist" profile, with overrides.json merged on top
Safe to re-run: overrides.json is never touched, and a folder whose style.json says "source": "stylist"
(a style we made ourselves) is never overwritten. styles/catalog.json lists everything, ours included.
"""
import json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "styles"
SCORES = json.loads((ROOT / "tools" / "style_scores.json").read_text("utf8"))   # per-style band, read from each sound palette


def score_of(slug, prof):
    sc = dict(SCORES.get(slug) or {"genre": prof["music"]})
    if sc["genre"] != "none":
        sc["render"] = render_of(sc)
    return sc


# ---------- how the score is played: notes.py (General MIDI, acoustic) or synth.py (Surge XT, electronic) ----------
# voice -> (GM program for notes.py, Surge factory patch for synth.py); every voice works in either engine
VOICE = {
    "piano": (0, "Keys/EP 2"), "honky_tonk": (3, "Keys/Circus 1"), "epiano": (4, "Keys/DX EP"), "harpsichord": (6, "Keys/Digi Harpsi"),
    "glockenspiel": (9, "Plucks/Bell 1"), "pluck:music_box": (10, "Plucks/Magic Music Box"), "vibraphone": (11, "Plucks/Bell 2"),
    "vibraphone_bowed": (11, "Pads/Bell Pad"), "vibraphone_hard": (11, "Plucks/Bell 2"), "marimba": (12, "Plucks/Woody"),
    "xylophone": (13, "Plucks/Woody"), "hand_chimes": (14, "Plucks/Fantasy Bell"), "glass": (92, "Pads/Sparkly"),
    "organ_soft": (19, "Keys/Organ 1"), "organ_pedal": (19, "Keys/Church"), "accordion": (21, "Keys/Organ 2"), "harmonica": (22, "Leads/Formant Pulse"),
    "pluck:nylon_guitar": (24, "Plucks/Guitar"), "ukulele": (24, "Plucks/Guitar"), "pluck:acoustic_guitar": (25, "Plucks/Guitar"),
    "strumstick": (25, "Plucks/Guitar"), "electric_guitar": (29, "Leads/Synth Guitar 1"),
    "jazz_bass": (32, "Basses/Fingered"), "upright": (32, "Basses/Fingered"), "contrabass_pizz": (32, "Basses/Fingered"), "contrabass": (43, "Basses/Mellow"),
    "electric_bass": (33, "Basses/E-Bass"), "synthbass": (38, "Basses/Bass 1"), "triangle": (38, "Basses/Sub Square"),
    "violin": (40, "Leads/Violini Solo"), "erhu": (110, "Leads/Violini Solo"), "cellos": (42, "Polysynths/Juno-60 Strings"),
    "violins": (48, "Polysynths/Juno-60 Strings"), "violins_spic": (48, "Plucks/Nice Pluck 2"), "cellos_spic": (48, "Plucks/Nice Pluck 2"),
    "violins_trem": (44, "Pads/Subtle Comb Strings"), "violins_pizz": (45, "Plucks/Nice Pluck 1"), "cellos_pizz": (45, "Plucks/Nice Pluck 1"),
    "harp": (46, "Plucks/Harmonics 1"), "trumpet": (56, "Brass/Synth Brass 1"), "trumpet_stac": (56, "Brass/OB-8 Jump"),
    "trombone": (57, "Brass/Brassy"), "trombone_stac": (57, "Brass/Brassy"), "tuba_stac": (58, "Basses/Plain"), "trumpet_mute": (59, "Brass/Plastic Brass"),
    "horn": (60, "Brass/JX-10 Double Brass"), "alto_sax": (65, "Brass/Toto Brass"), "bassoon": (70, "Winds/Low"), "bassoon_stac": (70, "Winds/Low"),
    "clarinet": (71, "Winds/Clarinet"), "clarinet_stac": (71, "Winds/Clarinet"), "flute": (73, "Winds/Flute 1"), "flute_stac": (73, "Winds/Flute 2"),
    "recorder": (74, "Winds/Dreamy Flute"), "pluck:banjo": (105, "Leads/Banjo Remains"), "pluck:shamisen": (106, "Plucks/East"),
    "pluck:koto": (107, "Plucks/East"), "pluck:guqin": (107, "Plucks/East"), "pluck:pipa": (107, "Plucks/East"), "dan_tranh": (107, "Plucks/East"),
    "kalimba": (108, "Plucks/Mol"), "hang": (114, "Plucks/Bell 1"),
    # synth voices
    "pad": (89, "Polysynths/Juno-60 Strings"), "saw": (81, "Leads/Moogy Saw"), "supersaw": (81, "Polysynths/Super Jupiter"),
    "square": (80, "Leads/Square"), "pulse25": (80, "Plucks/Simple PW"), "pulse12": (80, "Plucks/Pure Square"), "pluck": (81, "Plucks/The 1980s"),
    "sinebell": (88, "Plucks/Bell 1"), "theremin": (79, "Leads/Sine Lead"),
}
SYNTH_VOICES = {"pad", "saw", "supersaw", "square", "pulse25", "pulse12", "pluck", "sinebell", "theremin", "synthbass", "triangle"}
ELECTRONIC = {"synthwave", "chiptune", "future-pop", "city-pop"}
ELECTRIC = {"epiano", "electric_bass", "electric_guitar"}   # sit in either world: they don't pull a band to notes
GENRE_BAND = {   # what each groove plays when the style names nothing for a role
    "cinematic-pulse": dict(pad="violins", pulse="saw", bass="synthbass", lead="piano"),
    "future-pop": dict(pad="supersaw", bass="synthbass", lead="pluck"),
    "lofi-chill": dict(pad="epiano", bass="jazz_bass", lead="vibraphone"),
    "synthwave": dict(pad="pad", pulse="saw", bass="synthbass", lead="saw"),
    "ambient-wonder": dict(pad="violins", lead="piano", sparkle="hand_chimes"),
    "chiptune": dict(pad="pulse25", bass="triangle", lead="square"),
    "jazz-combo": dict(pad="vibraphone", bass="jazz_bass", lead="flute"),
    "hot-jazz": dict(pad="honky_tonk", bass="tuba_stac", lead="trumpet", pulse="pluck:banjo"),
    "minimal-pulse": dict(pad="marimba", bass="contrabass_pizz", lead="vibraphone", pulse="glockenspiel"),
    "folk-acoustic": dict(pad="pluck:acoustic_guitar", bass="jazz_bass", lead="harmonica"),
    "chamber-march": dict(pad="cellos_spic", bass="tuba_stac", lead="xylophone", pulse="bassoon_stac"),
    "baroque-motor": dict(pad="harpsichord", bass="contrabass_pizz", lead="bassoon"),
    "east-asian": dict(pad="cellos", lead="flute", pulse="pluck:koto"),
    "drone-sparse": dict(pad="cellos", lead="vibraphone_bowed", pulse="vibraphone", sparkle="glockenspiel"),
    "city-pop": dict(pad="epiano", bass="electric_bass", lead="alto_sax"),
    "rock-opening": dict(pad="electric_guitar", bass="electric_bass", lead="square"),
}
ROLES_ORDER = ("lead", "counter", "pad", "pulse", "bass", "sparkle")
GM_DRUMS = {"orch": {"timpani": 47}, "taiko": {"taiko": 116}, "wood": {"woodblock": 115}, "hand": {"woodblock": 115}}   # pitched GM percussion
SURGE_DRUMS = {"kick": "Percussion/Kick Tech 1", "snare": "Percussion/Snare Tight", "tom": "Percussion/Synth Tom 1"}
SURGE_LIST = set((ROOT / "tools" / "surge_patches.txt").read_text("utf8").splitlines()) if (ROOT / "tools" / "surge_patches.txt").exists() else None   # Surge 1.3.4 factory, for checking


def render_of(sc):
    band = dict(GENRE_BAND.get(sc["genre"], {}))
    for r in ROLES_ORDER:
        if r in sc:
            v = sc[r]["inst"] if isinstance(sc[r], dict) else sc[r]
            band[r] = v
    band = {r: band[r] for r in ROLES_ORDER if band.get(r) in VOICE}
    synth_n = sum(v in SYNTH_VOICES for v in band.values())
    acoustic_n = sum(v not in SYNTH_VOICES | ELECTRIC for v in band.values())
    engine = "synth" if acoustic_n <= 1 and (sc["genre"] in ELECTRONIC or synth_n >= 2) else "notes"
    kit = sc.get("drums", "genre")
    if engine == "synth":
        out = {r: {"voice": v, "patch": VOICE[v][1]} for r, v in band.items()}
        drums = {} if kit == "none" else SURGE_DRUMS
        space = "dry" if sc.get("space") == "dry" else "neon"
    else:
        out = {r: {"voice": v, "gm": VOICE[v][0]} for r, v in band.items()}
        drums = GM_DRUMS.get(kit, {})
        space = "dry" if sc.get("space") == "dry" else "hall"
    if SURGE_LIST:
        for p in [x["patch"] for x in out.values() if "patch" in x] + list(drums.values() if engine == "synth" else []):
            assert p in SURGE_LIST, f"unknown Surge patch {p}"
    return {"engine": engine, "space": space, "band": out, "drums": drums}
LIB = Path(os.environ.get("LEMO_OPUSCAR_HOME") or Path.home() / "lemo-opuscar")

CATEGORY_TR = {
    "Edit & Documentary": "Kurgu & Belgesel", "Painting & Illustration": "Resim & İllüstrasyon", "Sketch & Board": "Eskiz & Tahta",
    "Traditional Crafts": "Geleneksel Sanatlar", "Print & Printmaking": "Baskı & Gravür", "Graphic & Type": "Grafik & Tipografi",
    "Line Diagrams": "Çizgi Diyagramlar", "Cartoons": "Çizgi Film", "Games": "Oyun", "Film & Tape": "Film & Kaset",
    "Screens & Interfaces": "Ekran & Arayüz", "Light & Lines": "Işık & Çizgi", "3D & Miniature": "3D & Minyatür",
    "Instruments & Evidence": "Cihaz & Kanıt", "Data & Maps": "Veri & Harita",
}
NAME_TR = {
    "Caption News": "Altyazılı Haber", "1920s Newsreel": "1920'ler Haber Filmi", "Live Countdown Split-screen": "Canlı Geri Sayım Bölünmüş Ekran",
    "City Symphony": "Şehir Senfonisi", "Visual Investigation": "Görsel Soruşturma", "Constructivist Montage": "Konstrüktivist Montaj",
    "Sports Telestrator": "Spor Taktik Tahtası", "Broadcast News Package": "TV Haber Paketi",
    "Crayon Picture Book": "Pastel Boya Resimli Kitap", "Watercolor Brush": "Suluboya Fırça", "Impasto Oil Painting": "Kalın Yağlıboya",
    "Urban Sketch · Pen & Wash": "Kent Eskizi · Kalem & Lavi", "Colored-Pencil Science Illustration": "Kuru Boya Bilim İllüstrasyonu",
    "One-line Drawing": "Tek Çizgi Çizim", "Whiteboard Explainer": "Beyaz Tahta Anlatım", "Chalkboard": "Kara Tahta Tebeşir",
    "Sketchnote": "Görsel Not", "Stick-figure Explainer": "Çöp Adam Anlatım", "Tablet Sketch Explainer": "Tablet Eskiz Anlatım",
    "Marker on Paper": "Kâğıda Keçeli Kalem",
    "Chinese Ink Wash": "Çin Mürekkep Resmi", "Shadow Puppetry": "Gölge Oyunu", "Ukiyo-e": "Ukiyo-e Gravür", "Red Paper-cut": "Kırmızı Kâğıt Kesme",
    "Paper-cut Lightbox": "Kâğıt Kesme Işık Kutusu", "Stained Glass": "Vitray", "Gilded Illumination": "Altın Varaklı Tezhip",
    "Risograph Print": "Risograf Baskı", "Halftone Dossier": "Raster Dosya", "Woodcut Print": "Ağaç Baskı", "Copperplate Engraving": "Bakır Gravür",
    "Silkscreen Travel Poster": "Serigrafi Seyahat Afişi", "Scratchboard Long Take": "Kazıma Pano Uzun Plan", "Pop Art": "Pop Art",
    "Vintage Engraving Collage": "Eski Gravür Kolaj",
    "Swiss Motion Graphics": "İsviçre Hareketli Grafik", "60s Spy Title Sequence": "60'lar Casus Jeneriği", "Art Deco": "Art Deco",
    "Pictogram Motion": "Piktogram Animasyon", "Bauhaus Shapes": "Bauhaus Formlar", "Scale Zoom Explainer": "Ölçek Yakınlaştırma Anlatım",
    "Text Flash Cuts": "Hızlı Metin Kesmeleri", "Silhouette Rhythm": "Siluet Ritim",
    "Blueprint": "Mühendislik Planı", "Isometric Infographic": "İzometrik İnfografik", "Exploded Teardown": "Patlatılmış Parça Görünüşü",
    "Line-Art Cutaway": "Çizgi Kesit Görünüş", "Color-Coded Mechanism": "Renk Kodlu Mekanizma", "Instruction Manual Art": "Kullanım Kılavuzu Çizimi",
    "Pen Plotter": "Kalem Çizici (Plotter)", "Assembly-Line Diagram": "Montaj Hattı Diyagramı",
    "1930s Rubber Hose Cartoon": "1930'lar Lastik Hortum Çizgi Film", "80s Cel Anime": "80'ler Cel Anime", "Sci-Fi Sitcom Toon": "Bilimkurgu Sitkom Çizgi Film",
    "Mid-century Cartoon": "Yüzyıl Ortası Çizgi Film", "Comic History Cartoon": "Komik Tarih Çizgi Filmi", "Manga Panels": "Manga Kareleri",
    "16-bit Pixel RPG": "16-bit Piksel RPG", "2.5D Pixel Art": "2.5D Piksel Sanat", "Microgame Frenzy": "Mikro Oyun Çılgınlığı",
    "Rhythm Game Show": "Ritim Yarışma Programı",
    "CRT ASCII Terminal": "CRT ASCII Terminal", "1920s Silent Film": "1920'ler Sessiz Film", "Liminal Found Footage": "Liminal Buluntu Kayıt",
    "Scratch Film": "Film Üstü Kazıma", "Double Exposure": "Çift Pozlama",
    "Dark Tech Keynote": "Karanlık Teknoloji Lansmanı", "Mascot Screencast": "Maskotlu Ekran Kaydı", "Sci-fi Hologram HUD": "Bilimkurgu Hologram HUD",
    "Tabletop App Flythrough": "Masaüstü Uygulama Turu", "Spreadsheet Film": "Tablo Filmi", "1-bit Dither": "1-bit Dither",
    "Circuit Board": "Devre Kartı", "Firefly Pointillism": "Ateşböceği Noktacılık", "Flow-field Wind Lines": "Akış Alanı Rüzgâr Çizgileri",
    "Oscilloscope Math": "Osiloskop Matematiği", "Neon Tubes": "Neon Tüpler",
    "Brick Toy": "Yapı Oyuncağı", "Paper Pop-up Book": "Kâğıt Pop-up Kitap", "Tilt-Shift Miniature": "Tilt-Shift Minyatür",
    "Low-poly Isometric Island": "Low-poly İzometrik Ada", "Glass Product Render": "Cam Ürün Render", "Memphis Diorama": "Memphis Diorama",
    "Isometric People Scene": "İzometrik İnsan Sahnesi", "Crayon World 3D": "3D Pastel Boya Dünyası",
    "Satellite Briefing": "Uydu Brifingi", "Engineering Briefing Board": "Mühendislik Brifing Panosu", "LiDAR Survey": "LiDAR Tarama",
    "Under the Microscope": "Mikroskop Altında", "Archive Light Table": "Arşiv Işık Masası", "Security X-ray": "Güvenlik Röntgeni",
    "Radar Sweep Documentary": "Radar Taraması Belgeseli", "Thermal Camera": "Termal Kamera",
    "Data Storytelling": "Veri Hikâyeciliği", "Projection-Mapped Model": "Projeksiyonlu Maket", "Data Physicalization": "Verinin Nesneleşmesi",
    "Transit Map": "Metro Haritası", "3D Map Explainer": "3D Harita Anlatım", "Blob Simulation": "Figür Simülasyonu",
}
# Motion profile and default 3D mode per category (guide "motion", guide "3d"). Edit per style in overrides.json.
CATEGORY_PROFILE = {
    "Edit & Documentary":      {"cuts": "camera-led cuts: slide or push-through on motion", "rig": "editorial", "move_frames": [6, 10], "ease": "accelExit", "reveal": "wipe", "mblur": True, "three_d": "none", "music": "cinematic-pulse"},
    "Painting & Illustration": {"cuts": "slow drift, push-through with a focus pull", "rig": "calm", "move_frames": [14, 24], "ease": "softLand", "reveal": "focus", "mblur": True, "three_d": "none", "music": "ambient-wonder"},
    "Sketch & Board":          {"cuts": "draw-on, camera reframes", "rig": "editorial", "move_frames": [8, 12], "ease": "softLand", "reveal": "draw", "mblur": True, "three_d": "none", "music": "lofi-chill"},
    "Traditional Crafts":      {"cuts": "slow, staged, push-through", "rig": "calm", "move_frames": [16, 24], "ease": "softLand", "reveal": "focus", "mblur": True, "three_d": "B", "music": "ambient-wonder"},
    "Print & Printmaking":     {"cuts": "print-registration jumps with a slide", "rig": "editorial", "move_frames": [10, 14], "ease": "snapSettle", "reveal": "rise", "mblur": True, "three_d": "none", "music": "lofi-chill"},
    "Graphic & Type":          {"cuts": "snap zoom on the beat", "rig": "punchy", "move_frames": [4, 8], "ease": "snapSettle", "reveal": "track", "mblur": True, "three_d": "none", "music": "future-pop"},
    "Line Diagrams":           {"cuts": "continuous camera over one sheet", "rig": "calm", "move_frames": [10, 14], "ease": "softLand", "reveal": "draw", "mblur": True, "three_d": "A", "music": "cinematic-pulse"},
    "Cartoons":                {"cuts": "snap zoom, squash and stretch", "rig": "punchy", "move_frames": [6, 10], "ease": "snapSettle", "reveal": "rise", "mblur": True, "three_d": "B", "music": "future-pop"},
    "Games":                   {"cuts": "snap zoom, stepped motion", "rig": "punchy", "move_frames": [4, 8], "ease": "snapSettle", "reveal": "draw", "mblur": False, "three_d": "none", "music": "synthwave"},
    "Film & Tape":             {"cuts": "slide / whip pan, period grammar", "rig": "editorial", "move_frames": [8, 12], "ease": "accelExit", "reveal": "focus", "mblur": True, "three_d": "none", "music": "synthwave"},
    "Screens & Interfaces":    {"cuts": "one-take UI flythrough or snap zoom", "rig": "punchy", "move_frames": [8, 12], "ease": "snapSettle", "reveal": "rise", "mblur": True, "three_d": "A", "music": "future-pop"},
    "Light & Lines":           {"cuts": "continuous, slow builds", "rig": "calm", "move_frames": [12, 20], "ease": "softLand", "reveal": "draw", "mblur": True, "three_d": "none", "music": "synthwave"},
    "3D & Miniature":          {"cuts": "camera moves through one set", "rig": "calm", "move_frames": [12, 18], "ease": "softLand", "reveal": "rise", "mblur": True, "three_d": "A+B", "music": "future-pop"},
    "Instruments & Evidence":  {"cuts": "instrument sweeps, slide between readings", "rig": "editorial", "move_frames": [10, 16], "ease": "softLand", "reveal": "wipe", "mblur": True, "three_d": "A", "music": "cinematic-pulse"},
    "Data & Maps":             {"cuts": "continuous camera, chart builds", "rig": "editorial", "move_frames": [10, 14], "ease": "softLand", "reveal": "wipe", "mblur": True, "three_d": "A", "music": "cinematic-pulse"},
}
# Words in a style's own Sound palette → which of our library roles to search, and with what word.
SOUND_WORDS = [
    (r"\bclick|\btick|\bpen cap|\bkey(?:board|stroke)|\btyp", "UI/CLICK"),
    (r"\bwhoosh|\bswish|\bswoosh|\bswipe|\bwhip", "WHOOSH/SWISH"),
    (r"\briser|\bswell|\bbuild-?up|\bdrone", "DESIGNED/RISER"),
    (r"\bthump|\bthud|\bimpact|\bhit\b|\bslam|\bstamp|\bboom|\bknock", "IMPACT/HIT"),
    (r"\bchime|\bbell|\bding", "DESIGNED/CHIME"),   # not celesta / music box: those are the score, not SFX
    (r"\bpaper|\bpage|\brustle|\bscratch|\bpencil|\bcrayon|\bchalk|\bmarker", "FOLEY/PAPER"),
    (r"\bmetal|\bgear|\bmechan|\bspring|\bratchet|\bclank|\bshutter", "FOLEY/MECHANICAL"),
    (r"\bsiren|\balarm|\balert|\bbeep", "DESIGNED/ALERT"),
    (r"\bwind\b|\brain\b|\bambien|\broom tone|\bcity\b|\bbirds", "AMBIENCE"),
]


def section(md, title):
    m = re.search(rf"^## [\d. ]*{title}.*?$(.*?)(?=^## |\Z)", md, re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def sfx_families(palette):
    """3–4 families in the order the style's own palette names them (guide 'sound')."""
    hits = []
    for pat, role in SOUND_WORDS:
        m = re.search(pat, palette, re.I)
        if m:
            word = re.match(r"[\w-]+", palette[m.start():]).group(0).lower()   # the whole word: "mechanical", not "mechan"
            hits.append((m.start(), role, word))
    fams = [{"role": r, "query": w} for _, r, w in sorted(hits)]
    return fams[:4] or [{"role": "UI/CLICK", "query": ""}, {"role": "WHOOSH/SWISH", "query": ""}, {"role": "IMPACT/HIT", "query": ""}]


def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", s)).strip()


def _bullets(text, n=None):
    out = [_clean(m) for m in re.findall(r"^\s*(?:[-*]|\d+\.) (.+)$", text, re.M)]   # "- x" and "1. x" lists
    return out[:n] if n else out


GENERIC_CAMERA = [   # for the few styles whose STYLE.md has no camera section: a plain documentary vocabulary
    ("Hard cut on the beat", "pace, one fact per shot", "a list; a sequence of facts"),
    ("Slow push in on a detail", "attention, the thing that matters", "a key number; a mechanism; the moment of change"),
    ("Pan and scan across material", "reading a document or a scene", "evidence; a process in stages"),
    ("Split screen", "comparison, two states at once", "before/after; cause and effect"),
    ("Match cut on shape", "continuity of an idea", "a transformation; from one step to the next"),
    ("Pull back to the whole", "context, scale, the verdict", "an ending; the result"),
]


def edit_profile(md, cuts_default="Hard cuts on the beat"):
    """The style's own editing language, read from its STYLE.md, for plan_edit (router): which camera move serves what,
    how it cuts, how a label looks in this medium, how things move, and the medium's native moves."""
    cam_sec = section(md, r"[^\n]*camera") or section(md, r"[^\n]*edit")
    rows = [l for l in cam_sec.splitlines() if l.startswith("|") and not set(l) <= set("|-: ")]
    camera = []
    for l in rows[1:]:                                       # first row is the header
        cells = [_clean(c) for c in l.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0]:
            camera.append({"move": cells[0], "expresses": cells[1], "serves": cells[2] if len(cells) > 2 else ""})
    if not camera:                                           # editing-grammar styles: bullets instead of a table
        for b in _bullets(cam_sec):
            head, _, rest = b.partition(":") if ":" in b[:60] else b.partition(".")
            camera.append({"move": head.strip()[:80], "expresses": rest.strip()[:200], "serves": ""})
    if not camera:
        camera = [{"move": m, "expresses": e, "serves": v} for m, e, v in GENERIC_CAMERA]
    prose = _clean("\n".join(l for l in cam_sec.splitlines() if not l.startswith("|")))   # table rows are not sentences
    trans = [s.strip() for s in re.split(r"(?<=[.;])\s+", prose) if re.search(r"transition|cut|dissolve|wipe", s, re.I)]
    type_sec = section(md, r"[^\n]*(?:type|caption|subtitle)")   # non-capturing: section() reads group 1
    natives = []
    for b in re.findall(r"^\s*(?:[-*]|\d+\.) (.+)$", section(md, "Native moves"), re.M):
        m = re.match(r"\*\*(.+?)\*\*\s*[—:-]?\s*(.*?)(?:\*Fits content like:\*\s*(.*))?$", b)
        if m:
            natives.append({"name": _clean(m.group(1)).rstrip("."), "does": _clean(m.group(2)), "fits": _clean(m.group(3) or "")})
    if not natives:                                          # plain bullets: first clause is the name
        natives = [{"name": b.split(".")[0][:60], "does": b, "fits": ""} for b in _bullets(section(md, "Native moves"))]
    if not natives:                                          # a table of moves
        for l in section(md, "Native moves").splitlines()[2:]:
            cells = [_clean(c) for c in l.strip().strip("|").split("|")]
            if l.startswith("|") and cells[0]:
                natives.append({"name": cells[0], "does": "", "fits": ""})
    trans = [re.sub(r"^[-*]\s*", "", s) for s in trans] or [f"{cuts_default}."]
    return {"camera": camera[:14], "transitions": trans[:4], "labels": _bullets(type_sec, 4),
            "motion": _bullets(section(md, "Motion"), 4), "native_moves": natives[:10]}


def merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def music_md(s):
    sc = s.get("score") or {"genre": s["music"]}
    if sc["genre"] == "none":
        return f"**Music**: {sc.get('note', '')}. Build the diegetic sound instead (guide \"music\")."
    r = sc.get("render") or render_of(sc)
    synth = r["engine"] == "synth"
    band = ", ".join(f"{role} {v['voice']} (`{v['patch']}`)" if synth else f"{role} {v['voice']} (GM {v['gm']})" for role, v in r["band"].items())
    drums = ", ".join(f"{k} `{v}`" if synth else f"{k} (GM {v})" for k, v in r["drums"].items()) or "none: the comping instruments keep time"
    extra = "".join([f"; mode `{sc['mode']}`" if sc.get("mode") else "", f"; {sc['bpm']} BPM" if sc.get("bpm") else "",
                     f"; never {', '.join(sc['avoid'])}" if sc.get("avoid") else ""])
    tool = "kit `audio/synth.py` (Surge XT patches in DawDreamer)" if synth else "kit `audio/notes.py` (MusicXML + General MIDI)"
    return (f"**Music (made by default, guide \"music\")**: {sc.get('note', '')}. Write it as notes and play it with {tool}, "
            f"space `{r['space']}`. Band: {band}. Drums: {drums}. Groove reference `{sc['genre']}`{extra}. "
            "Band, engine and space are in style.json `stylist.score.render`; the **topic** picks mood, tempo and key. "
            "The customer can ask for another genre or no music.")


def layer_md(meta):
    s = meta["stylist"]
    fams = "\n".join(f"- `{f['role']}`" + (f" — search word \"{f['query']}\"" if f["query"] else "") for f in s["sfx_families"])
    lo, hi = s["motion"]["move_frames"]
    # ponytail: per-style motion_note (overrides.json) replaces the generic cinematic-rig wording for styles it contradicts
    note = s.get("motion_note")
    camera = ("Where the rules above name a camera move or transition, keep it. Music genre and level follow guide \"music\"." if note else
              """**Camera, motion and pacing** follow the Stylist cinematic standard (guide "motion"): a virtual camera that never rests, camera-based
transitions, idle life on everything on screen, three depth layers with parallax, staggered spring/ease-out entrances. Where the rules
above name a camera move or transition, keep it and run it on that rig. Music genre and level follow guide "music".""")
    profile = note or f"""camera rig `{s['motion'].get('rig', 'editorial')}` (kit `motion/motion_pro.js` `RIGS`); {s['motion']['cuts']}; typical move {lo}–{hi} frames; default curve `{s['motion']['ease']}`, never linear; text reveal `{s['motion']['reveal']}` (kit `reveal()`, words staggered, exits backwards); motion blur on fast camera moves {'on (`rig().mb`)' if s['motion']['mblur'] else 'off: this look stays crisp'}."""
    return f"""

---

## Stylist layer

Added by Stylist on top of the rules above. **The look** (palette, type, drawing, materials, atmosphere) is the rules above, unchanged.
{camera}

**SFX families** (call `search_sfx` with these; 3–4 families for the whole film, guide "sound"):
{fams}

**Motion profile**: {profile} Gates G0–G6 before the full render.

{music_md(s)}

**3D mode**: {s['three_d']} (guide "3d": none = 2D only, A = SVG extruded, B = skeletonless / rigid joints; never outside 3D sites).

**Formats**: {", ".join(s['aspects'])}.
""" + (f"\n**Notes from Stylist**: {s['notes']}\n" if s.get("notes") else "")


def main():
    lemo = json.loads((LIB / "styleboard" / "catalog.json").read_text("utf8"))
    OUT.mkdir(exist_ok=True)
    made = 0
    for c in lemo:
        src, dst = LIB / "styles" / c["slug"], OUT / c["slug"]
        dst.mkdir(exist_ok=True)
        old = dst / "style.json"
        if old.exists() and json.loads(old.read_text("utf8")).get("source") == "stylist":
            continue   # we took this one over; never overwrite it
        md = (src / "STYLE.md").read_text("utf8")
        # relative links (DEMO.md, ../../DIRECTOR.md) would break here: point them at the library on GitHub
        base = f"https://github.com/lemomo-ai/lemo-opuscar/blob/main/styles/{c['slug']}/"
        md = re.sub(r"\]\((?!https?:|#|mailto:)([^)\s]+)\)", lambda m: f"]({base}{m.group(1)})", md)
        prof = CATEGORY_PROFILE[c["cat_en"]]
        meta = merge(json.loads((src / "style.json").read_text("utf8")), {
            "source": "lemo-opuscar", "lemo_slug": c["slug"], "license": "MIT (lemo-opuscar docs), Stylist layer ours",
            "name_tr": NAME_TR.get(c["en"], c["en"]), "category_tr": CATEGORY_TR[c["cat_en"]], "category_en": c["cat_en"],
            "stylist": {"sfx_families": sfx_families(section(md, "Sound")),
                        "motion": {k: prof[k] for k in ("cuts", "rig", "move_frames", "ease", "reveal", "mblur")},
                        "three_d": prof["three_d"], "music": score_of(dst.name, prof)["genre"], "score": score_of(dst.name, prof), "aspects": ["16:9", "9:16", "1:1"], "hidden": False, "notes": "",
                        "edit": edit_profile(md, prof["cuts"])},
        })
        ov = dst / "overrides.json"
        if ov.exists():
            meta = merge(meta, json.loads(ov.read_text("utf8")))
        (dst / "style.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), "utf8")
        head = f"<!-- Stylist edition of lemo-opuscar `{c['slug']}` (github.com/lemomo-ai/lemo-opuscar, MIT). Regenerate with tools/import_styles.py; edit overrides.json, not this file. -->\n"
        (dst / "STYLE.md").write_text(head + md + layer_md(meta), "utf8")
        made += 1
    write_catalog()
    print(f"{made} lemo styles customised -> {OUT}")


def relayer():
    """Re-apply the category profile and the Stylist layer to styles/ without the lemo library (keeps all other fields)."""
    made = 0
    for d in sorted(p for p in OUT.iterdir() if (p / "style.json").exists()):
        meta = json.loads((d / "style.json").read_text("utf8"))
        if meta.get("source") != "lemo-opuscar":
            continue
        prof = CATEGORY_PROFILE[meta["category_en"]]
        meta["stylist"]["motion"] = {k: prof[k] for k in ("cuts", "rig", "move_frames", "ease", "reveal", "mblur")}
        meta["stylist"]["score"] = score_of(d.name, prof); meta["stylist"]["music"] = meta["stylist"]["score"]["genre"]
        ov = d / "overrides.json"
        if ov.exists():
            meta = merge(meta, json.loads(ov.read_text("utf8")))
        md = (d / "STYLE.md").read_text("utf8").split("\n\n---\n\n## Stylist layer")[0]
        (d / "style.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), "utf8")
        (d / "STYLE.md").write_text(md + layer_md(meta), "utf8")
        made += 1
    write_catalog()
    print(f"{made} styles re-layered -> {OUT}")


def write_catalog():
    rows = []
    for d in sorted(p for p in OUT.iterdir() if (p / "style.json").exists()):
        m = json.loads((d / "style.json").read_text("utf8"))
        if m.get("stylist", {}).get("hidden"):
            continue
        rows.append({"slug": d.name, "name_en": m.get("en", d.name), "name_tr": m.get("name_tr", m.get("en", d.name)),
                     "name_cn": m.get("cn", ""), "category_en": m.get("category_en", ""), "category_tr": m.get("category_tr", ""),
                     "pitch": m.get("line", ""), "uses": m.get("uses", []), "source": m.get("source", "stylist"),
                     "needs_images": "image-generation" in m.get("needs", []), "three_d": m.get("stylist", {}).get("three_d", "none")})
    (OUT / "catalog.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), "utf8")


if __name__ == "__main__":
    if "--relayer" in sys.argv:
        sys.exit(relayer())
    if not (LIB / "styleboard" / "catalog.json").exists():
        sys.exit(f"lemo-opuscar not found at {LIB}; set LEMO_OPUSCAR_HOME")
    main()
