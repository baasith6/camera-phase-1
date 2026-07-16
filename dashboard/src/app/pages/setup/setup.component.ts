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
            {{ c.name }} <span class="muted small">[{{ c.status }}]</span>
          </div>
        }
        @if (storeId) {
          <div class="add-col">
            <input placeholder="Camera name" [(ngModel)]="newCamName" />
            <input placeholder="rtsp:// or file://samples/test.mp4" [(ngModel)]="newCamUrl" />
            <button (click)="addCamera()">Add camera</button>
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

    @if (cameraId) {
      <div class="card">
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
        <canvas #cv width="480" height="270" (click)="onCanvasClick($event)"></canvas>
      </div>
    }
  `,
  styles: [`
    .grid3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; }
    .row-item { padding:.4rem .5rem; border-radius:6px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; }
    .row-item:hover { background:#1b2027; }
    .row-item.sel { background:#22303f; }
    .add-row, .add-col { display:flex; gap:.4rem; margin-top:.6rem; }
    .add-col { flex-direction:column; }
    .draw-toolbar { display:flex; gap:.5rem; margin-bottom:.5rem; align-items:center; flex-wrap:wrap; }
    canvas { background:#0b0e12; border:1px solid #333; border-radius:6px; cursor:crosshair; }
    .small { font-size:.8rem; }
  `],
})
export class SetupComponent implements OnInit, AfterViewInit {
  @ViewChild('cv') canvasRef?: ElementRef<HTMLCanvasElement>;

  stores: Store[] = [];
  cameras: Camera[] = [];
  zones: Zone[] = [];
  storeId = '';
  cameraId = '';

  newStoreName = '';
  newCamName = '';
  newCamUrl = 'file://samples/test.mp4';

  draftName = '';
  draftType = 'HighValue';
  draftPoints: [number, number][] = [];

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.loadStores(); }
  ngAfterViewInit(): void { this.redraw(); }

  loadStores(): void { this.api.listStores().subscribe((s) => (this.stores = s)); }

  selectStore(id: string): void {
    this.storeId = id; this.cameraId = ''; this.zones = [];
    this.api.listCameras(id).subscribe((c) => (this.cameras = c));
  }

  selectCamera(id: string): void {
    this.cameraId = id;
    this.api.listZones(id).subscribe((z) => { this.zones = z; setTimeout(() => this.redraw()); });
  }

  addStore(): void {
    if (!this.newStoreName) return;
    this.api.createStore(this.newStoreName).subscribe(() => { this.newStoreName = ''; this.loadStores(); });
  }

  addCamera(): void {
    if (!this.newCamName) return;
    this.api.createCamera(this.storeId, this.newCamName, this.newCamUrl).subscribe(() => {
      this.newCamName = '';
      this.selectStore(this.storeId);
    });
  }

  deleteZone(id: string): void {
    this.api.deleteZone(id).subscribe(() => this.selectCamera(this.cameraId));
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
