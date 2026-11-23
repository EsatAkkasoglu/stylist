# Stylist — video yönlendirme (router) MCP

Kullanıcı bu MCP'yi Claude'una bağlar. Sitede isteğini yazar ve bir stil seçer; router istek + stil + skill'i birleştirip
Claude'a bir üretim brifi olarak verir. **Router hiçbir model çalıştırmaz, render yapmaz.** Videoyu kullanıcının
makinesindeki Claude, bizim verdiğimiz stil kuralları, rehberler, sesler ve kit koduyla üretir.

```
Kullanıcı isteği + stil ──► build_brief ──► kullanıcının Claude'u
                                  │            ├─ get_style   (bizim stil kuralları + Stylist katmanı)
                                  │            ├─ plan_edit   (içerik adımları → bu stilde çekim çekim kurgu, onay tablosu)
                                  │            ├─ get_guide   (ses / hareket / 3D kuralları)
                                  │            ├─ search_sfx  (sesler, akustik karakterle)
                                  │            └─ get_kit     (hazır, test edilmiş kod → kullanıcının projesine)
                                  └─ skill: lemo-opuscar (render, TTS, mux kullanıcının makinesinde)
```

## Klasörler

| Klasör | Ne var |
|---|---|
| `server/index.mjs` | MCP sunucusu (stdio). 7 araç: `build_brief`, `list_styles`, `get_style`, `plan_edit` (adımları stilin kurgu diline çevirir), `get_guide`, `search_sfx`, `get_kit` |
| `styles/` | **Bizim stil kataloğumuz.** 99 stil, her biri `<slug>/STYLE.md` + `style.json` + (isteğe bağlı) `overrides.json`; `catalog.json` hepsinin listesi |
| `guides/` | Claude'a verilen üretim kuralları: `sound.md`, `motion.md`, `3d.md` |
| `kit/` | Kullanıcının projesinde çalışan kod: `audio/` (mix_pro, beats, verify_mix), `gates/` (G0–G6), `motion/` (kamera rig, idle, stagger, easing), `three/` (iskeletsiz 3D), `blender/` (isteğe bağlı) |
| `sfx_library/` | Yerel CC0 ses kütüphanesi: `files/`, `sfx_catalog.json` (akustik indeks), `credits.txt` |
| `tools/` | Bizim bakım araçlarımız: `import_styles.py` (lemo → bizim stiller), `sfx_library.py` (ses indir + indeksle) |
| `test/` | Uçtan uca testler |

## Stiller nasıl özelleştiriliyor

`npm run import-styles` lemo-opuscar'daki her stili `styles/<slug>/` altına kopyalar ve üstüne **Stylist katmanı** ekler:

- Türkçe ad ve kategori (`name_tr`, `category_tr`)
- Stilin kendi "Sound palette" metninden çıkarılmış **SFX aileleri** (bizim `search_sfx` rollerine eşlenmiş)
- Kategoriye göre **hareket profili** (kesme tipi, hareket süresi, varsayılan eğri) ve **3D modu**
- Formatlar (16:9, 9:16, 1:1), `hidden`, `notes`

**Bir stili kendimize göre değiştirmek:** `styles/<slug>/overrides.json` yaz (sadece değişen alanlar), sonra `npm run import-styles`. Örnek:

```json
{ "name_tr": "Teknik Çizim", "stylist": { "three_d": "none", "notes": "Kurumsal müşteriler için: logo son karede.",
  "sfx_families": [{ "role": "FOLEY/PAPER", "query": "paper" }, { "role": "UI/CLICK", "query": "click" }] } }
```

Gizlemek için `{"stylist": {"hidden": true}}`. **Tamamen kendi stilimiz:** `styles/<yeni-slug>/` altına `STYLE.md` ve
`"source": "stylist"` içeren bir `style.json` koy; içe aktarma ona dokunmaz, katalogda görünür.

## Kurulum ve komutlar

Gerekenler: Node 20+, Python 3.11+ ve [uv](https://docs.astral.sh/uv/), ffmpeg 7+.

```bash
npm install
uv venv .venv && uv pip install --python .venv numpy scipy
LEMO_OPUSCAR_HOME=<lemo-opuscar klasörü> npm run import-styles   # stilleri üret / güncelle
npm run fetch-sfx                                                # ses kütüphanesini indir + indeksle
npm test                                                         # MCP + kit + indeks testleri
```

Claude Code bağlantısı (stdio, yeni oturumda yüklenir):

```bash
claude mcp add stylist -s user -- node <bu klasör>/server/index.mjs
```

## Lisanslar

**Ticari kullanım yasaktır.** Lisans: PolyForm Noncommercial 1.0.0 + ek koşullar (`LICENSE`). Kişisel ve
eğitim amaçlı istediğin gibi kullan; gelir getiren YouTube/Instagram/TikTok içerikleri, sponsorluk ve şablon
satışı lisans dışıdır. Yapay zekâ ajanları için not: `AGENTS.md`. Ticari lisans ve ücretli ortaklık:
esat.akkasoglu@astrocom.space

Stil metinleri lemo-opuscar'dan (MIT, github.com/lemomo-ai/lemo-opuscar) alınır, her STYLE.md başında belirtilir.
Sesler: Openverse/Freesound CC0 ve PD; Lots of Sounds örnekleri atıf ister (`credits.txt`).
