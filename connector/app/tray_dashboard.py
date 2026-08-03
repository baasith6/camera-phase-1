"""Native tray dashboard for local connector monitoring and zone access."""
from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .tray_zone_editor import _json, _request


BACKGROUND = "#0e141b"
PANEL = "#161e28"
PANEL_ALT = "#111923"
LINE = "#2a3644"
TEXT = "#e8eef5"
MUTED = "#8b9aab"
GREEN = "#3ecf8e"
YELLOW = "#f7c948"
RED = "#f07178"
ACCENT = "#3d9cf0"


class TrayDashboard:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("ONEVO Local Connector")
        self.root.geometry("1120x720")
        self.root.minsize(900, 620)
        self.root.configure(bg=BACKGROUND)
        self._refresh_after: str | None = None
        self._build()
        self.refresh()

    def _label(self, parent, text="", size=10, bold=False, color="#dbe7f5"):
        return tk.Label(
            parent, text=text, bg=parent.cget("bg"), fg=color,
            font=("Segoe UI", size, "bold" if bold else "normal"),
        )

    @staticmethod
    def _button(parent, text, command, *, primary=False):
        return tk.Button(
            parent, text=text, command=command, relief="flat",
            bg=ACCENT if primary else PANEL_ALT,
            fg="#061018" if primary else TEXT,
            activebackground="#65b7ff" if primary else "#223143",
            activeforeground="#061018" if primary else TEXT,
            padx=12, pady=8, cursor="hand2", borderwidth=0,
            font=("Segoe UI", 9, "bold"),
        )

    def _panel(self, parent, **pack):
        panel = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        panel.pack(**pack)
        return panel

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=PANEL_ALT, padx=22, pady=16)
        header.pack(fill="x")
        self._label(header, "ONEVO", 18, True, ACCENT).pack(side="left")
        self._label(header, "Local Connector", 18, True).pack(side="left", padx=(8, 0))
        self.running = self._label(header, "● Checking…", 11, True, YELLOW)
        self.running.pack(side="right")

        content = tk.Frame(self.root, bg=BACKGROUND, padx=18, pady=16)
        content.pack(fill="both", expand=True)

        cards = tk.Frame(content, bg=BACKGROUND)
        cards.pack(fill="x")
        self.card_values = {}
        for key, title in (
            ("sources", "Sources"), ("zones", "Zones"), ("clips", "Clips"),
            ("uploads", "Uploads OK"),
        ):
            card = self._panel(cards, side="left", fill="x", expand=True, padx=(0, 10) if key != "uploads" else 0)
            inner = tk.Frame(card, bg=PANEL, padx=16, pady=12)
            inner.pack(fill="both", expand=True)
            self._label(inner, title, 9, False, MUTED).pack(anchor="w")
            value = self._label(inner, "0", 23, True, TEXT)
            value.pack(anchor="w", pady=(4, 0))
            self.card_values[key] = value

        body = tk.Frame(content, bg=BACKGROUND, pady=14)
        body.pack(fill="both", expand=True)
        left = self._panel(body, side="left", fill="both", expand=True, padx=(0, 7))
        right = self._panel(body, side="right", fill="both", expand=True, padx=(7, 0))
        left_inner = tk.Frame(left, bg=PANEL, padx=16, pady=14)
        left_inner.pack(fill="both", expand=True)
        right_inner = tk.Frame(right, bg=PANEL, padx=16, pady=14)
        right_inner.pack(fill="both", expand=True)
        self._label(left_inner, "Camera Sources", 12, True).pack(anchor="w")
        self.sources = tk.Listbox(
            left_inner, bg=PANEL_ALT, fg=TEXT, selectbackground="#223143",
            highlightthickness=0, relief="flat", borderwidth=0, font=("Segoe UI", 10),
        )
        self.sources.pack(fill="both", expand=True, pady=8)
        self._label(right_inner, "Zones", 12, True).pack(anchor="w")
        self.zones = tk.Listbox(
            right_inner, bg=PANEL_ALT, fg=TEXT, selectbackground="#223143",
            highlightthickness=0, relief="flat", borderwidth=0, font=("Segoe UI", 10),
        )
        self.zones.pack(fill="both", expand=True, pady=8)

        actions = self._panel(content, fill="x")
        actions_inner = tk.Frame(actions, bg=PANEL, padx=16, pady=13)
        actions_inner.pack(fill="x")
        self._label(actions_inner, "Quick Actions", 10, True, MUTED).pack(side="left", padx=(0, 12))
        self._button(actions_inner, "Pause Monitoring", self.pause_monitoring).pack(side="left", padx=3)
        self._button(actions_inner, "Cut Clip Now", self.cut_clip).pack(side="left", padx=3)
        self._button(actions_inner, "Edit Zones", self.edit_zones, primary=True).pack(side="left", padx=3)
        self._button(actions_inner, "Refresh", self.refresh).pack(side="left", padx=3)
        self._button(actions_inner, "Close", self.root.destroy).pack(side="right")
        self.storage = self._label(actions_inner, "", 9, False, YELLOW)
        self.storage.pack(side="right", padx=16)

    def refresh(self) -> None:
        try:
            status = _json("/setup/wizard/status")
            source_data = _json("/sources")
            wizard = _json("/setup/wizard/status")
            cameras = wizard.get("cameras") or []
            zone_rows = []
            for camera in cameras:
                camera_id = camera.get("cameraId") or camera.get("CameraId")
                if camera_id:
                    for zone in _json(f"/setup/wizard/cameras/{camera_id}/zones"):
                        zone_rows.append(zone)
            sources = source_data.get("sources") or []
            self.running.configure(
                text="● Running" if status.get("capturing") else "● Connected",
                fg="#4ade80",
            )
            self.card_values["sources"].configure(text=str(len(sources)))
            self.card_values["zones"].configure(text=str(len(zone_rows)))
            self.card_values["clips"].configure(text=str(status.get("clipsCreated", 0)))
            self.card_values["uploads"].configure(text=str(status.get("uploadsOk", 0)))
            self.sources.delete(0, "end")
            for source in sources:
                name = source.get("name") or "Camera"
                state = "Online" if source.get("cameraId") else "Pending"
                self.sources.insert("end", f"{name}   • {state}")
            self.zones.delete(0, "end")
            for zone in zone_rows:
                self.zones.insert("end", zone.get("name") or zone.get("Name") or "Zone")
            disk = status.get("diskFreePct")
            self.storage.configure(text=f"Disk free: {disk}%" if disk is not None else "")
        except Exception as exc:
            self.running.configure(text="● Offline", fg=RED)
            self.storage.configure(text=str(exc))
        finally:
            if self._refresh_after is not None:
                self.root.after_cancel(self._refresh_after)
            self._refresh_after = self.root.after(5000, self.refresh)

    def _action(self, path: str, success: str) -> None:
        try:
            _request(path, "POST")
            self.storage.configure(text=success, fg=GREEN)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("ONEVO Connector", str(exc), parent=self.root)

    def pause_monitoring(self) -> None:
        self._action("/capture/pause", "Monitoring paused")

    def cut_clip(self) -> None:
        self._action("/capture/trigger-now", "Capture requested")

    def edit_zones(self) -> None:
        subprocess.Popen(
            [sys.executable, "--edit-zones"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def run(self) -> int:
        self.root.mainloop()
        return 0


def run_tray_dashboard() -> int:
    return TrayDashboard().run()
