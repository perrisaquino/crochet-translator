# Photo-to-Amigurumi Pattern Generator — Design Spec

**Date:** 2026-04-07
**Project:** crochet-translator (perrisaquino/crochet-translator)
**Status:** Approved

---

## Overview

Extend the existing Crochet Notation Translator with a Photo-to-Amigurumi mode. The user drags and drops photos of a real-world object, the system reconstructs a 3D mesh via photogrammetry (TripoSR), converts the mesh to an amigurumi crochet pattern using the AmiGo algorithm, and outputs a downloadable PDF pattern.

The core value proposition: take a photo of anything and get a crocheable amigurumi pattern. No existing tool does this as a local, offline pipeline.

---

## Architecture

The existing `index.html` (vanilla JS + Three.js) is extended with a new Photo mode tab. A Python FastAPI backend runs locally on `localhost:8000` and handles all heavy computation. The frontend communicates via `fetch()`. No changes to existing Profile, Labubu, or Grid Paint modes.

### File Structure

```
crochet-translator/
├── index.html                  ← existing UI, minor additions only
├── server.py                   ← new FastAPI entry point (also serves index.html as static)
├── pipeline/
│   ├── reconstruct.py          ← TripoSR: photos → .obj mesh
│   ├── mesh_repair.py          ← Open3D: cleanup, watertight check, decimate
│   └── pattern_gen.py          ← AmiGo algorithm: mesh → pattern JSON
├── templates/
│   └── pattern.html            ← Jinja2 template for PDF export
├── tmp/                        ← temp mesh storage, cleared on server restart
└── requirements.txt
```

**Note:** FastAPI must serve `index.html` as a static file (via `StaticFiles`) so that `fetch()` calls to `localhost:8000` are same-origin. Opening `index.html` directly as `file://` will cause CORS errors.

**Note:** `index.html` needs one additional Three.js script import for mesh loading:
```html
<script src="https://unpkg.com/three@0.139.0/examples/js/loaders/OBJLoader.js"></script>
```

### API Endpoints

| Method | Endpoint | Input | Output |
|--------|----------|-------|--------|
| POST | `/api/reconstruct` | multipart photos + height_cm | `{ job_id }` |
| GET | `/api/job/{job_id}` | job_id | `{ status, step, mesh_url }` |
| GET | `/api/mesh/{job_id}` | job_id | `.obj` file for Three.js |
| POST | `/api/pattern` | `{ job_id, gauge, yarn_weight, hook_size }` | pattern JSON |
| GET | `/api/export/pdf/{job_id}` | job_id | PDF download |

### Data Flow

```
User drops photos + enters height
  → POST /api/reconstruct
    → TripoSR: photos → raw mesh (30-90s on M1)
    → Open3D: hole fill, decimate, watertight check
    → store mesh.obj to temp dir, return job_id

Frontend polls GET /api/job/{job_id} every 2s
  → updates step progress overlay in center panel
  → on complete: loads mesh.obj into Three.js viewer

User reviews 3D mesh, clicks Generate Pattern
  → POST /api/pattern
    → AmiGo algorithm: mesh + gauge → pattern JSON
  → Right panel renders round-by-round instructions

User clicks Download PDF
  → GET /api/export/pdf/{job_id}
    → WeasyPrint renders pattern.html template → PDF
```

---

## Pipeline Detail

### Stage 1 — 3D Reconstruction (reconstruct.py)

- **Library:** TripoSR (Hugging Face, MIT license)
- **Input:** 3-15 photos, real-world height in cm
- **Process:** Run TripoSR inference via Apple MPS (Metal Performance Shaders) for M1 GPU acceleration
- **Scale fix:** After reconstruction, apply uniform scale so bounding box height matches the user-provided `height_cm`
- **Output:** Raw `.obj` mesh

### Stage 2 — Mesh Repair (mesh_repair.py)

- **Library:** Open3D
- **Steps:**
  1. Load mesh, check manifold/watertight status
  2. Fill holes (required for AmiGo — must be closed mesh)
  3. Decimate to ~5,000-10,000 triangles (balance between detail and compute)
  4. Smooth normals
- **Output:** Clean, watertight `.obj` mesh

### Stage 3 — Pattern Generation (pattern_gen.py)

- **Algorithm:** Re-implementation of AmiGo (Edelstein et al., ACM 2022) in Python + NumPy
- **Input:** Watertight mesh + gauge (stitches per 10cm) + seed point (default: top of bounding box)
- **Core steps:**
  1. Compute geodesic distance from seed point across mesh surface
  2. Generate crochet graph: concentric "rounds" at equal geodesic distances
  3. Detect curvature changes → place `inc` (increase) or `dec` (decrease) stitches
  4. Segment mesh into separate crochetable components where curvature is too high for a single piece
  5. Translate graph to notation: `sc`, `inc`, `dec` with stitch counts per round
