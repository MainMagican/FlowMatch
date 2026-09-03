"""Deterministic step-breakdown helper for the Guided Workspace
(design.md FR24, spec section 14.3). Never fabricates business facts - every
sentence is built directly from stored workflow/opportunity data. Always
states that human review is required.
"""


class GuidedTaskAssistantService:
    def build_guidance(self, opportunity, stage, workflow):
        steps = []
        steps.append("Understand the goal: {}".format(opportunity.get("desired_outcome") or "not specified by the owner yet."))
        if stage:
            steps.append("This opportunity sits at the workflow stage '{}': {}".format(
                stage.get("name"), stage.get("description") or "no further description provided."
            ))
            if stage.get("inputs"):
                steps.append("Confirm you have the required input: {}".format(stage["inputs"]))
            if stage.get("outputs"):
                steps.append("Your expected output for this stage is: {}".format(stage["outputs"]))
        steps.append("Definition of done: {}".format(opportunity.get("definition_of_done") or "not specified - ask the reviewer before proceeding."))
        if opportunity.get("participation_boundary"):
            steps.append("Stay within this boundary: {}".format(opportunity["participation_boundary"]))
        if opportunity.get("escalation_points"):
            steps.append("Escalate to the reviewer if: {}".format(opportunity["escalation_points"]))
        steps.append("Prepare your draft output and submit it for review - the reviewer will confirm before it is considered final. This guidance is a suggestion; it does not replace human review.")
        return {
            "steps": steps,
            "workflow_name": workflow.get("name") if workflow else None,
            "requires_human_review": True,
        }
