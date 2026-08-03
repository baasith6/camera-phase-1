import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.main import _provision_native_installer, _reconcile_paired_wizard
from app.paths import (
    CameraSource,
    PendingZone,
    WizardConfig,
    apply_pending_source_update,
    load_wizard_config,
    normalize_polygon,
    save_wizard_config,
)
from app.provisioning import provision_sources, source_key_for


class InstallerConfigParsingTests(unittest.TestCase):
    def test_source_update_preserves_connector_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = WizardConfig(
                setup_complete=True,
                store_id="store-id",
                connector_name="Existing Connector",
                sources=[CameraSource(name="Old", rtsp_url="rtsp://old/live")],
            )
            with patch("app.paths.program_data_root", return_value=root):
                save_wizard_config(original)
                (root / "source-update.json").write_text(
                    '{"sources":[{"name":"New","rtsp_url":"rtsp://new/live"}]}',
                    encoding="utf-8",
                )
                self.assertTrue(apply_pending_source_update(original))
                updated = load_wizard_config()

            self.assertEqual(updated.store_id, "store-id")
            self.assertEqual(updated.connector_name, "Existing Connector")
            self.assertEqual(updated.sources[0].rtsp_url, "rtsp://new/live")
            self.assertFalse(updated.setup_complete)

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

    def test_parses_multiple_local_videos_from_sources_list(self):
        cfg = WizardConfig.from_dict({
            "sources": [
                {"name": "Video 1", "source_file": r"C:\videos\one.mp4", "loop": True},
                {"name": "Video 2", "source_file": r"C:\videos\two.mp4", "loop": True},
            ],
        })

        self.assertEqual(len(cfg.sources), 2)
        self.assertEqual(cfg.sources[1].source_file, r"C:\videos\two.mp4")
        self.assertTrue(all(source.loop for source in cfg.sources))

    def test_normalizes_legacy_pending_zone_points(self):
        cfg = WizardConfig(
            sources=[CameraSource(name="Camera 1", rtsp_url="rtsp://camera/live")],
            pending_zones=[
                PendingZone(
                    source_index=0,
                    name="High-value shelf",
                    zone_type="HighValue",
                    polygon=normalize_polygon([
                        {"x": 0.1, "y": 0.2},
                        {"x": 0.7, "y": 0.2},
                        {"x": 0.7, "y": 0.8},
                    ]),
                )
            ],
        )

        restored = WizardConfig.from_dict(cfg.to_dict())

        self.assertEqual(restored.pending_zones[0].source_index, 0)
        self.assertEqual(restored.pending_zones[0].zone_type, "HighValue")
        self.assertEqual(restored.pending_zones[0].polygon, [[0.1, 0.2], [0.7, 0.2], [0.7, 0.8]])


