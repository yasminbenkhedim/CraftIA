# VIDEO PIPELINE ARCHITECTURE V2 — CreateFlow AI
## Professional Video Generation Engine (Vyra-Quality Target)

---

## MISSION

Upgrade CreateFlow AI's video generation from "random stock clips slideshow" to a **professional explainer video engine** comparable to Vyra (https://www.usevyra.com/). The system must produce videos where every visual, narration line, and transition feels intentionally crafted — not randomly assembled.

---

## CURRENT PROBLEMS TO SOLVE

1. **Random Pexels clips** — Videos look like random stock footage thrown together with no narrative connection
2. **No real script** — Screenwriter uses deterministic templates, not LLM-generated narration
3. **No user video uploads** — Cannot use custom footage the user provides
4. **No visual storytelling** — No text animations, motion graphics, or data visualizations on screen
5. **Poor scene coherence** — Each scene is visually disconnected from the next

---

## TARGET OUTPUT (Vyra-Style)

A 30-90 second professional video with:
- AI-written narration that tells a coherent story
- Mix of: user-uploaded clips + relevant stock footage + motion graphics overlays
- Clean typography overlays (key stats, quotes, section titles) that animate in/out
- Smooth transitions between scenes
- Single clean subtitle bar at bottom
- Professional background music with voice ducking
- Consistent color palette throughout

---

## NEW ARCHITECTURE

```
USER INPUT
    │
    ├── Prompt text: "Create a video about AI in healthcare"
    ├── Uploaded files (optional): video1.mp4, video2.mp4, logo.png
    └── Style preference: corporate / creative / minimal
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 1: AI DIRECTOR (LLM — Groq Llama 3.3 70B)   │
│                                                      │
│  Input: user prompt + uploaded file descriptions     │
│  Output: VideoDirectorPlan JSON                      │
│                                                      │
│  Decides:                                            │
│  - Overall narrative arc (hook → problem → solution  │
│    → proof → CTA)                                    │
│  - Number of scenes (4-8)                            │
│  - For each scene: purpose, mood, visual strategy    │
│  - Where to use uploaded videos vs stock vs graphics │
│  - Color palette + typography style                  │
│  - Music mood                                        │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 2: AI SCREENWRITER (LLM — Groq)              │
│                                                      │
│  Input: VideoDirectorPlan + user prompt              │
│  Output: SceneScript[] JSON                          │
│                                                      │
│  For each scene generates:                           │
│  - narration_text: natural spoken text (2-3 lines)   │
│  - on_screen_title: short impactful text overlay     │
│  - on_screen_stats: key numbers/data to display      │
│  - visual_description: what the viewer should see    │
│  - stock_search_queries: 3 specific search terms     │
│  - transition_to_next: type of transition            │
│  - mood: emotional tone of scene                     │
│                                                      │
│  CRITICAL: The screenwriter must write narration     │
│  that flows naturally as spoken speech, NOT bullet   │
│  points or robotic text. Each scene's narration      │
│  should connect to the next.                         │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 3: MEDIA ASSEMBLY ENGINE                      │
│                                                      │
│  Three parallel tracks:                              │
│                                                      │
│  Track A — User Uploads                              │
│  • Analyze uploaded videos (duration, content)       │
│  • Smart-trim to scene duration                      │
│  • Color-grade to match palette                      │
│                                                      │
│  Track B — Stock Video (Pexels Videos API)           │
│  • Use screenwriter's stock_search_queries           │
│  • Download 3 candidates per scene                   │
│  • Rank by visual relevance + quality score          │
│  • Pick best match                                   │
│                                                      │
│  Track C — Motion Graphics Generator                 │
│  • Generate text overlay animations (OpenCV/PIL):    │
│    - Animated titles (fade in, slide up)             │
│    - Stat counters ("85% improvement" counting up)   │
│    - Lower-third banners                             │
│    - Logo placement (if uploaded)                    │
│  • These render as transparent PNG sequences         │
│    composited OVER the video track                   │
│                                                      │
│  SCENE MEDIA PRIORITY:                               │
│  1. User-uploaded video (if assigned by director)    │
│  2. Pexels video clip (if available)                 │
│  3. Pexels photo + Ken Burns (fallback)              │
│  4. Procedural gradient background (last resort)     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 4: TTS VOICE ENGINE                           │
│                                                      │
│  Input: SceneScript[].narration_text                 │
│  Output: per-scene WAV + word timestamps             │
│                                                      │
│  • Edge-TTS with en-US-JennyNeural                   │
│  • WordBoundary timestamps for subtitle sync         │
│  • VAD silence trimming                              │
│  • Dynamic scene duration = audio duration + 0.5s    │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 5: VIDEO COMPOSITOR (FFmpeg + OpenCV)         │
│                                                      │
│  Assembles final video:                              │
│                                                      │
│  Layer stack (bottom to top):                        │
│  ┌─────────────────────────────┐                     │
│  │ L1: Background video/image  │ (full frame)       │
│  │ L2: Color grade overlay     │ (consistent look)  │
│  │ L3: Motion graphics         │ (titles, stats)    │
│  │ L4: Subtitle bar            │ (single, bottom)   │
│  └─────────────────────────────┘                     │
│                                                      │
│  Scene transitions:                                  │
│  • Crossfade (default, 0.5s)                         │
│  • Slide left/right                                  │
│  • Zoom through                                      │
│                                                      │
│  Audio mix:                                          │
│  • Voice track (100% volume)                         │
│  • Background music (15% volume, ducked under voice) │
│                                                      │
│  Output: 1280x720 H.264 MP4, 30fps                  │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  PHASE 6: QUALITY REVIEWER                           │
│                                                      │
│  Validates:                                          │
│  • File size > 0                                     │
│  • Video duration matches expected                   │
│  • Audio track present                               │
│  • Resolution correct                                │
│  • No black frames                                   │
└─────────────────────────────────────────────────────┘
```

