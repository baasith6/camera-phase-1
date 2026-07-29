import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.capture import CapturePipeline, validate_rtsp_stream
from app.config import Config
from app.onvif_client import OnvifCamera, _inject_credentials
from app.orchestrator import StoreOrchestrator
from app.runtime import RuntimeState
from app.wizard import parse_rtsp_urls


def _minimal_cfg(**overrides) -> Config:
    base = dict(
        backend_url="http://localhost:8081",
        bootstrap_key="key",
        store_id="store",
        connector_name="test",
        version="1.0.0",
        source="rtsp://127.0.0.1/stream",
        loop=False,
        admin_port=8099,
        admin_token="",
        admin_bind_host="127.0.0.1",
        state_dir="data",
        camera_id="cam-1",
        fps=10.0,
        pre_seconds=4.0,
        post_seconds=4.0,
        cooldown_seconds=60.0,
        motion_area_frac=0.02,
        use_person_filter=False,
        disk_warn_pct=20.0,
        disk_critical_pct=10.0,
        max_upload_retries=5,
        rtsp_reconnect_max_sec=60.0,
        onvif_host="",
        onvif_port=80,
        onvif_user="admin",
        onvif_pass="admin",
        onvif_profile="auto",
    )
    base.update(overrides)
    return Config(**base)


class ParseRtspUrlsTests(unittest.TestCase):
    def test_splits_newlines_and_semicolons(self):
        urls = parse_rtsp_urls("rtsp://a/live; rtsp://b/live\nrtsp://c/live")
        self.assertEqual(
            urls,
            ["rtsp://a/live", "rtsp://b/live", "rtsp://c/live"],
        )


class OnvifCredentialTests(unittest.TestCase):
    def test_inject_credentials_uses_wrapper_password(self):
        cam = OnvifCamera()
        cam.username = "admin"
        cam.password = "secret"
        url = _inject_credentials("rtsp://192.168.1.64/stream1", cam.username, cam.password)
        self.assertIn("admin:secret@", url)

    def test_connect_stores_password_on_wrapper(self):
        fake_onvif = MagicMock()
        fake_onvif.return_value.create_media_service.return_value.GetProfiles.return_value = []
        fake_module = MagicMock()
        fake_module.ONVIFCamera = fake_onvif
        with patch.dict("sys.modules", {"onvif": fake_module}):
            cam = OnvifCamera().connect("192.168.1.64", 80, "admin", "s3cret")
        self.assertEqual(cam.password, "s3cret")


class ValidateRtspStreamTests(unittest.TestCase):
    def test_skips_non_rtsp_sources(self):
        ok, msg = validate_rtsp_stream("file://samples/test.mp4")
        self.assertTrue(ok)
        self.assertEqual(msg, "not an RTSP source")

    @patch("app.capture._build_video_capture")
    def test_fails_when_stream_cannot_open(self, mock_open):
        cap = MagicMock()
        cap.isOpened.return_value = False
        mock_open.return_value = cap

        ok, msg = validate_rtsp_stream("rtsp://127.0.0.1/nope")
        self.assertFalse(ok)
        self.assertIn("cannot open", msg)

    @patch("app.capture._build_video_capture")
    def test_fails_when_no_frame_received(self, mock_open):
        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.read.return_value = (False, None)
        mock_open.return_value = cap

        ok, msg = validate_rtsp_stream("rtsp://127.0.0.1/stream")
        self.assertFalse(ok)
        self.assertIn("no frame", msg)

    @patch("app.capture._build_video_capture")
    def test_succeeds_when_frame_received(self, mock_open):
        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.read.return_value = (True, object())
        mock_open.return_value = cap

        ok, msg = validate_rtsp_stream("rtsp://127.0.0.1/stream")
        self.assertTrue(ok)
        self.assertEqual(msg, "RTSP stream OK")


class CaptureInitialRetryTests(unittest.TestCase):
    @patch("app.capture.RTSP_INITIAL_MAX_ATTEMPTS", 3)
    def test_open_initial_retries_until_success(self):
        cfg = _minimal_cfg(source="rtsp://127.0.0.1/stream")
        state = RuntimeState()
        pipeline = CapturePipeline(cfg, state)

        caps = [MagicMock(isOpened=lambda: False) for _ in range(2)]
        good = MagicMock()
        good.isOpened.return_value = True
        caps.append(good)

        with patch("app.capture.time.sleep"), patch.object(pipeline, "_open", side_effect=caps) as mock_open:
            opened = pipeline._open_initial()

        self.assertIs(opened, good)
        self.assertEqual(mock_open.call_count, 3)

    @patch("app.capture.RTSP_INITIAL_MAX_ATTEMPTS", 3)
    def test_open_initial_gives_up_after_max_attempts(self):
        cfg = _minimal_cfg(source="rtsp://127.0.0.1/stream")
        state = RuntimeState()
        pipeline = CapturePipeline(cfg, state)

        bad = MagicMock()
        bad.isOpened.return_value = False

        with patch("app.capture.time.sleep"), patch.object(pipeline, "_open", return_value=bad) as mock_open:
            opened = pipeline._open_initial()

        self.assertIsNone(opened)
        self.assertEqual(mock_open.call_count, 3)


class OrchestratorRestartTests(unittest.TestCase):
    def test_removes_dead_pipeline_before_restart(self):
        cfg = _minimal_cfg(camera_id="")
        state = RuntimeState()
        orch = StoreOrchestrator(cfg, state, SimpleNamespace(), SimpleNamespace())

        dead_pipeline = MagicMock()
        dead_thread = MagicMock(is_alive=lambda: False)
        orch.pipelines["cam-1"] = dead_pipeline
        orch.threads["cam-1"] = dead_thread

        thread = orch.threads.get("cam-1")
        self.assertFalse(thread.is_alive())
        orch.pipelines["cam-1"].stop()
        del orch.pipelines["cam-1"]
        del orch.threads["cam-1"]

        self.assertNotIn("cam-1", orch.pipelines)
        dead_pipeline.stop.assert_called_once()

    @patch("app.orchestrator.time.sleep")
    @patch("app.orchestrator.threading.Thread")
    @patch("app.orchestrator.CapturePipeline")
    def test_run_restarts_dead_pipeline(self, mock_pipeline_cls, mock_thread_cls, _sleep):
        cfg = _minimal_cfg(camera_id="")
        state = RuntimeState()
        client = SimpleNamespace(
            get_cameras=lambda: [{"id": "cam-1", "rtspUrl": "rtsp://127.0.0.1/a"}]
        )
        store = SimpleNamespace(pending_count=lambda: 0)
        orch = StoreOrchestrator(cfg, state, client, store)

        dead_pipeline = MagicMock()
        dead_thread = MagicMock(is_alive=lambda: False)
        orch.pipelines["cam-1"] = dead_pipeline
        orch.threads["cam-1"] = dead_thread

        mock_thread_cls.return_value = MagicMock()
        mock_pipeline_cls.return_value = MagicMock()

        iterations = [False, True]

        with patch.object(orch.stop_event, "is_set", side_effect=lambda: iterations.pop(0)):
            orch.run()

        dead_pipeline.stop.assert_called_once()
        mock_pipeline_cls.assert_called_once()
        mock_thread_cls.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
