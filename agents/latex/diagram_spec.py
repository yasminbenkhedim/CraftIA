"""
Structured descriptions of the diagrams a report can legitimately contain.

THE RULE THIS MODULE EXISTS TO ENFORCE
--------------------------------------
A generated figure is honest only when everything in it is already stated in the report's
own text. The previous diagram generator failed that test completely: it drew this
product's architecture -- "Angular 18 Frontend / FastAPI Backend / Agent Engines" -- into
every report whatever the subject, with only the caption changed.

So the structure is not invented here and it is not hardcoded. It is EXTRACTED from the
chapters the LLM already wrote, as data, and then validated against that same text: an
entity or component whose name does not appear in the report is dropped before anything
is drawn. A diagram that survives that check says nothing the report does not already say.

WHAT IS DELIBERATELY NOT GENERATED
----------------------------------
Anything carrying measurements: performance charts, latency graphs, coverage bars, load
test results. Those require numbers the student measured, and a plausible invented curve
is exactly the kind of thing a jury would (rightly) treat as fabricated data. Those keep
their "[Insérez votre graphique de résultats ici]" placeholder -- see
generators/figure_placeholder.py.
"""
import re
import unicodedata
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

class ArchitectureTier(BaseModel):
    """One horizontal layer: a name plus the components the report places in it."""
    name: str
    components: List[str] = Field(default_factory=list)


class ArchitectureSpec(BaseModel):
    title: str = ""
    tiers: List[ArchitectureTier] = Field(default_factory=list)
    # [source tier, target tier, label] -- e.g. ["Client", "Serveur", "HTTPS / JSON"].
    flows: List[List[str]] = Field(default_factory=list)

    def is_renderable(self) -> bool:
        """
        At least two tiers that actually contain something.

        Counting tiers alone was not enough: when grounding removed every component as
        ungrounded, three empty boxes remained and still reported themselves renderable --
        which would have drawn an "architecture" of the report's own tier names over a
        subject the report never described.
        """
        filled = [t for t in self.tiers if t.name and t.components]
        return len(filled) >= 2


# ---------------------------------------------------------------------------
# Entity-relationship
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    name: str
    attributes: List[str] = Field(default_factory=list)


class Relation(BaseModel):
    source: str
    target: str
    # Free text so the model can answer in the report's own notation ("1,N", "0..*").
    cardinality: str = ""
    label: str = ""


class ERSpec(BaseModel):
    title: str = ""
    entities: List[Entity] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)

    def is_renderable(self) -> bool:
        """
        Two entities are not a data model. A relationship is what an ER diagram is FOR,
        so a spec without one is not worth drawing: it renders as two disconnected boxes,
        one of them frequently empty, which tells the reader less than the placeholder
        asking the student to supply the real thing.
        """
        with_attrs = [e for e in self.entities if e.attributes]
        return len(self.entities) >= 2 and len(self.relations) >= 1 and len(with_attrs) >= 1


# ---------------------------------------------------------------------------
# Sequence
# ---------------------------------------------------------------------------

class SequenceMessage(BaseModel):
    source: str
    target: str
    label: str = ""
    # A dashed return arrow rather than a solid call.
    is_return: bool = False


class SequenceSpec(BaseModel):
    title: str = ""
    actors: List[str] = Field(default_factory=list)
    messages: List[SequenceMessage] = Field(default_factory=list)

    def is_renderable(self) -> bool:
        return len(self.actors) >= 2 and len(self.messages) >= 2


class DiagramSet(BaseModel):
    architecture: Optional[ArchitectureSpec] = None
    er: Optional[ERSpec] = None
    sequences: List[SequenceSpec] = Field(default_factory=list)

    def any_renderable(self) -> bool:
        return bool(
            (self.architecture and self.architecture.is_renderable())
            or (self.er and self.er.is_renderable())
            or any(s.is_renderable() for s in self.sequences)
        )


# ---------------------------------------------------------------------------
# Grounding: everything drawn must already be in the report
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t)).strip()


# Words that carry no evidence either way, so they neither prove nor disprove a label.
_STOPWORDS = {
    "de", "des", "du", "la", "le", "les", "et", "ou", "un", "une", "dans", "pour", "avec",
    "sur", "par", "the", "and", "for", "with", "layer", "couche", "tier", "module",
    "service", "services", "application", "app",
}


