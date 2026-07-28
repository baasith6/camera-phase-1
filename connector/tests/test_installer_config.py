import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.main import _provision_native_installer
from app.paths import WizardConfig


class InstallerConfigParsingTests(unittest.TestCase):
    def test_parses_multiple_rtsp_urls(self):
        cfg = WizardConfig.from_dict({
            "rtsp_text": "rtsp://camera-1/live; rtsp://camera-2/live",
        })

        self.assertEqual(
            [source.rtsp_url for source in cfg.sources],
            ["rtsp://camera-1/live", "rtsp://camera-2/live"],
        )

    def test_parses_multiple_onvif_hosts_with_per_host_port(self):
        cfg = WizardConfig.from_dict({
            "onvif_text": "192.168.1.10;camera-2.local:8080",
            "onvif_port": 80,
            "onvif_user": "installer",
            "onvif_pass": "secret",
        })

        self.assertEqual(
            [(source.onvif_host, source.onvif_port) for source in cfg.sources],
            [("192.168.1.10", 80), ("camera-2.local", 8080)],
        )
        self.assertTrue(all(source.onvif_user == "installer" for source in cfg.sources))


class NativeProvisioningTests(unittest.TestCase):
    def test_selected_mp4_is_created_and_setup_is_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "selected.mp4"
            video.write_bytes(b"video")
            wizard = WizardConfig.from_dict({
                "setup_code": "ABCD-EFGH",
                "connector_name": "Store Connector",
                "source_file": str(video),
                "loop_file": True,
            })
            client = SimpleNamespace(
                claim_setup_code=lambda *_: ("connector-id", "api-key", "store-id"),
                set_credentials=lambda *_: None,
            )
            created = []
            client.create_camera = lambda body: created.append(body) or {"id": "camera-id"}
            stored = {}
            store = SimpleNamespace(set_cred=lambda key, value: stored.__setitem__(key, value))
            state = SimpleNamespace(connector_id=None, log=lambda *_: None)
            runtime_cfg = SimpleNamespace(version="1.0.0")

            with patch("app.main.save_wizard_config"):
                ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

            self.assertTrue(ok)
            self.assertTrue(wizard.setup_complete)
            self.assertEqual(created[0]["rtspUrl"], f"file://{video}")
            self.assertTrue(created[0]["useDemoZones"])
            self.assertEqual(stored["connector_id"], "connector-id")

    def test_rtsp_camera_does_not_request_demo_zones(self):
        wizard = WizardConfig.from_dict({
            "setup_code": "ABCD-EFGH",
            "connector_name": "Store Connector",
            "rtsp_text": "rtsp://camera-1/live",
        })
        client = SimpleNamespace(
            claim_setup_code=lambda *_: ("connector-id", "api-key", "store-id"),
            set_credentials=lambda *_: None,
        )
        created = []
        client.create_camera = lambda body: created.append(body) or {"id": "camera-id"}
        store = SimpleNamespace(set_cred=lambda *_: None)
        state = SimpleNamespace(connector_id=None, log=lambda *_: None)
        runtime_cfg = SimpleNamespace(version="1.0.0")

        with patch("app.main.save_wizard_config"), patch(
            "app.main.validate_rtsp_stream", return_value=(True, "RTSP stream OK")
        ):
            ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

        self.assertTrue(ok)
        self.assertFalse(created[0]["useDemoZones"])

    def test_partial_failure_clears_consumed_setup_code(self):
        wizard = WizardConfig.from_dict({
            "setup_code": "ABCD-EFGH",
            "connector_name": "Store Connector",
            "rtsp_text": "rtsp://camera-1/live",
        })
        client = SimpleNamespace(
            claim_setup_code=lambda *_: ("connector-id", "api-key", "store-id"),
            set_credentials=lambda *_: None,
        )
        def fail_create(_body):
            raise RuntimeError("camera create failed")

        client.create_camera = fail_create
        stored = {}
        store = SimpleNamespace(
            set_cred=lambda key, value: stored.__setitem__(key, value),
            get_cred=lambda key: stored.get(key),
        )
        state = SimpleNamespace(connector_id=None, log=lambda *_: None, degraded_reason=None)
        runtime_cfg = SimpleNamespace(version="1.0.0")

        with patch("app.main.save_wizard_config") as save_cfg, patch(
            "app.main.validate_rtsp_stream", return_value=(True, "RTSP stream OK")
        ):
            ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

        self.assertFalse(ok)
        self.assertEqual(wizard.setup_code, "")
        self.assertIn("camera create failed", wizard.activation_error)
        save_cfg.assert_called_once()


if __name__ == "__main__":
    unittest.main()
