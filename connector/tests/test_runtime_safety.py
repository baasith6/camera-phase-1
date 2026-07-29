import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.instance_lock import InstanceLock
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
        with (
            patch("app.tray.health_ready", return_value=False),
            patch("app.tray.service_status", return_value="stopped"),
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

    def test_tray_exit_writes_signal_in_connector_state_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("app.tray.default_state_dir", return_value=temp):
                self.assertEqual(tray.request_tray_exit(), 0)
            self.assertTrue((Path(temp) / tray.TRAY_EXIT_SIGNAL).exists())


if __name__ == "__main__":
    unittest.main()
