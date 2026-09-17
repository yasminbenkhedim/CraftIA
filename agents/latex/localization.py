"""
Report language: the chrome strings and the instruction given to the LLM.

Everything a reader sees that the LLM did not write -- "Table des matières",
"Résumé", page furniture, the placeholders a student must fill in -- lives here, so a
French report is French all the way through rather than French prose wrapped in English
headings.

The set of supported codes is deliberately NOT redefined here. `normalize` comes from
agents.video.language, which is the one place that decides what "fr" means for this
product; a second table would let the video selector and the report selector drift apart
and offer different languages. That module is a leaf (it imports only typing), so the
dependency costs nothing at import time.
"""
from typing import Dict

from agents.video.language import normalize  # noqa: F401  (re-exported deliberately)


class ReportStrings:
    """Chrome for one language."""

    def __init__(self, code: str, mapping: Dict[str, str]):
        self.code = code
        self._m = mapping

    def __getattr__(self, key: str) -> str:
        try:
            return self._m[key]
        except KeyError as exc:
            raise AttributeError(f"No '{key}' string for language '{self.code}'.") from exc


_EN = {
    "language_name": "English",
    # Front matter
    "toc_title": "Table of Contents",
    "abstract_title": "Abstract",
    "references_title": "References",
    # Cover labels
    "cover_university": "University",
    "cover_degree": "Final Year Project Report",
    "cover_author": "Submitted by",
    "cover_supervisor": "Supervisor",
    "cover_year": "Academic year",
    # Placeholders the student replaces. Square brackets on purpose -- they read as a
    # blank to fill, and they are trivially greppable in the finished PDF.
    "ph_author": "[Student name]",
    "ph_university": "[University / School]",
    "ph_supervisor": "[Supervisor]",
    "ph_year": "[Academic year]",
    "ph_figure": "[Insert your architecture diagram here]",
    "ph_chart": "[Insert your results chart here]",
    "ph_figure_hint": "This report generator does not invent figures. Replace this frame "
                      "with a diagram of your own system.",
    "ph_chart_hint": "Results charts are never generated: they would be invented "
                     "measurements. Insert your own benchmark, coverage or load-test "
                     "figures here.",
    "ph_references_note": "No references are generated automatically: an invented citation "
                          "is worse than none. Add the sources you actually consulted here.",
    "figure_label": "Figure",
    "llm_instruction": "Write in English.",
}

_FR = {
    "language_name": "Français",
    "toc_title": "Table des matières",
    "abstract_title": "Résumé",
    "references_title": "Références",
    "cover_university": "Université",
    "cover_degree": "Rapport de projet de fin d'études",
    "cover_author": "Réalisé par",
    "cover_supervisor": "Encadrant",
    "cover_year": "Année universitaire",
    "ph_author": "[Nom de l'étudiant]",
    "ph_university": "[Université / École]",
    "ph_supervisor": "[Nom de l'encadrant]",
    "ph_year": "[Année universitaire]",
    "ph_figure": "[Insérez votre schéma d'architecture ici]",
    "ph_chart": "[Insérez votre graphique de résultats ici]",
    "ph_figure_hint": "Ce générateur n'invente pas de figures. Remplacez ce cadre par un "
                      "schéma de votre propre système.",
    "ph_chart_hint": "Les graphiques de résultats ne sont jamais générés : ce seraient des "
                     "mesures inventées. Insérez ici vos propres relevés de performance, "
                     "de couverture ou de charge.",
    "ph_references_note": "Aucune référence n'est générée automatiquement : une citation "
                          "inventée est pire que pas de citation. Ajoutez ici les sources "
                          "que vous avez réellement consultées.",
    "figure_label": "Figure",
    "llm_instruction": (
        "Rédige entièrement en français, dans un registre académique soutenu. "
        "Les titres de chapitres et de sections doivent eux aussi être en français. "
        "Conserve en anglais uniquement les termes techniques usuels (React, Node.js, "
        "REST, front-end, back-end)."
    ),
}

_STRINGS = {"en": ReportStrings("en", _EN), "fr": ReportStrings("fr", _FR)}


def strings(language: str) -> ReportStrings:
    """Chrome for a language code, normalized first. Unknown codes fall back to English."""
    return _STRINGS[normalize(language)]
