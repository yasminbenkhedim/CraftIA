# CreateFlow AI — Commercial License Compliance Report

> # ⚠️ DEPLOYMENT MODEL: HOSTED SaaS ONLY
>
> **CreateFlow AI is delivered exclusively as a hosted service.** Clients use the product
> through our website. We never ship source code, Docker images, Helm charts, Kubernetes
> manifests, installers, or any build artifact to a customer or third party.
>
> **This is not a preference — it is the legal basis for the current compliance position.**
> Several dependencies are GPL/LGPL-licensed. Their copyleft obligations are triggered by
> *distribution*, and hosting a service is not distribution. Under this model they impose
> nothing. **The moment any build is handed to a customer — an on-prem install, a
> container image, a "run it yourself" evaluation copy, a Helm chart, even a one-off ZIP
> for a large client — those obligations activate and this product becomes non-compliant.**
>
> **Before agreeing to any on-prem, self-hosted, white-label, air-gapped, or "we need it in
> our own cloud" deal, re-read this document and budget the remediation.** The blocking
> item is R6′ (`phonemizer` / espeak-ng, GPL-3.0) and it has no quick fix.
>
> **One exception that hosting does NOT cure:** the **AGPL**. Its §13 network clause is
> triggered by users interacting with the software *over a network*, which is exactly what
> a SaaS does. AGPL dependencies are forbidden here regardless of deployment model — that
> is why PyMuPDF had to be removed (R3) rather than tolerated. **Never add an AGPL
> dependency to this project.**

**Original audit:** 2026-08-28 · **Remediation completed:** 2026-08-28 · **Deployment model confirmed:** 2026-08-29
**Scope:** All Python and npm dependencies, ML model weights, bundled fonts, and stock-media sources.

> **This is an engineering audit, not legal advice.** The hosted-only conclusions below should be confirmed by counsel before commercial launch.

## How this was produced

| Surface | Tool | Result |
|---|---|---|
| Python | `pip-licenses 5.5.5` | 167 packages |
| npm | `license-checker` | 839 packages (+1 own) |
| Model weights | manual inspection of disk + upstream license text | 1 artifact |
| Fonts | TrueType `name` table extraction | 2 files |

---

## Compliance status

### For the hosted-SaaS model actually in use: **0 RED items.**

### If the product were ever distributed: **1 RED item** (R6′).

| # | Item | Original | Hosted-SaaS status |
|---|---|---|---|
| R1 | XTTS v2 weights (CPML, non-commercial) | 🔴 | 🟢 **Resolved** — weights deleted, engine removed, Kokoro-82M now default |
| R2 | Wav2Lip (research-only, LRS2) | 🔴 | 🟢 **Resolved** — source, 3 checkpoint copies, face detector deleted |
| R3 | PyMuPDF (AGPL-3.0) | 🔴 | 🟢 **Resolved** — renderer ported to reportlab (BSD), package uninstalled |
| R4 | "Inter" fonts that were really Arial | 🔴 | 🟢 **Resolved** — deleted; DejaVu is the only bundled face |
| R5 | Media filter accepting NC/ND content | 🔴 | 🟢 **Resolved** — rewritten default-deny; per-job attribution manifest added |
| R6 | piper-tts (GPL-3.0) | 🔴 | 🟢 **Resolved** — removed |
| R6′ | `phonemizer` / espeak-ng (GPL-3.0) | — | 🟢 **Compliant, hosted-only** — see below. 🔴 **if ever distributed.** |

R1–R4 are resolved unconditionally: the offending code and weights no longer exist in the
product, so no deployment model can bring them back. R5 is a code fix, equally
unconditional. Only **R6′ is conditional**, and its condition is the deployment model
stated at the top of this document.

### A correction worth keeping on the record

An earlier revision of this report claimed a RED count of 0 *before* the deployment model
was settled — and that claim was false at the time, for a reason worth preserving. The
classifier matched only the SPDX spelling `GPL-3.0-or-later`, so it missed phonemizer's
actual metadata string, `GNU General Public License v3 or later (GPLv3+)`. That string
then reached a dual-license branch testing for the substring `OR`, which matches the
"**or** later" in the version phrase — and phonemizer was reported **GREEN**. One
unanchored pattern turned a GPL-3.0 dependency into a green tick.

The count is 0 again now, but for a completely different and legitimate reason: the
dependency is unchanged and still GPL-3.0, and it is compliant because we do not
distribute. The distinction matters — the first zero was a measurement bug, this one is a
documented legal position with a stated condition. The classifier now matches GPL
generally, subtracts LGPL first, and requires a named permissive alternative before
honouring a dual-license claim.

---

## 🟢 R6′. phonemizer 3.4.0 — GPL-3.0-or-later — compliant under hosted SaaS

**Decision (2026-08-29): accept, hosted-only.** Option 1 of the three presented.

- **What it is:** a hard dependency of `kokoro-onnx`, which runs the default TTS engine.
  It performs grapheme-to-phoneme conversion, wrapping `espeak-ng` (also GPL-3.0).
- **Verified on the live path:** synthesising a line imports both `phonemizer` and
  `espeakng-loader`. It is not an optional extra — Kokoro cannot speak without it.
- **Why the Apache-2.0 headline is only half the story:** Kokoro-82M's *weights* are
  genuinely Apache-2.0, and that is what removed the R1 blocker. The phoneme layer is a
  separate component with a separate licence. The reference `kokoro` package has identical
  exposure via `misaki[en]` → `espeakng-loader` + `phonemizer-fork`, so this is a property
  of Kokoro, not of choosing the ONNX runtime.

**Why hosting makes this compliant.** GPL-3.0's obligations — providing corresponding
source, passing on the licence — attach to *conveying* the work (GPL-3.0 §4–6). Running
software on your own servers and letting users interact with the results over a network is
not conveying. Unlike the AGPL, GPL-3.0 contains no network-use clause. So while
CreateFlow AI is hosted-only, phonemizer imposes no obligation on us.

**What would flip this back to RED — treat each as a launch blocker:**

- Shipping a Docker image, Helm chart, or Kubernetes manifest to a customer
- Any on-premises, self-hosted, or air-gapped deployment
- White-label or OEM builds a partner runs themselves
- Handing over source or a build as part of an acquisition, escrow, or due-diligence process
- Bundling the backend into a desktop or mobile application
- Publishing the repository, or the container image, publicly

**If that day comes, the options are:** replace the G2P layer with a permissively-licensed
lexicon (CMUdict-based — real work, and it changes pronunciation on unusual words); move
to a commercial TTS API; or negotiate/verify separate terms. None is a quick fix, which is
why it should be priced into any such deal before it is signed.

**Net effect of the TTS migration, stated plainly:** it removed a *non-commercial* blocker
(XTTS/CPML) that was absolute and unfixable, since Coqui dissolved in January 2024 and no
counterparty exists to sell an exception. It did not remove GPL exposure — that moved from
the engine (piper-tts) to the phoneme layer. Under hosted-only both are moot; under
distribution both would block.

---

## 🟡 YELLOW — conditions apply

Under hosted-only deployment, the LGPL entries below impose **no obligations** for the same
reason as R6′ — no distribution, no trigger. They are listed because they would activate
under a distribution model, and because notice retention is good practice regardless.

| Package | Version | License | Note (hosted-only) |
|---|---|---|---|
| `edge-tts` | 7.2.8 | LGPL-3.0 | Fallback engine. Licence is moot; the **ToS** issue below is not. |
| `fpdf2` | 2.8.7 | LGPL-3.0-only | LaTeX report agent (`agents/latex/agent.py:352`). No obligation. |
| `psycopg2-binary` | 2.9.12 | LGPL | No obligation. |
| `num2words` | 0.5.14 | LGPL | Transitive. No obligation. |
| `soxr` | 1.1.0 | LGPL-2.1-or-later | Transitive (librosa). No obligation. |
| `espeakng-loader` | 0.2.4 | UNKNOWN (bundles GPL-3.0 espeak-ng) | Covered by R6′. |
| `certifi` | 2026.7.22 | MPL-2.0 | File-level copyleft; unmodified. |
| `tqdm` | 4.70.0 | MPL-2.0 AND MIT | Unmodified. |
| `torchcodec` | 0.16.0 | UNKNOWN | Upstream BSD-3-Clause; metadata missing. Verify and record. |
| `kokoro-onnx` | 0.6.1 | UNKNOWN | Upstream MIT; metadata missing. Verify and record. |
| `caniuse-lite` | — | CC-BY-4.0 | Build-time only, never reaches the browser bundle. |
| `spdx-exceptions` | — | CC-BY-3.0 | Build-time only. |

### Y6. edge-tts — a terms-of-service risk that hosting does NOT cure

This is the one YELLOW item the hosted-only model does not help with, and it is worth more
attention than its licence. `edge-tts` is LGPL-3.0, which is moot for us. The problem is
that it works by calling Microsoft Edge's **private, undocumented** Read-Aloud endpoint
with a hard-coded client token and no API agreement. Microsoft's terms do not contemplate
third-party commercial resale, and the endpoint can be changed or blocked without notice.
That is a contractual and business-continuity exposure, not a copyright one, so no
deployment model resolves it. It is now the *fallback* rather than the default, which
limits blast radius. **Recommend legal review, and consider removing the fallback entirely.**

### Y13. Google Fonts CDN — GDPR

`frontend/src/styles.css:7` loads Instrument Sans and JetBrains Mono from
`fonts.googleapis.com`. Both are OFL-1.1 and commercially safe. However a German court
(LG München I, 3 O 17493/20) held that transmitting visitor IPs to Google Fonts without
consent violates GDPR. Since clients reach the product through our website, **their
end-users' browsers make that request** — this one is squarely in scope for a hosted
product with EU users. Self-host both files.

### Y12. Pexels

Commercial use allowed; attribution not required. Prohibited: selling unaltered copies, and
redistributing assets on another stock platform. Compositing clips into edited videos is
squarely permitted. Watch for scope creep: exposing raw downloaded clips as a browsable
library would edge toward prohibited redistribution.

---

## 🟢 GREEN — no action

156 of 167 Python packages and 837 of 839 npm packages are permissive (MIT, Apache-2.0,
BSD-2/3-Clause, ISC, 0BSD, PSF, CC0, Zlib, BlueOak). This includes the entire shipped
frontend runtime — `@angular/*` (MIT), `rxjs` (Apache-2.0), `tslib` (0BSD), `zone.js`
(MIT) — and the core backend (FastAPI, SQLAlchemy, Pydantic, uvicorn, Celery, NumPy,
PyTorch, OpenCV, Pillow, reportlab).

**Fonts:** `DejaVuSans.ttf` / `DejaVuSans-Bold.ttf` — Bitstream Vera + public-domain terms,
freely redistributable, and the only face the renderer uses.

**Model weights:** `storage/models/kokoro/kokoro-v1.0.onnx` + `voices-v1.0.bin` —
Kokoro-82M, **Apache-2.0** — the only ML weights in the product.

---

## What changed during remediation

**Deleted from disk** (~2.8 GB): XTTS v2 weights (1.8 GB); `third_party/Wav2Lip/` (505 MB);
three copies of `wav2lip_gan.pth` (416 MB each, one of which — under
`backend/storage/models/` — was missed by the original audit and found during cleanup);
`s3fd.pth`; the Piper voice model; `Inter-Regular.ttf` / `Inter-Bold.ttf` (Arial).