def _mentioned(name: str, corpus: str) -> bool:
    """
    True when the report's text actually supports drawing `name`.

    Matched on significant TOKENS rather than the whole string. A diagram label and the
    prose describing it rarely agree word for word: the text says "React 18" while the
    label reads "React 18 (SPA)", or "Sequelize" against "Sequelize ORM". Requiring the
    complete label as a substring rejected all of those -- and a check that deletes the
    real components as readily as the invented ones is no check at all.

    A label survives when at least half of its meaningful tokens appear in the report,
    and at least one does. That still removes anything genuinely absent: "Kafka",
    "Facturation" and "Redis" share no token with a text that never mentions them.
    """
    n = _normalize(name)
    # Only a one- or two-character label escapes the check; a three-letter acronym like
    # "JWT" is exactly the kind of thing that must be verified, not waved through.
    if len(n) < 3:
        return True
    if n in corpus:
        return True

    candidates = set(n.split())
    # A CamelCase identifier is often written with a space in prose ("MouvementStock" ->
    # "mouvement stock"). Applied only to genuinely mixed-case names: splitting an
    # all-caps acronym this way turns "API REST" into single letters, which then get
    # filtered out as too short and left the label with nothing to verify -- so it passed
    # against any text at all.
    raw = str(name)
    if raw != raw.upper():
        spaced = _normalize(re.sub(r"(?<!^)(?=[A-Z])", " ", raw))
        if spaced and spaced in corpus:
            return True
        candidates |= set(spaced.split())

    tokens = [t for t in candidates
              if len(t) >= 3 and t not in _STOPWORDS and not t.isdigit()]
    if not tokens:
        return True                     # nothing substantive left to verify
    present = sum(1 for t in tokens if t in corpus)
    return present >= 1 and present * 2 >= len(tokens)


def ground(spec: DiagramSet, report_text: str) -> tuple:
    """
    Drop anything the report does not actually mention. Returns (spec, [what was dropped]).

    This is the check that separates a generated diagram from a fabricated one. The model
    is asked to extract only what the text states, but asking is not proof -- so every
    component, entity and actor is verified against the text before it can be drawn, and
    a diagram left too thin to be meaningful is discarded entirely.
    """
    corpus = _normalize(report_text)
    dropped: List[str] = []

    if spec.architecture:
        for tier in spec.architecture.tiers:
            kept = [c for c in tier.components if _mentioned(c, corpus)]
            dropped += [f"architecture component '{c}'" for c in tier.components if c not in kept]
            tier.components = kept
        # A tier with nothing left in it is an empty box; drop it before deciding.
        empty = [t.name for t in spec.architecture.tiers if not t.components]
        if empty:
            dropped += [f"empty tier '{n}'" for n in empty]
            spec.architecture.tiers = [t for t in spec.architecture.tiers if t.components]
            kept_names = {t.name for t in spec.architecture.tiers}
            spec.architecture.flows = [f for f in spec.architecture.flows
                                       if len(f) >= 2 and f[0] in kept_names and f[1] in kept_names]
        if not spec.architecture.is_renderable():
            spec.architecture = None
            dropped.append("architecture diagram (too little grounded content)")

    if spec.er:
        kept_entities = [e for e in spec.er.entities if _mentioned(e.name, corpus)]
        dropped += [f"entity '{e.name}'" for e in spec.er.entities if e not in kept_entities]
        spec.er.entities = kept_entities
        names = {e.name for e in kept_entities}
        # A relation pointing at an entity that was dropped would draw an arrow to nothing.
        kept_rel = [r for r in spec.er.relations if r.source in names and r.target in names]
        dropped += [f"relation {r.source}->{r.target}" for r in spec.er.relations if r not in kept_rel]
        spec.er.relations = kept_rel
        if not spec.er.is_renderable():
            spec.er = None
            dropped.append("ER diagram (fewer than 2 grounded entities)")

    kept_seqs = []
    for seq in spec.sequences:
        actors = [a for a in seq.actors if _mentioned(a, corpus)]
        dropped += [f"actor '{a}'" for a in seq.actors if a not in actors]
        seq.actors = actors
        seq.messages = [m for m in seq.messages if m.source in actors and m.target in actors]
        if seq.is_renderable():
            kept_seqs.append(seq)
        else:
            dropped.append(f"sequence '{seq.title}' (not enough grounded participants)")
    spec.sequences = kept_seqs

    return spec, dropped
