import os
import re
import threading
import time
import copy
from typing import Dict

from .capture import CapturePipeline
from .config import Config
from .runtime import RuntimeState
from .backend_client import BackendClient
from .store import LocalStore


class StoreOrchestrator:
    def __init__(self, base_cfg: Config, state: RuntimeState, client: BackendClient, store: LocalStore):
        self.base_cfg = base_cfg
        self.state = state
        self.client = client
        self.store = store
        self.pipelines: Dict[str, CapturePipeline] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.source_fingerprints: Dict[str, tuple] = {}
        self.stop_event = threading.Event()

    def run(self):
        self.state.log("Orchestrator starting. Polling for cameras...")
        while not self.stop_event.is_set():
            # Stop all backend polling and pipeline management while the local
            # control page is in its managed stopped state.
            if self.state.capture_paused:
                time.sleep(0.25)
                continue
            try:
                cams = self.client.get_cameras()
            except Exception as e:
                self.state.log(f"Error fetching cameras: {e}")
                time.sleep(10)
                continue

            active_cam_ids = {c["id"] for c in cams}
            capture_cams = [c for c in cams if c.get("rtspUrl")]
            if len(capture_cams) == 1:
                only = capture_cams[0]
                self.state.camera_id = only["id"]
                self.state.source = only.get("rtspUrl") or ""
            elif len(capture_cams) > 1:
                self.state.camera_id = None
                self.state.source = f"{len(capture_cams)} configured camera sources"
            else:
                self.state.camera_id = None
                self.state.source = ""
            
            # Restart pipelines whose capture thread died (e.g. initial RTSP failure).
            for cid in list(self.pipelines.keys()):
                cam = next((item for item in cams if item["id"] == cid), None)
                fingerprint = self._fingerprint(cam) if cam else None
                if cam is not None and self.source_fingerprints.get(cid) != fingerprint:
                    self.state.log(f"Orchestrator: source changed for camera {cid}")
                    self._remove_pipeline(cid)
                    continue
                thread = self.threads.get(cid)
                if thread is not None and thread.is_alive():
                    continue
                self.state.log(f"Orchestrator: restarting dead pipeline for camera {cid}")
                self._remove_pipeline(cid)

            # Start new cameras
            for cam in cams:
                cid = cam["id"]
                if cid not in self.pipelines:
                    rtsp = cam.get("rtspUrl")
                    if not rtsp:
                        continue  # Needs RTSP URL to capture
                    local_source = rtsp[7:] if rtsp.lower().startswith("file://") else rtsp
                    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", local_source):
                        self.state.log(f"Orchestrator: skipping foreign Windows file source for camera {cid}")
                        continue
                    self.state.log(f"Orchestrator: Starting pipeline for camera {cid}")
                    
                    # Create a copy of config for this specific pipeline
                    cam_cfg = copy.copy(self.base_cfg)
                    cam_cfg.camera_id = cid
                    # Backend represents shop-local MP4 files as file:// paths.
                    # OpenCV on Windows needs the native path, not the URI.
                    cam_cfg.source = local_source
                    # Loop local/test file sources so continuous monitoring keeps firing motion.
                    src_l = (rtsp or "").lower()
                    if src_l.startswith("file://") or src_l.endswith(".mp4") or src_l.endswith(".avi"):
                        cam_cfg.loop = True
                    if cam.get("onvifHost"):
                        cam_cfg.onvif_host = cam["onvifHost"]
                        cam_cfg.onvif_port = cam.get("onvifPort") or 80

                    # Note: We reuse the global state for metrics
                    def publish_reference(camera_id: str, jpeg: bytes) -> bool:
                        try:
                            self.client.upload_reference_frame(camera_id, jpeg)
                            self.state.log(f"Saved zone reference frame for camera {camera_id}")
                            return True
                        except Exception as exc:  # noqa: BLE001
                            self.state.log(f"Reference frame upload failed for camera {camera_id}: {exc}")
                            return False

                    pipeline = CapturePipeline(
                        cam_cfg,
                        self.state,
                        zone_provider=lambda _cid=cid: self.client.get_zones(_cid),
                        zone_revision=lambda _cid=cid: self.state.zone_revision(_cid),
                        reference_frame_publisher=publish_reference,
                    )
                    
                    def on_clip(path: str, duration: float, trigger: str, _cid=cid):
                        self.store.enqueue(path, _cid, duration, trigger)
                        self.state.queue_depth = self.store.pending_count()

                    t = threading.Thread(target=pipeline.run, args=(on_clip,), daemon=True)
                    t.start()
                    
                    self.pipelines[cid] = pipeline
                    self.threads[cid] = t
                    self.state.pipelines[cid] = pipeline
                    self.source_fingerprints[cid] = self._fingerprint(cam)

            # Stop removed cameras
            for cid in list(self.pipelines.keys()):
                if cid not in active_cam_ids:
                    self.state.log(f"Orchestrator: Stopping pipeline for camera {cid}")
                    self._remove_pipeline(cid)

            time.sleep(10)

    def stop(self):
        self.stop_event.set()
        for p in self.pipelines.values():
            p.stop()
        for t in self.threads.values():
            t.join(timeout=2.0)

    @staticmethod
    def _fingerprint(cam: dict | None) -> tuple | None:
        if cam is None:
            return None
        return (
            cam.get("rtspUrl") or "",
            cam.get("onvifHost") or "",
            cam.get("onvifPort") or 0,
            cam.get("status") or "",
        )

    def _remove_pipeline(self, camera_id: str) -> None:
        pipeline = self.pipelines.pop(camera_id, None)
        if pipeline is not None:
            pipeline.stop()
        self.threads.pop(camera_id, None)
        self.source_fingerprints.pop(camera_id, None)
        self.state.remove_camera(camera_id)
