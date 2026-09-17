# CreateFlow AI — AI Multi-Agent Generation Platform

## What this is

CreateFlow AI is a SaaS platform that generates professional videos (French and
English), LaTeX-quality reports, and slide presentations from a single text prompt,
using a multi-agent AI pipeline. Target market: Tunisian students producing PFE
(*projet de fin d'études*) final-year reports and videos, and local businesses needing
fast marketing/explainer content.

**Current status:** MVP complete — video, report and presentation pipelines all work
end to end, with a credit system, brand kits, and a premium Angular UI. Not yet
integrated with a payment provider, and not yet deployed to a cloud GPU host. See
[What's done vs what's next](#whats-done-vs-whats-next).

---

## Architecture overview

```
Angular frontend (4200)  ──HTTP──>  FastAPI backend (8000)  ──>  SQLite (dev) / PostgreSQL (prod)
                                            │
                                            ├── agents/video/    (video pipeline)
                                            ├── agents/latex/    (report pipeline)
                                            ├── agents/presentation/ (deck pipeline)
                                            └── app/services/    (credits, brand kit, auth, LLM)
```

Jobs run as FastAPI `BackgroundTasks` (see `backend/app/orchestrator/workflow.py`), not
as a separate worker process — `start_worker.ps1` exists (Celery + Redis) but is legacy
infrastructure from an earlier presenter-video design and is **not required** to run the
app today.

### Key modules

**`agents/video/`** — the full video pipeline. Entry point `agent.py` →
`pipeline.py` (`EndToEndVideoPipeline`). Roughly: `ai_director.py` (narrative arc) →
`ai_screenwriter.py` (per-scene narration, language-aware) → stock footage via
`orchestration/producer.py` (Pexels primary, Openverse fallback, licence-filtered by
`license_policy.py`) → `kokoro_tts.py` (voice, per-job language+voice pairing) →
`python_editor/renderer.py` (H.264 compositing: text overlays, captions, brand theme,
logo watermark). Language selection (`language.py`) and brand kit (`python_editor/
brand_theme.py`) both resolve per-job via `threading.local()`, because renders run
concurrently on the FastAPI threadpool.

**`agents/latex/`** — `LaTeXReportAgent` (`agent.py`). Despite the name, the live
render path is FPDF2 with a Unicode (DejaVu) font, not LaTeX — `pdflatex` is used only
if it happens to be on `PATH` (see [Key decisions](#key-decisions--why)). Pipeline:
`cognitive_planner.py` (outline + a **fixed tech stack** shared by every chapter) →
`chapter_generator.py` (per-chapter content, paced and retried against Groq's rate
limit, **fails the job rather than emitting placeholder text on failure**) →
`diagram_extractor.py` + `diagram_spec.py` (structural diagrams — architecture, ER,
sequence — extracted from the chapter text the LLM just wrote, then verified word-for-
word against that same text before anything is drawn, so a diagram can never claim
something the report doesn't say) → `generators/structural_diagrams.py` (matplotlib
rendering) → `agent.py::_render_pdf` (FPDF2 assembly, real page-numbered TOC).
Performance/results charts are **never** generated — only a labelled placeholder frame,
because those numbers belong to the student's own measurements.

**`agents/presentation/`** — slide deck generation; PDF export path is
`native_pptx_engine.py` using `reportlab` (BSD), not `PyMuPDF` (AGPL) — see
[Key decisions](#key-decisions--why).

**`backend/app/services/llm/`** — the LLM abstraction. **Read this carefully**:
`backend/app/services/llm.py` (a flat *file*) also exists in the same directory as this
package, and it is dead code — Python resolves the package over the file, so
`from app.services.llm import LLMService` always loads
`backend/app/services/llm/service.py` → `groq.py` (`GroqProvider`, model
`openai/gpt-oss-120b`). The `.py` file is never imported; don't edit it expecting it to
take effect.

**`backend/app/services/`** — `credits.py` (the only module that reads/writes credit
columns — monthly allowance per plan, debited only when a job **completes**, never on
failure), `thumbnail.py`, `storage.py`. Brand kit logic lives in
`backend/app/api/endpoints/brand_kit.py` directly (logo files under
`storage/brand_kits/`, keyed by user id).

**`backend/app/core/security.py`** — JWT auth (`get_current_user`), a `demo-token` /
`ALLOW_DEV_ANONYMOUS_AUTH` bypass for local testing, PBKDF2 password hashing.

---

## Local setup (step by step)

Tested on Windows 10/11 with PowerShell. Commands are POSIX-shell by default; a
PowerShell variant is given for the couple of steps that differ.

### 1. Prerequisites

- **Python 3.11–3.13** (this project was built and tested against 3.13.1; the TTS
  dependency `kokoro-onnx` was specifically chosen over `kokoro` because the latter
  doesn't support 3.13+ — see [Key decisions](#key-decisions--why))
- **Node.js 18+** and npm
- **Git**
- A free **Groq API key** (https://console.groq.com/keys) — the backend refuses to
  start without one
- Optional: a free **Pexels API key** (https://www.pexels.com/api/) — stock video
  quality is noticeably better with one, but the app runs without it (Openverse only)

### 2. Clone and install the backend

```bash
git clone <repo-url> CreateFlow-AI
cd CreateFlow-AI/backend
pip install -r requirements.txt
```

`requirements.txt` documents licence-sensitive exclusions inline (PyMuPDF, XTTS/
coqui-tts, piper-tts) — do not re-add any of them without reading the comment above
each entry and updating `LICENSES.md`.

### 3. Install the frontend

```bash
cd ../frontend
npm install
```

### 4. Configure environment

```bash
cd ..
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Then edit `.env` and fill in at minimum `OPENAI_API_KEY` (your Groq key) and
`JWT_SECRET_KEY` (any long random string). Every variable is documented inline in
`.env.example` — see also [Environment variables](#environment-variables-envexample)
below.

### 5. Start the backend

```powershell
.\start_backend.ps1
```

This sets `DATABASE_URL` to a local SQLite file, loads `.env` via
`backend/env_bootstrap.py`, and launches uvicorn on `127.0.0.1:8000`. (It also detects
and works around a `.venv` created on a different machine — falls back to the system
Python with the venv's `site-packages` on `PYTHONPATH` if the venv's own interpreter
doesn't run.)

Equivalent manual command, from `backend/`:

```bash
DATABASE_URL=sqlite:///./createflow.db python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

First boot creates the SQLite schema automatically (`init_db()` in
`backend/app/core/database.py`) and runs additive migrations for any column added since
the DB file was created. Confirm it's up:

```bash
curl http://127.0.0.1:8000/health
```

### 6. Start the frontend

```bash
cd frontend
npm start          # = ng serve, http://localhost:4200
```

CORS on the backend already allows `http://localhost:4200` (see
`backend/app/main.py`).

### 7. Create your first user

No seed script — register through the real endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"a-real-password","full_name":"Your Name"}'
```

This returns a JWT `access_token`. The new account lands on the **free** plan with 3
credits and a real one-month period (see `credits.py`). Easier in practice: open
`http://localhost:4200`, use the Register page, then log in — the token is stored for
you and every API call goes through the `authInterceptor`.

---

## Environment variables (`.env.example`)

Full reference with defaults, sources, and links to get each key lives in
[`.env.example`](.env.example) — every variable is commented in place there rather than
duplicated here, so the two can't drift apart. Summary:

| Variable | Required? | What it's for |
|---|---|---|
| `OPENAI_API_KEY` | **Required** | Groq API key (`gsk_...`). Backend raises at startup if unset. |
| `OPENAI_MODEL` | Required (has a default) | Groq model id, default `openai/gpt-oss-120b`. |
| `OPENAI_BASE_URL` | Required (has a default) | `https://api.groq.com`. |
| `JWT_SECRET_KEY` | **Required for anything real** | Signs auth tokens; insecure hardcoded fallback exists for solo local testing only. |
| `DATABASE_URL` | Recommended for dev | `sqlite:///./createflow.db` is the simplest path. |
| `POSTGRES_*` | Alternative to `DATABASE_URL` | Used to build a Postgres URL if `DATABASE_URL` is unset; falls back to SQLite automatically on connection failure. |
| `PEXELS_API_KEY` | Optional | Better stock footage; Openverse alone is used without it. |
| `TTS_ENGINE` | Optional (default `kokoro`) | `kokoro` or `edge`. **Never** `xtts` or `piper` — removed, see below. |
| `KOKORO_VOICE` / `KOKORO_LANG` | Optional | Process-wide fallback only; real jobs resolve voice+language per request. |
| `STORAGE_RETENTION_DAYS` | Optional (code default 90) | `0` disables the artifact-deletion sweep — recommended in dev. |
| `CREDITS_ADMIN_TOKEN` | Optional, off by default | Enables the credit-testing admin endpoint. Keep unset outside your own machine. |
| `ALLOW_DEV_ANONYMOUS_AUTH` | Optional, off by default | Bypasses auth with a shared demo account. Local convenience only. |

---

## Key decisions & why

- **Groq, not Azure OpenAI.** The project originally targeted a PwC-hosted Azure
  OpenAI proxy; that endpoint was inaccessible outside the corporate network, so the
  LLM layer moved to Groq's free OpenAI-compatible API. The env var is still named
  `OPENAI_API_KEY` for that historical reason — it is read by the Groq provider, not by
  OpenAI.

- **Kokoro TTS instead of XTTS v2.** XTTS v2's *weights* are licensed CPML
  (non-commercial), which also covers the audio it generates — a fact easy to miss
  since the code itself is Apache-2.0 ("the XTTS trap"). Kokoro-82M ships Apache-2.0
  weights throughout. Integrated via `kokoro-onnx` rather than the `kokoro` package
  because the latter requires Python `<3.13`.

- **Wav2Lip removed entirely.** Research/non-commercial licence (LRS2 dataset terms).
  The lip-sync code path is gone, not just disabled; `presenter_mode` fields remain on
  `SceneDefinition` as inert historical fields.

- **FPDF2 instead of PyMuPDF for PDF rendering.** PyMuPDF is AGPL-3.0, whose network
  clause is triggered by users interacting with the software *over a network* — which
  describes this product exactly, since it's a hosted SaaS. FPDF2 is LGPL and reportlab
  (used by the presentation PDF path) is BSD; both are fine. See `LICENSES.md` R3.

- **SQLite in dev, PostgreSQL in prod.** `backend/app/core/database.py` tries
  `DATABASE_URL` / `POSTGRES_*` first and transparently falls back to a local SQLite
  file if the connection fails — so the same codebase runs with zero external
  dependencies locally and against a real database in production.

- **Hosted-SaaS-only deployment model.** Kokoro's espeak-based phoneme layer
  (`phonemizer`) is GPL-3.0. GPL obligations trigger on **distribution**, not on
  hosting — so serving the product from your own infrastructure is compliant, but
  shipping a Docker image, Helm chart, or on-prem build to a customer would not be. See
  [Commercial compliance](#commercial-compliance) below; this is the single most
  important constraint on how this product can ever be delivered.

- **Structural report diagrams are generated; results charts never are.**
  `agents/latex/diagram_extractor.py` extracts architecture/data-model/sequence
  structure from chapters the LLM already wrote, then `diagram_spec.ground()` deletes
  anything not actually present in that text before rendering. Performance, coverage,
  and load-test charts stay placeholders unconditionally, because those require real
  measurements a generator cannot honestly produce.

- **Credits debit on success, never on failure.** A crashed or rejected render must
  cost the user nothing (`app/services/credits.py::consume_for_completed_job`, called
  only from the workflow's completion gate). Admission is checked against *available*
  credits (balance minus jobs already queued/running), not raw balance, so a user
  can't spend the same credit twice by submitting jobs faster than the first one
  finishes.

---

## Commercial compliance

Full dependency-by-dependency audit: [`LICENSES.md`](LICENSES.md). Asset attribution
records (fonts, stock media, per-job provenance): [`ATTRIBUTIONS.md`](ATTRIBUTIONS.md).

> **This project is licensed for HOSTED SAAS DEPLOYMENT ONLY.**
> Distributing a Docker image, Helm chart, or any on-premise build to a customer would
> require first replacing `phonemizer` (GPL-3.0-or-later, a Kokoro TTS dependency) —
> GPL's obligations trigger on distribution, and hosting does not cure that; it also
> does not create the obligation in the first place. As long as customers only ever
> reach this product over the network you operate, the current dependency set is
> compliant. The Docker/Helm/k8s files in this repo carry inline comments to this
> effect — they are for *your own* deployment infrastructure, never to be handed to a
> client.

Current state for the hosted-SaaS model actually in use: **0 RED (blocking) items.**

---

## What's done vs what's next

### Done

- Full video pipeline: AI-authored script (language-aware — French or English), Pexels/
  Openverse stock footage with licence filtering, Kokoro voice synthesis with per-job
  voice+language pairing, motion graphics (animated stats, captions), brand kit
  (palette + logo + font applied to overlays, not just decoration)
- Report generator: French PFE-quality writing, real structural diagrams
  (architecture/ER/sequence) extracted and verified from the report's own text, correct
  page-numbered table of contents, Unicode (French accent) rendering
- Presentation/deck generation with PDF export
- Premium Angular UI: Create, Dashboard (active runs), Job detail/progress, Library
  (finished work, searchable, with one-click re-run of expired jobs), Brand kit editor,
  Pricing (catalogue only, no checkout yet)
- Auth: JWT register/login, credit system (free: 3/month, starter: 30/month, pro:
  100/month)
- Commercial licence compliance: 0 RED items for hosted-SaaS deployment
  (`LICENSES.md`)

### TODO (next priorities)

- **Payment integration.** Paddle is the better fit for a Tunisia-facing product than
  Stripe (Stripe's Tunisia support is limited); nothing is wired up yet — `pricing`
  page currently only displays the plan catalogue.
- **Cloud GPU hosting for production.** Kokoro and video rendering are CPU-bound
  today and workable for testing, but a production launch needs GPU capacity sized
  for real concurrent load.
- **Brand kit: more fonts.** Only DejaVu Sans (regular/bold) ships today — see the
  inventory note at the top of `backend/app/core/brand.py`. Adding a font means
  dropping an OFL-licensed TTF into `agents/video/assets/fonts/`, registering it in
  `FONT_CHOICES`, and recording it in `ATTRIBUTIONS.md`.
- **Report generation, pass 2 (academic polish).** Bilingual (FR/EN) abstract, roman-
  numeral front matter with arabic pagination starting at the introduction, numbered
  subsections, in-text citations, a real `pdflatex` path (the FPDF2 renderer is what
  actually ships today; `main.tex` is written to disk but not compiled unless
  `pdflatex` happens to be on `PATH`).
- **Arabic TTS.** Kokoro has no Arabic voice at all (no `ar`-prefixed preset in the
  pack) — relevant given the Tunisia launch. Needs a separate engine evaluated
  end-to-end, including a fresh commercial-licence check before adoption.

---

## For Claude Code

If you're an AI assistant picking this codebase up fresh: this is a complete SaaS MVP,
not a prototype — the pipelines genuinely work end to end and have been tested with
real renders, not just unit tests. Read in this order:

1. **`backend/app/main.py`** — startup: CORS, DB init, the storage-retention sweep,
   route mounting.
2. **`agents/video/pipeline.py`** (`EndToEndVideoPipeline`) — the video pipeline
   orchestrator. (Not `pipeline_v2.py` — that file doesn't exist; this is the only
   pipeline.)
3. **`agents/latex/agent.py`** (`LaTeXReportAgent`) — the report pipeline. (Not
   `agents/report/` — that directory doesn't exist either; reports live under
   `agents/latex/` for historical reasons even though the live render path is FPDF2,
   not LaTeX.)
4. **`frontend/src/app/app.routes.ts`** — every page and its auth guard.

Three traps worth knowing before you start editing:

- **`backend/app/services/llm.py` is dead code.** A same-named package
  `backend/app/services/llm/` sits beside it and wins on import
  (`from app.services.llm import LLMService` resolves to the package's
  `service.py`/`groq.py`). Edit the package, not the file — this was empirically
  verified, not assumed.
- **`.env` has real live secrets** (Groq key, Pexels key, JWT signing key). Never
  commit it, never print its contents, never send it anywhere. `.gitignore` already
  excludes it; `.env.example` is the only variant meant to be committed.
- **Credits are debited only at the workflow's completion gate**
  (`backend/app/orchestrator/workflow.py`), never at job creation. If you touch job
  creation or the agent pipelines, re-read `app/services/credits.py` first — the
  admission check (`can_start_job`) and the debit (`consume_for_completed_job`) are
  deliberately two different functions at two different points in the job lifecycle,
  and conflating them was a real bug caught during development (a user could submit
  more jobs than their balance allowed by racing the completion of an earlier one).

To verify a change actually works: start the backend, then the frontend, then run one
real video generation through the UI (or via `POST /api/jobs` with
`agent_type: "video"`) and confirm the artifact lands in `storage/artifacts/{job_id}/`.
Don't rely on unit tests alone for pipeline changes — this codebase's real bugs (TOC
page numbers, mid-word encoding truncation, fabricated diagram content) were all found
by generating and inspecting real output, not by tests passing.
