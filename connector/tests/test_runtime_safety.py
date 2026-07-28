import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

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