---

## FILE CHANGES REQUIRED

### NEW FILES TO CREATE

```
agents/video/
├── pipeline_v2.py              # New orchestrator replacing EndToEndVideoPipeline
├── ai_director.py              # Phase 1: LLM-powered director
├── ai_screenwriter.py          # Phase 2: LLM-powered script writer
├── media_assembler.py          # Phase 3: Smart media collection & assignment
├── motion_graphics.py          # Phase 3C: Text overlay animations
├── video_compositor.py         # Phase 5: Layer-based video assembly
├── user_upload_manager.py      # Handle uploaded video files
└── schemas_v2.py               # New Pydantic schemas for V2 pipeline
```

### FILES TO MODIFY

```
agents/video/agent.py           # Route to pipeline_v2 instead of legacy
backend/app/api/endpoints/      # Add upload endpoint for user videos
backend/app/api/router.py       # Register new upload route
```

---

## SCHEMA DEFINITIONS

### Phase 1 Output: VideoDirectorPlan

```python
class VideoDirectorPlan(BaseModel):
    title: str                          # "AI Revolution in Healthcare"
    narrative_arc: str                  # "hook-problem-solution-proof-cta"
    total_target_duration: int          # 60 (seconds)
    color_palette: dict                 # {"primary": "#1a1a2e", "accent": "#e94560", "text": "#ffffff"}
    music_mood: str                     # "corporate_upbeat"
    scenes: list[DirectorScene]

class DirectorScene(BaseModel):
    scene_number: int
    purpose: str                        # "hook", "problem", "solution", "proof", "cta"
    mood: str                           # "energetic", "serious", "hopeful"
    visual_strategy: str                # "user_upload_1", "stock_video", "motion_graphic"
    target_duration: float              # 8.0 seconds
    key_message: str                    # "AI reduces diagnostic errors by 40%"
    uploaded_file_ref: Optional[str]    # "video1.mp4" if using user upload
```

### Phase 2 Output: SceneScript

```python
class SceneScript(BaseModel):
    scene_number: int
    narration_text: str                 # "In today's healthcare landscape, artificial intelligence is transforming how doctors diagnose diseases..."
    on_screen_title: Optional[str]      # "The AI Advantage" (short, impactful)
    on_screen_stats: Optional[list[str]]# ["40% fewer errors", "3x faster diagnosis"]
    visual_description: str             # "Doctor using tablet with AI interface, hospital setting"
    stock_search_queries: list[str]     # ["doctor tablet hospital", "medical AI interface", "hospital technology"]
    transition_type: str                # "crossfade", "slide_left", "zoom"
```

---

## LLM PROMPTS

### Director System Prompt

```
You are a professional video director. Given a user's topic and any uploaded
files they've provided, create a structured video plan.

Rules:
- Always start with a HOOK scene (grab attention in first 3 seconds)
- Follow with PROBLEM → SOLUTION → PROOF → CTA narrative arc
- Each scene: 5-12 seconds
- Total video: 30-90 seconds
- If user uploaded videos, assign them to the most relevant scenes
- Choose visual_strategy: "user_upload" when user file fits, "stock_video"
  for professional b-roll, "motion_graphic" for data/stats scenes

Output strict JSON matching the VideoDirectorPlan schema.
```

