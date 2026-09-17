"""
Reads the generated chapters and describes the diagrams they already imply.

Runs AFTER chapter generation, deliberately. The planner's outline says what the report
will cover; only the finished text says what it actually describes -- which entities the
"Modélisation des données" section defines, which components the architecture section
names. Extracting from the text is what makes the resulting figure a picture of this
report rather than a picture of a plausible report.

Everything it returns is then verified against that same text (diagram_spec.ground), so a
component the model added on its own initiative never reaches the page.

Failure here is NOT fatal. A report with placeholder figures is complete and honest; a
failed job over a missing diagram would cost the student a credit and a render. So this
returns an empty set on any problem and the placeholders stay.
"""
import json
import logging
import time
from typing import List

from agents.latex.diagram_spec import DiagramSet, ground

logger = logging.getLogger("uvicorn")

# Only the sections that actually describe structure are sent, and each is capped, so the
# request stays inside the token budget the chapter generator is already pacing against.
MAX_CHARS_PER_SECTION = 1400
MAX_TOTAL_CHARS = 9000

# This call follows six chapter generations back to back, so the per-minute token budget
# is already exhausted when it starts. A settle pause first, then the same backoff the
# chapter generator uses.
SETTLE_SEC = 12.0
MAX_ATTEMPTS = 3
BACKOFF_BASE_SEC = 20.0

_SYSTEM = (
    "You extract diagram structure from an existing engineering report. "
    "You describe ONLY what the provided text already states. "
    "You never invent a component, entity, table, actor or relationship that the text "
    "does not mention. If the text does not describe something, return null for that "
    "diagram rather than filling it in. "
    "You never produce measurements, performance figures or test results of any kind. "
    "Output strict raw JSON and nothing else."
)

_SCHEMA = (
    '{"architecture":{"title":"...","tiers":[{"name":"Client","components":["React 18"]},'
    '{"name":"Serveur","components":["Express"]},{"name":"Donnees","components":["PostgreSQL"]}],'
    '"flows":[["Client","Serveur","HTTPS / JSON"],["Serveur","Donnees","SQL"]]},'
    '"er":{"title":"...","entities":[{"name":"Produit","attributes":["id","reference"]}],'
    '"relations":[{"source":"Produit","target":"MouvementStock","cardinality":"1,N","label":"concerne"}]},'
    '"sequences":[{"title":"Authentification","actors":["Utilisateur","Client React","API Express"],'
    '"messages":[{"source":"Utilisateur","target":"Client React","label":"saisit ses identifiants",'
    '"is_return":false}]}]}'
)


class DiagramExtractor:

    @classmethod
    def extract(cls, chapters: List, language: str = "en") -> DiagramSet:
        """
        Describe the report's architecture, data model and key flows, or return nothing.

        `chapters` are GeneratedChapter objects; only their text is used.
        """
        report_text = cls._corpus(chapters)
        if not report_text.strip():
            return DiagramSet()

        # Paced and retried like the chapter calls. This request lands immediately after
        # six chapter generations, so it arrives with the token-per-minute budget already
        # spent -- without a wait it simply fails and every figure silently reverts to a
        # placeholder, which looks like the feature not working at all.
        spec = None
        last = "not attempted"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                wait = BACKOFF_BASE_SEC * attempt
                logger.info(
                    f"DiagramExtractor: attempt {attempt - 1} failed ({last}); "
                    f"retrying in {wait:.0f}s."
                )
                time.sleep(wait)
            else:
                time.sleep(SETTLE_SEC)
            try:
                spec = cls._ask(report_text, language)
                break
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"

        if spec is None:
            logger.warning(
                f"DiagramExtractor: could not extract diagram structure after "
                f"{MAX_ATTEMPTS} attempts ({last}); the report keeps its figure "
                f"placeholders. The report itself is unaffected."
            )
            return DiagramSet()

        spec, dropped = ground(spec, report_text)
        for item in dropped:
            logger.info(f"DiagramExtractor: dropped {item} -- not found in the report's own text.")

        if spec.any_renderable():
            bits = []
            if spec.architecture:
                bits.append(f"architecture ({len(spec.architecture.tiers)} tiers)")
            if spec.er:
                bits.append(f"ER ({len(spec.er.entities)} entities, "
                            f"{len(spec.er.relations)} relations)")
            if spec.sequences:
                bits.append(f"{len(spec.sequences)} sequence diagram(s)")
            logger.info(f"DiagramExtractor: grounded structure -- {', '.join(bits)}.")
        else:
            logger.info("DiagramExtractor: nothing verifiable to draw; keeping placeholders.")
        return spec

    # ------------------------------------------------------------------

    @staticmethod
    def _corpus(chapters: List) -> str:
        """The report's text, trimmed to the parts that describe structure."""
        parts = []
        total = 0
        for ch in chapters:
            for title, body in (ch.sections or {}).items():
                chunk = f"[{ch.title} / {title}]\n{str(body)[:MAX_CHARS_PER_SECTION]}"
                if total + len(chunk) > MAX_TOTAL_CHARS:
                    return "\n\n".join(parts)
                parts.append(chunk)
                total += len(chunk)
        return "\n\n".join(parts)

    @classmethod
    def _ask(cls, report_text: str, language: str) -> DiagramSet:
        import sys
        from pathlib import Path
        backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from app.services.llm import LLMService

        user_msg = (
            "Here are sections of an engineering report:\n\n"
            f"{report_text}\n\n"
            "From THIS text only, describe three diagrams:\n"
            "1. architecture -- the tiers and the components the report places in each. Use "
            "the exact technology names the text uses.\n"
            "2. er -- the entities the report defines for its data model, their main "
            "attributes, and the relationships between them with their cardinalities.\n"
            "3. sequences -- up to two interaction flows the text actually describes "
            "(for example an authentication flow, or creating a record). List the "
            "participants and the ordered messages between them.\n"
            "Use null for any diagram the text does not describe. Do not add anything that "
            "is not in the text above. Keep every label under 40 characters. "
            "Keep the labels in the language of the text.\n"
            f"Output strict JSON shaped exactly like: {_SCHEMA}"
        )

        # Empty fallback: LLMService returns this argument instead of raising, so {} is
        # what distinguishes a failed call from a real answer.
        raw = LLMService.generate_json(user_msg, _SYSTEM, {})
        if not isinstance(raw, dict) or not raw:
            raise ValueError("no JSON returned")
        raw.pop("_llm_meta", None)
        return DiagramSet.model_validate(json.loads(json.dumps(raw)))