**Code removed:** `agents/video/xtts_tts.py`, `agents/video/piper_tts.py`,
`agents/video/wav2lip_engine.py`, the Wav2Lip pipeline stage, and the tests that drove them.

**Code added / rewritten:**
- `agents/video/kokoro_tts.py` — Apache-2.0 weights, mirrors the previous engine interface.
- `agents/video/license_policy.py` — rewritten default-deny (see below).
- `agents/video/attribution.py` — per-job provenance manifest.
- `agents/presentation/native_pptx_engine.py` — PDF tier ported from PyMuPDF to reportlab.
- `backend/requirements.txt` — now reflects what actually ships, with a "do not re-add" list.

**Packages uninstalled:** `PyMuPDF`, `piper-tts`, `coqui-tts`, `coqui-tts-trainer`.

### R5 detail — how the media filter now behaves

The old evaluator was default-ALLOW and tested `"by" in lic_str` *before* the
non-commercial check, making that check unreachable for every `by-nc*`/`by-nd*` variant.
The rewrite is default-DENY with an explicit allowlist, restriction matching on token
boundaries, and the restriction check running first so no ordering accident can shadow it
again.

Verified against 18 must-reject and 8 must-accept cases, plus the real provider strings:

| Input | Before | After |
|---|---|---|
| `cc-by-nc-4.0`, `CC BY-NC-SA 4.0`, `by-nc-nd`, `cc-by-nd-4.0` | accepted | **rejected** |
| `by-sa`, `cc-by-sa-4.0` (ShareAlike) | accepted | **rejected** |
| `""` (empty) | accepted as CC0 | **rejected** |
| `some-new-license-2027` | accepted as CC0 | **rejected** |
| `CC CC0`, `CC PDM` (real Openverse format) | accepted | accepted ✓ |
| `cc-by-4.0` **without** attribution | accepted | **rejected** |
| Attribution containing "Sanders"/"Anderson" | — | accepted ✓ (no false positives) |

A regression was caught during testing: the first version of the normalizer rejected
`"CC CC0"` — the exact string OpenverseStockProvider produces — which would have silently
emptied the only CC0 image source. Fixed and covered above.

**Attribution manifest.** Every render writes `storage/artifacts/{job_id}/attributions.json`
recording, per asset: provider, source_url, creator, title, license, license_url,
attribution string, whether credit is required, and retrieved_at. Confirmed on a real
20-second render (4 Pexels clips, 0 requiring credit). Recording is thread-local so
concurrent jobs on the BackgroundTasks threadpool cannot cross-contaminate.

---

## Remaining checklist

| # | Item | Action | Blocks hosted launch? |
|---|---|---|---|
| Y6 | `edge-tts` Microsoft ToS | Legal review; consider dropping the fallback | **Recommended** — hosting does not cure this |
| Y13 | Google Fonts CDN | Self-host for EU end-users | **Recommended** — in scope for a hosted product |
| Y9 | `torchcodec`, `kokoro-onnx`, `espeakng-loader` metadata | Confirm upstream licences and record | No |
| R6′ | `phonemizer` / espeak-ng (GPL-3.0) | Nothing, while hosted-only. Re-open before any distribution deal. | No |
| R7 | `backend/.venv` is broken (points at another machine) | Rebuild so the declared env matches the running one | No — but it makes audits unreliable |

---

## Full dependency inventory

Regenerate with:

```bash
python -m pip install pip-licenses
python -m piplicenses --format=csv --with-urls --output-file=sys_licenses.csv
cd frontend && npx license-checker --json > npm_licenses.json
```

The `Risk` column below is a **package-metadata** classification and is deployment-agnostic:
it marks `phonemizer` RED because GPL-3.0 is RED *under distribution*. Read it together
with the deployment banner at the top — under hosted-only that row is compliant. See R6′.

### Python — 167 packages

| Package | Version | License | Commercial OK? | Attribution? | Risk | Notes |
|---|---|---|---|---|---|---|
| absl-py | 2.5.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| aiofiles | 25.1.0 | Apache Software License | Yes | Yes | GREEN |  |
| aiohappyeyeballs | 2.7.1 | Python Software Foundation License | Yes | No | GREEN |  |
| aiohttp | 3.14.3 | Apache-2.0 AND MIT | Yes | Yes | GREEN |  |
| aiosignal | 1.4.0 | Apache Software License | Yes | Yes | GREEN |  |
| alembic | 1.19.0 | MIT | Yes | Yes | GREEN |  |
| amqp | 5.3.1 | BSD License | Yes | Yes | GREEN |  |
| annotated-doc | 0.0.5 | MIT | Yes | Yes | GREEN |  |
| annotated-types | 0.8.0 | MIT | Yes | Yes | GREEN |  |
| anyascii | 0.3.3 | ISC License (ISCL) | Yes | No | GREEN |  |
| anyio | 4.14.2 | MIT | Yes | Yes | GREEN |  |
| asgiref | 3.12.1 | BSD License | Yes | Yes | GREEN |  |
| attrs | 26.1.0 | MIT | Yes | Yes | GREEN |  |
| audioop-lts | 0.2.2 | PSF-2.0 | Yes | No | GREEN |  |
| audioread | 3.1.0 | MIT | Yes | Yes | GREEN |  |
| billiard | 4.2.4 | BSD License | Yes | Yes | GREEN |  |
| celery | 5.6.3 | BSD-3-Clause | Yes | Yes | GREEN |  |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | Conditional | Yes | YELLOW | Weak/file-level copyleft or attribution - fine if unmodified, keep notices |
| cffi | 2.1.1 | MIT-0 | Yes | Yes | GREEN |  |
| charset-normalizer | 3.4.9 | MIT | Yes | Yes | GREEN |  |
| click | 8.4.2 | BSD-3-Clause | Yes | Yes | GREEN |  |
| click-didyoumean | 0.3.1 | MIT License | Yes | Yes | GREEN |  |
| click-plugins | 1.1.1.2 | BSD License | Yes | Yes | GREEN |  |
| click-repl | 0.3.0 | MIT | Yes | Yes | GREEN |  |
| colorama | 0.4.6 | BSD License | Yes | Yes | GREEN |  |
| contourpy | 1.3.3 | BSD License | Yes | Yes | GREEN |  |
| coqpit-config | 0.2.5 | MIT | Yes | Yes | GREEN |  |
| cycler | 0.12.1 | BSD License | Yes | Yes | GREEN |  |
| decorator | 5.3.1 | BSD-2-Clause | Yes | Yes | GREEN |  |
| defusedxml | 0.7.1 | Python Software Foundation License | Yes | No | GREEN |  |
| dlinfo | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| docopt | 0.6.2 | MIT License | Yes | Yes | GREEN |  |
| edge-tts | 7.2.8 | GNU Lesser General Public License v3 (LGPLv3) | Conditional | Yes | YELLOW | LGPL - OK if dynamically linked & unmodified; obligations trigger on distribution |
| einops | 0.8.2 | MIT License | Yes | Yes | GREEN |  |
| espeakng-loader | 0.2.4 | UNKNOWN | Conditional | Yes | YELLOW | License metadata missing - verify upstream before launch |
| fastapi | 0.141.1 | MIT | Yes | Yes | GREEN |  |
| filelock | 3.32.2 | MIT | Yes | Yes | GREEN |  |
| flatbuffers | 25.12.19 | Apache Software License | Yes | Yes | GREEN |  |
| fonttools | 4.63.0 | MIT | Yes | Yes | GREEN |  |
| fpdf2 | 2.8.7 | LGPL-3.0-only | Conditional | Yes | YELLOW | LGPL - OK if dynamically linked & unmodified; obligations trigger on distribution |
| frozenlist | 1.8.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| fsspec | 2026.7.0 | BSD-3-Clause | Yes | Yes | GREEN |  |
| googleapis-common-protos | 1.75.1 | Apache Software License | Yes | Yes | GREEN |  |
| greenlet | 3.5.4 | MIT AND PSF-2.0 | Yes | Yes | GREEN |  |
| grpcio | 1.83.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| h11 | 0.16.0 | MIT License | Yes | Yes | GREEN |  |
| hf-xet | 1.6.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| httpcore | 1.0.9 | BSD-3-Clause | Yes | Yes | GREEN |  |
| httptools | 0.8.0 | MIT | Yes | Yes | GREEN |  |
| httpx | 0.28.1 | BSD License | Yes | Yes | GREEN |  |
| huggingface_hub | 0.36.2 | Apache Software License | Yes | Yes | GREEN |  |
| idna | 3.18 | BSD-3-Clause | Yes | Yes | GREEN |  |
| ImageIO | 2.37.4 | BSD-2-Clause | Yes | Yes | GREEN |  |
| imageio-ffmpeg | 0.6.0 | BSD License | Yes | Yes | GREEN |  |
| inflect | 7.5.0 | MIT License | Yes | Yes | GREEN |  |
| Jinja2 | 3.1.6 | BSD License | Yes | Yes | GREEN |  |
| joblib | 1.5.3 | BSD-3-Clause | Yes | Yes | GREEN |  |
| kiwisolver | 1.5.0 | BSD License | Yes | Yes | GREEN |  |
| ko-speech-tools | 0.1.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| kokoro-onnx | 0.6.1 | UNKNOWN | Conditional | Yes | YELLOW | License metadata missing - verify upstream before launch |
| kombu | 5.6.2 | BSD-3-Clause | Yes | Yes | GREEN |  |
| lazy-loader | 0.5 | BSD-3-Clause | Yes | Yes | GREEN |  |
| librosa | 0.11.0 | ISC License (ISCL) | Yes | No | GREEN |  |
| llvmlite | 0.48.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception | Yes | Yes | GREEN |  |
| lxml | 6.1.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| Mako | 1.4.1 | MIT | Yes | Yes | GREEN |  |
| Markdown | 3.10.3 | BSD-3-Clause | Yes | Yes | GREEN |  |
| markdown-it-py | 4.2.0 | MIT License | Yes | Yes | GREEN |  |
| MarkupSafe | 3.0.3 | BSD-3-Clause | Yes | Yes | GREEN |  |
| matplotlib | 3.11.1 | Python Software Foundation License | Yes | No | GREEN |  |
| mdurl | 0.1.2 | MIT License | Yes | Yes | GREEN |  |
| ml_dtypes | 0.6.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| monotonic-alignment-search | 0.2.1 | MIT License | Yes | Yes | GREEN |  |
| more-itertools | 11.1.0 | MIT | Yes | Yes | GREEN |  |
| mpmath | 1.3.0 | BSD License | Yes | Yes | GREEN |  |
| msgpack | 1.2.1 | Apache-2.0 | Yes | Yes | GREEN |  |
| multidict | 6.7.1 | Apache License 2.0 | Yes | Yes | GREEN |  |
| narwhals | 2.24.0 | MIT | Yes | Yes | GREEN |  |
| networkx | 3.6.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| num2words | 0.5.14 | GNU Library or Lesser General Public License (LGPL) | Conditional | Yes | YELLOW | LGPL - OK if dynamically linked & unmodified; obligations trigger on distribution |
| numba | 0.66.0 | BSD License | Yes | Yes | GREEN |  |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Yes | Yes | GREEN |  |
| onnx | 1.22.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| onnxruntime | 1.28.0 | MIT License | Yes | Yes | GREEN |  |
| opencv-python | 5.0.0.93 | Apache Software License | Yes | Yes | GREEN |  |
| opentelemetry-api | 1.44.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-exporter-otlp | 1.44.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-exporter-otlp-proto-common | 1.44.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-exporter-otlp-proto-grpc | 1.44.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-exporter-otlp-proto-http | 1.44.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-instrumentation | 0.65b0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-instrumentation-asgi | 0.65b0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-instrumentation-fastapi | 0.65b0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-proto | 1.44.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-sdk | 1.44.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-semantic-conventions | 0.65b0 | Apache-2.0 | Yes | Yes | GREEN |  |
| opentelemetry-util-http | 0.65b0 | Apache-2.0 | Yes | Yes | GREEN |  |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Yes | Yes | GREEN |  |
| pathvalidate | 3.3.1 | MIT License | Yes | Yes | GREEN |  |
| phonemizer | 3.4.0 | GNU General Public License v3 or later (GPLv3+) | NO | Yes | RED | Strong copyleft - safe hosted-only, blocks distribution (Docker/Helm/on-prem) |
| pillow | 11.3.0 | MIT-CMU | Yes | Yes | GREEN |  |
| platformdirs | 4.11.1 | MIT | Yes | Yes | GREEN |  |
| pooch | 1.9.0 | BSD-3-Clause | Yes | Yes | GREEN |  |
| prometheus_client | 0.26.0 | Apache-2.0 AND BSD-2-Clause | Yes | Yes | GREEN |  |
| prompt_toolkit | 3.0.53 | BSD License | Yes | Yes | GREEN |  |
| propcache | 0.5.2 | Apache Software License | Yes | Yes | GREEN |  |
| protobuf | 7.35.1 | 3-Clause BSD License | Yes | Yes | GREEN |  |
| psutil | 7.2.2 | BSD-3-Clause | Yes | Yes | GREEN |  |
| psycopg2-binary | 2.9.12 | GNU Library or Lesser General Public License (LGPL) | Conditional | Yes | YELLOW | LGPL - OK if dynamically linked & unmodified; obligations trigger on distribution |
| pycparser | 3.0 | BSD-3-Clause | Yes | Yes | GREEN |  |
| pydantic | 2.13.4 | MIT | Yes | Yes | GREEN |  |
| pydantic-settings | 2.15.0 | MIT | Yes | Yes | GREEN |  |
| pydantic_core | 2.46.4 | MIT | Yes | Yes | GREEN |  |
| pydub | 0.25.1 | MIT License | Yes | Yes | GREEN |  |
| Pygments | 2.21.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| PyJWT | 2.13.0 | MIT | Yes | Yes | GREEN |  |
| pyparsing | 3.3.2 | MIT | Yes | Yes | GREEN |  |
| pysbd | 0.3.4 | MIT License | Yes | Yes | GREEN |  |
| python-dateutil | 2.9.0.post0 | Apache Software License; BSD License | Yes | Yes | GREEN |  |
| python-dotenv | 1.2.2 | BSD-3-Clause | Yes | Yes | GREEN |  |
| python-multipart | 0.0.32 | Apache-2.0 | Yes | Yes | GREEN |  |
| python-pptx | 1.0.2 | MIT License | Yes | Yes | GREEN |  |
| PyYAML | 6.0.3 | MIT License | Yes | Yes | GREEN |  |
| redis | 6.4.0 | MIT | Yes | Yes | GREEN |  |
| regex | 2026.7.19 | Apache-2.0 AND CNRI-Python | Yes | Yes | GREEN |  |
| reportlab | 5.0.1 | BSD License | Yes | Yes | GREEN |  |
| requests | 2.34.2 | Apache Software License | Yes | Yes | GREEN |  |
| rich | 15.0.0 | MIT License | Yes | Yes | GREEN |  |
| safetensors | 0.8.0 | Apache Software License | Yes | Yes | GREEN |  |
| scikit-learn | 1.9.0 | BSD-3-Clause | Yes | Yes | GREEN |  |
| scipy | 1.18.0 | BSD License | Yes | Yes | GREEN |  |
| shellingham | 1.5.4 | ISC License (ISCL) | Yes | No | GREEN |  |
| six | 1.17.0 | MIT License | Yes | Yes | GREEN |  |
| soundfile | 0.14.0 | BSD License | Yes | Yes | GREEN |  |
| soxr | 1.1.0 | LGPL-2.1-or-later | Conditional | Yes | YELLOW | LGPL - OK if dynamically linked & unmodified; obligations trigger on distribution |
| SQLAlchemy | 2.0.51 | MIT | Yes | Yes | GREEN |  |
| standard-aifc | 3.13.0 | Python Software Foundation License | Yes | No | GREEN |  |
| standard-chunk | 3.13.0 | Python Software Foundation License | Yes | No | GREEN |  |
| standard-sunau | 3.13.0 | Python Software Foundation License | Yes | No | GREEN |  |
| starlette | 1.5.0 | BSD-3-Clause | Yes | Yes | GREEN |  |
| sympy | 1.14.0 | BSD License | Yes | Yes | GREEN |  |
| tabulate | 0.10.0 | MIT | Yes | Yes | GREEN |  |
| tensorboard | 2.21.0 | Apache Software License | Yes | Yes | GREEN |  |
| tensorboard-data-server | 0.7.2 | Apache Software License | Yes | Yes | GREEN |  |
| threadpoolctl | 3.6.0 | BSD License | Yes | Yes | GREEN |  |
| tokenizers | 0.22.2 | Apache Software License | Yes | Yes | GREEN |  |
| torch | 2.13.0+cu126 | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT | Yes | Yes | GREEN |  |
| torchaudio | 2.11.0 | BSD License | Yes | Yes | GREEN |  |
| torchcodec | 0.16.0 | UNKNOWN | Conditional | Yes | YELLOW | License metadata missing - verify upstream before launch |
| torchvision | 0.28.0 | BSD | Yes | Yes | GREEN |  |
| tqdm | 4.70.0 | MPL-2.0 AND MIT | Conditional | Yes | YELLOW | Weak/file-level copyleft or attribution - fine if unmodified, keep notices |
| transformers | 4.57.6 | Apache Software License | Yes | Yes | GREEN |  |
| typeguard | 4.6.0 | MIT | Yes | Yes | GREEN |  |
| typer | 0.27.1 | MIT | Yes | Yes | GREEN |  |
| typing-inspection | 0.4.2 | MIT | Yes | Yes | GREEN |  |
| typing_extensions | 4.16.0 | PSF-2.0 | Yes | No | GREEN |  |
| tzdata | 2026.3 | Apache-2.0 | Yes | Yes | GREEN |  |
| tzlocal | 5.4.4 | MIT | Yes | Yes | GREEN |  |
| urllib3 | 2.7.0 | MIT | Yes | Yes | GREEN |  |
| uvicorn | 0.52.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| vine | 5.1.0 | BSD License | Yes | Yes | GREEN |  |
| watchfiles | 1.2.0 | MIT License | Yes | Yes | GREEN |  |
| websockets | 17.0.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| Werkzeug | 3.1.8 | BSD-3-Clause | Yes | Yes | GREEN |  |
| wrapt | 2.3.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| xlsxwriter | 3.2.9 | BSD License | Yes | Yes | GREEN |  |
| yarl | 1.24.5 | Apache-2.0 | Yes | Yes | GREEN |  |

