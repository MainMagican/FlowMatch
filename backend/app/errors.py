"""Shared API error type used by all routers."""


class ApiError(Exception):
    """Raised by route handlers / services to produce a structured JSON error.

    Attributes:
        message: human-readable error message.
        status_code: HTTP status code to return.
        reasons: optional list of structured reason strings (used for the
            opportunity-publish blocking flow, design.md FR14, and the
            eligibility-filter blocking flow, design.md FR16).
    """

    def __init__(self, message, status_code=400, reasons=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.reasons = reasons or []

    def to_dict(self):
        payload = {"error": self.message}
        if self.reasons:
            payload["reasons"] = self.reasons
        return payload
