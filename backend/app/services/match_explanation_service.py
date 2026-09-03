"""Builds the human-readable "Recommended because..." explanation
(design.md FR18, spec section 12.5). Deterministic - not a call to an
external LLM (docs/DECISIONS.md #4).
"""


class MatchExplanationService:
    def build_explanation(self, opportunity, components, eligibility_reasons):
        matched = [c for c in components if c["matched"]]
        missing = [c for c in components if not c["matched"]]

        if matched:
            reasons_text = "; ".join(c["detail"] for c in matched)
            headline = "Recommended because: {}.".format(reasons_text)
        else:
            headline = "Recommended as a possible fit, though no strong overlap was found yet."

        return {
            "headline": headline,
            "matched_components": matched,
            "missing_components": missing,
            "eligibility_notes": eligibility_reasons,
            "human_approval_required": "The opportunity owner must approve your expression of interest before you can start.",
        }