### Screenwriter System Prompt

```
You are a professional video scriptwriter. Given a director's plan,
write natural spoken narration for each scene.

Rules:
- Write as SPOKEN SPEECH, not written text (conversational, flowing)
- Each scene: 2-3 short sentences (15-25 words per scene)
- Scene 1 (hook): Start with a compelling question or bold statement
- Connect each scene to the next with natural transitions
- Include specific on_screen_title (3-5 words, impactful)
- Include stock_search_queries that will find RELEVANT footage
  (be specific: "surgeon operating room technology" not "medical")
- NEVER include the raw user prompt in narration text
- NEVER start narration with "Generate" or "Create"

Output strict JSON as an array of SceneScript objects.
```

---

## USER UPLOAD FEATURE

### Frontend Changes (Angular)

Add a file upload zone on the "New Deliverable" page:
- Drag & drop zone for .mp4, .mov, .webm files
- Multiple file upload support (up to 5 files)
- File preview thumbnails
- Upload to backend via multipart/form-data

### Backend Endpoint

```python
@router.post("/jobs/{job_id}/uploads")
async def upload_media(job_id: str, files: list[UploadFile]):
    """Accept user video uploads and store them for the pipeline."""
    upload_dir = STORAGE_DIR / job_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        path = upload_dir / f.filename
        with open(path, "wb") as out:
            content = await f.read()
            out.write(content)
        saved.append({"filename": f.filename, "path": str(path), "size": len(content)})
    return {"uploaded": saved}
```

### Pipeline Integration

```python
class UserUploadManager:
    """Analyzes and prepares user-uploaded videos for the pipeline."""

    def analyze(self, upload_dir: Path) -> list[UploadedMedia]:
        """Probe each uploaded file: duration, resolution, content description."""
        results = []
        for f in upload_dir.glob("*.mp4"):
            cap = cv2.VideoCapture(str(f))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frames / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            results.append(UploadedMedia(
                filename=f.name,
                path=str(f),
                duration=duration,
                resolution=f"{width}x{height}"
            ))
        return results

    def extract_segment(self, path: str, start: float, duration: float,
                        target_resolution: tuple = (1280, 720)) -> np.ndarray:
        """Extract and resize a segment of user video as frame array."""
        ...
```

---

## IMPLEMENTATION ORDER

### Step 1: AI Screenwriter with LLM (HIGH PRIORITY)
- Create `ai_screenwriter.py`
- Call Groq LLM with screenwriter system prompt
- Parse JSON response into SceneScript objects
- Wire into existing pipeline (replace deterministic fallback)
- **Test: generate a video and verify narration sounds natural**

### Step 2: AI Director with LLM
- Create `ai_director.py`
- Call Groq LLM with director system prompt
- Generate VideoDirectorPlan with narrative arc
- Feed plan into screenwriter
- **Test: verify scenes follow hook→problem→solution→proof→cta**

### Step 3: Smart Media Assembly
- Improve stock_search_queries (use screenwriter output)
- Rank Pexels results by relevance
- Ensure visual coherence between consecutive scenes
- **Test: verify stock footage matches narration topic**

### Step 4: Motion Graphics
- Create `motion_graphics.py`
- Animated text overlays (titles fade in/out)
- Stat counter animations
- Lower-third banners
- **Test: verify overlays appear and disappear cleanly**

### Step 5: User Upload Pipeline
- Backend upload endpoint
- Frontend drag & drop UI
- UserUploadManager analysis
- Director assigns uploads to scenes
- **Test: upload a video and verify it appears in the output**

### Step 6: Video Compositor V2
- Layer-based rendering
- Consistent color grading
- Smooth transitions
- Clean single subtitle
- **Test: full end-to-end render matches Vyra quality**

---

## IMPORTANT CONSTRAINTS

- Keep using Groq (Llama 3.3 70B) — it's free and already configured
- Keep using Edge-TTS with JennyNeural — already working
- Keep using Pexels API for stock video — already has key
- Keep using FFmpeg via imageio-ffmpeg — already installed
- Keep using OpenCV for frame manipulation — already installed
- Do NOT add new paid APIs
- Do NOT break existing presentation/latex agents
- Maintain the existing FastAPI + Angular architecture
- Each step should be independently testable
