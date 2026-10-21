from __future__ import annotations


class YouTubeMCPError(ValueError):
    """Application failure with a stable code for a client to diagnose."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(f"{code}: {message}" )
        self.code = code
        self.retryable = retryable
