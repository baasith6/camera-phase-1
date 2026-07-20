import { AfterViewInit, Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { Camera, Store, Zone } from '../../core/models';

@Component({
  selector: 'app-setup',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h2>Setup &amp; Zones</h2>

    <div class="grid3">
      <!-- Stores -->
      <div class="card">
        <h3>Stores</h3>
        @for (s of stores; track s.id) {
          <div class="row-item" [class.sel]="s.id === storeId" (click)="selectStore(s.id)">
            {{ s.name }} <span class="muted small">({{ s.alertVisibilityMode }})</span>
          </div>
        }
        <div class="add-row">
          <input placeholder="New store name" [(ngModel)]="newStoreName" />
          <button (click)="addStore()">Add</button>
        </div>
      </div>

      <!-- Cameras -->
      <div class="card">
        <h3>Cameras</h3>
        @if (!storeId) { <p class="muted">Select a store.</p> }
        @for (c of cameras; track c.id) {
          <div class="row-item" [class.sel]="c.id === cameraId" (click)="selectCamera(c.id)">
            <div>
              <span>{{ c.name }}</span>
              <span class="muted small"> [{{ c.status }}]</span>
              @if (c.cameraModel) {
                <span class="chip">{{ c.cameraManufacturer }} {{ c.cameraModel }}</span>
              }
            </div>
          </div>
        }
        @if (storeId) {
          <div class="add-col" style="margin-top:.75rem">
            <div class="field-row">
              <label>Name</label>
              <input placeholder="Camera name" [(ngModel)]="newCamName" />
            </div>
            <div class="field-row">
              <label>RTSP URL</label>
              <input placeholder="rtsp://user:pass@ip:554/... (or auto via ONVIF)" [(ngModel)]="newCamUrl" />
            </div>
            <div class="onvif-section">
              <div class="onvif-header" (click)="showOnvifForm = !showOnvifForm">
                <span>⚙ ONVIF (optional — auto-fetch RTSP URL)</span>
                <span class="toggle">{{ showOnvifForm ? '▲' : '▼' }}</span>
              </div>
              @if (showOnvifForm) {
                <div class="onvif-fields">
                  <div class="field-row">
                    <label>Camera IP</label>
                    <input placeholder="192.168.1.64" [(ngModel)]="newOnvifHost" />
                  </div>
                  <div class="field-row">
                    <label>ONVIF port</label>
                    <input type="number" placeholder="80" [(ngModel)]="newOnvifPort" />
                  </div>
                </div>
              }
            </div>
            <button (click)="addCamera()" [disabled]="!newCamName">Add camera</button>
          </div>
        }
      </div>

      <!-- Zone list -->
      <div class="card">
        <h3>Zones</h3>
        @if (!cameraId) { <p class="muted">Select a camera.</p> }
        @for (z of zones; track z.id) {
          <div class="row-item">
            {{ z.name }} <span class="muted small">[{{ z.zoneType }}]</span>
            <button class="ghost small" (click)="deleteZone(z.id)">x</button>
          </div>
        }
      </div>
    </div>

    <!-- Camera detail panel -->
    @if (selectedCamera) {
      <div class="card" style="margin-top:1rem">
        <div class="cam-detail-header">
          <h3>{{ selectedCamera.name }}</h3>
          <div style="display:flex;gap:.5rem">
            <button class="ghost small" (click)="testStream()" [disabled]="testingStream">
              {{ testingStream ? 'Testing…' : '🔌 Test Stream' }}
            </button>
            @if (selectedCamera.onvifHost) {
              <a class="btn-link" [href]="'http://' + connectorAdminHost + ':8099/onvif/snapshot'" target="_blank">
                📷 Live Snapshot
              </a>
            }
          </div>
        </div>

        <div class="detail-grid">
          <div class="detail-row">
            <span class="dk">RTSP URL</span>
            <span class="dv">{{ selectedCamera.rtspUrl || '—' }}</span>
          </div>
          <div class="detail-row">
            <span class="dk">Status</span>
            <span class="badge" [class]="selectedCamera.status.toLowerCase()">{{ selectedCamera.status }}</span>
          </div>
          @if (selectedCamera.onvifHost) {
            <div class="detail-row">
              <span class="dk">ONVIF Host</span>
              <span class="dv">{{ selectedCamera.onvifHost }}:{{ selectedCamera.onvifPort || 80 }}</span>
            </div>
          }
          @if (selectedCamera.cameraManufacturer) {
            <div class="detail-row">
              <span class="dk">Manufacturer</span>
              <span class="dv">{{ selectedCamera.cameraManufacturer }}</span>
            </div>
            <div class="detail-row">
              <span class="dk">Model</span>
              <span class="dv">{{ selectedCamera.cameraModel }}</span>
            </div>
            <div class="detail-row">
              <span class="dk">Serial</span>
              <span class="dv">{{ selectedCamera.cameraSerial }}</span>
            </div>
            <div class="detail-row">
              <span class="dk">Firmware</span>
              <span class="dv">{{ selectedCamera.cameraFirmware }}</span>
            </div>
          } @else {
            <div class="detail-row">
              <span class="dk">ONVIF Info</span>
              <span class="dv muted">Not yet populated (start connector with --onvif-host)</span>
            </div>
          }
        </div>

        @if (streamTestResult) {
          <div class="test-result" [class.ok]="streamTestResult.ok" [class.err]="!streamTestResult.ok">
            {{ streamTestResult.message }}
          </div>
        }
      </div>
    }

    <!-- Zone drawing canvas -->
    @if (cameraId) {
      <div class="card" style="margin-top:1rem">
        <h3>Draw a zone</h3>
        <p class="muted small">Click on the canvas to add polygon points, then name the zone and save.
          (In production the camera still frame is shown here; coordinates are stored normalized 0..1.)</p>
        <div class="draw-toolbar">
          <input placeholder="Zone name" [(ngModel)]="draftName" />
          <select [(ngModel)]="draftType">
            <option value="Shelf">Shelf</option>
            <option value="HighValue">High-value shelf</option>
            <option value="Checkout">Checkout</option>
            <option value="Exit">Exit</option>
            <option value="BlindSpot">Blind spot</option>
            <option value="Staff">Staff</option>
          </select>
          <button class="ghost" (click)="clearDraft()">Clear points</button>
          <button (click)="saveZone()" [disabled]="draftPoints.length < 3">Save zone ({{ draftPoints.length }} pts)</button>
        </div>
        <canvas #cv width="480" height="270" 
                (click)="onCanvasClick($event)" 
                [style.background-image]="snapshotUrl"
                style="background-size: cover; background-position: center;"></canvas>
      </div>
    }
  `,
  styles: [`
    .grid3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; }
    .row-item { padding:.4rem .5rem; border-radius:6px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; }
    .row-item:hover { background:#1b2027; }
    .row-item.sel { background:#22303f; }
    .add-row { display:flex; gap:.4rem; margin-top:.6rem; }
    .add-col { display:flex; flex-direction:column; gap:.4rem; }
    .field-row { display:flex; flex-direction:column; gap:.15rem; }
    .field-row label { font-size:.75rem; color:#8ab4f8; }
    .onvif-section { border:1px solid #2a3540; border-radius:6px; overflow:hidden; margin:.2rem 0; }
    .onvif-header { display:flex; justify-content:space-between; padding:.4rem .6rem;
                    cursor:pointer; font-size:.8rem; color:#8ab4f8; background:#1b2027; }
    .onvif-header:hover { background:#22303f; }
    .toggle { font-size:.7rem; }
    .onvif-fields { padding:.5rem .6rem; display:flex; flex-direction:column; gap:.4rem; background:#141820; }
    .chip { display:inline-block; margin-left:.4rem; padding:.1rem .4rem; border-radius:10px;
            font-size:.7rem; background:#1e2e3f; color:#8ab4f8; }
    .draw-toolbar { display:flex; gap:.5rem; margin-bottom:.5rem; align-items:center; flex-wrap:wrap; }
    canvas { background:#0b0e12; border:1px solid #333; border-radius:6px; cursor:crosshair; }
    .small { font-size:.8rem; }
    .cam-detail-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .cam-detail-header h3 { margin:0; }
    .detail-grid { display:flex; flex-direction:column; gap:.3rem; }
    .detail-row { display:flex; gap:1rem; font-size:.85rem; }
    .dk { min-width:140px; color:#8ab4f8; font-size:.8rem; }
    .dv { color:#e6e6e6; word-break:break-all; }
    .badge { padding:.15rem .5rem; border-radius:10px; font-size:.75rem; }
    .badge.online { background:#1e4a2a; color:#8ae0a0; }
    .badge.pending { background:#2a2a2a; color:#aaa; }
    .badge.offline { background:#5a1e1e; color:#ff9f9f; }
    .btn-link { display:inline-block; padding:.3rem .65rem; border-radius:6px; font-size:.78rem;
                background:#1e2530; color:#8ab4f8; text-decoration:none; border:1px solid #2a3a50; }
    .btn-link:hover { background:#2a3a50; }
    .test-result { margin-top:.75rem; padding:.5rem .75rem; border-radius:6px; font-size:.82rem; }
    .test-result.ok { background:#1a3a2a; color:#5cdb7f; }
    .test-result.err { background:#3a1a1a; color:#f07070; }
  `],
})
export class SetupComponent implements OnInit, AfterViewInit {
  @ViewChild('cv') canvasRef?: ElementRef<HTMLCanvasElement>;

  stores: Store[] = [];
  cameras: Camera[] = [];
  zones: Zone[] = [];
  storeId = '';
  cameraId = '';
  selectedCamera: Camera | null = null;

  newStoreName = '';
  newCamName = '';
  newCamUrl = '';
  newOnvifHost = '';
  newOnvifPort: number = 80;
  showOnvifForm = false;

  draftName = '';
  draftType = 'HighValue';
  draftPoints: [number, number][] = [];

  testingStream = false;
  streamTestResult: { ok: boolean; message: string } | null = null;
  connectorAdminHost = 'localhost';

  constructor(private api: ApiService) {}

  get snapshotUrl(): string {
    return this.cameraId ? `url(http://${this.connectorAdminHost}:8099/snapshot?camera_id=${this.cameraId})` : 'none';
  }

  ngOnInit(): void { this.loadStores(); }
  ngAfterViewInit(): void { this.redraw(); }

  loadStores(): void { this.api.listStores().subscribe((s) => (this.stores = s)); }

  selectStore(id: string): void {
    this.storeId = id; this.cameraId = ''; this.zones = []; this.selectedCamera = null;
    this.api.listCameras(id).subscribe((c) => (this.cameras = c));
  }

  selectCamera(id: string): void {
    this.cameraId = id;
    this.streamTestResult = null;
    this.selectedCamera = this.cameras.find(c => c.id === id) ?? null;
    // Refresh full camera detail (includes ONVIF metadata from backend)
    this.api.getCamera(id).subscribe(cam => {
      this.selectedCamera = cam;
      if (cam.onvifHost) this.connectorAdminHost = cam.onvifHost;
    });
    this.api.listZones(id).subscribe((z) => { this.zones = z; setTimeout(() => this.redraw()); });
  }

  addStore(): void {
    if (!this.newStoreName) return;
    this.api.createStore(this.newStoreName).subscribe(() => { this.newStoreName = ''; this.loadStores(); });
  }

  addCamera(): void {
    if (!this.newCamName) return;
    const rtsp = this.newCamUrl || '';
    const onvifHost = this.newOnvifHost || undefined;
    const onvifPort = this.newOnvifHost ? (this.newOnvifPort || 80) : undefined;
    this.api.createCamera(this.storeId, this.newCamName, rtsp, onvifHost, onvifPort)
      .subscribe(() => {
        this.newCamName = ''; this.newCamUrl = ''; this.newOnvifHost = '';
        this.newOnvifPort = 80; this.showOnvifForm = false;
        this.selectStore(this.storeId);
      });
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

  onCanvasClick(ev: MouseEvent): void {
    const canvas = this.canvasRef!.nativeElement;
    const rect = canvas.getBoundingClientRect();
    const x = (ev.clientX - rect.left) / rect.width;
    const y = (ev.clientY - rect.top) / rect.height;
    this.draftPoints.push([Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000]);
    this.redraw();
  }

  clearDraft(): void { this.draftPoints = []; this.redraw(); }

  saveZone(): void {
    if (this.draftPoints.length < 3 || !this.draftName) return;
    this.api.createZone(this.cameraId, this.draftName, this.draftType, JSON.stringify(this.draftPoints))
      .subscribe(() => { this.draftName = ''; this.draftPoints = []; this.selectCamera(this.cameraId); });
  }

  private redraw(): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Existing zones.
    for (const z of this.zones) {
      let pts: [number, number][] = [];
      try { pts = JSON.parse(z.polygonJson); } catch { pts = []; }
      this.drawPoly(ctx, pts, w, h, z.zoneType === 'HighValue' ? 'rgba(255,120,120,0.35)' : 'rgba(120,160,255,0.3)');
    }
    // Draft.
    this.drawPoly(ctx, this.draftPoints, w, h, 'rgba(255,220,120,0.5)', true);
  }

  private drawPoly(ctx: CanvasRenderingContext2D, pts: [number, number][], w: number, h: number, fill: string, dots = false): void {
    if (pts.length === 0) return;
    ctx.beginPath();
    ctx.moveTo(pts[0][0] * w, pts[0][1] * h);
    for (const p of pts.slice(1)) ctx.lineTo(p[0] * w, p[1] * h);
    if (pts.length >= 3) ctx.closePath();
    ctx.fillStyle = fill;
    ctx.strokeStyle = '#e6e6e6';
    ctx.lineWidth = 1.5;
    ctx.fill();
    ctx.stroke();
    if (dots) {
      ctx.fillStyle = '#ffd678';
      for (const p of pts) { ctx.beginPath(); ctx.arc(p[0] * w, p[1] * h, 3, 0, Math.PI * 2); ctx.fill(); }
    }
  }
}

