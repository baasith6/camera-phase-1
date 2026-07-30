import { AfterViewInit, Component, ElementRef, ViewChild, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SetupContextService } from './setup-context.service';

@Component({
  selector: 'app-setup-zones-step',
  standalone: true,
  imports: [FormsModule],
  template: `
    <ul class="need-list muted small">
      <li>A camera selected from step 2</li>
      <li>Draw areas where you want extra attention (e.g. high-value shelves)</li>
    </ul>

    @if (!ctx.cameraId) {
      <div class="card muted">Select a camera in step 2 first, then come back here to draw zones.</div>
    } @else {
      <div class="card">
        <h3>Draw zones on your camera view</h3>
        <p class="muted small">Click on the picture to mark an area. Drag the yellow dots to adjust.</p>

        <div class="draw-toolbar">
          <input placeholder="Zone name (e.g. High-value shelf)" [(ngModel)]="ctx.draftName" style="width:200px" />
          <select [(ngModel)]="ctx.draftType">
            <option value="HighValue">High-value shelf</option>
            <option value="Shelf">Shelf</option>
            <option value="Checkout">Checkout</option>
            <option value="Exit">Exit</option>
            <option value="BlindSpot">Blind spot</option>
            <option value="Staff">Staff area</option>
          </select>
          <button class="ghost" (click)="ctx.undoPoint(redraw.bind(this))" [disabled]="ctx.draftPoints.length === 0">Undo point</button>
          <button class="ghost" (click)="ctx.clearDraft(redraw.bind(this))" [disabled]="ctx.draftPoints.length === 0">Clear</button>
          <button class="ghost" (click)="ctx.loadSnapshot(redraw.bind(this))" [disabled]="ctx.loadingSnapshot">
            {{ ctx.loadingSnapshot ? 'Loading…' : 'Refresh picture' }}
          </button>
          <button class="btn-primary" (click)="ctx.saveZone()" [disabled]="ctx.draftPoints.length < 3 || !ctx.draftName">
            Save zone
          </button>
        </div>

        @if (ctx.snapshotError) {
          <p class="err-text">{{ ctx.snapshotError }} — you can still draw on the blank canvas.</p>
        }

        <div class="canvas-container">
          <canvas #zoneCanvas width="640" height="360"
                  (mousedown)="onCanvasMouseDown($event)"
                  (mousemove)="onCanvasMouseMove($event)"
                  (mouseup)="onCanvasMouseUp()"
                  (mouseleave)="onCanvasMouseUp()"></canvas>
        </div>
      </div>
    }
  `,
  styles: [`
    .need-list { margin: 0 0 12px; padding-left: 18px; }
    .draw-toolbar { display: flex; gap: .5rem; margin-bottom: .75rem; align-items: center; flex-wrap: wrap; }
    .btn-primary { background: var(--accent); color: #fff; border: none; padding: .4rem .9rem; border-radius: var(--radius-sm); font-weight: 600; cursor: pointer; }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .canvas-container canvas { max-width: 100%; height: auto; background: var(--bg); border: 1px solid var(--border-strong); border-radius: var(--radius-sm); cursor: crosshair; display: block; }
    .err-text { color: var(--danger); font-size: .82rem; }
    .small { font-size: .8rem; }
  `],
})
export class SetupZonesStepComponent implements AfterViewInit {
  readonly ctx = inject(SetupContextService);
  @ViewChild('zoneCanvas') canvasRef?: ElementRef<HTMLCanvasElement>;

  ngAfterViewInit(): void {
    this.redraw();
  }

