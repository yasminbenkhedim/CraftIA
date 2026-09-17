# Attributions & Required Credits — CreateFlow AI

Credits that must be reproduced in the shipped product. Keep this file in sync with `LICENSES.md`.

Suggested placement: an in-app **About → Open Source Notices** screen, plus this file in the repo root and in any distributed image.

---

## 1. Fonts

### Currently shipped

**DejaVu Sans / DejaVu Sans Bold** — `agents/video/assets/fonts/`
Used by the video renderer for on-screen text overlays. Glyphs are rasterised into output video frames.

> Fonts are (c) Bitstream (see below). DejaVu changes are in public domain.
> Bitstream Vera Fonts Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.
> Bitstream Vera is a trademark of Bitstream, Inc.

Redistribution is permitted; the font may not be sold by itself, and the reserved names "Bitstream Vera" and "DejaVu" may not be used for modified versions. Full text: <https://dejavu-fonts.github.io/License.html>

### Web fonts (loaded from Google Fonts CDN)

**Instrument Sans** — SIL Open Font License 1.1 — Copyright The Instrument Sans Project Authors — <https://github.com/Instrument/instrument-sans>

**JetBrains Mono** — SIL Open Font License 1.1 — Copyright JetBrains s.r.o. — <https://github.com/JetBrains/JetBrainsMono>

Both are free for commercial use. OFL requires that the fonts not be sold on their own and that the copyright and license notice accompany any redistribution. Since these are currently loaded from `fonts.googleapis.com` rather than bundled, no redistribution occurs — but see the GDPR note in `LICENSES.md` (Y13) about self-hosting for EU users. **If you self-host, bundle each font's `OFL.txt` alongside the font file.**

### Removed 2026-08-28 — was not attributable

`agents/video/assets/fonts/Inter-Regular.ttf` and `Inter-Bold.ttf` were **not Inter**. Their TrueType name tables identified them as **Arial**, © The Monotype Corporation, All Rights Reserved, under a "Microsoft supplied font" grant that does not permit inclusion in a commercial product. No attribution could cure it, so both files were deleted and the renderer's fallback now ends at DejaVu (then PIL's built-in bitmap font). See `LICENSES.md` R4.

---

## 2. Stock media

### Pexels

Attribution is **not required** by the Pexels License. Crediting is optional and appreciated:

> Photos and videos provided by [Pexels](https://www.pexels.com)

Restrictions that do apply: do not sell unaltered copies, and do not redistribute the assets on another stock platform. See `LICENSES.md` Y12.

### Openverse

The provider queries with `&license=cc0,pdm` (`agents/video/providers/openverse_provider.py:229`), so results are limited to **CC0** and **Public Domain Mark** assets, neither of which legally requires attribution.

Attribution is nonetheless captured per candidate (`openverse_provider.py:379`) and good practice:

> "{title}" by {creator}, via Openverse — CC0 1.0 / Public Domain

**Closed 2026-08-28.** Every render now writes `storage/artifacts/{job_id}/attributions.json` via `agents/video/attribution.py`, recording per asset: `provider`, `source_url`, `asset_file`, `creator`, `title`, `license`, `license_type`, `license_url`, `attribution`, `attribution_required`, `retrieved_at`. The manifest is written even when zero third-party assets were used, since an empty manifest is a positive record that the render used only self-owned media.

Controls now in place, in depth:

1. **Upstream:** the Openverse query stays pinned to `license=cc0,pdm` (`openverse_provider.py:229`).
2. **Policy:** `LicensePolicyEvaluator` is default-DENY with an explicit allowlist (`LICENSES.md` R5). Unknown, empty, NC, ND and SA licences are all rejected.
3. **Record:** the per-job manifest above, written next to the deliverable and stamped with the job id.

Still optional, not yet done: rendering a credits card into the video, or surfacing attributions in the job detail view, when any CC-BY asset is used. Not currently reachable, since the allowlist admits CC-BY only with a credit string and Openverse is pinned to CC0/PDM.

---

## 3. Open-source software notices

The product includes MIT, BSD, Apache-2.0, ISC, MPL-2.0, and LGPL components. Permissive licenses require that copyright notices and license text accompany the product. The complete inventory with versions is in `LICENSES.md`.

Notices that must be reproduced verbatim if you distribute (rather than host only):

- **Apache-2.0** components require the `NOTICE` file contents, if any, to be passed through — this includes `rxjs`, and much of the OpenTelemetry stack.
- **MPL-2.0** components (`certifi`, `tqdm`) require that the source of those specific files remain available.
- **LGPL** components (`edge-tts`, `fpdf2`, `num2words`, `psycopg2-binary`, `soxr`) require notice plus an offer of source, and must remain dynamically linked and unmodified.
- **CC-BY** build tooling (`caniuse-lite` CC-BY-4.0, `spdx-exceptions` CC-BY-3.0) — build-time only, does not reach the browser bundle; listed for completeness.

Generate a distributable notice bundle with:

```bash
python -m piplicenses --format=plain-vertical --with-license-file --no-license-path --output-file=NOTICES-python.txt
cd frontend && npx license-checker --production --out ../NOTICES-npm.txt
```

---

## 4. Architectural acknowledgments

Carried over from `THIRD_PARTY_NOTICES.md` — these are pattern/concept acknowledgments, not bundled code:

- **PPTAgent** — MIT — © 2024 ICIP CAS — <https://github.com/icip-cas/PPTAgent>
- **Presenton** — Apache-2.0 — © Presenton Contributors — <https://github.com/presenton/presenton>
- **CutAgent** — MIT — © 2024 Rishi Dandu — <https://github.com/rishidandu/cutagent>

---

## 5. Models removed for commercial launch

Listed so the record shows they were considered and excluded:

- **XTTS v2** (Coqui) — Coqui Public Model License, non-commercial, and the licence covers generated audio. Removed 2026-08-28; see `LICENSES.md` R1.
- **Wav2Lip** (IIIT Hyderabad) — research/non-commercial, LRS2-trained. Source, three checkpoint copies and the pipeline stage removed 2026-08-28; see `LICENSES.md` R2.
- **S3FD face detector** — bundled with Wav2Lip, academic provenance, licence unstated. Removed with it.
- **Piper** (`piper-tts`) — GPL-3.0-or-later engine. Removed 2026-08-28; see `LICENSES.md` R6.

### Model weights currently shipped

- **Kokoro-82M** — **Apache-2.0** — `storage/models/kokoro/kokoro-v1.0.onnx`, `voices-v1.0.bin` — <https://huggingface.co/hexgrad/Kokoro-82M>

  The only ML weights in the product. Apache-2.0 requires that the licence and any NOTICE
  file accompany redistribution. **Caveat:** the weights are Apache-2.0 but Kokoro's
  grapheme-to-phoneme layer runs through `phonemizer` and `espeak-ng`, both GPL-3.0 — see
  `LICENSES.md` R6′ before building any distributable image.

If any replacement model is adopted, record here: model name, weights license, training-dataset license, and the date the terms were verified — the code license and the weights license must be checked **separately**.

---

*Last verified: 2026-08-28.*