### npm — 839 packages

Only the four runtime dependencies (@angular/*, rxjs, tslib, zone.js) ship in the browser bundle; the remainder are build/test tooling.

| Package | Version | License | Commercial OK? | Attribution? | Risk | Notes |
|---|---|---|---|---|---|---|
| @ampproject/remapping | 2.3.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @angular-devkit/architect | 0.1802.21 | MIT | Yes | Yes | GREEN |  |
| @angular-devkit/build-angular | 18.2.21 | MIT | Yes | Yes | GREEN |  |
| @angular-devkit/build-webpack | 0.1802.21 | MIT | Yes | Yes | GREEN |  |
| @angular-devkit/core | 18.2.21 | MIT | Yes | Yes | GREEN |  |
| @angular-devkit/schematics | 18.2.21 | MIT | Yes | Yes | GREEN |  |
| @angular/animations | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/build | 18.2.21 | MIT | Yes | Yes | GREEN |  |
| @angular/cli | 18.2.21 | MIT | Yes | Yes | GREEN |  |
| @angular/common | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/compiler | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/compiler-cli | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/core | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/forms | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/platform-browser | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/platform-browser-dynamic | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @angular/router | 18.2.14 | MIT | Yes | Yes | GREEN |  |
| @babel/code-frame | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/compat-data | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/core | 7.25.2 | MIT | Yes | Yes | GREEN |  |
| @babel/core | 7.26.10 | MIT | Yes | Yes | GREEN |  |
| @babel/generator | 7.26.10 | MIT | Yes | Yes | GREEN |  |
| @babel/generator | 7.29.8 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-annotate-as-pure | 7.24.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-annotate-as-pure | 7.25.9 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-annotate-as-pure | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-compilation-targets | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-create-class-features-plugin | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-create-regexp-features-plugin | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-define-polyfill-provider | 0.6.8 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-globals | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-member-expression-to-functions | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-module-imports | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-module-transforms | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-optimise-call-expression | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-plugin-utils | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-remap-async-to-generator | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-replace-supers | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-skip-transparent-expression-wrappers | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-split-export-declaration | 7.24.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-string-parser | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-validator-identifier | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-validator-option | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helper-wrap-function | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/helpers | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/parser | 7.29.8 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-bugfix-firefox-class-in-computed-class-key | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-bugfix-safari-class-field-initializer-scope | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-bugfix-safari-id-destructuring-collision-in-function-expression | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-bugfix-v8-spread-parameters-in-optional-chaining | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-bugfix-v8-static-class-fields-redefine-readonly | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-proposal-private-property-in-object | 7.21.0-placeholder-for-preset-env.2 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-syntax-import-assertions | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-syntax-import-attributes | 7.24.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-syntax-import-attributes | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-syntax-unicode-sets-regex | 7.18.6 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-arrow-functions | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-async-generator-functions | 7.26.8 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-async-to-generator | 7.25.9 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-block-scoped-functions | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-block-scoping | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-class-properties | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-class-static-block | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-classes | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-computed-properties | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-destructuring | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-dotall-regex | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-duplicate-keys | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-duplicate-named-capturing-groups-regex | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-dynamic-import | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-exponentiation-operator | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-export-namespace-from | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-for-of | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-function-name | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-json-strings | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-literals | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-logical-assignment-operators | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-member-expression-literals | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-modules-amd | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-modules-commonjs | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-modules-systemjs | 7.29.8 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-modules-umd | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-named-capturing-groups-regex | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-new-target | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-nullish-coalescing-operator | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-numeric-separator | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-object-rest-spread | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-object-super | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-optional-catch-binding | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-optional-chaining | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-parameters | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-private-methods | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-private-property-in-object | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-property-literals | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-regenerator | 7.29.8 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-regexp-modifiers | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-reserved-words | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-runtime | 7.26.10 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-shorthand-properties | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-spread | 7.29.8 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-sticky-regex | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-template-literals | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-typeof-symbol | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-unicode-escapes | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-unicode-property-regex | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-unicode-regex | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/plugin-transform-unicode-sets-regex | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/preset-env | 7.26.9 | MIT | Yes | Yes | GREEN |  |
| @babel/preset-modules | 0.1.6-no-external-plugins | MIT | Yes | Yes | GREEN |  |
| @babel/runtime | 7.26.10 | MIT | Yes | Yes | GREEN |  |
| @babel/template | 7.29.7 | MIT | Yes | Yes | GREEN |  |
| @babel/traverse | 7.29.8 | MIT | Yes | Yes | GREEN |  |
| @babel/types | 7.29.8 | MIT | Yes | Yes | GREEN |  |
| @colors/colors | 1.5.0 | MIT | Yes | Yes | GREEN |  |
| @discoveryjs/json-ext | 0.6.1 | MIT | Yes | Yes | GREEN |  |
| @esbuild/win32-x64 | 0.21.5 | MIT | Yes | Yes | GREEN |  |
| @esbuild/win32-x64 | 0.23.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/checkbox | 2.5.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/confirm | 3.1.22 | MIT | Yes | Yes | GREEN |  |
| @inquirer/core | 9.2.1 | MIT | Yes | Yes | GREEN |  |
| @inquirer/editor | 2.2.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/expand | 2.3.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/figures | 1.0.15 | MIT | Yes | Yes | GREEN |  |
| @inquirer/input | 2.3.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/number | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/password | 2.2.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/prompts | 5.3.8 | MIT | Yes | Yes | GREEN |  |
| @inquirer/rawlist | 2.3.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/search | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/select | 2.5.0 | MIT | Yes | Yes | GREEN |  |
| @inquirer/type | 1.5.5 | MIT | Yes | Yes | GREEN |  |
| @inquirer/type | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| @isaacs/cliui | 8.0.2 | ISC | Yes | No | GREEN |  |
| @istanbuljs/schema | 0.1.6 | MIT | Yes | Yes | GREEN |  |
| @jridgewell/gen-mapping | 0.3.13 | MIT | Yes | Yes | GREEN |  |
| @jridgewell/resolve-uri | 3.1.2 | MIT | Yes | Yes | GREEN |  |
| @jridgewell/source-map | 0.3.11 | MIT | Yes | Yes | GREEN |  |
| @jridgewell/sourcemap-codec | 1.5.5 | MIT | Yes | Yes | GREEN |  |
| @jridgewell/trace-mapping | 0.3.31 | MIT | Yes | Yes | GREEN |  |
| @jsonjoy.com/base64 | 1.1.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/base64 | 17.67.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/buffers | 1.2.1 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/buffers | 17.67.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/codegen | 1.0.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/codegen | 17.67.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-core | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-fsa | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-node | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-node-builtins | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-node-to-fsa | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-node-utils | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-print | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/fs-snapshot | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/json-pack | 1.21.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/json-pack | 17.67.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/json-pointer | 1.0.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/json-pointer | 17.67.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/util | 1.9.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @jsonjoy.com/util | 17.67.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @leichtgewicht/ip-codec | 2.0.5 | MIT | Yes | Yes | GREEN |  |
| @listr2/prompt-adapter-inquirer | 2.0.15 | MIT | Yes | Yes | GREEN |  |
| @lmdb/lmdb-win32-x64 | 3.0.13 | MIT | Yes | Yes | GREEN |  |
| @msgpackr-extract/msgpackr-extract-win32-x64 | 3.0.4 | MIT | Yes | Yes | GREEN |  |
| @ngtools/webpack | 18.2.21 | MIT | Yes | Yes | GREEN |  |
| @nodelib/fs.scandir | 2.1.5 | MIT | Yes | Yes | GREEN |  |
| @nodelib/fs.stat | 2.0.5 | MIT | Yes | Yes | GREEN |  |
| @nodelib/fs.walk | 1.2.8 | MIT | Yes | Yes | GREEN |  |
| @npmcli/agent | 2.2.2 | ISC | Yes | No | GREEN |  |
| @npmcli/fs | 3.1.1 | ISC | Yes | No | GREEN |  |
| @npmcli/git | 5.0.8 | ISC | Yes | No | GREEN |  |
| @npmcli/installed-package-contents | 2.1.0 | ISC | Yes | No | GREEN |  |
| @npmcli/node-gyp | 3.0.0 | ISC | Yes | No | GREEN |  |
| @npmcli/package-json | 5.2.1 | ISC | Yes | No | GREEN |  |
| @npmcli/promise-spawn | 7.0.2 | ISC | Yes | No | GREEN |  |
| @npmcli/redact | 2.0.1 | ISC | Yes | No | GREEN |  |
| @npmcli/run-script | 8.1.0 | ISC | Yes | No | GREEN |  |
| @pkgjs/parseargs | 0.11.0 | MIT | Yes | Yes | GREEN |  |
| @rollup/rollup-win32-x64-msvc | 4.22.4 | MIT | Yes | Yes | GREEN |  |
| @schematics/angular | 18.2.21 | MIT | Yes | Yes | GREEN |  |
| @sigstore/bundle | 2.3.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| @sigstore/core | 1.1.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| @sigstore/protobuf-specs | 0.3.3 | Apache-2.0 | Yes | Yes | GREEN |  |
| @sigstore/sign | 2.3.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| @sigstore/tuf | 2.3.4 | Apache-2.0 | Yes | Yes | GREEN |  |
| @sigstore/verify | 1.2.1 | Apache-2.0 | Yes | Yes | GREEN |  |
| @sindresorhus/merge-streams | 2.3.0 | MIT | Yes | Yes | GREEN |  |
| @socket.io/component-emitter | 3.1.2 | MIT | Yes | Yes | GREEN |  |
| @tufjs/canonical-json | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| @tufjs/models | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| @types/body-parser | 1.19.6 | MIT | Yes | Yes | GREEN |  |
| @types/bonjour | 3.5.13 | MIT | Yes | Yes | GREEN |  |
| @types/connect | 3.4.38 | MIT | Yes | Yes | GREEN |  |
| @types/connect-history-api-fallback | 1.5.4 | MIT | Yes | Yes | GREEN |  |
| @types/cors | 2.8.19 | MIT | Yes | Yes | GREEN |  |
| @types/estree | 1.0.5 | MIT | Yes | Yes | GREEN |  |
| @types/express | 4.17.25 | MIT | Yes | Yes | GREEN |  |
| @types/express-serve-static-core | 4.19.9 | MIT | Yes | Yes | GREEN |  |
| @types/http-errors | 2.0.5 | MIT | Yes | Yes | GREEN |  |
| @types/http-proxy | 1.17.17 | MIT | Yes | Yes | GREEN |  |
| @types/jasmine | 5.1.15 | MIT | Yes | Yes | GREEN |  |
| @types/json-schema | 7.0.15 | MIT | Yes | Yes | GREEN |  |
| @types/mime | 1.3.5 | MIT | Yes | Yes | GREEN |  |
| @types/mute-stream | 0.0.4 | MIT | Yes | Yes | GREEN |  |
| @types/node | 22.20.1 | MIT | Yes | Yes | GREEN |  |
| @types/node-forge | 1.3.14 | MIT | Yes | Yes | GREEN |  |
| @types/qs | 6.15.1 | MIT | Yes | Yes | GREEN |  |
| @types/range-parser | 1.2.7 | MIT | Yes | Yes | GREEN |  |
| @types/retry | 0.12.2 | MIT | Yes | Yes | GREEN |  |
| @types/send | 0.17.6 | MIT | Yes | Yes | GREEN |  |
| @types/send | 1.2.1 | MIT | Yes | Yes | GREEN |  |
| @types/serve-index | 1.9.4 | MIT | Yes | Yes | GREEN |  |
| @types/serve-static | 1.15.10 | MIT | Yes | Yes | GREEN |  |
| @types/sockjs | 0.3.36 | MIT | Yes | Yes | GREEN |  |
| @types/wrap-ansi | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| @types/ws | 8.18.1 | MIT | Yes | Yes | GREEN |  |
| @vitejs/plugin-basic-ssl | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/ast | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/floating-point-hex-parser | 1.13.2 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/helper-api-error | 1.13.2 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/helper-buffer | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/helper-numbers | 1.13.2 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/helper-wasm-bytecode | 1.13.2 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/helper-wasm-section | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/ieee754 | 1.13.2 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/leb128 | 1.13.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| @webassemblyjs/utf8 | 1.13.2 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/wasm-edit | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/wasm-gen | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/wasm-opt | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/wasm-parser | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @webassemblyjs/wast-printer | 1.14.1 | MIT | Yes | Yes | GREEN |  |
| @xtuc/ieee754 | 1.2.0 | BSD-3-Clause | Yes | Yes | GREEN |  |
| @xtuc/long | 4.2.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| @yarnpkg/lockfile | 1.1.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| abbrev | 2.0.0 | ISC | Yes | No | GREEN |  |
| accepts | 1.3.8 | MIT | Yes | Yes | GREEN |  |
| acorn | 8.18.0 | MIT | Yes | Yes | GREEN |  |
| acorn-import-attributes | 1.9.5 | MIT | Yes | Yes | GREEN |  |
| adjust-sourcemap-loader | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| agent-base | 7.1.4 | MIT | Yes | Yes | GREEN |  |
| aggregate-error | 3.1.0 | MIT | Yes | Yes | GREEN |  |
| ajv | 6.15.0 | MIT | Yes | Yes | GREEN |  |
| ajv | 8.17.1 | MIT | Yes | Yes | GREEN |  |
| ajv-formats | 2.1.1 | MIT | Yes | Yes | GREEN |  |
| ajv-formats | 3.0.1 | MIT | Yes | Yes | GREEN |  |
| ajv-keywords | 3.5.2 | MIT | Yes | Yes | GREEN |  |
| ajv-keywords | 5.1.0 | MIT | Yes | Yes | GREEN |  |
| ansi-colors | 4.1.3 | MIT | Yes | Yes | GREEN |  |
| ansi-escapes | 4.3.2 | MIT | Yes | Yes | GREEN |  |
| ansi-escapes | 7.3.0 | MIT | Yes | Yes | GREEN |  |
| ansi-html-community | 0.0.8 | Apache-2.0 | Yes | Yes | GREEN |  |
| ansi-regex | 5.0.1 | MIT | Yes | Yes | GREEN |  |
| ansi-regex | 6.2.2 | MIT | Yes | Yes | GREEN |  |
| ansi-styles | 4.3.0 | MIT | Yes | Yes | GREEN |  |
| ansi-styles | 6.2.3 | MIT | Yes | Yes | GREEN |  |
| anymatch | 3.1.3 | ISC | Yes | No | GREEN |  |
| argparse | 2.0.1 | Python-2.0 | Yes | No | GREEN |  |
| array-flatten | 1.1.1 | MIT | Yes | Yes | GREEN |  |
| autoprefixer | 10.4.20 | MIT | Yes | Yes | GREEN |  |
| babel-loader | 9.1.3 | MIT | Yes | Yes | GREEN |  |
| babel-plugin-polyfill-corejs2 | 0.4.17 | MIT | Yes | Yes | GREEN |  |
| babel-plugin-polyfill-corejs3 | 0.11.1 | MIT | Yes | Yes | GREEN |  |
| babel-plugin-polyfill-regenerator | 0.6.8 | MIT | Yes | Yes | GREEN |  |
| balanced-match | 1.0.2 | MIT | Yes | Yes | GREEN |  |
| base64-js | 1.5.1 | MIT | Yes | Yes | GREEN |  |
| base64id | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| baseline-browser-mapping | 2.11.12 | Apache-2.0 | Yes | Yes | GREEN |  |
| batch | 0.6.1 | MIT | Yes | Yes | GREEN |  |
| big.js | 5.2.2 | MIT | Yes | Yes | GREEN |  |
| binary-extensions | 2.3.0 | MIT | Yes | Yes | GREEN |  |
| bl | 4.1.0 | MIT | Yes | Yes | GREEN |  |
| body-parser | 1.20.6 | MIT | Yes | Yes | GREEN |  |
| bonjour-service | 1.4.4 | MIT | Yes | Yes | GREEN |  |
| boolbase | 1.0.0 | ISC | Yes | No | GREEN |  |
| brace-expansion | 1.1.18 | MIT | Yes | Yes | GREEN |  |
| brace-expansion | 2.1.4 | MIT | Yes | Yes | GREEN |  |
| braces | 3.0.3 | MIT | Yes | Yes | GREEN |  |
| browserslist | 4.28.8 | MIT | Yes | Yes | GREEN |  |
| buffer | 5.7.1 | MIT | Yes | Yes | GREEN |  |
| buffer-from | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| bundle-name | 4.1.0 | MIT | Yes | Yes | GREEN |  |
| bytes | 3.1.2 | MIT | Yes | Yes | GREEN |  |
| cacache | 18.0.4 | ISC | Yes | No | GREEN |  |
| call-bind-apply-helpers | 1.0.2 | MIT | Yes | Yes | GREEN |  |
| call-bound | 1.0.4 | MIT | Yes | Yes | GREEN |  |
| callsites | 3.1.0 | MIT | Yes | Yes | GREEN |  |
| caniuse-lite | 1.0.30001809 | CC-BY-4.0 | Conditional | Yes | YELLOW | Weak/file-level copyleft or attribution - fine if unmodified, keep notices |
| chalk | 4.1.2 | MIT | Yes | Yes | GREEN |  |
| chardet | 0.7.0 | MIT | Yes | Yes | GREEN |  |
| chokidar | 3.6.0 | MIT | Yes | Yes | GREEN |  |
| chokidar | 4.0.3 | MIT | Yes | Yes | GREEN |  |
| chownr | 2.0.0 | ISC | Yes | No | GREEN |  |
| chrome-trace-event | 1.0.4 | MIT | Yes | Yes | GREEN |  |
| clean-stack | 2.2.0 | MIT | Yes | Yes | GREEN |  |
| cli-cursor | 3.1.0 | MIT | Yes | Yes | GREEN |  |
| cli-cursor | 5.0.0 | MIT | Yes | Yes | GREEN |  |
| cli-spinners | 2.9.2 | MIT | Yes | Yes | GREEN |  |
| cli-truncate | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| cli-width | 4.1.0 | ISC | Yes | No | GREEN |  |
| cliui | 7.0.4 | ISC | Yes | No | GREEN |  |
| cliui | 8.0.1 | ISC | Yes | No | GREEN |  |
| clone | 1.0.4 | MIT | Yes | Yes | GREEN |  |
| clone-deep | 4.0.1 | MIT | Yes | Yes | GREEN |  |
| color-convert | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| color-name | 1.1.4 | MIT | Yes | Yes | GREEN |  |
| colorette | 2.0.20 | MIT | Yes | Yes | GREEN |  |
| commander | 2.20.3 | MIT | Yes | Yes | GREEN |  |
| common-path-prefix | 3.0.0 | ISC | Yes | No | GREEN |  |
| compressible | 2.0.18 | MIT | Yes | Yes | GREEN |  |
| compression | 1.8.1 | MIT | Yes | Yes | GREEN |  |
| concat-map | 0.0.1 | MIT | Yes | Yes | GREEN |  |
| connect | 3.7.0 | MIT | Yes | Yes | GREEN |  |
| connect-history-api-fallback | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| content-disposition | 0.5.4 | MIT | Yes | Yes | GREEN |  |
| content-type | 1.0.5 | MIT | Yes | Yes | GREEN |  |
| convert-source-map | 1.9.0 | MIT | Yes | Yes | GREEN |  |
| convert-source-map | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| cookie | 0.7.2 | MIT | Yes | Yes | GREEN |  |
| cookie-signature | 1.0.7 | MIT | Yes | Yes | GREEN |  |
| copy-anything | 2.0.6 | MIT | Yes | Yes | GREEN |  |
| copy-webpack-plugin | 12.0.2 | MIT | Yes | Yes | GREEN |  |
| core-js-compat | 3.50.0 | MIT | Yes | Yes | GREEN |  |
| core-util-is | 1.0.3 | MIT | Yes | Yes | GREEN |  |
| cors | 2.8.6 | MIT | Yes | Yes | GREEN |  |
| cosmiconfig | 9.0.2 | MIT | Yes | Yes | GREEN |  |
| critters | 0.0.24 | Apache-2.0 | Yes | Yes | GREEN |  |
| cross-spawn | 7.0.6 | MIT | Yes | Yes | GREEN |  |
| css-loader | 7.1.2 | MIT | Yes | Yes | GREEN |  |
| css-select | 5.2.2 | BSD-2-Clause | Yes | Yes | GREEN |  |
| css-what | 6.2.2 | BSD-2-Clause | Yes | Yes | GREEN |  |
| cssesc | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| custom-event | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| date-format | 4.0.14 | MIT | Yes | Yes | GREEN |  |
| debug | 2.6.9 | MIT | Yes | Yes | GREEN |  |
| debug | 4.4.3 | MIT | Yes | Yes | GREEN |  |
| default-browser | 5.5.0 | MIT | Yes | Yes | GREEN |  |
| default-browser-id | 5.0.1 | MIT | Yes | Yes | GREEN |  |
| defaults | 1.0.4 | MIT | Yes | Yes | GREEN |  |
| define-lazy-prop | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| depd | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| depd | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| destroy | 1.2.0 | MIT | Yes | Yes | GREEN |  |
| detect-libc | 2.1.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| detect-node | 2.1.0 | MIT | Yes | Yes | GREEN |  |
| di | 0.0.1 | MIT | Yes | Yes | GREEN |  |
| dns-packet | 5.6.1 | MIT | Yes | Yes | GREEN |  |
| dom-serialize | 2.2.1 | MIT | Yes | Yes | GREEN |  |
| dom-serializer | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| domelementtype | 2.3.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| domhandler | 5.0.3 | BSD-2-Clause | Yes | Yes | GREEN |  |
| domutils | 3.2.2 | BSD-2-Clause | Yes | Yes | GREEN |  |
| dunder-proto | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| eastasianwidth | 0.2.0 | MIT | Yes | Yes | GREEN |  |
| ee-first | 1.1.1 | MIT | Yes | Yes | GREEN |  |
| electron-to-chromium | 1.5.402 | ISC | Yes | No | GREEN |  |
| emoji-regex | 10.6.0 | MIT | Yes | Yes | GREEN |  |
| emoji-regex | 8.0.0 | MIT | Yes | Yes | GREEN |  |
| emoji-regex | 9.2.2 | MIT | Yes | Yes | GREEN |  |
| emojis-list | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| encodeurl | 1.0.2 | MIT | Yes | Yes | GREEN |  |
| encodeurl | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| encoding | 0.1.13 | MIT | Yes | Yes | GREEN |  |
| engine.io | 6.6.9 | MIT | Yes | Yes | GREEN |  |
| engine.io-parser | 5.2.3 | MIT | Yes | Yes | GREEN |  |
| enhanced-resolve | 5.24.5 | MIT | Yes | Yes | GREEN |  |
| ent | 2.2.2 | MIT | Yes | Yes | GREEN |  |
| entities | 4.5.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| entities | 6.0.1 | BSD-2-Clause | Yes | Yes | GREEN |  |
| env-paths | 2.2.1 | MIT | Yes | Yes | GREEN |  |
| environment | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| err-code | 2.0.3 | MIT | Yes | Yes | GREEN |  |
| errno | 0.1.8 | MIT | Yes | Yes | GREEN |  |
| error-ex | 1.3.4 | MIT | Yes | Yes | GREEN |  |
| es-define-property | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| es-errors | 1.3.0 | MIT | Yes | Yes | GREEN |  |
| es-module-lexer | 1.7.0 | MIT | Yes | Yes | GREEN |  |
| es-object-atoms | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| esbuild | 0.21.5 | MIT | Yes | Yes | GREEN |  |
| esbuild | 0.23.0 | MIT | Yes | Yes | GREEN |  |
| esbuild-wasm | 0.23.0 | MIT | Yes | Yes | GREEN |  |
| escalade | 3.2.0 | MIT | Yes | Yes | GREEN |  |
| escape-html | 1.0.3 | MIT | Yes | Yes | GREEN |  |
| eslint-scope | 5.1.1 | BSD-2-Clause | Yes | Yes | GREEN |  |
| esrecurse | 4.3.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| estraverse | 4.3.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| estraverse | 5.3.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| esutils | 2.0.3 | BSD-2-Clause | Yes | Yes | GREEN |  |
| etag | 1.8.1 | MIT | Yes | Yes | GREEN |  |
| eventemitter3 | 4.0.7 | MIT | Yes | Yes | GREEN |  |
| eventemitter3 | 5.0.4 | MIT | Yes | Yes | GREEN |  |
| events | 3.3.0 | MIT | Yes | Yes | GREEN |  |
| exponential-backoff | 3.1.3 | Apache-2.0 | Yes | Yes | GREEN |  |
| express | 4.22.2 | MIT | Yes | Yes | GREEN |  |
| extend | 3.0.2 | MIT | Yes | Yes | GREEN |  |
| external-editor | 3.1.0 | MIT | Yes | Yes | GREEN |  |
| fast-deep-equal | 3.1.3 | MIT | Yes | Yes | GREEN |  |
| fast-glob | 3.3.2 | MIT | Yes | Yes | GREEN |  |
| fast-glob | 3.3.3 | MIT | Yes | Yes | GREEN |  |
| fast-json-stable-stringify | 2.1.0 | MIT | Yes | Yes | GREEN |  |
| fast-uri | 3.1.5 | BSD-3-Clause | Yes | Yes | GREEN |  |
| fastq | 1.20.1 | ISC | Yes | No | GREEN |  |
| faye-websocket | 0.11.4 | Apache-2.0 | Yes | Yes | GREEN |  |
| fill-range | 7.1.1 | MIT | Yes | Yes | GREEN |  |
| finalhandler | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| finalhandler | 1.3.2 | MIT | Yes | Yes | GREEN |  |
| find-cache-dir | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| find-up | 6.3.0 | MIT | Yes | Yes | GREEN |  |
| flat | 5.0.2 | BSD-3-Clause | Yes | Yes | GREEN |  |
| flatted | 3.4.4 | ISC | Yes | No | GREEN |  |
| follow-redirects | 1.16.0 | MIT | Yes | Yes | GREEN |  |
| foreground-child | 3.3.1 | ISC | Yes | No | GREEN |  |
| forwarded | 0.2.0 | MIT | Yes | Yes | GREEN |  |
| fraction.js | 4.3.7 | MIT | Yes | Yes | GREEN |  |
| fresh | 0.5.2 | MIT | Yes | Yes | GREEN |  |
| fs-extra | 8.1.0 | MIT | Yes | Yes | GREEN |  |
| fs-minipass | 2.1.0 | ISC | Yes | No | GREEN |  |
| fs-minipass | 3.0.3 | ISC | Yes | No | GREEN |  |
| fs.realpath | 1.0.0 | ISC | Yes | No | GREEN |  |
| function-bind | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| gensync | 1.0.0-beta.2 | MIT | Yes | Yes | GREEN |  |
| get-caller-file | 2.0.5 | ISC | Yes | No | GREEN |  |
| get-east-asian-width | 1.6.0 | MIT | Yes | Yes | GREEN |  |
| get-intrinsic | 1.3.0 | MIT | Yes | Yes | GREEN |  |
| get-proto | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| glob | 10.5.0 | ISC | Yes | No | GREEN |  |
| glob | 7.2.3 | ISC | Yes | No | GREEN |  |
| glob-parent | 5.1.2 | ISC | Yes | No | GREEN |  |
| glob-parent | 6.0.2 | ISC | Yes | No | GREEN |  |
| glob-to-regex.js | 1.2.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| glob-to-regexp | 0.4.1 | BSD-2-Clause | Yes | Yes | GREEN |  |
| globby | 14.1.0 | MIT | Yes | Yes | GREEN |  |
| gopd | 1.2.0 | MIT | Yes | Yes | GREEN |  |
| graceful-fs | 4.2.11 | ISC | Yes | No | GREEN |  |
| handle-thing | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| has-flag | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| has-symbols | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| has-tostringtag | 1.0.2 | MIT | Yes | Yes | GREEN |  |
| hasown | 2.0.4 | MIT | Yes | Yes | GREEN |  |
| hosted-git-info | 7.0.2 | ISC | Yes | No | GREEN |  |
| hpack.js | 2.1.6 | MIT | Yes | Yes | GREEN |  |
| html-escaper | 2.0.2 | MIT | Yes | Yes | GREEN |  |
| htmlparser2 | 8.0.2 | MIT | Yes | Yes | GREEN |  |
| http-cache-semantics | 4.2.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| http-deceiver | 1.2.7 | MIT | Yes | Yes | GREEN |  |
| http-errors | 1.8.1 | MIT | Yes | Yes | GREEN |  |
| http-errors | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| http-parser-js | 0.5.10 | MIT | Yes | Yes | GREEN |  |
| http-proxy | 1.18.1 | MIT | Yes | Yes | GREEN |  |
| http-proxy-agent | 7.0.2 | MIT | Yes | Yes | GREEN |  |
| http-proxy-middleware | 2.0.10 | MIT | Yes | Yes | GREEN |  |
| http-proxy-middleware | 3.0.5 | MIT | Yes | Yes | GREEN |  |
| https-proxy-agent | 7.0.5 | MIT | Yes | Yes | GREEN |  |
| hyperdyperid | 1.2.0 | MIT | Yes | Yes | GREEN |  |
| iconv-lite | 0.4.24 | MIT | Yes | Yes | GREEN |  |
| iconv-lite | 0.6.3 | MIT | Yes | Yes | GREEN |  |
| icss-utils | 5.1.0 | ISC | Yes | No | GREEN |  |
| ieee754 | 1.2.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| ignore | 7.0.6 | MIT | Yes | Yes | GREEN |  |
| ignore-walk | 6.0.5 | ISC | Yes | No | GREEN |  |
| image-size | 0.5.5 | MIT | Yes | Yes | GREEN |  |
| immutable | 4.3.9 | MIT | Yes | Yes | GREEN |  |
| import-fresh | 3.3.1 | MIT | Yes | Yes | GREEN |  |
| imurmurhash | 0.1.4 | MIT | Yes | Yes | GREEN |  |
| indent-string | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| inflight | 1.0.6 | ISC | Yes | No | GREEN |  |
| inherits | 2.0.4 | ISC | Yes | No | GREEN |  |
| ini | 4.1.3 | ISC | Yes | No | GREEN |  |
| ip-address | 10.4.0 | MIT | Yes | Yes | GREEN |  |
| ipaddr.js | 1.9.1 | MIT | Yes | Yes | GREEN |  |
| ipaddr.js | 2.5.0 | MIT | Yes | Yes | GREEN |  |
| is-arrayish | 0.2.1 | MIT | Yes | Yes | GREEN |  |
| is-binary-path | 2.1.0 | MIT | Yes | Yes | GREEN |  |
| is-core-module | 2.16.2 | MIT | Yes | Yes | GREEN |  |
| is-docker | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| is-extglob | 2.1.1 | MIT | Yes | Yes | GREEN |  |
| is-fullwidth-code-point | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| is-fullwidth-code-point | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| is-fullwidth-code-point | 5.1.0 | MIT | Yes | Yes | GREEN |  |
| is-glob | 4.0.3 | MIT | Yes | Yes | GREEN |  |
| is-inside-container | 1.0.0 | MIT | Yes | Yes | GREEN |  |
| is-interactive | 1.0.0 | MIT | Yes | Yes | GREEN |  |
| is-lambda | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| is-network-error | 1.3.2 | MIT | Yes | Yes | GREEN |  |
| is-number | 7.0.0 | MIT | Yes | Yes | GREEN |  |
| is-plain-obj | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| is-plain-object | 2.0.4 | MIT | Yes | Yes | GREEN |  |
| is-plain-object | 5.0.0 | MIT | Yes | Yes | GREEN |  |
| is-regex | 1.2.1 | MIT | Yes | Yes | GREEN |  |
| is-unicode-supported | 0.1.0 | MIT | Yes | Yes | GREEN |  |
| is-what | 3.14.1 | MIT | Yes | Yes | GREEN |  |
| is-wsl | 3.1.1 | MIT | Yes | Yes | GREEN |  |
| isarray | 1.0.0 | MIT | Yes | Yes | GREEN |  |
| isbinaryfile | 4.0.10 | MIT | Yes | Yes | GREEN |  |
| isexe | 2.0.0 | ISC | Yes | No | GREEN |  |
| isexe | 3.1.5 | BlueOak-1.0.0 | Yes | No | GREEN |  |
| isobject | 3.0.1 | MIT | Yes | Yes | GREEN |  |
| istanbul-lib-coverage | 3.2.2 | BSD-3-Clause | Yes | Yes | GREEN |  |
| istanbul-lib-instrument | 5.2.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| istanbul-lib-instrument | 6.0.3 | BSD-3-Clause | Yes | Yes | GREEN |  |
| istanbul-lib-report | 3.0.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| istanbul-lib-source-maps | 4.0.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| istanbul-reports | 3.2.0 | BSD-3-Clause | Yes | Yes | GREEN |  |
| jackspeak | 3.4.3 | BlueOak-1.0.0 | Yes | No | GREEN |  |
| jasmine-core | 4.6.1 | MIT | Yes | Yes | GREEN |  |
| jasmine-core | 5.2.0 | MIT | Yes | Yes | GREEN |  |
| jest-worker | 27.5.1 | MIT | Yes | Yes | GREEN |  |
| jiti | 1.21.7 | MIT | Yes | Yes | GREEN |  |
| js-tokens | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| js-yaml | 4.3.1 | MIT | Yes | Yes | GREEN |  |
| jsesc | 3.1.0 | MIT | Yes | Yes | GREEN |  |
| json-parse-even-better-errors | 2.3.1 | MIT | Yes | Yes | GREEN |  |
| json-parse-even-better-errors | 3.0.2 | MIT | Yes | Yes | GREEN |  |
| json-schema-traverse | 0.4.1 | MIT | Yes | Yes | GREEN |  |
| json-schema-traverse | 1.0.0 | MIT | Yes | Yes | GREEN |  |
| json5 | 2.2.3 | MIT | Yes | Yes | GREEN |  |
| jsonc-parser | 3.3.1 | MIT | Yes | Yes | GREEN |  |
| jsonfile | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| jsonparse | 1.3.1 | MIT | Yes | Yes | GREEN |  |
| karma | 6.4.4 | MIT | Yes | Yes | GREEN |  |
| karma-chrome-launcher | 3.2.0 | MIT | Yes | Yes | GREEN |  |
| karma-coverage | 2.2.1 | MIT | Yes | Yes | GREEN |  |
| karma-jasmine | 5.1.0 | MIT | Yes | Yes | GREEN |  |
| karma-jasmine-html-reporter | 2.1.0 | MIT | Yes | Yes | GREEN |  |
| karma-source-map-support | 1.4.0 | MIT | Yes | Yes | GREEN |  |
| kind-of | 6.0.3 | MIT | Yes | Yes | GREEN |  |
| launch-editor | 2.14.1 | MIT | Yes | Yes | GREEN |  |
| less | 4.2.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| less-loader | 12.2.0 | MIT | Yes | Yes | GREEN |  |
| license-webpack-plugin | 4.0.2 | ISC | Yes | No | GREEN |  |
| lines-and-columns | 1.2.4 | MIT | Yes | Yes | GREEN |  |
| listr2 | 8.2.4 | MIT | Yes | Yes | GREEN |  |
| lmdb | 3.0.13 | MIT | Yes | Yes | GREEN |  |
| loader-runner | 4.3.2 | MIT | Yes | Yes | GREEN |  |
| loader-utils | 2.0.4 | MIT | Yes | Yes | GREEN |  |
| loader-utils | 3.3.1 | MIT | Yes | Yes | GREEN |  |
| locate-path | 7.2.0 | MIT | Yes | Yes | GREEN |  |
| lodash | 4.18.1 | MIT | Yes | Yes | GREEN |  |
| lodash.debounce | 4.0.8 | MIT | Yes | Yes | GREEN |  |
| log-symbols | 4.1.0 | MIT | Yes | Yes | GREEN |  |
| log-update | 6.1.0 | MIT | Yes | Yes | GREEN |  |
| log4js | 6.9.1 | Apache-2.0 | Yes | Yes | GREEN |  |
| lru-cache | 10.4.3 | ISC | Yes | No | GREEN |  |
| lru-cache | 5.1.1 | ISC | Yes | No | GREEN |  |
| magic-string | 0.30.11 | MIT | Yes | Yes | GREEN |  |
| make-dir | 2.1.0 | MIT | Yes | Yes | GREEN |  |
| make-dir | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| make-fetch-happen | 13.0.1 | ISC | Yes | No | GREEN |  |
| math-intrinsics | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| media-typer | 0.3.0 | MIT | Yes | Yes | GREEN |  |
| memfs | 4.68.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| merge-descriptors | 1.0.3 | MIT | Yes | Yes | GREEN |  |
| merge-stream | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| merge2 | 1.4.1 | MIT | Yes | Yes | GREEN |  |
| methods | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| micromatch | 4.0.8 | MIT | Yes | Yes | GREEN |  |
| mime | 1.6.0 | MIT | Yes | Yes | GREEN |  |
| mime | 2.6.0 | MIT | Yes | Yes | GREEN |  |
| mime-db | 1.52.0 | MIT | Yes | Yes | GREEN |  |
| mime-types | 2.1.35 | MIT | Yes | Yes | GREEN |  |
| mimic-fn | 2.1.0 | MIT | Yes | Yes | GREEN |  |
| mimic-function | 5.0.1 | MIT | Yes | Yes | GREEN |  |
| mini-css-extract-plugin | 2.9.0 | MIT | Yes | Yes | GREEN |  |
| minimalistic-assert | 1.0.1 | ISC | Yes | No | GREEN |  |
| minimatch | 3.1.5 | ISC | Yes | No | GREEN |  |
| minimatch | 9.0.9 | ISC | Yes | No | GREEN |  |
| minimist | 1.2.8 | MIT | Yes | Yes | GREEN |  |
| minipass | 3.3.6 | ISC | Yes | No | GREEN |  |
| minipass | 5.0.0 | ISC | Yes | No | GREEN |  |
| minipass | 7.1.3 | BlueOak-1.0.0 | Yes | No | GREEN |  |
| minipass-collect | 2.0.1 | ISC | Yes | No | GREEN |  |
| minipass-fetch | 3.0.5 | MIT | Yes | Yes | GREEN |  |
| minipass-flush | 1.0.7 | BlueOak-1.0.0 | Yes | No | GREEN |  |
| minipass-pipeline | 1.2.4 | ISC | Yes | No | GREEN |  |
| minipass-sized | 1.0.3 | ISC | Yes | No | GREEN |  |
| minizlib | 2.1.2 | MIT | Yes | Yes | GREEN |  |
| mkdirp | 0.5.6 | MIT | Yes | Yes | GREEN |  |
| mkdirp | 1.0.4 | MIT | Yes | Yes | GREEN |  |
| mrmime | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| ms | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| ms | 2.1.3 | MIT | Yes | Yes | GREEN |  |
| msgpackr | 1.12.1 | MIT | Yes | Yes | GREEN |  |
| msgpackr-extract | 3.0.4 | MIT | Yes | Yes | GREEN |  |
| multicast-dns | 7.2.5 | MIT | Yes | Yes | GREEN |  |
| mute-stream | 1.0.0 | ISC | Yes | No | GREEN |  |
| nanoid | 3.3.18 | MIT | Yes | Yes | GREEN |  |
| needle | 3.5.0 | MIT | Yes | Yes | GREEN |  |
| negotiator | 0.6.3 | MIT | Yes | Yes | GREEN |  |
| negotiator | 0.6.4 | MIT | Yes | Yes | GREEN |  |
| neo-async | 2.6.2 | MIT | Yes | Yes | GREEN |  |
| node-addon-api | 6.1.0 | MIT | Yes | Yes | GREEN |  |
| node-forge | 1.4.0 | (BSD-3-Clause OR GPL-2.0) | Yes | Yes | GREEN | Dual-licensed with a permissive option - elect that one |
| node-gyp | 10.3.1 | MIT | Yes | Yes | GREEN |  |
| node-gyp-build-optional-packages | 5.2.2 | MIT | Yes | Yes | GREEN |  |
| node-releases | 2.0.53 | MIT | Yes | Yes | GREEN |  |
| nopt | 7.2.1 | ISC | Yes | No | GREEN |  |
| normalize-package-data | 6.0.2 | BSD-2-Clause | Yes | Yes | GREEN |  |
| normalize-path | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| normalize-range | 0.1.2 | MIT | Yes | Yes | GREEN |  |
| npm-bundled | 3.0.1 | ISC | Yes | No | GREEN |  |
| npm-install-checks | 6.3.0 | BSD-2-Clause | Yes | Yes | GREEN |  |
| npm-normalize-package-bin | 3.0.1 | ISC | Yes | No | GREEN |  |
| npm-package-arg | 11.0.3 | ISC | Yes | No | GREEN |  |
| npm-packlist | 8.0.2 | ISC | Yes | No | GREEN |  |
| npm-pick-manifest | 9.1.0 | ISC | Yes | No | GREEN |  |
| npm-registry-fetch | 17.1.0 | ISC | Yes | No | GREEN |  |
| nth-check | 2.1.1 | BSD-2-Clause | Yes | Yes | GREEN |  |
| object-assign | 4.1.1 | MIT | Yes | Yes | GREEN |  |
| object-inspect | 1.13.4 | MIT | Yes | Yes | GREEN |  |
| obuf | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| on-finished | 2.3.0 | MIT | Yes | Yes | GREEN |  |
| on-finished | 2.4.1 | MIT | Yes | Yes | GREEN |  |
| on-headers | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| once | 1.4.0 | ISC | Yes | No | GREEN |  |
| onetime | 5.1.2 | MIT | Yes | Yes | GREEN |  |
| onetime | 7.0.0 | MIT | Yes | Yes | GREEN |  |
| open | 10.1.0 | MIT | Yes | Yes | GREEN |  |
| ora | 5.4.1 | MIT | Yes | Yes | GREEN |  |
| ordered-binary | 1.6.1 | MIT | Yes | Yes | GREEN |  |
| os-tmpdir | 1.0.2 | MIT | Yes | Yes | GREEN |  |
| p-limit | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| p-locate | 6.0.0 | MIT | Yes | Yes | GREEN |  |
| p-map | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| p-retry | 6.2.1 | MIT | Yes | Yes | GREEN |  |
| package-json-from-dist | 1.0.1 | BlueOak-1.0.0 | Yes | No | GREEN |  |
| pacote | 18.0.6 | ISC | Yes | No | GREEN |  |
| parent-module | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| parse-json | 5.2.0 | MIT | Yes | Yes | GREEN |  |
| parse-node-version | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| parse5 | 7.3.0 | MIT | Yes | Yes | GREEN |  |
| parse5-html-rewriting-stream | 7.0.0 | MIT | Yes | Yes | GREEN |  |
| parse5-sax-parser | 7.0.0 | MIT | Yes | Yes | GREEN |  |
| parseurl | 1.3.3 | MIT | Yes | Yes | GREEN |  |
| path-exists | 5.0.0 | MIT | Yes | Yes | GREEN |  |
| path-is-absolute | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| path-key | 3.1.1 | MIT | Yes | Yes | GREEN |  |
| path-parse | 1.0.7 | MIT | Yes | Yes | GREEN |  |
| path-scurry | 1.11.1 | BlueOak-1.0.0 | Yes | No | GREEN |  |
| path-to-regexp | 0.1.13 | MIT | Yes | Yes | GREEN |  |
| path-type | 6.0.0 | MIT | Yes | Yes | GREEN |  |
| picocolors | 1.1.1 | ISC | Yes | No | GREEN |  |
| picomatch | 2.3.2 | MIT | Yes | Yes | GREEN |  |
| picomatch | 4.0.2 | MIT | Yes | Yes | GREEN |  |
| pify | 4.0.1 | MIT | Yes | Yes | GREEN |  |
| piscina | 4.6.1 | MIT | Yes | Yes | GREEN |  |
| pkg-dir | 7.0.0 | MIT | Yes | Yes | GREEN |  |
| postcss | 8.4.41 | MIT | Yes | Yes | GREEN |  |
| postcss | 8.5.26 | MIT | Yes | Yes | GREEN |  |
| postcss-loader | 8.1.1 | MIT | Yes | Yes | GREEN |  |
| postcss-media-query-parser | 0.2.3 | MIT | Yes | Yes | GREEN |  |
| postcss-modules-extract-imports | 3.1.0 | ISC | Yes | No | GREEN |  |
| postcss-modules-local-by-default | 4.2.0 | MIT | Yes | Yes | GREEN |  |
| postcss-modules-scope | 3.2.1 | ISC | Yes | No | GREEN |  |
| postcss-modules-values | 4.0.0 | ISC | Yes | No | GREEN |  |
| postcss-selector-parser | 7.1.5 | MIT | Yes | Yes | GREEN |  |
| postcss-value-parser | 4.2.0 | MIT | Yes | Yes | GREEN |  |
| proc-log | 4.2.0 | ISC | Yes | No | GREEN |  |
| process-nextick-args | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| promise-inflight | 1.0.1 | ISC | Yes | No | GREEN |  |
| promise-retry | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| proxy-addr | 2.0.7 | MIT | Yes | Yes | GREEN |  |
| prr | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| punycode | 1.4.1 | MIT | Yes | Yes | GREEN |  |
| punycode | 2.3.1 | MIT | Yes | Yes | GREEN |  |
| qjobs | 1.2.0 | MIT | Yes | Yes | GREEN |  |
| qs | 6.15.3 | BSD-3-Clause | Yes | Yes | GREEN |  |
| queue-microtask | 1.2.3 | MIT | Yes | Yes | GREEN |  |
| randombytes | 2.1.0 | MIT | Yes | Yes | GREEN |  |
| range-parser | 1.2.1 | MIT | Yes | Yes | GREEN |  |
| range-parser | 1.3.0 | MIT | Yes | Yes | GREEN |  |
| raw-body | 2.5.3 | MIT | Yes | Yes | GREEN |  |
| readable-stream | 2.3.8 | MIT | Yes | Yes | GREEN |  |
| readable-stream | 3.6.2 | MIT | Yes | Yes | GREEN |  |
| readdirp | 3.6.0 | MIT | Yes | Yes | GREEN |  |
| readdirp | 4.1.2 | MIT | Yes | Yes | GREEN |  |
| reflect-metadata | 0.2.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| regenerate | 1.4.2 | MIT | Yes | Yes | GREEN |  |
| regenerate-unicode-properties | 10.2.2 | MIT | Yes | Yes | GREEN |  |
| regenerator-runtime | 0.14.1 | MIT | Yes | Yes | GREEN |  |
| regex-parser | 2.3.1 | MIT | Yes | Yes | GREEN |  |
| regexpu-core | 6.4.0 | MIT | Yes | Yes | GREEN |  |
| regjsgen | 0.8.0 | MIT | Yes | Yes | GREEN |  |
| regjsparser | 0.13.2 | BSD-2-Clause | Yes | Yes | GREEN |  |
| require-directory | 2.1.1 | MIT | Yes | Yes | GREEN |  |
| require-from-string | 2.0.2 | MIT | Yes | Yes | GREEN |  |
| requires-port | 1.0.0 | MIT | Yes | Yes | GREEN |  |
| resolve | 1.22.12 | MIT | Yes | Yes | GREEN |  |
| resolve | 1.22.8 | MIT | Yes | Yes | GREEN |  |
| resolve-from | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| resolve-url-loader | 5.0.0 | MIT | Yes | Yes | GREEN |  |
| restore-cursor | 3.1.0 | MIT | Yes | Yes | GREEN |  |
| restore-cursor | 5.1.0 | MIT | Yes | Yes | GREEN |  |
| retry | 0.12.0 | MIT | Yes | Yes | GREEN |  |
| retry | 0.13.1 | MIT | Yes | Yes | GREEN |  |
| reusify | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| rfdc | 1.4.1 | MIT | Yes | Yes | GREEN |  |
| rimraf | 3.0.2 | ISC | Yes | No | GREEN |  |
| rollup | 4.22.4 | MIT | Yes | Yes | GREEN |  |
| run-applescript | 7.1.0 | MIT | Yes | Yes | GREEN |  |
| run-parallel | 1.2.0 | MIT | Yes | Yes | GREEN |  |
| rxjs | 7.8.1 | Apache-2.0 | Yes | Yes | GREEN |  |
| rxjs | 7.8.2 | Apache-2.0 | Yes | Yes | GREEN |  |
| safe-buffer | 5.1.2 | MIT | Yes | Yes | GREEN |  |
| safe-buffer | 5.2.1 | MIT | Yes | Yes | GREEN |  |
| safe-regex-test | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| safer-buffer | 2.1.2 | MIT | Yes | Yes | GREEN |  |
| sass | 1.77.6 | MIT | Yes | Yes | GREEN |  |
| sass-loader | 16.0.0 | MIT | Yes | Yes | GREEN |  |
| sax | 1.6.1 | BlueOak-1.0.0 | Yes | No | GREEN |  |
| schema-utils | 3.3.0 | MIT | Yes | Yes | GREEN |  |
| schema-utils | 4.3.3 | MIT | Yes | Yes | GREEN |  |
| select-hose | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| selfsigned | 2.4.1 | MIT | Yes | Yes | GREEN |  |
| semver | 5.7.2 | ISC | Yes | No | GREEN |  |
| semver | 6.3.1 | ISC | Yes | No | GREEN |  |
| semver | 7.6.3 | ISC | Yes | No | GREEN |  |
| send | 0.19.2 | MIT | Yes | Yes | GREEN |  |
| serialize-javascript | 6.0.2 | BSD-3-Clause | Yes | Yes | GREEN |  |
| serve-index | 1.9.2 | MIT | Yes | Yes | GREEN |  |
| serve-static | 1.16.3 | MIT | Yes | Yes | GREEN |  |
| setprototypeof | 1.2.0 | ISC | Yes | No | GREEN |  |
| shallow-clone | 3.0.1 | MIT | Yes | Yes | GREEN |  |
| shebang-command | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| shebang-regex | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| shell-quote | 1.10.0 | MIT | Yes | Yes | GREEN |  |
| side-channel | 1.1.1 | MIT | Yes | Yes | GREEN |  |
| side-channel-list | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| side-channel-map | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| side-channel-weakmap | 1.0.2 | MIT | Yes | Yes | GREEN |  |
| signal-exit | 3.0.7 | ISC | Yes | No | GREEN |  |
| signal-exit | 4.1.0 | ISC | Yes | No | GREEN |  |
| sigstore | 2.3.1 | Apache-2.0 | Yes | Yes | GREEN |  |
| slash | 5.1.0 | MIT | Yes | Yes | GREEN |  |
| slice-ansi | 5.0.0 | MIT | Yes | Yes | GREEN |  |
| slice-ansi | 7.1.2 | MIT | Yes | Yes | GREEN |  |
| smart-buffer | 4.2.0 | MIT | Yes | Yes | GREEN |  |
| socket.io | 4.8.3 | MIT | Yes | Yes | GREEN |  |
| socket.io-adapter | 2.5.8 | MIT | Yes | Yes | GREEN |  |
| socket.io-parser | 4.2.7 | MIT | Yes | Yes | GREEN |  |
| sockjs | 0.3.24 | MIT | Yes | Yes | GREEN |  |
| socks | 2.8.9 | MIT | Yes | Yes | GREEN |  |
| socks-proxy-agent | 8.0.5 | MIT | Yes | Yes | GREEN |  |
| source-map | 0.6.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| source-map | 0.7.4 | BSD-3-Clause | Yes | Yes | GREEN |  |
| source-map-js | 1.2.1 | BSD-3-Clause | Yes | Yes | GREEN |  |
| source-map-loader | 5.0.0 | MIT | Yes | Yes | GREEN |  |
| source-map-support | 0.5.21 | MIT | Yes | Yes | GREEN |  |
| spdx-correct | 3.2.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| spdx-exceptions | 2.5.0 | CC-BY-3.0 | Conditional | Yes | YELLOW | Weak/file-level copyleft or attribution - fine if unmodified, keep notices |
| spdx-expression-parse | 3.0.1 | MIT | Yes | Yes | GREEN |  |
| spdx-license-ids | 3.0.23 | CC0-1.0 | Yes | No | GREEN |  |
| spdy | 4.0.2 | MIT | Yes | Yes | GREEN |  |
| spdy-transport | 3.0.0 | MIT | Yes | Yes | GREEN |  |
| ssri | 10.0.6 | ISC | Yes | No | GREEN |  |
| statuses | 1.5.0 | MIT | Yes | Yes | GREEN |  |
| statuses | 2.0.2 | MIT | Yes | Yes | GREEN |  |
| streamroller | 3.1.5 | MIT | Yes | Yes | GREEN |  |
| string-width | 4.2.3 | MIT | Yes | Yes | GREEN |  |
| string-width | 5.1.2 | MIT | Yes | Yes | GREEN |  |
| string-width | 7.2.0 | MIT | Yes | Yes | GREEN |  |
| string_decoder | 1.1.1 | MIT | Yes | Yes | GREEN |  |
| string_decoder | 1.3.0 | MIT | Yes | Yes | GREEN |  |
| strip-ansi | 6.0.1 | MIT | Yes | Yes | GREEN |  |
| strip-ansi | 7.2.0 | MIT | Yes | Yes | GREEN |  |
| supports-color | 7.2.0 | MIT | Yes | Yes | GREEN |  |
| supports-color | 8.1.1 | MIT | Yes | Yes | GREEN |  |
| supports-preserve-symlinks-flag | 1.0.0 | MIT | Yes | Yes | GREEN |  |
| symbol-observable | 4.0.0 | MIT | Yes | Yes | GREEN |  |
| tapable | 2.3.3 | MIT | Yes | Yes | GREEN |  |
| tar | 6.2.1 | ISC | Yes | No | GREEN |  |
| terser | 5.31.6 | BSD-2-Clause | Yes | Yes | GREEN |  |
| terser-webpack-plugin | 5.6.1 | MIT | Yes | Yes | GREEN |  |
| thingies | 2.6.1 | MIT | Yes | Yes | GREEN |  |
| thunky | 1.1.0 | MIT | Yes | Yes | GREEN |  |
| tmp | 0.0.33 | MIT | Yes | Yes | GREEN |  |
| tmp | 0.2.7 | MIT | Yes | Yes | GREEN |  |
| to-regex-range | 5.0.1 | MIT | Yes | Yes | GREEN |  |
| toidentifier | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| tree-dump | 1.1.0 | Apache-2.0 | Yes | Yes | GREEN |  |
| tree-kill | 1.2.2 | MIT | Yes | Yes | GREEN |  |
| tslib | 2.6.3 | 0BSD | Yes | Yes | GREEN |  |
| tslib | 2.8.1 | 0BSD | Yes | Yes | GREEN |  |
| tuf-js | 2.2.1 | MIT | Yes | Yes | GREEN |  |
| type-fest | 0.21.3 | (MIT OR CC0-1.0) | Yes | Yes | GREEN |  |
| type-is | 1.6.18 | MIT | Yes | Yes | GREEN |  |
| typed-assert | 1.0.9 | MIT | Yes | Yes | GREEN |  |
| typescript | 5.5.4 | Apache-2.0 | Yes | Yes | GREEN |  |
| ua-parser-js | 0.7.41 | MIT | Yes | Yes | GREEN |  |
| undici-types | 6.21.0 | MIT | Yes | Yes | GREEN |  |
| unicode-canonical-property-names-ecmascript | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| unicode-match-property-ecmascript | 2.0.0 | MIT | Yes | Yes | GREEN |  |
| unicode-match-property-value-ecmascript | 2.2.1 | MIT | Yes | Yes | GREEN |  |
| unicode-property-aliases-ecmascript | 2.2.0 | MIT | Yes | Yes | GREEN |  |
| unicorn-magic | 0.3.0 | MIT | Yes | Yes | GREEN |  |
| unique-filename | 3.0.0 | ISC | Yes | No | GREEN |  |
| unique-slug | 4.0.0 | ISC | Yes | No | GREEN |  |
| universalify | 0.1.2 | MIT | Yes | Yes | GREEN |  |
| unpipe | 1.0.0 | MIT | Yes | Yes | GREEN |  |
| update-browserslist-db | 1.3.0 | MIT | Yes | Yes | GREEN |  |
| uri-js | 4.4.1 | BSD-2-Clause | Yes | Yes | GREEN |  |
| util-deprecate | 1.0.2 | MIT | Yes | Yes | GREEN |  |
| utils-merge | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| uuid | 8.3.2 | MIT | Yes | Yes | GREEN |  |
| validate-npm-package-license | 3.0.4 | Apache-2.0 | Yes | Yes | GREEN |  |
| validate-npm-package-name | 5.0.1 | ISC | Yes | No | GREEN |  |
| vary | 1.1.2 | MIT | Yes | Yes | GREEN |  |
| vite | 5.4.21 | MIT | Yes | Yes | GREEN |  |
| void-elements | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| watchpack | 2.4.1 | MIT | Yes | Yes | GREEN |  |
| wbuf | 1.7.3 | MIT | Yes | Yes | GREEN |  |
| wcwidth | 1.0.1 | MIT | Yes | Yes | GREEN |  |
| weak-lru-cache | 1.2.2 | MIT | Yes | Yes | GREEN |  |
| webpack | 5.94.0 | MIT | Yes | Yes | GREEN |  |
| webpack-dev-middleware | 7.4.2 | MIT | Yes | Yes | GREEN |  |
| webpack-dev-server | 5.2.2 | MIT | Yes | Yes | GREEN |  |
| webpack-merge | 6.0.1 | MIT | Yes | Yes | GREEN |  |
| webpack-sources | 3.5.1 | MIT | Yes | Yes | GREEN |  |
| webpack-subresource-integrity | 5.1.0 | MIT | Yes | Yes | GREEN |  |
| websocket-driver | 0.7.5 | Apache-2.0 | Yes | Yes | GREEN |  |
| websocket-extensions | 0.1.4 | Apache-2.0 | Yes | Yes | GREEN |  |
| which | 1.3.1 | ISC | Yes | No | GREEN |  |
| which | 2.0.2 | ISC | Yes | No | GREEN |  |
| which | 4.0.0 | ISC | Yes | No | GREEN |  |
| wildcard | 2.0.1 | MIT | Yes | Yes | GREEN |  |
| wrap-ansi | 6.2.0 | MIT | Yes | Yes | GREEN |  |
| wrap-ansi | 7.0.0 | MIT | Yes | Yes | GREEN |  |
| wrap-ansi | 8.1.0 | MIT | Yes | Yes | GREEN |  |
| wrap-ansi | 9.0.2 | MIT | Yes | Yes | GREEN |  |
| wrappy | 1.0.2 | ISC | Yes | No | GREEN |  |
| ws | 8.21.3 | MIT | Yes | Yes | GREEN |  |
| y18n | 5.0.8 | ISC | Yes | No | GREEN |  |
| yallist | 3.1.1 | ISC | Yes | No | GREEN |  |
| yallist | 4.0.0 | ISC | Yes | No | GREEN |  |
| yargs | 16.2.2 | MIT | Yes | Yes | GREEN |  |
| yargs | 17.7.2 | MIT | Yes | Yes | GREEN |  |
| yargs-parser | 20.2.9 | ISC | Yes | No | GREEN |  |
| yargs-parser | 21.1.1 | ISC | Yes | No | GREEN |  |
| yocto-queue | 1.2.2 | MIT | Yes | Yes | GREEN |  |
| yoctocolors-cjs | 2.1.3 | MIT | Yes | Yes | GREEN |  |
| zone.js | 0.14.10 | MIT | Yes | Yes | GREEN |  |

---

*Generated 2026-08-29 from pip-licenses 5.5.5 and license-checker against the live post-remediation environment.*
*Deployment model: hosted SaaS only — see the banner at the top of this document.*
