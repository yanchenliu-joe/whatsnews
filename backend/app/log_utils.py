"""Shared structured logging helper, used across every pipeline/admin/notification module."""


def _log(event: str, **kwargs) -> None:
    """
    Emit a structured log line for all generation lifecycle events.
    Format: [whatsnews] event=<name> key=value ...
    """
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())
