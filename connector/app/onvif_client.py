"""ONVIF camera client — WS-Discovery + direct connection.

Provides:
  - discover(timeout)           : WS-Discovery scan → list cameras on LAN
  - OnvifCamera.connect(...)    : connect to a single camera by IP
  - get_rtsp_url(profile)       : auto-extract the RTSP stream URL
  - get_snapshot_url(profile)   : live JPEG snapshot URL
  - get_device_info()           : manufacturer / model / serial / firmware
  - get_profiles()              : all stream profiles on the camera

Requires:  onvif-zeep>=0.2.12   wsdiscovery>=2.0
"""
from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredCamera:
    """A camera found via WS-Discovery."""
    xaddr: str          # ONVIF device service URL  e.g. http://192.168.1.64/onvif/device_service
    ip: str             # extracted IP address
    name: str = ""      # friendly name if provided in probe match
    scopes: list[str] = field(default_factory=list)


@dataclass
class DeviceInfo:
    manufacturer: str = ""
    model: str = ""
    serial: str = ""
    firmware: str = ""
    hardware: str = ""


@dataclass
class StreamProfile:
    token: str
    name: str
    encoding: str = ""
    width: int = 0
    height: int = 0


# ---------------------------------------------------------------------------
# WS-Discovery (subnet broadcast — finds all ONVIF cameras on the LAN)
# ---------------------------------------------------------------------------

