"""
MotionGraphicsDataValidator for CraftAI (Upgrade 7).
Enforces strict data integrity, zero-total pie detection, category count bounds, and scale policy rules.
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
from agents.video.motion_graphics.schemas import MetricDatum, CategoryDatum, MotionChartType

logger = logging.getLogger("uvicorn")


class MotionGraphicsDataValidator:
    """
    Data validation & honest chart scale policy engine.
    Ensures no malformed or misleading graphic renders silently.
    """

    @classmethod
    def validate_category_data(
        cls,
        categories: List[CategoryDatum],
        chart_type: MotionChartType = MotionChartType.BAR
    ) -> Tuple[bool, List[CategoryDatum], List[str]]:
        warnings = []
        if not categories:
            warnings.append("Empty category list provided")
            return False, [], warnings

        valid_cats = []
        seen_cats = set()
        total_val = 0.0

        for cat in categories:
            if not cat.category or cat.category.strip() == "":
                warnings.append(f"Skipping empty category label in {cat}")
                continue
            if cat.category in seen_cats:
                warnings.append(f"Duplicate category '{cat.category}' detected -- deduplicating")
                continue

            # Chart-specific numeric rules
            if chart_type in (MotionChartType.PIE, MotionChartType.DONUT) and cat.value < 0:
                warnings.append(f"Negative value {cat.value} prohibited in {chart_type.value} chart -- clamping to 0")
                cat.value = max(0.0, cat.value)

            seen_cats.add(cat.category)
            total_val += abs(cat.value)
            valid_cats.append(cat)

        if chart_type in (MotionChartType.PIE, MotionChartType.DONUT) and total_val <= 0.0001:
            warnings.append(f"Zero-total data detected for {chart_type.value} chart")
            return False, valid_cats, warnings

        # Category count bounds limit
        if len(valid_cats) > 12:
            warnings.append(f"Excessive category count ({len(valid_cats)} > 12) -- truncating for visual readability")
            valid_cats = valid_cats[:12]

        return True, valid_cats, warnings
