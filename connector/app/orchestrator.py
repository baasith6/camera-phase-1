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
        self.stop_event = threading.Event()

    def run(self):
        self.state.log("Orchestrator starting. Polling for cameras...")
        while not self.stop_event.is_set():
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
                thread = self.threads.get(cid)
                if thread is not None and thread.is_alive():
                    continue
                self.state.log(f"Orchestrator: restarting dead pipeline for camera {cid}")
                self.pipelines[cid].stop()
                del self.pipelines[cid]
                if cid in self.threads:
                    del self.threads[cid]

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
                    cam_cfg.source = rtsp
                    # Loop local/test file sources so continuous monitoring keeps firing motion.
                    src_l = (rtsp or "").lower()
                    if src_l.startswith("file://") or src_l.endswith(".mp4") or src_l.endswith(".avi"):
                        cam_cfg.loop = True
                    if cam.get("onvifHost"):
                        cam_cfg.onvif_host = cam["onvifHost"]
                        cam_cfg.onvif_port = cam.get("onvifPort") or 80

                    # Note: We reuse the global state for metrics
                    pipeline = CapturePipeline(cam_cfg, self.state)
                    
                    def on_clip(path: str, duration: float, trigger: str, _cid=cid):
                        self.store.enqueue(path, _cid, duration, trigger)
                        self.state.queue_depth = self.store.pending_count()

                    t = threading.Thread(target=pipeline.run, args=(on_clip,), daemon=True)
                    t.start()
                    
                    self.pipelines[cid] = pipeline
                    self.threads[cid] = t

            # Stop removed cameras
            for cid in list(self.pipelines.keys()):
                if cid not in active_cam_ids:
                    self.state.log(f"Orchestrator: Stopping pipeline for camera {cid}")
                    self.pipelines[cid].stop()
                    del self.pipelines[cid]
                    del self.threads[cid]

            time.sleep(10)

    def stop(self):
        self.stop_event.set()
        for p in self.pipelines.values():
            p.stop()
        for t in self.threads.values():
            t.join(timeout=2.0)
