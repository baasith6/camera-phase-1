import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.instance_lock import InstanceLock
from app.runtime import RuntimeState
from app.store import LocalStore
from app import tray


class InstanceLockTests(unittest.TestCase):
    def test_second_connector_instance_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            first = InstanceLock(temp)
            second = InstanceLock(temp)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_unwritable_lock_path_returns_false(self):
        lock = InstanceLock("ignored")
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            self.assertFalse(lock.acquire())


class LocalStoreConcurrencyTests(unittest.TestCase):
    @patch("app.runtime.os.cpu_count", return_value=12)
    def test_worker_counts_are_cpu_aware_and_capped(self, _cpu_count):
        state = RuntimeState()
        snapshot = state.snapshot()
        self.assertEqual(snapshot["logicalCpus"], 12)
        self.assertEqual(snapshot["analysisWorkers"], 4)
        self.assertEqual(snapshot["ffmpegWorkers"], 2)
        state.shutdown_workers()

    def test_analysis_pool_returns_result(self):
        state = RuntimeState()
        self.assertEqual(state.run_analysis(lambda value: value * 2, 21), 42)
        self.assertEqual(state.snapshot()["analysisQueueDepth"], 0)
        state.shutdown_workers()

    @patch("app.runtime.os.cpu_count", return_value=8)
    def test_clip_queue_applies_backpressure(self, _cpu_count):
        state = RuntimeState()
        release = threading.Event()

        def blocked_job():
            release.wait(timeout=2)
            return "clip.mp4"

        accepted = [state.submit_clip_job(blocked_job) for _ in range(4)]
        self.assertEqual(accepted, [True, True, True, True])
        self.assertFalse(state.submit_clip_job(blocked_job))
        self.assertEqual(state.snapshot()["clipJobsDropped"], 1)
        release.set()
        state.shutdown_workers()

    def test_runtime_logs_clear_atomically(self):
        state = RuntimeState()
        state.log("first")
        state.log("second")
        self.assertEqual(state.clear_logs(), 2)
        self.assertEqual(state.snapshot()["logs"], [])
        state.shutdown_workers()

    def test_reference_frame_is_separate_from_live_frame(self):
        state = RuntimeState()
        state.cache_reference_frame("camera-1", b"stable")
        state.cache_frame("camera-1", b"live")
        self.assertEqual(state.get_reference_frame("camera-1"), b"stable")
        self.assertEqual(state.get_frame("camera-1"), b"live")
        state.shutdown_workers()

    def test_managed_stop_preserves_local_control_state(self):
        state = RuntimeState()
        state.cache_frame("camera-1", b"last-live-frame")
        state.cache_reference_frame("camera-1", b"saved-zone-frame")
        state.set_paused(True)
        self.assertTrue(state.capture_paused)
        self.assertEqual(state.snapshot()["monitoringState"], "stopped")
        self.assertEqual(state.get_frame("camera-1"), b"last-live-frame")
        self.assertEqual(state.get_reference_frame("camera-1"), b"saved-zone-frame")
        stopped = threading.Event()
        stopped.set()
        self.assertFalse(state.wait_until_running(stopped, timeout=0.001))

        state.set_paused(False)
        self.assertEqual(state.snapshot()["monitoringState"], "running")
        self.assertTrue(state.wait_until_running(threading.Event(), timeout=0.001))
        state.shutdown_workers()

    def test_managed_stop_rejects_queued_event_analysis_and_clip_work(self):
        state = RuntimeState()
        state.set_paused(True)
        called = []

        event = state.submit_event(lambda: called.append("event"))
        self.assertIsNone(event.result(timeout=1))
        self.assertIsNone(state.run_analysis(lambda: called.append("analysis")))
        self.assertTrue(state.submit_clip_job(lambda: called.append("clip")))
        state.shutdown_workers()
        self.assertEqual(called, [])

    def test_monitoring_pause_setting_survives_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            store = LocalStore(temp)
            self.assertFalse(store.get_bool_setting("monitoring_paused"))
            store.set_bool_setting("monitoring_paused", True)
            store.close()

            reopened = LocalStore(temp)
            self.assertTrue(reopened.get_bool_setting("monitoring_paused"))
            reopened.set_bool_setting("monitoring_paused", False)
            self.assertFalse(reopened.get_bool_setting("monitoring_paused"))
            reopened.close()

    def test_parallel_camera_enqueues_are_serialized(self):
        with tempfile.TemporaryDirectory() as temp:
            store = LocalStore(temp)
            threads = [
                threading.Thread(
                    target=store.enqueue,
                    args=(f"clip-{index}.mp4", f"camera-{index}", 10.0, "motion"),
                )
                for index in range(20)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(store.pending_count(), 20)
            store.close()


class TrayLogicTests(unittest.TestCase):
    def test_cancelled_update_prompt_is_remembered_per_version(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "app.tray.default_state_dir", return_value=temp
        ):
            app = tray.TrayApplication()
            self.assertEqual(app._prompted_update_version(), "")
            app._mark_update_prompted("9.9.9")
            self.assertEqual(app._prompted_update_version(), "9.9.9")

    def test_update_is_hidden_when_manifest_is_not_newer(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "version": tray.CURRENT_VERSION,
            "downloadUrl": "https://example.test/connector.exe",
            "sha256": "abc",
        }
        with tempfile.TemporaryDirectory() as temp, patch(
            "app.tray.default_state_dir", return_value=temp
        ), patch("app.tray.requests.get", return_value=response):
            app = tray.TrayApplication()
            app._check_updates(notify=False)
        self.assertFalse(app.update_available)

    def test_newer_manifest_enables_update_menu_state(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "version": "99.0.0",
            "downloadUrl": "https://example.test/connector.exe",
            "sha256": "abc",
        }
        with tempfile.TemporaryDirectory() as temp, patch(
            "app.tray.default_state_dir", return_value=temp
        ), patch("app.tray.requests.get", return_value=response):
            app = tray.TrayApplication()
            app._check_updates(notify=False)
        self.assertTrue(app.update_available)
        self.assertEqual(app.latest_version, "99.0.0")

    def test_tray_uses_a_separate_instance_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            service = InstanceLock(temp)
            tray_lock = InstanceLock(temp, tray.TRAY_LOCK)
            self.assertTrue(service.acquire())
            self.assertTrue(tray_lock.acquire())
            tray_lock.release()
            service.release()

    def test_open_admin_starts_stopped_service_and_opens_dashboard(self):
        with tempfile.TemporaryDirectory() as temp:
            with (
                patch("app.tray.health_ready", return_value=False),
                patch("app.tray.service_status", return_value="stopped"),
                patch("app.tray.pause_marker_path", return_value=Path(temp) / "not-paused"),
                patch("app.tray.service_action", return_value=True) as action,
                patch("app.tray.wait_for_health", return_value=True),
                patch("app.tray.webbrowser.open", return_value=True) as browser,
            ):
                self.assertTrue(tray.open_admin())

        action.assert_called_once_with("start")
        browser.assert_called_once_with(tray.DEFAULT_ADMIN_URL)

    def test_open_admin_does_not_open_browser_when_health_never_recovers(self):
        with (
            patch("app.tray.health_ready", return_value=False),
            patch("app.tray.service_status", return_value="running"),
            patch("app.tray.wait_for_health", return_value=False),
            patch("app.tray.webbrowser.open") as browser,
        ):
            self.assertFalse(tray.open_admin(max_wait=0))

        browser.assert_not_called()

    def test_open_admin_resumes_paused_monitoring_before_opening_dashboard(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("app.tray.health_ready", return_value=False),
            patch("app.tray.service_status", return_value="stopped"),
            patch("app.tray.pause_marker_path", return_value=Path(temp) / "paused"),
            patch("app.tray.request_resume_monitoring", return_value=True) as resume,
            patch("app.tray.wait_for_health", return_value=True),
            patch("app.tray.service_action") as action,
            patch("app.tray.webbrowser.open", return_value=True) as browser,
        ):
            (Path(temp) / "paused").touch()
            self.assertTrue(tray.open_admin())

        resume.assert_called_once_with()
        action.assert_not_called()
        browser.assert_called_once_with(tray.DEFAULT_ADMIN_URL)

    def test_resume_monitoring_repairs_missing_windows_service(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("app.tray.pause_marker_path", return_value=Path(temp) / "missing.pause"),
            patch("app.tray.default_state_dir", return_value=temp),
            patch("app.tray.set_service_auto_start", return_value=True),
            patch("app.tray.service_status", return_value="missing"),
            patch("app.tray.service_action", side_effect=[True, True]) as action,
            patch("app.tray.wait_for_health", return_value=True),
        ):
            self.assertTrue(tray.resume_monitoring())

        self.assertEqual(action.call_args_list[0].args, ("install",))
        self.assertEqual(action.call_args_list[1].args, ("start",))

    def test_tray_exit_writes_signal_in_connector_state_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("app.tray.default_state_dir", return_value=temp):
                self.assertEqual(tray.request_tray_exit(), 0)
            self.assertTrue((Path(temp) / tray.TRAY_EXIT_SIGNAL).exists())


if __name__ == "__main__":
    unittest.main()
