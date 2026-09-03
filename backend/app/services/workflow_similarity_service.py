"""Deterministic similarity heuristic between two workflow stages
(design.md FR21, spec section 13.2-13.3). Not a real ML model
(docs/DECISIONS.md #4) - compares simple keyword/input/output/system overlap
and always states required owner confirmation.
"""

STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "is", "are"}


def _keywords(text):
    if not text:
        return set()
    words = [w.strip(".,;:()").lower() for w in text.split()]
    return {w for w in words if w and w not in STOPWORDS}


class WorkflowSimilarityService:
    def compare_stages(self, stage_a, stage_b):
        kw_a = _keywords(stage_a.get("activities") or stage_a.get("description"))
        kw_b = _keywords(stage_b.get("activities") or stage_b.get("description"))
        shared = kw_a & kw_b
        differences = (kw_a | kw_b) - shared

        systems_a = _keywords(stage_a.get("systems"))
        systems_b = _keywords(stage_b.get("systems"))
        shared_systems = systems_a & systems_b

        total_terms = len(kw_a | kw_b) or 1
        overlap_ratio = len(shared) / total_terms
        if overlap_ratio >= 0.4 or shared_systems:
            confidence = "medium-high"
        elif overlap_ratio > 0.15:
            confidence = "low-medium"
        else:
            confidence = "low"

        return {
            "shared_characteristics": sorted(shared) + ["shared systems: " + ", ".join(sorted(shared_systems))] if shared_systems else sorted(shared),
            "differences": sorted(differences),
            "confidence": confidence,
            "requires_owner_confirmation": True,
            "recommendation": (
                "Both workflow owners should review this similarity and confirm whether the "
                "processes are genuinely comparable before any reuse is considered."
            ),
        }
