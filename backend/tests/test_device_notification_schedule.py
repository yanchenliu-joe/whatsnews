"""Tests for per-device scheduled push delivery (Phase 34, added 2026-07-06).

Devices can register a preferred local delivery time (notification_time +
timezone) via POST /devices; a separate tick loop
(_run_device_notification_tick) delivers the already-generated day's push to
each device once its local time arrives, instead of blasting everyone the
instant the pipeline finishes. Devices with no preference (notification_time
IS NULL) keep the pre-Phase-34 behavior of an immediate push. No test hits
the real Supabase instance or the real Expo push API.
"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import MagicMock, patch

import app.main as main
from app.notifications.device_scheduler import (
    _immediate_group_devices,
    _is_device_due_for_push,
    _mark_devices_pushed,
    _run_device_notification_tick,
    _todays_report_exists,
)
from app.pipeline.orchestrator import _notify_after_pipeline


def _fake_conn(fetchone_results=None, fetchall_results=None) -> MagicMock:
    fetchone_queue = list(fetchone_results or [])
    fetchall_queue = list(fetchall_results or [])
    cur = MagicMock()
    cur.fetchone.side_effect = lambda: fetchone_queue.pop(0) if fetchone_queue else None
    cur.fetchall.side_effect = lambda: fetchall_queue.pop(0) if fetchall_queue else []
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class IsDeviceDueForPushTests(unittest.TestCase):
    def test_due_when_local_time_has_passed_and_not_sent_today(self) -> None:
        now_utc = datetime(2026, 7, 6, 15, 0, tzinfo=dt_timezone.utc)  # 08:00 America/Los_Angeles (PDT)
        is_due, local_today = _is_device_due_for_push(now_utc, "07:30", "America/Los_Angeles", None)
        self.assertTrue(is_due)
        self.assertEqual(local_today, date(2026, 7, 6))

    def test_not_due_before_target_time(self) -> None:
        now_utc = datetime(2026, 7, 6, 13, 0, tzinfo=dt_timezone.utc)  # 06:00 America/Los_Angeles
        is_due, _ = _is_device_due_for_push(now_utc, "07:30", "America/Los_Angeles", None)
        self.assertFalse(is_due)

    def test_not_due_if_already_sent_today(self) -> None:
        now_utc = datetime(2026, 7, 6, 15, 0, tzinfo=dt_timezone.utc)
        is_due, _ = _is_device_due_for_push(
            now_utc, "07:30", "America/Los_Angeles", date(2026, 7, 6)
        )
        self.assertFalse(is_due)

    def test_due_again_if_last_sent_was_a_different_day(self) -> None:
        now_utc = datetime(2026, 7, 6, 15, 0, tzinfo=dt_timezone.utc)
        is_due, local_today = _is_device_due_for_push(
            now_utc, "07:30", "America/Los_Angeles", date(2026, 7, 5)
        )
        self.assertTrue(is_due)
        self.assertEqual(local_today, date(2026, 7, 6))

    def test_missing_timezone_falls_back_to_scheduler_timezone_env(self) -> None:
        with patch.dict(os.environ, {"SCHEDULER_TIMEZONE": "America/Los_Angeles"}):
            now_utc = datetime(2026, 7, 6, 15, 0, tzinfo=dt_timezone.utc)
            is_due, _ = _is_device_due_for_push(now_utc, "07:30", None, None)
        self.assertTrue(is_due)

    def test_malformed_notification_time_is_not_due(self) -> None:
        now_utc = datetime(2026, 7, 6, 15, 0, tzinfo=dt_timezone.utc)
        is_due, _ = _is_device_due_for_push(now_utc, "garbage", "UTC", None)
        self.assertFalse(is_due)

    def test_invalid_timezone_falls_back_to_utc(self) -> None:
        now_utc = datetime(2026, 7, 6, 8, 0, tzinfo=dt_timezone.utc)
        is_due, local_today = _is_device_due_for_push(now_utc, "07:00", "Not/ARealZone", None)
        self.assertTrue(is_due)
        self.assertEqual(local_today, date(2026, 7, 6))


class TodaysReportExistsTests(unittest.TestCase):
    def test_true_when_row_found(self) -> None:
        conn = _fake_conn(fetchone_results=[(1,)])
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            self.assertTrue(_todays_report_exists(date(2026, 7, 6)))

    def test_false_when_no_row(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            self.assertFalse(_todays_report_exists(date(2026, 7, 6)))

    def test_false_when_no_database(self) -> None:
        with patch("app.notifications.device_scheduler.get_connection", side_effect=ValueError("no db")):
            self.assertFalse(_todays_report_exists(date(2026, 7, 6)))

    def test_false_when_query_raises(self) -> None:
        conn = MagicMock()
        conn.cursor.side_effect = Exception("boom")
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            self.assertFalse(_todays_report_exists(date(2026, 7, 6)))


class ImmediateGroupDevicesTests(unittest.TestCase):
    def test_returns_devices_with_null_notification_time(self) -> None:
        conn = _fake_conn(fetchall_results=[[
            {"id": 1, "push_token": "a"}, {"id": 2, "push_token": "b"},
        ]])
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            devices = _immediate_group_devices(date(2026, 7, 6))
        self.assertEqual(devices, [{"id": 1, "push_token": "a"}, {"id": 2, "push_token": "b"}])
        executed_sql = conn.cursor.return_value.execute.call_args[0][0]
        self.assertIn("notification_time IS NULL", executed_sql)
        self.assertIn("last_push_sent_date", executed_sql)

    def test_no_database_returns_empty_list(self) -> None:
        with patch("app.notifications.device_scheduler.get_connection", side_effect=ValueError("no db")):
            self.assertEqual(_immediate_group_devices(date(2026, 7, 6)), [])


class MarkDevicesPushedTests(unittest.TestCase):
    def test_updates_last_push_sent_date_for_each_id(self) -> None:
        conn = _fake_conn()
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            _mark_devices_pushed([1, 2], date(2026, 7, 6))
        update_calls = conn.cursor.return_value.execute.call_args_list
        self.assertEqual(len(update_calls), 2)
        self.assertEqual(update_calls[0][0][1], (date(2026, 7, 6), 1))
        self.assertEqual(update_calls[1][0][1], (date(2026, 7, 6), 2))

    def test_no_ids_is_a_noop(self) -> None:
        with patch("app.notifications.device_scheduler.get_connection") as mock_conn:
            _mark_devices_pushed([], date(2026, 7, 6))
        mock_conn.assert_not_called()


class RegisterDeviceUpsertTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        self.client = TestClient(main.app)

    def test_full_valid_body_upserts_all_fields(self) -> None:
        conn = _fake_conn()
        with patch("app.public_routes.get_connection", return_value=conn):
            response = self.client.post("/devices", json={
                "push_token": "ExponentPushToken[abc]",
                "platform": "ios",
                "notification_time": "07:30",
                "timezone": "America/Los_Angeles",
            })
        self.assertEqual(response.status_code, 200)
        executed_sql, params = conn.cursor.return_value.execute.call_args[0]
        self.assertIn("ON CONFLICT (push_token) DO UPDATE", executed_sql)
        self.assertEqual(params, ("ExponentPushToken[abc]", "ios", "07:30", "America/Los_Angeles"))

    def test_missing_push_token_is_422(self) -> None:
        response = self.client.post("/devices", json={})
        self.assertEqual(response.status_code, 422)

    def test_invalid_notification_time_format_is_422(self) -> None:
        response = self.client.post("/devices", json={
            "push_token": "tok", "notification_time": "7:30am",
        })
        self.assertEqual(response.status_code, 422)

    def test_invalid_timezone_is_422(self) -> None:
        response = self.client.post("/devices", json={
            "push_token": "tok", "timezone": "Mars/Colony_One",
        })
        self.assertEqual(response.status_code, 422)

    def test_null_notification_time_clears_it(self) -> None:
        conn = _fake_conn()
        with patch("app.public_routes.get_connection", return_value=conn):
            response = self.client.post("/devices", json={
                "push_token": "tok", "notification_time": None,
            })
        self.assertEqual(response.status_code, 200)
        params = conn.cursor.return_value.execute.call_args[0][1]
        self.assertIsNone(params[2])

    def test_bare_registration_without_schedule_fields_still_works(self) -> None:
        conn = _fake_conn()
        with patch("app.public_routes.get_connection", return_value=conn):
            response = self.client.post("/devices", json={"push_token": "tok", "platform": "android"})
        self.assertEqual(response.status_code, 200)


class NotifyAfterPipelineImmediateGroupTests(unittest.TestCase):
    def test_sends_only_to_immediate_group_not_everyone(self) -> None:
        with patch("app.pipeline.orchestrator._build_push_copy", return_value=("WhatsNews", "Top story", None)), \
             patch("app.pipeline.orchestrator._immediate_group_devices", return_value=[{"id": 1, "push_token": "tok-a"}]) as mock_immediate, \
             patch("app.pipeline.orchestrator._send_push_to_tokens", return_value={"status": "ok", "sent": 1, "errors": 0}) as mock_send, \
             patch("app.notifications.push._send_push_to_all_devices") as mock_blast, \
             patch("app.pipeline.orchestrator._mark_devices_pushed") as mock_mark, \
             patch("app.pipeline.orchestrator._record_event"):
            _notify_after_pipeline({"status": "completed"})

        mock_immediate.assert_called_once()
        mock_send.assert_called_once_with(["tok-a"], "WhatsNews", "Top story", None)
        mock_blast.assert_not_called()
        mock_mark.assert_called_once_with([1], mock_immediate.call_args[0][0])

    def test_skips_when_pipeline_not_completed(self) -> None:
        with patch("app.pipeline.orchestrator._send_push_to_tokens") as mock_send:
            _notify_after_pipeline({"status": "failed"})
        mock_send.assert_not_called()

    def test_second_slot_same_day_does_not_repush_already_marked_devices(self) -> None:
        """Devices _immediate_group_devices() already excluded (last_push_sent_date ==
        today) simply never appear in its result — this asserts _notify_after_pipeline
        only ever sends to whatever that function returns, so its own dedup query is
        the single source of truth (tested separately in ImmediateGroupDevicesTests)."""
        with patch("app.pipeline.orchestrator._build_push_copy", return_value=("WhatsNews", "Top story", None)), \
             patch("app.pipeline.orchestrator._immediate_group_devices", return_value=[]) as mock_immediate, \
             patch("app.pipeline.orchestrator._send_push_to_tokens", return_value={"status": "skipped", "sent": 0, "errors": 0}) as mock_send, \
             patch("app.pipeline.orchestrator._mark_devices_pushed") as mock_mark:
            _notify_after_pipeline({"status": "completed"})

        mock_send.assert_called_once_with([], "WhatsNews", "Top story", None)
        mock_mark.assert_not_called()


class RunDeviceNotificationTickTests(unittest.TestCase):
    def test_skips_when_no_report_yet(self) -> None:
        with patch("app.notifications.device_scheduler._todays_report_exists", return_value=False), \
             patch("app.notifications.device_scheduler._send_push_to_tokens") as mock_send:
            result = _run_device_notification_tick()
        self.assertEqual(result["status"], "skipped")
        mock_send.assert_not_called()

    def test_sends_only_to_due_devices_and_marks_them_sent(self) -> None:
        devices = [
            {"id": 1, "push_token": "due-tok", "notification_time": "07:00",
             "timezone": "UTC", "last_push_sent_date": None},
            {"id": 2, "push_token": "not-due-tok", "notification_time": "23:00",
             "timezone": "UTC", "last_push_sent_date": None},
        ]
        conn = _fake_conn(fetchall_results=[devices])

        def fake_is_due(now_utc, notification_time, tz, last_sent):
            return (notification_time == "07:00"), date(2026, 7, 6)

        with patch("app.notifications.device_scheduler._todays_report_exists", return_value=True), \
             patch("app.notifications.device_scheduler.get_connection", return_value=conn), \
             patch("app.notifications.device_scheduler._is_device_due_for_push", side_effect=fake_is_due), \
             patch("app.notifications.device_scheduler._build_push_copy", return_value=("WhatsNews", "Top story", None)), \
             patch("app.notifications.device_scheduler._send_push_to_tokens", return_value={"status": "ok", "sent": 1, "errors": 0}) as mock_send, \
             patch("app.notifications.device_scheduler._record_event"):
            result = _run_device_notification_tick()

        mock_send.assert_called_once_with(["due-tok"], "WhatsNews", "Top story", None)
        self.assertEqual(result["sent"], 1)
        update_calls = [
            c for c in conn.cursor.return_value.execute.call_args_list if "UPDATE" in c[0][0]
        ]
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][0][1][1], 1)  # device_id param for the due device

    def test_no_due_devices_sends_nothing(self) -> None:
        devices = [{"id": 1, "push_token": "tok", "notification_time": "23:00",
                    "timezone": "UTC", "last_push_sent_date": None}]
        conn = _fake_conn(fetchall_results=[devices])
        with patch("app.notifications.device_scheduler._todays_report_exists", return_value=True), \
             patch("app.notifications.device_scheduler.get_connection", return_value=conn), \
             patch("app.notifications.device_scheduler._is_device_due_for_push", return_value=(False, date(2026, 7, 6))), \
             patch("app.notifications.device_scheduler._send_push_to_tokens") as mock_send:
            result = _run_device_notification_tick()
        mock_send.assert_not_called()
        self.assertEqual(result["sent"], 0)


if __name__ == "__main__":
    unittest.main()
