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
        <div class="zone-header">
          <div>
            <h3>Zone Editor &amp; Visual Canvas</h3>
            <p class="muted small">
              Click on the canvas to draw a box or multi-point zone. Drag yellow corner points anytime to adjust exact boundaries.
            </p>
          </div>
        </div>

        <div class="draw-toolbar">
          <input placeholder="Zone name (e.g. High-Value Shelf)" [(ngModel)]="draftName" style="width:200px" />
          <select [(ngModel)]="draftType">
            <option value="HighValue">High-value shelf</option>
            <option value="Shelf">Shelf</option>
            <option value="Checkout">Checkout</option>
            <option value="Exit">Exit</option>
            <option value="BlindSpot">Blind spot</option>
            <option value="Staff">Staff</option>
          </select>
          <button class="ghost" (click)="undoPoint()" [disabled]="draftPoints.length === 0">↩ Undo Point</button>
          <button class="ghost" (click)="clearDraft()" [disabled]="draftPoints.length === 0">Clear points</button>
          <button class="btn-primary" (click)="saveZone()" [disabled]="draftPoints.length < 3 || !draftName">
            💾 Save Zone ({{ draftPoints.length }} pts)
          </button>
        </div>

        <div class="canvas-container">
          <canvas #cv width="640" height="360"
                  (mousedown)="onCanvasMouseDown($event)"
                  (mousemove)="onCanvasMouseMove($event)"
                  (mouseup)="onCanvasMouseUp($event)"
                  (mouseleave)="onCanvasMouseUp($event)"
                  [style.background-image]="effectiveSnapshotUrl"
                  style="background-size: cover; background-position: center;"></canvas>
          <div class="canvas-hint muted small">
            💡 <strong>Tip:</strong> Click 2 opposite corners to draw a Box, or keep clicking to add points. Drag yellow dots to adjust points anytime!
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .grid3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; }
    .row-item { padding:.4rem .5rem; border-radius:6px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; }
    .row-item:hover { background:var(--accent-soft); }
    .row-item.sel { background:var(--accent-soft); border-left:2px solid var(--accent); }
    .add-row { display:flex; gap:.4rem; margin-top:.6rem; }
    .add-col { display:flex; flex-direction:column; gap:.4rem; }
    .field-row { display:flex; flex-direction:column; gap:.15rem; }
    .field-row label { font-size:.75rem; color:var(--accent-2); }
    .onvif-section { border:1px solid var(--border-strong); border-radius:var(--radius-sm); overflow:hidden; margin:.2rem 0; }
    .onvif-header { display:flex; justify-content:space-between; padding:.4rem .6rem;
                    cursor:pointer; font-size:.8rem; color:var(--accent-2); background:var(--surface-2); }
    .onvif-header:hover { background:var(--accent-soft); }
    .toggle { font-size:.7rem; }
    .onvif-fields { padding:.5rem .6rem; display:flex; flex-direction:column; gap:.4rem; background:var(--surface); }
    .chip { display:inline-block; margin-left:.4rem; padding:.1rem .4rem; border-radius:999px;
            font-size:.7rem; background:var(--info-soft); color:var(--accent-2); }
    .zone-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:.75rem; }
    .draw-toolbar { display:flex; gap:.5rem; margin-bottom:.75rem; align-items:center; flex-wrap:wrap; }
    .btn-primary { background:var(--accent); color:#fff; border:none; padding:.4rem .9rem; border-radius:var(--radius-sm); font-weight:600; cursor:pointer; }
    .btn-primary:disabled { opacity:0.5; cursor:not-allowed; }
    .canvas-container { position:relative; display:inline-block; max-width:100%; }
    canvas { background:var(--bg); border:1px solid var(--border-strong); border-radius:var(--radius-sm); cursor:crosshair; display:block; }
    .canvas-hint { margin-top:.4rem; font-size:.8rem; }
    .small { font-size:.8rem; }
    .cam-detail-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .cam-detail-header h3 { margin:0; }
    .detail-grid { display:flex; flex-direction:column; gap:.3rem; }
    .detail-row { display:flex; gap:1rem; font-size:.85rem; }
    .dk { min-width:140px; color:var(--accent-2); font-size:.8rem; }
    .dv { color:var(--text); word-break:break-all; }
    .badge { padding:.18rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600; }
    .badge.online { background:var(--success-soft); color:var(--success); border:1px solid rgba(52,211,153,.3); }
    .badge.pending { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .badge.offline { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3); }
    .btn-link { display:inline-block; padding:.3rem .65rem; border-radius:var(--radius-sm); font-size:.78rem;
                background:var(--accent-soft); color:var(--accent-2); text-decoration:none; border:1px solid var(--border-strong); }
    .btn-link:hover { background:rgba(139,92,246,.22); border-color:var(--accent); }
    .test-result { margin-top:.75rem; padding:.5rem .75rem; border-radius:var(--radius-sm); font-size:.82rem; }
    .test-result.ok { background:var(--success-soft); color:var(--success); }
    .test-result.err { background:var(--danger-soft); color:var(--danger); }
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
  rectStart: [number, number] | null = null;
  rectCurrent: [number, number] | null = null;

  draggedPointIndex: number | null = null;
  hoverPointIndex: number | null = null;

  testingStream = false;
  streamTestResult: { ok: boolean; message: string } | null = null;
  connectorAdminHost = 'localhost';

  constructor(private api: ApiService) {}

  get effectiveSnapshotUrl(): string {
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
    this.draftPoints = [];
    this.rectStart = null;
    this.rectCurrent = null;
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

  undoPoint(): void {
    if (this.draftPoints.length > 0) {
      this.draftPoints.pop();
      this.redraw();
    }
  }

  clearDraft(): void {
    this.draftPoints = [];
    this.rectStart = null;
    this.rectCurrent = null;
    this.redraw();
  }

  onCanvasMouseDown(ev: MouseEvent): void {
    const canvas = this.canvasRef!.nativeElement;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(((ev.clientX - rect.left) / rect.width) * 1000) / 1000;
    const y = Math.round(((ev.clientY - rect.top) / rect.height) * 1000) / 1000;

    // Check if clicking near an existing draft point to start dragging
    const clickRadius = 0.04; // 4% threshold for handle hit
    const nearIdx = this.draftPoints.findIndex(p => Math.hypot(p[0] - x, p[1] - y) < clickRadius);

    if (nearIdx !== -1) {
      this.draggedPointIndex = nearIdx;
      return;
    }

    if (this.draftPoints.length === 0) {
      // First click: start rectangle / point sequence
      this.rectStart = [x, y];
      this.rectCurrent = [x, y];
      this.draftPoints.push([x, y]);
    } else if (this.draftPoints.length === 1 && this.rectStart) {
      // Second click: complete initial box
      const x1 = Math.min(this.rectStart[0], x);
      const y1 = Math.min(this.rectStart[1], y);
      const x2 = Math.max(this.rectStart[0], x);
      const y2 = Math.max(this.rectStart[1], y);
      this.draftPoints = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]];
      this.rectStart = null;
      this.rectCurrent = null;
    } else {
      // Additional clicks: append polygon point
      this.draftPoints.push([x, y]);
    }
    this.redraw();
  }

  onCanvasMouseMove(ev: MouseEvent): void {
    const canvas = this.canvasRef!.nativeElement;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(((ev.clientX - rect.left) / rect.width) * 1000) / 1000;
    const y = Math.round(((ev.clientY - rect.top) / rect.height) * 1000) / 1000;

    // Handle point dragging
    if (this.draggedPointIndex !== null) {
      this.draftPoints[this.draggedPointIndex] = [x, y];
      this.redraw();
      return;
    }

    // Hover effect for points
    const hoverRadius = 0.04;
    const nearIdx = this.draftPoints.findIndex(p => Math.hypot(p[0] - x, p[1] - y) < hoverRadius);
    if (nearIdx !== this.hoverPointIndex) {
      this.hoverPointIndex = nearIdx !== -1 ? nearIdx : null;
      canvas.style.cursor = nearIdx !== -1 ? 'grab' : 'crosshair';
      this.redraw();
    }

    // Live preview for initial box creation
    if (this.rectStart && this.draftPoints.length === 1) {
      this.rectCurrent = [x, y];
      this.redraw();
    }
  }

  onCanvasMouseUp(ev: MouseEvent): void {
    if (this.draggedPointIndex !== null) {
      this.draggedPointIndex = null;
      this.redraw();
    }
  }

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

    // Existing saved zones
    for (const z of this.zones) {
      let pts: [number, number][] = [];
      try { pts = JSON.parse(z.polygonJson); } catch { pts = []; }
      this.drawPoly(ctx, pts, w, h, z.zoneType === 'HighValue' ? 'rgba(255,120,120,0.35)' : 'rgba(120,160,255,0.3)');
    }

    // Current draft polygon / preview box
    if (this.draftPoints.length > 1) {
      this.drawPoly(ctx, this.draftPoints, w, h, 'rgba(255,220,120,0.5)', true);
    } else if (this.draftPoints.length === 1 && this.rectStart && this.rectCurrent) {
      const x1 = Math.min(this.rectStart[0], this.rectCurrent[0]);
      const y1 = Math.min(this.rectStart[1], this.rectCurrent[1]);
      const x2 = Math.max(this.rectStart[0], this.rectCurrent[0]);
      const y2 = Math.max(this.rectStart[1], this.rectCurrent[1]);
      const rectPts: [number, number][] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]];
      this.drawPoly(ctx, rectPts, w, h, 'rgba(255,220,120,0.4)', true);
    }
  }

  private drawPoly(ctx: CanvasRenderingContext2D, pts: [number, number][], w: number, h: number, fill: string, interactive = false): void {
    if (pts.length === 0) return;
    ctx.beginPath();
    ctx.moveTo(pts[0][0] * w, pts[0][1] * h);
    for (const p of pts.slice(1)) ctx.lineTo(p[0] * w, p[1] * h);
    if (pts.length >= 3) ctx.closePath();
    ctx.fillStyle = fill;
    ctx.strokeStyle = interactive ? '#ffd678' : '#e6e6e6';
    ctx.lineWidth = interactive ? 2.5 : 1.5;
    ctx.fill();
    ctx.stroke();

    if (interactive) {
      for (let i = 0; i < pts.length; i++) {
        const px = pts[i][0] * w;
        const py = pts[i][1] * h;
        const isHover = i === this.hoverPointIndex || i === this.draggedPointIndex;

        ctx.beginPath();
        ctx.arc(px, py, isHover ? 8 : 5, 0, Math.PI * 2);
        ctx.fillStyle = isHover ? '#ffffff' : '#ffd678';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
        ctx.shadowBlur = 4;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.strokeStyle = '#8b5cf6';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }
  }
}

