"""
Push notification delivery — Expo Push API senders plus the per-device
scheduled-delivery tick loop (Phase 34).

Public API:
  _send_push_to_tokens(tokens, title, body, data=None) -> dict
  _send_push_to_all_devices(title, body, data=None) -> dict
  _run_device_notification_tick() -> dict
  _device_notification_scheduler_loop() -> None (async loop)
  _build_push_copy() -> tuple
"""

from app.notifications.push import EXPO_PUSH_URL, _send_push_to_all_devices, _send_push_to_tokens
from app.notifications.device_scheduler import (
    _FALLBACK_PUSH_COPY,
    _build_push_copy,
    _device_notification_scheduler_loop,
    _immediate_group_devices,
    _is_device_due_for_push,
    _mark_devices_pushed,
    _run_device_notification_tick,
    _todays_report_exists,
)

__all__ = [
    "EXPO_PUSH_URL",
    "_send_push_to_all_devices",
    "_send_push_to_tokens",
    "_FALLBACK_PUSH_COPY",
    "_build_push_copy",
    "_device_notification_scheduler_loop",
    "_immediate_group_devices",
    "_is_device_due_for_push",
    "_mark_devices_pushed",
    "_run_device_notification_tick",
    "_todays_report_exists",
]
