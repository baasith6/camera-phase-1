"""Native Windows zone editor launched from the notification-area tray.

This is only a native presentation layer. It deliberately reuses the existing
local connector wizard endpoints, which in turn use the established backend
zone APIs and models.
"""
from __future__ import annotations

import io
import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image, ImageTk


BASE_URL = "http://127.0.0.1:8099"
CANVAS_WIDTH = 760
CANVAS_HEIGHT = 428


def _request(path: str, method: str = "GET", body: dict | None = None) -> bytes:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except Exception:
            pass
        raise RuntimeError(str(detail)) from exc


def _json(path: str, method: str = "GET", body: dict | None = None):
    raw = _request(path, method, body)
    return json.loads(raw.decode("utf-8")) if raw else {}


class ZoneEditor:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("ONEVO Local Connector — Edit Zones")
        self.root.geometry("1120x760")
        self.root.minsize(980, 680)
        self.cameras: list[dict] = []
        self.zones: list[dict] = []
        self.points: list[tuple[float, float]] = []
        self.selected_zone: dict | None = None
        self.photo = None
        self._build()
        self._async(self._load_cameras)

    def _build(self) -> None:
        root = self.root
        root.configure(bg="#f5f6f8")
        style = ttk.Style(root)
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 11, "bold"))

        top = ttk.Frame(root, padding=16)
        top.pack(fill="x")
        ttk.Label(top, text="Edit Camera Zones", style="Title.TLabel").pack(side="left")
        self.status = ttk.Label(top, text="Connecting…")
        self.status.pack(side="right")

        controls = ttk.Frame(root, padding=(16, 0, 16, 10))
        controls.pack(fill="x")
        ttk.Label(controls, text="Camera:").pack(side="left")
        self.camera = ttk.Combobox(controls, state="readonly", width=34)
        self.camera.pack(side="left", padx=(6, 14))
        self.camera.bind("<<ComboboxSelected>>", lambda _e: self._load_camera_async())
        ttk.Button(controls, text="Refresh Frame", command=self._refresh_frame_async).pack(side="left")

        editor = ttk.Frame(root, padding=(16, 0, 16, 8))
        editor.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            editor, width=CANVAS_WIDTH, height=CANVAS_HEIGHT,
            bg="#111827", highlightthickness=1, highlightbackground="#9ca3af",
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._canvas_click)

        side = ttk.Frame(editor, padding=(14, 0, 0, 0), width=270)
        side.pack(side="right", fill="y")
        ttk.Label(side, text="Saved zones", style="Heading.TLabel").pack(anchor="w")
        self.zone_list = tk.Listbox(side, width=35, height=15, exportselection=False)
        self.zone_list.pack(fill="both", expand=True, pady=(8, 8))
        self.zone_list.bind("<<ListboxSelect>>", lambda _e: self._select_zone())
        row = ttk.Frame(side)
        row.pack(fill="x")
        ttk.Button(row, text="Edit", command=self._select_zone).pack(side="left")
        ttk.Button(row, text="Delete", command=self._delete_zone_async).pack(side="left", padx=6)

        form = ttk.Frame(root, padding=(16, 8, 16, 8))
        form.pack(fill="x")
        ttk.Label(form, text="Zone name:").grid(row=0, column=0, sticky="w")
        self.name = ttk.Entry(form, width=30)
        self.name.grid(row=0, column=1, padx=(6, 18), sticky="ew")
        ttk.Label(form, text="Zone type:").grid(row=0, column=2, sticky="w")
        self.zone_type = ttk.Combobox(
            form, state="readonly", width=22,
            values=("HighValue", "Shelf", "Checkout", "Exit", "BlindSpot", "Staff"),
        )
        self.zone_type.set("HighValue")
        self.zone_type.grid(row=0, column=3, padx=6)
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(root, padding=(16, 4, 16, 16))
        actions.pack(fill="x")
        ttk.Button(actions, text="+ New Zone", command=self._new_zone).pack(side="left")
        ttk.Button(actions, text="Undo Point", command=self._undo).pack(side="left", padx=6)
        ttk.Button(actions, text="Clear Points", command=self._clear_points).pack(side="left")
        ttk.Button(actions, text="Save Zone", command=self._save_zone_async).pack(side="left", padx=6)
        ttk.Button(actions, text="Close", command=root.destroy).pack(side="right")

    def _async(self, operation) -> None:
        self.status.configure(text="Working…")

        def worker():
            try:
                operation()
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("ONEVO", str(exc), parent=self.root))
            finally:
                self.root.after(0, lambda: self.status.configure(text="Synchronized with dashboard"))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _camera_id(item: dict) -> str:
        return str(item.get("cameraId") or item.get("CameraId") or "")

    def _load_cameras(self) -> None:
        status = _json("/setup/wizard/status")
        cameras = status.get("cameras") or []
        self.cameras = [item for item in cameras if self._camera_id(item)]

        def update():
            self.camera["values"] = [
                item.get("name") or item.get("Name") or f"Camera {index + 1}"
                for index, item in enumerate(self.cameras)
            ]
            if self.cameras:
                self.camera.current(0)
                self._load_camera_async()
            else:
                self.status.configure(text="No configured cameras")
                messagebox.showinfo(
                    "ONEVO", "No configured cameras. Add a source from the local dashboard first.",
                    parent=self.root,
                )

        self.root.after(0, update)

    def _current_camera_id(self) -> str:
        index = self.camera.current()
        if index < 0 or index >= len(self.cameras):
            raise RuntimeError("Select a camera")
        return self._camera_id(self.cameras[index])

    def _load_camera_async(self) -> None:
        camera_id = self._current_camera_id()
        self._async(lambda: self._load_camera(camera_id))

    def _load_camera(self, camera_id: str) -> None:
        zones = _json(f"/setup/wizard/cameras/{camera_id}/zones")
        frame = _request(f"/snapshot?camera_id={camera_id}")
        image = Image.open(io.BytesIO(frame)).convert("RGB")
        self.zones = zones
        self.root.after(0, lambda: self._apply_camera(image))

    def _apply_camera(self, image: Image.Image) -> None:
        self._new_zone()
        self.zone_list.delete(0, "end")
        for zone in self.zones:
            self.zone_list.insert("end", zone.get("name") or zone.get("Name") or "Zone")
        self.base_image = image
        self._draw()

    def _refresh_frame_async(self) -> None:
        camera_id = self._current_camera_id()
        self._async(lambda: self._refresh_frame(camera_id))

    def _refresh_frame(self, camera_id: str) -> None:
        frame = _request(f"/snapshot?camera_id={camera_id}&refresh=1")
        image = Image.open(io.BytesIO(frame)).convert("RGB")
        self.root.after(0, lambda: self._set_frame(image))

    def _set_frame(self, image: Image.Image) -> None:
        self.base_image = image
        self._draw()

    def _canvas_click(self, event) -> None:
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.points.append((event.x / width, event.y / height))
        self._draw()

    def _polygon(self, zone: dict) -> list:
        raw = zone.get("polygonJson") or zone.get("PolygonJson") or zone.get("polygon") or []
        polygon = json.loads(raw) if isinstance(raw, str) else raw
        # Read legacy {x,y} zones as well, but always save the canonical
        # [[x,y], ...] format expected by dashboard and Cloud AI.
        return [
            [float(point["x"]), float(point["y"])]
            if isinstance(point, dict)
            else [float(point[0]), float(point[1])]
            for point in polygon
        ]

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), CANVAS_WIDTH)
        height = max(self.canvas.winfo_height(), CANVAS_HEIGHT)
        if getattr(self, "base_image", None):
            fitted = self.base_image.resize((width, height), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(fitted)
            self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        for zone in self.zones:
            polygon = self._polygon(zone)
            coords = [(point[0] * width, point[1] * height) for point in polygon]
            if len(coords) >= 3:
                flat = [value for point in coords for value in point]
                self.canvas.create_polygon(*flat, outline="#3b82f6", fill="#3b82f6", stipple="gray25", width=2)
        coords = [(x * width, y * height) for x, y in self.points]
        if len(coords) >= 2:
            self.canvas.create_line(*[v for p in coords for v in p], fill="#facc15", width=3)
        for x, y in coords:
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="#facc15", outline="white")

    def _new_zone(self) -> None:
        self.selected_zone = None
        self.points = []
        self.name.delete(0, "end")
        self.zone_type.set("HighValue")
        self._draw()

    def _select_zone(self) -> None:
        selected = self.zone_list.curselection()
        if not selected:
            return
        self.selected_zone = self.zones[selected[0]]
        self.points = [
            (point[0], point[1])
            for point in self._polygon(self.selected_zone)
        ]
        self.name.delete(0, "end")
        self.name.insert(0, self.selected_zone.get("name") or self.selected_zone.get("Name") or "")
        self.zone_type.set(
            self.selected_zone.get("zoneType") or self.selected_zone.get("ZoneType") or "HighValue"
        )
        self._draw()

    def _undo(self) -> None:
        if self.points:
            self.points.pop()
            self._draw()

    def _clear_points(self) -> None:
        self.points = []
        self._draw()

    def _save_zone_async(self) -> None:
        name = self.name.get().strip()
        if not name or len(self.points) < 3:
            messagebox.showerror(
                "ONEVO", "Enter a zone name and draw at least 3 points", parent=self.root
            )
            return
        camera_id = self._current_camera_id()
        zone_id = None
        if self.selected_zone:
            zone_id = self.selected_zone.get("id") or self.selected_zone.get("Id")
        body = {
            "zoneId": zone_id,
            "name": name,
            "zoneType": self.zone_type.get(),
            "polygon": [[x, y] for x, y in self.points],
        }
        self._async(lambda: self._save_zone(camera_id, body))

    def _save_zone(self, camera_id: str, body: dict) -> None:
        _json(f"/setup/wizard/cameras/{camera_id}/zones", "POST", body)
        self._load_camera(camera_id)

    def _delete_zone_async(self) -> None:
        if not self.selected_zone:
            messagebox.showerror("ONEVO", "Select a zone to delete", parent=self.root)
            return
        zone_id = self.selected_zone.get("id") or self.selected_zone.get("Id")
        if not messagebox.askyesno("ONEVO", "Delete the selected zone?", parent=self.root):
            return
        camera_id = self._current_camera_id()
        self._async(lambda: self._delete_zone(camera_id, zone_id))

    def _delete_zone(self, camera_id: str, zone_id: str) -> None:
        _request(f"/setup/wizard/zones/{zone_id}", "DELETE")
        self._load_camera(camera_id)

    def run(self) -> int:
        self.root.mainloop()
        return 0


def run_zone_editor() -> int:
    return ZoneEditor().run()