def discover(timeout: float = 5.0) -> list[DiscoveredCamera]:
    """Run WS-Discovery and return all ONVIF cameras found on the LAN.

    Requires the ``wsdiscovery`` package.  If it isn't installed, logs a
    warning and returns an empty list so the rest of the connector still works.
    """
    try:
        from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery  # type: ignore
    except ImportError:
        logger.warning("[onvif] wsdiscovery not installed — discovery disabled")
        return []

    found: list[DiscoveredCamera] = []
    try:
        wsd = WSDiscovery()
        wsd.start()
        services = wsd.searchServices(timeout=timeout)
        wsd.stop()
        for svc in services:
            xaddrs = svc.getXAddrs()
            if not xaddrs:
                continue
            xaddr = xaddrs[0]
            ip = _extract_ip(xaddr)
            scopes = [str(s) for s in svc.getScopes()]
            name = _scope_name(scopes) or ip
            found.append(DiscoveredCamera(xaddr=xaddr, ip=ip, name=name, scopes=scopes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[onvif] WS-Discovery error: %s", exc)
    return found


# ---------------------------------------------------------------------------
# Direct camera connection
# ---------------------------------------------------------------------------

class OnvifCamera:
    """Wraps onvif-zeep for device info + stream URL extraction.

    Usage::
        cam = OnvifCamera()
        cam.connect("192.168.1.64", port=80, username="admin", password="admin")
        info   = cam.get_device_info()
        rtsp   = cam.get_rtsp_url()
        snap   = cam.get_snapshot_url()
    """

    def __init__(self) -> None:
        self._cam = None        # onvif.ONVIFCamera
        self._media = None      # media service
        self._profiles: list[StreamProfile] = []
        self.host: str = ""
        self.port: int = 80
        self.username: str = ""

    # ------------------------------------------------------------------
    def connect(self, host: str, port: int = 80, username: str = "admin",
                password: str = "admin") -> "OnvifCamera":
        """Connect to a camera and load stream profiles.

        Raises ``RuntimeError`` if onvif-zeep is not installed or connection fails.
        """
        try:
            from onvif import ONVIFCamera  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "onvif-zeep is not installed. Run: pip install onvif-zeep"
            ) from exc

        self.host = host
        self.port = port
        self.username = username
        logger.info("[onvif] connecting to %s:%s as %s", host, port, username)

        self._cam = ONVIFCamera(host, port, username, password)
        self._media = self._cam.create_media_service()
        self._profiles = self._load_profiles()
        logger.info("[onvif] connected — %d profile(s): %s",
                    len(self._profiles), [p.name for p in self._profiles])
        return self

    # ------------------------------------------------------------------
    def get_profiles(self) -> list[StreamProfile]:
        """Return all stream profiles detected on the camera."""
        return list(self._profiles)

    def get_device_info(self) -> DeviceInfo:
        """Query ONVIF GetDeviceInfo and return a DeviceInfo dataclass."""
        self._check_connected()
        try:
            dev_svc = self._cam.create_devicemgmt_service()
            info = dev_svc.GetDeviceInformation()
            return DeviceInfo(
                manufacturer=getattr(info, "Manufacturer", ""),
                model=getattr(info, "Model", ""),
                serial=getattr(info, "SerialNumber", ""),
                firmware=getattr(info, "FirmwareVersion", ""),
                hardware=getattr(info, "HardwareId", ""),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[onvif] GetDeviceInformation failed: %s", exc)
            return DeviceInfo()

    def get_rtsp_url(self, profile_token: Optional[str] = None) -> str:
        """Return the RTSP stream URL for the given profile (or best/first profile).

        The URL is returned in the form ``rtsp://user:pass@host:port/path``.
        """
        self._check_connected()
        token = profile_token or self._best_token()
        try:
            req = self._media.create_type("GetStreamUri")
            req.ProfileToken = token
            req.StreamSetup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }
            resp = self._media.GetStreamUri(req)
            raw_url: str = resp.Uri
            # Inject credentials into the URL so OpenCV can auth.
            return _inject_credentials(raw_url, self.username,
                                       getattr(self._cam, "_password", ""))
        except Exception as exc:
            raise RuntimeError(f"GetStreamUri failed: {exc}") from exc

    def get_snapshot_url(self, profile_token: Optional[str] = None) -> str:
        """Return the snapshot (JPEG) URL for the given profile."""
        self._check_connected()
        token = profile_token or self._best_token()
        try:
            req = self._media.create_type("GetSnapshotUri")
            req.ProfileToken = token
            resp = self._media.GetSnapshotUri(req)
            return _inject_credentials(resp.Uri, self.username,
                                       getattr(self._cam, "_password", ""))
        except Exception as exc:
            raise RuntimeError(f"GetSnapshotUri failed: {exc}") from exc

    def fetch_snapshot_bytes(self, profile_token: Optional[str] = None) -> bytes:
        """Download and return raw JPEG bytes from the snapshot URL."""
        import urllib.request
        url = self.get_snapshot_url(profile_token)
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            return resp.read()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_connected(self) -> None:
        if self._cam is None:
            raise RuntimeError("OnvifCamera.connect() has not been called")

    def _best_token(self) -> str:
        if not self._profiles:
            raise RuntimeError("No ONVIF profiles found on this camera")
        # Prefer the highest-resolution profile (first after sort by pixel count desc).
        best = sorted(self._profiles, key=lambda p: p.width * p.height, reverse=True)[0]
        return best.token

    def _load_profiles(self) -> list[StreamProfile]:
        profiles = []
        try:
            raw = self._media.GetProfiles()
            for p in raw:
                token = getattr(p, "token", "")
                name = getattr(p, "Name", token)
                enc = width = height = ""
                vc = getattr(p, "VideoEncoderConfiguration", None)
                if vc is not None:
                    enc = getattr(vc, "Encoding", "")
                    res = getattr(vc, "Resolution", None)
                    if res is not None:
                        width = getattr(res, "Width", 0)
                        height = getattr(res, "Height", 0)
                profiles.append(StreamProfile(
                    token=token, name=name,
                    encoding=str(enc), width=int(width or 0), height=int(height or 0)
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[onvif] GetProfiles failed: %s", exc)
        return profiles


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _extract_ip(xaddr: str) -> str:
    """Pull the host/IP from an ONVIF xaddr URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(xaddr).hostname or xaddr
    except Exception:
        return xaddr


def _scope_name(scopes: list[str]) -> str:
    """Try to extract a human-readable name from ONVIF scope URIs."""
    for s in scopes:
        if "name" in s.lower():
            # e.g. onvif://www.onvif.org/name/IPCamera
            parts = s.rstrip("/").split("/")
            if parts:
                return parts[-1].replace("%20", " ")
    return ""


def _inject_credentials(url: str, username: str, password: str) -> str:
    """Insert user:pass@ into a URL if not already present."""
    if not username:
        return url
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.username:          # already has credentials
            return url
        netloc = f"{username}:{password}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return url