  onCanvasMouseDown(ev: MouseEvent): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(((ev.clientX - rect.left) / rect.width) * 1000) / 1000;
    const y = Math.round(((ev.clientY - rect.top) / rect.height) * 1000) / 1000;
    const clickRadius = 0.04;
    const nearIdx = this.ctx.draftPoints.findIndex((p) => Math.hypot(p[0] - x, p[1] - y) < clickRadius);
    if (nearIdx !== -1) {
      this.ctx.draggedPointIndex = nearIdx;
      return;
    }
    if (this.ctx.draftPoints.length === 0) {
      this.ctx.rectStart = [x, y];
      this.ctx.rectCurrent = [x, y];
      this.ctx.draftPoints.push([x, y]);
    } else if (this.ctx.draftPoints.length === 1 && this.ctx.rectStart) {
      const x1 = Math.min(this.ctx.rectStart[0], x);
      const y1 = Math.min(this.ctx.rectStart[1], y);
      const x2 = Math.max(this.ctx.rectStart[0], x);
      const y2 = Math.max(this.ctx.rectStart[1], y);
      this.ctx.draftPoints = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]];
      this.ctx.rectStart = null;
      this.ctx.rectCurrent = null;
    } else {
      this.ctx.draftPoints.push([x, y]);
    }
    this.redraw();
  }

  onCanvasMouseMove(ev: MouseEvent): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(((ev.clientX - rect.left) / rect.width) * 1000) / 1000;
    const y = Math.round(((ev.clientY - rect.top) / rect.height) * 1000) / 1000;
    if (this.ctx.draggedPointIndex !== null) {
      this.ctx.draftPoints[this.ctx.draggedPointIndex] = [x, y];
      this.redraw();
      return;
    }
    const hoverRadius = 0.04;
    const nearIdx = this.ctx.draftPoints.findIndex((p) => Math.hypot(p[0] - x, p[1] - y) < hoverRadius);
    if (nearIdx !== this.ctx.hoverPointIndex) {
      this.ctx.hoverPointIndex = nearIdx !== -1 ? nearIdx : null;
      canvas.style.cursor = nearIdx !== -1 ? 'grab' : 'crosshair';
      this.redraw();
    }
    if (this.ctx.rectStart && this.ctx.draftPoints.length === 1) {
      this.ctx.rectCurrent = [x, y];
      this.redraw();
    }
  }

  onCanvasMouseUp(): void {
    if (this.ctx.draggedPointIndex !== null) {
      this.ctx.draggedPointIndex = null;
      this.redraw();
    }
  }

  redraw(): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (this.ctx.snapshotImg) ctx.drawImage(this.ctx.snapshotImg, 0, 0, w, h);
    for (const z of this.ctx.zones) {
      let pts: [number, number][] = [];
      try {
        pts = JSON.parse(z.polygonJson);
      } catch {
        pts = [];
      }
      this.drawPoly(ctx, pts, w, h, z.zoneType === 'HighValue' ? 'rgba(255,120,120,0.35)' : 'rgba(120,160,255,0.3)');
    }
    if (this.ctx.draftPoints.length > 1) {
      this.drawPoly(ctx, this.ctx.draftPoints, w, h, 'rgba(255,220,120,0.5)', true);
    } else if (this.ctx.draftPoints.length === 1 && this.ctx.rectStart && this.ctx.rectCurrent) {
      const x1 = Math.min(this.ctx.rectStart[0], this.ctx.rectCurrent[0]);
      const y1 = Math.min(this.ctx.rectStart[1], this.ctx.rectCurrent[1]);
      const x2 = Math.max(this.ctx.rectStart[0], this.ctx.rectCurrent[0]);
      const y2 = Math.max(this.ctx.rectStart[1], this.ctx.rectCurrent[1]);
      this.drawPoly(ctx, [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], w, h, 'rgba(255,220,120,0.4)', true);
    }
  }

  private drawPoly(
    ctx: CanvasRenderingContext2D,
    pts: [number, number][],
    w: number,
    h: number,
    fill: string,
    interactive = false,
  ): void {
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
        const isHover = i === this.ctx.hoverPointIndex || i === this.ctx.draggedPointIndex;
        ctx.beginPath();
        ctx.arc(px, py, isHover ? 8 : 5, 0, Math.PI * 2);
        ctx.fillStyle = isHover ? '#ffffff' : '#ffd678';
        ctx.fill();
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }
  }
}
