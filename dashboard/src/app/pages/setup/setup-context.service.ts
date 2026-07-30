import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Camera, Connector, InstallerInfo, Store, Zone } from '../../core/models';
import { ConfirmDialogService } from '../../shared/confirm-dialog.service';

@Injectable()
export class SetupContextService {
  step = 1;
  readonly steps = [
    { id: 1, label: 'Connect shop PC' },
    { id: 2, label: 'Add cameras' },
    { id: 3, label: 'Draw zones' },
    { id: 4, label: 'Verify' },
  ];

  stores: Store[] = [];
  cameras: Camera[] = [];
  zones: Zone[] = [];
  storeId = '';
  cameraId = '';
  selectedCamera: Camera | null = null;
  selectedCameraIds = new Set<string>();
  editingCamera = false;
  savingCamera = false;
  editCamName = '';
  editCamUrl = '';
  editOnvifHost = '';
  editOnvifPort = 80;

  newStoreName = '';
  newCamName = '';
  newCamUrl = '';
  newOnvifHost = '';
  newOnvifPort = 80;
  showOnvifForm = false;

  draftName = '';
  draftType = 'HighValue';
  draftPoints: [number, number][] = [];
  rectStart: [number, number] | null = null;
  rectCurrent: [number, number] | null = null;
  draggedPointIndex: number | null = null;
  hoverPointIndex: number | null = null;

  testingStream = false;
  streamTestResult: { ok: boolean; message: string } | null = null;
  connectorAdminHost = 'localhost';
  connectorAdminPort = 8099;

  loadingSnapshot = false;
  snapshotError = '';
  snapshotImg: HTMLImageElement | null = null;

  generatingCode = false;
  setupCodeError = '';
  setupCode = '';
  setupCodeExpires = '';
  storeConnectors: Connector[] = [];
  installerInfo: InstallerInfo | null = null;
  installerError = '';

  constructor(
    private api: ApiService,
    public auth: AuthService,
    private router: Router,
    private confirm: ConfirmDialogService,
  ) {}

  get liveSnapshotUrl(): string {
    return this.cameraId
      ? `http://${this.connectorAdminHost}:${this.connectorAdminPort}/snapshot?camera_id=${this.cameraId}`
      : '';
  }

  get storeConnectorOnline(): boolean {
    const now = Date.now();
    return this.storeConnectors.some((c) => {
      if (!c.lastHeartbeat) return false;
      const age = now - new Date(c.lastHeartbeat).getTime();
      return age < 120_000 && (c.status === 'Healthy' || c.status === 'Degraded');
    });
  }

  get installerSizeMb(): string {
    return this.installerInfo?.sizeBytes
      ? (this.installerInfo.sizeBytes / 1048576).toFixed(1)
      : 'Unknown size';
  }

  get connectorUpdateAvailable(): boolean {
    if (!this.installerInfo || !this.storeConnectors.length) return false;
    return this.storeConnectors.some(
      (connector) => this.compareVersions(connector.version, this.installerInfo!.version) < 0,
    );
  }

  goToStep(id: number): void {
    this.step = id;
    const tree = this.router.parseUrl(this.router.url);
    tree.queryParams['step'] = String(id);
    this.router.navigateByUrl(tree, { replaceUrl: true });
  }

  loadStores(): void {
    this.api.listStores().subscribe((s) => {
      this.stores = s;
      const scoped = this.auth.storeId();
      if (scoped && !this.storeId && s.some((x) => x.id === scoped)) this.selectStore(scoped);
    });
  }

  loadInstallerInfo(): void {
    this.api.getInstallerInfo().subscribe({
      next: (info) => {
        this.installerInfo = info;
        this.installerError = '';
      },
      error: (err) => {
        this.installerInfo = null;
        this.installerError = err?.error?.error || 'Installer information is unavailable';
      },
    });
  }