- **Output:** Pattern JSON `{ parts: [{ name, rounds: [{ number, instructions, stitch_count }] }] }`

### Stage 4 — PDF Export (templates/pattern.html)

- **Libraries:** Jinja2 + WeasyPrint
- **Template contents:**
  - Pattern title + finished dimensions
  - Materials: yarn weight, hook size, gauge, stuffing
  - Abbreviations key
  - Round-by-round instructions per part
  - Assembly notes (which parts join where)
- **Output:** Downloadable PDF

---

## UI Changes (index.html)

### Header

Add one new mode tab: `Photo` with SVG camera icon. No emoji. Follows existing `.mode-tab` styling. Existing tabs unchanged.

### Left Panel — Photo Mode

Three zones, same panel width (`272px`), same warm cream background:

**Zone 1 — Photos**
- Dashed border drag-drop area, terracotta accent `#B56B45` on hover
- Photo thumbnail strip below drop zone (removable per-photo)
- Guidance text: "Take 8-15 photos walking around your object"

**Zone 2 — Scale Reference**
- Label: "Object height"
- Number input + "cm" unit label
- Required — red outline if empty when Generate is clicked

**Zone 3 — Yarn**
- Yarn weight dropdown: Lace / Fingering / Sport / DK / Worsted / Bulky
- Hook size dropdown: standard mm sizes 1.5mm through 10mm
- Gauge field: auto-populated from weight+hook lookup table, user-overridable
- "Generate Pattern" button (`.btn-a` style) — disabled until photos + height are filled

### Center Panel — Photo Mode

Existing Three.js canvas unchanged. During processing, semi-transparent overlay shows step progress:

```
Analyzing photos         [done]
Building 3D model        [active ←spinner]
Cleaning mesh            [pending]
Calculating pattern      [pending]
```

Overlay fades out on completion. Three.js mesh loads automatically.

### Right Panel — Photo Mode

Same `.pat-scroll` container, amigurumi-specific format:

```
Head
────
Magic Ring
Rnd 1:  6 sc in MR  (6)
Rnd 2:  inc × 6  (12)
Rnd 3:  [sc, inc] × 6  (18)
...

Body
────
...
```

Footer: existing "Copy Pattern" button + new "Download PDF" button.

---

## Design System

Follows existing app design language — no changes to color palette or typography:

- **Background:** `#F2EBD9`
- **Panel:** `#FDFAF2`
- **Accent:** `#B56B45` (terracotta)
- **Text:** `#241C0C`
- **Fonts:** Cormorant Garamond (display) / DM Sans (body) / DM Mono (measurements/code)
- **Interactions:** 150-200ms transitions, `cursor-pointer` on all clickables, disabled state on Generate button while processing
- **Icons:** SVG only (no emoji)

---

## Known Constraints

| Constraint | Detail |
|------------|--------|
| M1 Air thermal throttling | TripoSR reconstruction may take 60-90s; M1 Air may throttle under sustained GPU load. Progress overlay is critical UX to prevent perceived freeze. |
| Mesh quality depends on photos | Bad lighting, reflective surfaces, or fewer than 5 photos degrade mesh quality. Warn user in UI if mesh repair detects significant holes. |
| AmiGo algorithm complexity | The geodesic + curvature step is the hardest to implement. Start with simple convex shapes (spheres, ovals) before testing complex objects. |
| Stuffing compensation | v1 does not compensate for stuffing expansion. Patterns may need slight manual adjustment on first test. Flag this in the PDF notes. |
| Concave shapes | Legs, handles, protrusions require multi-part segmentation. v1 may produce single-part patterns for complex shapes — validate with simple objects first. |

---

## Phasing

**v1 (this spec):** Photo drag-drop → TripoSR → mesh → AmiGo pattern → PDF. Desktop only.

**v2:** STL/OBJ file import as alternative input path (skips photogrammetry, exact dimensions from file).

**v3:** Mobile — SwiftUI iOS app with live camera interface, calls the same FastAPI backend.

---

## References

- AmiGo paper: https://dl.acm.org/doi/fullHtml/10.1145/3559400.3562005
- TripoSR: https://huggingface.co/stabilityai/TripoSR
- Open3D: http://www.open3d.org/
- Craft Yarn Council gauge standards: https://www.craftyarncouncil.com/standards/yarn-weight-system
