import tempfile
import threading
import unittest

from app.instance_lock import InstanceLock
from app.store import LocalStore


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


if __name__ == "__main__":
    unittest.main()
