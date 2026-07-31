"""PyInstaller entry point for the ONEVO connector.

Keep this module outside the app package so importing app.main always creates
the correct package context for its relative imports.
"""
import sys
import time


def installer_capture(request_path: str, output_path: str) -> int:
    """Capture one setup-wizard frame without starting the connector service."""
    import json
    from pathlib import Path

    import cv2

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    source = str(request.get("rtsp_url") or request.get("source_file") or "")
    if request.get("onvif_host"):
        from app.onvif_client import OnvifCamera

        camera = OnvifCamera().connect(
            str(request["onvif_host"]),
            int(request.get("onvif_port") or 80),
            str(request.get("onvif_user") or "admin"),
            str(request.get("onvif_pass") or ""),
        )
        try:
            snapshot = camera.fetch_snapshot_bytes()
            frame = cv2.imdecode(
                __import__("numpy").frombuffer(snapshot, dtype="uint8"),
                cv2.IMREAD_COLOR,
            )
        except Exception:
            source = camera.get_rtsp_url()
            frame = None
    else:
        frame = None

    if frame is None:
        capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        try:
            if request.get("source_file"):
                # Each installer "Refresh Frame" runs in a short-lived helper
                # process. Seeking to a fixed timestamp meant every click
                # showed the same MP4 frame. Pick a valid changing frame so
                # the operator can choose the clearest moment for a zone.
                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                if frame_count > 1:
                    frame_index = time.time_ns() % frame_count
                    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                else:
                    capture.set(cv2.CAP_PROP_POS_MSEC, 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError("camera/video did not return a frame")
        finally:
            capture.release()

    frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(output_path, frame):
        raise RuntimeError("could not write captured frame")
    return 0


def installer_overlay(base_path: str, output_path: str, points_path: str) -> int:
    """Render the native wizard's polygon overlay into a BMP preview."""
    import json
    from pathlib import Path

    import cv2
    import numpy as np

    frame = cv2.imread(base_path)
    if frame is None:
        raise RuntimeError("captured frame is unavailable")
    points = json.loads(Path(points_path).read_text(encoding="utf-8"))
    if points:
        def coordinate(point, index: int) -> float:
            # Accept old installer previews while canonical saved polygons are
            # always [[x,y], ...].
            return float(point["x" if index == 0 else "y"]) if isinstance(point, dict) else float(point[index])

        pixel_points = np.array(
            [[round(coordinate(p, 0) * 640), round(coordinate(p, 1) * 360)] for p in points],
            dtype=np.int32,
        )
        for x, y in pixel_points:
            cv2.circle(frame, (int(x), int(y)), 6, (0, 210, 255), -1)
            cv2.circle(frame, (int(x), int(y)), 8, (255, 255, 255), 1)
        if len(pixel_points) > 1:
            cv2.polylines(frame, [pixel_points], len(pixel_points) >= 3, (0, 210, 255), 3)
        if len(pixel_points) >= 3:
            fill = frame.copy()
            cv2.fillPoly(fill, [pixel_points], (0, 140, 255))
            frame = cv2.addWeighted(fill, 0.18, frame, 0.82, 0)
    if not cv2.imwrite(output_path, frame):
        raise RuntimeError("could not write zone preview")
    return 0


def notify_uninstall() -> int:
    """Best-effort cloud status update before Inno Setup removes local data."""
    from app.backend_client import BackendClient
    from app.config import load_config
    from app.store import LocalStore

    cfg = load_config([])
    store = LocalStore(cfg.state_dir)
    try:
        connector_id = store.get_cred("connector_id")
        api_key = store.get_cred("api_key")
        if not connector_id or not api_key:
            return 0
        client = BackendClient(cfg.backend_url)
        client.set_credentials(connector_id, api_key)
        for attempt in range(5):
            try:
                client.notify_uninstall()
                return 0
            except Exception:
                if attempt == 4:
                    return 2
                time.sleep(2)
        return 2
    except Exception:
        return 2
    finally:
        store.close()


def dispatch(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 3 and args[0] == "--installer-capture":
        return installer_capture(args[1], args[2])
    if len(args) == 4 and args[0] == "--installer-overlay":
        return installer_overlay(args[1], args[2], args[3])
    if "--tray-exit" in args:
        from app.tray import request_tray_exit
        return request_tray_exit()
    if "--tray-uninstall" in args:
        from app.tray import uninstall_tray
        return uninstall_tray()
    if "--notify-uninstall" in args:
        return notify_uninstall()
    if "--open-admin" in args:
        from app.tray import open_admin
        return 0 if open_admin() else 2
    if "--start-monitoring" in args:
        from app.tray import resume_monitoring
        return 0 if resume_monitoring() else 2
    if "--tray" in args:
        from app.tray import run_tray
        return run_tray()
    if "--edit-zones" in args:
        from app.tray_zone_editor import run_zone_editor
        return run_zone_editor()
    if "--tray-dashboard" in args:
        from app.tray_dashboard import run_tray_dashboard
        return run_tray_dashboard()

    from app.main import main
    return main()


if __name__ == "__main__":
    raise SystemExit(dispatch())