  downloadInstaller(): void {
    if (!this.installerInfo?.downloadPath) return;
    const path = this.installerInfo.downloadPath;
    if (/^https?:\/\//i.test(path)) {
      window.location.assign(path);
      return;
    }
    this.api.downloadInstaller(path).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = this.installerInfo?.fileName || 'onetix-Connector-Setup.exe';
        anchor.click();
        URL.revokeObjectURL(url);
      },
      error: (err) => {
        this.installerError = err?.error?.error || 'Installer download failed';
      },
    });
  }

  generateSetupCode(): void {
    if (!this.storeId) return;
    this.generatingCode = true;
    this.setupCodeError = '';
    this.api.createSetupCode(this.storeId).subscribe({
      next: (res) => {
        this.setupCode = res.code;
        this.setupCodeExpires = new Date(res.expiresAt).toLocaleString();
        this.generatingCode = false;
      },
      error: (err) => {
        this.generatingCode = false;
        this.setupCodeError = err?.error?.error || 'Could not generate setup code';
      },
    });
  }

  copySetupCode(): void {
    if (!this.setupCode) return;
    navigator.clipboard?.writeText(this.setupCode);
  }

  refreshConnectors(): void {
    if (!this.storeId) {
      this.storeConnectors = [];
      return;
    }
    this.api.listConnectors(this.storeId).subscribe({
      next: (c) => {
        this.storeConnectors = c;
        const online = c.find((x) => x.adminHost && x.lastHeartbeat);
        if (online?.adminHost) {
          this.connectorAdminHost = online.adminHost;
          this.connectorAdminPort = online.adminPort || 8099;
        }
      },
      error: () => (this.storeConnectors = []),
    });
  }

  selectStore(id: string): void {
    this.storeId = id;
    this.cameraId = '';
    this.zones = [];
    this.selectedCamera = null;
    this.setupCode = '';
    this.setupCodeExpires = '';
    this.selectedCameraIds.clear();
    this.api.listCameras(id).subscribe((c) => (this.cameras = c.filter((x) => x.status !== 'Disabled')));
    this.refreshConnectors();
  }

  selectCamera(id: string, onLoaded?: () => void): void {
    this.cameraId = id;
    this.streamTestResult = null;
    this.selectedCamera = this.cameras.find((c) => c.id === id) ?? null;
    this.draftPoints = [];
    this.rectStart = null;
    this.rectCurrent = null;
    this.snapshotImg = null;
    this.snapshotError = '';
    this.api.getCamera(id).subscribe((cam) => {
      this.selectedCamera = cam;
      if (cam.onvifHost) this.connectorAdminHost = cam.onvifHost;
      this.loadSnapshot(onLoaded);
    });
    this.api.listZones(id).subscribe((z) => {
      this.zones = z;
      onLoaded?.();
    });
  }

  loadSnapshot(onLoaded?: () => void): void {
    if (!this.cameraId) return;
    this.loadingSnapshot = true;
    this.snapshotError = '';
    const img = new Image();
    img.src = `http://${this.connectorAdminHost}:8099/snapshot?camera_id=${this.cameraId}&t=${Date.now()}`;
    img.onload = () => {
      this.snapshotImg = img;
      this.loadingSnapshot = false;
      onLoaded?.();
    };
    img.onerror = () => {
      this.snapshotImg = null;
      this.loadingSnapshot = false;
      this.snapshotError = `No frame from connector (${this.connectorAdminHost}:8099). Is the connector running with this camera?`;
      onLoaded?.();
    };
  }

  addStore(): void {
    if (!this.newStoreName || !this.auth.isAdmin()) return;
    this.api.createStore({ name: this.newStoreName.trim(), alertVisibilityMode: 'ManagerOnly' }).subscribe(() => {
      this.newStoreName = '';
      this.loadStores();
    });
  }

  addCamera(): void {
    if (!this.newCamName) return;
    this.api
      .createCamera(
        this.storeId,
        this.newCamName,
        this.newCamUrl || '',
        this.newOnvifHost || undefined,
        this.newOnvifHost ? this.newOnvifPort || 80 : undefined,
      )
      .subscribe(() => {
        this.newCamName = '';
        this.newCamUrl = '';
        this.newOnvifHost = '';
        this.newOnvifPort = 80;
        this.showOnvifForm = false;
        this.selectStore(this.storeId);
      });
  }

  maskedRtsp(value?: string): string {
    if (!value) return '—';
    return value.replace(/(rtsp:\/\/[^:/@\s]+:)[^@\s]+@/i, '$1••••@');
  }

  startCameraEdit(): void {
    if (!this.selectedCamera) return;
    this.editingCamera = true;
    this.editCamName = this.selectedCamera.name;
    this.editCamUrl = this.selectedCamera.rtspUrl || '';
    this.editOnvifHost = this.selectedCamera.onvifHost || '';
    this.editOnvifPort = this.selectedCamera.onvifPort || 80;
  }

  saveCameraEdit(): void {
    if (!this.selectedCamera || !this.editCamName.trim()) return;
    this.savingCamera = true;
    this.api
      .updateCamera(this.selectedCamera.id, {
        name: this.editCamName.trim(),
        rtspUrl: this.editCamUrl.trim(),
        onvifHost: this.editOnvifHost.trim(),
        onvifPort: this.editOnvifPort || 80,
      })
      .subscribe({
        next: (camera) => {
          this.savingCamera = false;
          this.editingCamera = false;
          this.selectedCamera = camera;
          this.selectStore(this.storeId);
        },
        error: () => (this.savingCamera = false),
      });
  }

  toggleCameraSelection(id: string): void {
    if (this.selectedCameraIds.has(id)) this.selectedCameraIds.delete(id);
    else this.selectedCameraIds.add(id);
  }

  toggleAllCameras(): void {
    if (this.selectedCameraIds.size === this.cameras.length) this.selectedCameraIds.clear();
    else this.selectedCameraIds = new Set(this.cameras.map((camera) => camera.id));
  }

  async removeCamera(id: string): Promise<void> {
    const ok = await this.confirm.open({
      title: 'Remove camera',
      message: 'Remove this camera from monitoring?',
      confirmLabel: 'Remove',
      danger: true,
    });
    if (!ok) return;
    this.api.deleteCamera(id).subscribe(() => this.selectStore(this.storeId));
  }

  async removeSelectedCameras(): Promise<void> {
    const ids = [...this.selectedCameraIds];
    if (!ids.length) return;
    const ok = await this.confirm.open({
      title: 'Remove cameras',
      message: `Remove ${ids.length} selected camera(s) from monitoring?`,
      confirmLabel: 'Remove',
      danger: true,
    });
    if (!ok) return;
    this.api.bulkDisableCameras(ids).subscribe(() => this.selectStore(this.storeId));
  }

  deleteZone(id: string): void {
    this.api.deleteZone(id).subscribe(() => this.selectCamera(this.cameraId));
  }

  testStream(): void {
    if (!this.cameraId) return;
    this.testingStream = true;
    this.streamTestResult = null;
    this.api.testStream(this.cameraId).subscribe({
      next: (res) => {
        this.testingStream = false;
        this.streamTestResult = { ok: true, message: res.message ?? 'Stream test OK' };
      },
      error: (err) => {
        this.testingStream = false;
        this.streamTestResult = { ok: false, message: err?.error?.message ?? 'Stream test failed' };
      },
    });
  }

  undoPoint(redraw: () => void): void {
    if (this.draftPoints.length > 0) {
      this.draftPoints.pop();
      redraw();
    }
  }

  clearDraft(redraw: () => void): void {
    this.draftPoints = [];
    this.rectStart = null;
    this.rectCurrent = null;
    redraw();
  }

  saveZone(): void {
    if (this.draftPoints.length < 3 || !this.draftName) return;
    this.api
      .createZone(this.cameraId, this.draftName, this.draftType, JSON.stringify(this.draftPoints))
      .subscribe(() => {
        this.draftName = '';
        this.draftPoints = [];
        this.selectCamera(this.cameraId);
      });
  }

  private compareVersions(left: string, right: string): number {
    const parse = (value: string) => value.split('.').map((part) => Number.parseInt(part, 10) || 0);
    const a = parse(left);
    const b = parse(right);
    for (let index = 0; index < Math.max(a.length, b.length); index++) {
      if ((a[index] || 0) !== (b[index] || 0)) return (a[index] || 0) - (b[index] || 0);
    }
    return 0;
  }
}