class NativeProvisioningTests(unittest.TestCase):
    def test_paired_connector_clears_stale_setup_code_and_error(self):
        wizard = WizardConfig.from_dict({
            "setup_code": "USED-CODE",
            "activation_error": "Invalid, used, or expired setup code",
            "setup_complete": True,
        })
        credentials = {"connector_id": "existing-id", "api_key": "existing-key"}
        store = SimpleNamespace(get_cred=lambda key: credentials.get(key))

        with patch("app.main.save_wizard_config") as save:
            result = _reconcile_paired_wizard(wizard, store)

        self.assertIs(result, wizard)
        self.assertEqual(wizard.setup_code, "")
        self.assertEqual(wizard.activation_error, "")
        save.assert_called_once_with(wizard)

    def test_paired_connector_never_claims_a_new_setup_code(self):
        wizard = WizardConfig.from_dict({
            "setup_code": "DIFFERENT-STORE-CODE",
            "connector_name": "Store Connector",
            "sources": [],
        })
        credentials = {"connector_id": "existing-id", "api_key": "existing-key"}
        claims = []
        used = []
        client = SimpleNamespace(
            claim_setup_code=lambda *_: claims.append(True),
            set_credentials=lambda cid, key: used.append((cid, key)),
        )
        store = SimpleNamespace(
            get_cred=lambda key: credentials.get(key),
            set_cred=lambda key, value: credentials.__setitem__(key, value),
        )
        state = SimpleNamespace(
            connector_id=None, paired=False, degraded_reason=None, log=lambda *_: None
        )
        runtime_cfg = SimpleNamespace(version="1.1.16")

        with patch("app.main.save_wizard_config"), patch(
            "app.provisioning.paths.save_wizard_config"
        ):
            ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

        self.assertTrue(ok)
        self.assertEqual(claims, [])
        self.assertEqual(used, [("existing-id", "existing-key")])
        self.assertEqual(state.connector_id, "existing-id")
        self.assertTrue(state.paired)
        self.assertEqual(wizard.setup_code, "")

    def test_native_installer_can_skip_camera_sources(self):
        wizard = WizardConfig.from_dict({
            "setup_code": "ABCD-EFGH",
            "connector_name": "Store Connector",
            "sources": [],
        })
        client = SimpleNamespace(
            claim_setup_code=lambda *_: ("connector-id", "api-key", "store-id"),
            set_credentials=lambda *_: None,
            finalize_setup=lambda *_: self.fail("skip must not finalize an empty camera set"),
        )
        stored = {}
        store = SimpleNamespace(
            get_cred=lambda key: stored.get(key),
            set_cred=lambda key, value: stored.__setitem__(key, value),
        )
        state = SimpleNamespace(connector_id=None, log=lambda *_: None)
        runtime_cfg = SimpleNamespace(version="1.0.0")

        with patch("app.main.save_wizard_config"), patch(
            "app.provisioning.paths.save_wizard_config"
        ):
            ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

        self.assertTrue(ok)
        self.assertTrue(wizard.setup_complete)
        self.assertEqual(wizard.sources, [])
        self.assertEqual(stored["connector_id"], "connector-id")

    def test_selected_mp4_waits_for_browser_zone_setup(self):
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
                finalize_setup=lambda *_: {"ok": True},
            )
            created = []
            finalized = []
            client.create_camera = lambda body: created.append(body) or {"id": "camera-id"}
            client.finalize_setup = lambda keys: finalized.append(keys) or {"ok": True}
            stored = {}
            store = SimpleNamespace(
                set_cred=lambda key, value: stored.__setitem__(key, value),
                get_cred=lambda key: stored.get(key),
            )
            state = SimpleNamespace(connector_id=None, log=lambda *_: None)
            runtime_cfg = SimpleNamespace(version="1.0.0")

            with patch("app.main.save_wizard_config"), patch(
                "app.provisioning.paths.save_wizard_config"
            ):
                ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

            self.assertTrue(ok)
            self.assertFalse(wizard.setup_complete)
            self.assertEqual(created[0]["rtspUrl"], f"file://{video}")
            self.assertEqual(finalized, [[wizard.sources[0].source_key]])
            self.assertEqual(stored["connector_id"], "connector-id")

    def test_native_installer_zones_sync_after_camera_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "selected.mp4"
            video.write_bytes(b"video")
            polygon = [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8]]
            wizard = WizardConfig(
                setup_code="ABCD-EFGH",
                sources=[CameraSource(name="Video", source_file=str(video), loop=True)],
                pending_zones=[
                    PendingZone(0, "Checkout counter", "Checkout", polygon)
                ],
            )
            zones = []
            stored = {}
            client = SimpleNamespace(
                claim_setup_code=lambda *_: ("connector-id", "api-key", "store-id"),
                set_credentials=lambda *_: None,
                create_camera=lambda *_: {"id": "camera-id"},
                create_zone=lambda *args: zones.append(args) or {"id": "zone-id"},
                finalize_setup=lambda *_: {"ok": True},
            )
            store = SimpleNamespace(
                set_cred=lambda key, value: stored.__setitem__(key, value),
                get_cred=lambda key: stored.get(key),
            )
            state = SimpleNamespace(
                connector_id=None, paired=False, degraded_reason=None, log=lambda *_: None
            )

            with patch("app.main.save_wizard_config"), patch(
                "app.provisioning.paths.save_wizard_config"
            ):
                ok = _provision_native_installer(
                    SimpleNamespace(version="1.1.18"), wizard, client, store, state
                )

            self.assertTrue(ok)
            self.assertEqual(
                zones, [("camera-id", "Checkout counter", "Checkout", polygon)]
            )
            self.assertEqual(wizard.pending_zones, [])

    def test_rtsp_camera_does_not_request_demo_zones(self):
        wizard = WizardConfig.from_dict({
            "setup_code": "ABCD-EFGH",
            "connector_name": "Store Connector",
            "rtsp_text": "rtsp://camera-1/live",
        })
        client = SimpleNamespace(
            claim_setup_code=lambda *_: ("connector-id", "api-key", "store-id"),
            set_credentials=lambda *_: None,
            finalize_setup=lambda *_: {"ok": True},
        )
        created = []
        finalized = []
        client.create_camera = lambda body: created.append(body) or {"id": "camera-id"}
        client.finalize_setup = lambda keys: finalized.append(keys) or {"ok": True}
        stored = {}
        store = SimpleNamespace(
            set_cred=lambda key, value: stored.__setitem__(key, value),
            get_cred=lambda key: stored.get(key),
        )
        state = SimpleNamespace(connector_id=None, log=lambda *_: None)
        runtime_cfg = SimpleNamespace(version="1.0.0")

        with patch("app.main.save_wizard_config"), patch(
            "app.provisioning.paths.save_wizard_config"
        ), patch(
            "app.main.validate_rtsp_stream", return_value=(True, "RTSP stream OK")
        ):
            ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

        self.assertTrue(ok)
        self.assertEqual(len(finalized), 1)

    def test_pending_native_setup_retries_with_saved_credentials(self):
        wizard = WizardConfig.from_dict({
            "connector_name": "Store Connector",
            "rtsp_text": "rtsp://camera-1/live",
        })
        wizard.setup_complete = False
        credentials = {
            "connector_id": "connector-id",
            "api_key": "api-key",
        }
        client = SimpleNamespace(
            set_credentials=lambda connector_id, api_key: credentials.update(
                used_connector_id=connector_id, used_api_key=api_key
            ),
            create_camera=lambda *_: {"id": "camera-id"},
            finalize_setup=lambda *_: {"ok": True},
        )
        store = SimpleNamespace(get_cred=lambda key: credentials.get(key))
        state = SimpleNamespace(connector_id=None, log=lambda *_: None)
        runtime_cfg = SimpleNamespace(version="1.0.0")

        with patch("app.main.save_wizard_config"), patch(
            "app.provisioning.paths.save_wizard_config"
        ):
            ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

        self.assertTrue(ok)
        self.assertFalse(wizard.setup_complete)
        self.assertEqual(credentials["used_connector_id"], "connector-id")

    def test_retry_reuses_backend_camera_after_partial_failure(self):
        sources = WizardConfig.from_dict({
            "rtsp_text": "rtsp://camera-1/live;rtsp://camera-2/live",
        }).sources
        calls = []

        class RetryClient:
            failed_once = False

            def create_camera(self, body):
                calls.append(body["rtspUrl"])
                if body["rtspUrl"].endswith("camera-2/live") and not self.failed_once:
                    self.failed_once = True
                    raise RuntimeError("temporary failure")
                # The backend endpoint is idempotent for the same name/source.
                return {"id": f"camera-{body['name']}"}

        client = RetryClient()
        state = SimpleNamespace(log=lambda *_: None)
        with self.assertRaises(RuntimeError):
            provision_sources(client, sources, state)

        result = provision_sources(client, sources, state)
        self.assertEqual(len(result), 2)
        self.assertEqual(calls.count("rtsp://camera-1/live"), 1)
        self.assertTrue(all(source.camera_id for source in result))

    def test_rtsp_source_key_ignores_credentials_and_query_tokens(self):
        first = CameraSource(
            name="Front",
            rtsp_url="rtsp://old-user:old-pass@CAMERA.local/live?token=one",
        )
        second = CameraSource(
            name="Renamed",
            rtsp_url="rtsp://new-user:new-pass@camera.local:554/live?token=two",
        )
        self.assertEqual(source_key_for(first), source_key_for(second))

    def test_onvif_source_key_ignores_profile_selection(self):
        first = CameraSource(
            name="Camera",
            onvif_host="CAMERA.local",
            onvif_port=80,
            onvif_profile="auto",
        )
        second = CameraSource(
            name="Camera",
            onvif_host="camera.local",
            onvif_port=80,
            onvif_profile="profile-2",
        )
        self.assertEqual(source_key_for(first), source_key_for(second))

    def test_mp4_source_key_survives_path_change(self):
        with tempfile.TemporaryDirectory() as temp:
            first_path = Path(temp) / "first.mp4"
            second_path = Path(temp) / "moved.mp4"
            first_path.write_bytes(b"same-video")
            second_path.write_bytes(b"same-video")
            first = CameraSource(name="One", source_file=str(first_path))
            second = CameraSource(name="Two", source_file=str(second_path))
            self.assertEqual(source_key_for(first), source_key_for(second))

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
            "app.provisioning.paths.save_wizard_config"
        ), patch(
            "app.main.validate_rtsp_stream", return_value=(True, "RTSP stream OK")
        ):
            ok = _provision_native_installer(runtime_cfg, wizard, client, store, state)

        self.assertFalse(ok)
        self.assertEqual(wizard.setup_code, "")
        self.assertIn("camera create failed", wizard.activation_error)
        save_cfg.assert_called_once()


if __name__ == "__main__":
    unittest.main()
