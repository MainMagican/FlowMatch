"""Deterministic mock AI service that drafts a workflow from pasted source text.

Per docs/DECISIONS.md #4: no external AI provider is configured in this
environment, so this is a rule-based heuristic (not a real LLM call). It never
invents facts - every stage comes directly from a line of the pasted text.
Fields the heuristic cannot confidently determine are recorded in
uncertain_fields so the human owner knows what to check (design.md FR8).
"""

import re

DEFAULT_UNCERTAIN_FIELDS = ["responsible_role", "systems", "effort", "sensitivity"]


class WorkflowExtractionService:
    """Deterministic WorkflowExtractionService (docs/DECISIONS.md #4)."""

    def extract_stages(self, source_text):
        """Split pasted source text into a draft list of stages.

        Each non-empty line (optionally numbered, e.g. "1. Export records")
        becomes one stage. This is intentionally simple/deterministic per the
        MVP's "no external AI provider" constraint.
        """
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        stages = []
        for index, line in enumerate(lines, start=1):
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
            stages.append(
                {
                    "name": cleaned[:80],
                    "description": cleaned,
                    "sequence": index,
                    "activities": cleaned,
                    "responsible_role": None,
                    "inputs": None,
                    "outputs": None,
                    "systems": None,
                    "handoffs": None,
                    "decision_points": None,
                    "ai_generated": True,
                    "uncertain_fields": list(DEFAULT_UNCERTAIN_FIELDS),
                }
            )
        return stages
