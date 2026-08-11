import { AfterViewChecked, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { ClipDetail, TrackOverlay } from '../../core/models';
import { ConfirmDialogService } from '../../shared/confirm-dialog.service';
import { PageContainerComponent, PageHeaderComponent, ErrorBannerComponent, SkeletonListComponent } from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-clip-detail',
  standalone: true,
  imports: [DatePipe, DecimalPipe, RouterLink, PageContainerComponent, PageHeaderComponent, ErrorBannerComponent, SkeletonListComponent, StatusBadgeComponent],
  template: `
    <app-page-container>
      @if (loading) {
        <app-skeleton-list [count]="4" />
      } @else if (clip) {
        <app-page-header [title]="clip.cameraName">
          <div actions class="flex items-center gap-2">
            <app-status-badge [level]="clip.status" [label]="clip.status" />
            @if (auth.isManagerOrAdmin()) {
              <button class="ghost !text-danger !border-danger/35" type="button" (click)="deleteClip()" [disabled]="deleting">Delete</button>
            }
          </div>
          <div below>
            <a class="text-[0.82rem] text-accent no-underline" routerLink="/app/clips">Back to Clips</a>
          </div>
        </app-page-header>

        <div class="grid items-start gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div class="flex min-w-0 flex-col gap-4">
            <div class="card !mb-0">
              <h3>Video</h3>
              @if (clip.clipUrl) {
                <div class="video-shell" #videoShell>
                  <video
                    #clipVideo
                    class="clip-video"
                    [src]="clip.clipUrl"
                    controls
                    (loadedmetadata)="onVideoMeta()"
                    (timeupdate)="onTimeUpdate()"
                    (seeked)="onTimeUpdate()"
                    (play)="onTimeUpdate()"
                  ></video>
                  <canvas #trackCanvas class="track-overlay" aria-hidden="true"></canvas>
                </div>
              } @else {
                <div class="px-4 py-6 text-center">
                  <p class="muted">Clip not available yet — it may still be uploading or processing.</p>
                </div>
              }
            </div>

            <div class="card !mb-0">
              <h3>AI events ({{ clip.eventCount }})</h3>
              @if (clip.aiEvents.length === 0) {
                <p class="muted">No AI events recorded for this clip.</p>
              } @else {
                <table class="table compact">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Track</th>
                      <th>Zone</th>
                      <th>Confidence</th>
                      <th>Value</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (e of clip.aiEvents; track $index) {
                      <tr>
                        <td>{{ e.eventType }}</td>
                        <td>{{ e.trackId > 0 ? ('ID ' + e.trackId) : '—' }}</td>
                        <td>{{ e.zoneName || '—' }}</td>
                        <td>{{ e.confidence | number:'1.0-2' }}</td>
                        <td>{{ e.value | number:'1.0-1' }}</td>
                        <td>{{ e.startTs | date:'h:mm:ss a' }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              }
            </div>
          </div>

          <div class="flex min-w-0 flex-col gap-4">
            <div class="card !mb-0">
              <h3>Analysis</h3>
              <div class="flex flex-col">
                <div class="detail-item"><span class="dk">Store</span><span>{{ clip.storeName }}</span></div>
                <div class="detail-item"><span class="dk">Trigger</span><span>{{ clip.triggerReason }}</span></div>
                <div class="detail-item"><span class="dk">Duration</span><span>{{ clip.durationSec | number:'1.0-1' }}s</span></div>
                <div class="detail-item"><span class="dk">Uploaded</span><span>{{ clip.createdAt | date:'medium' }}</span></div>
                @if (clip.analyzedAt) {
                  <div class="detail-item"><span class="dk">Analyzed</span><span>{{ clip.analyzedAt | date:'medium' }}</span></div>
                }
                @if (clip.modelVersion) {
                  <div class="detail-item"><span class="dk">Model</span><span class="mono">{{ clip.modelVersion }}</span></div>
                }
                <div class="detail-item">
                  <span class="dk">Risk score</span>
                  <span class="font-semibold" [class.text-warning]="(clip.riskScore ?? 0) >= 40">
                    {{ clip.riskScore ?? '—' }}
                  </span>
                </div>
              </div>
            </div>

            @if (clip.analysisNote) {
              <div class="card !mb-0 !border-warning-soft">
                <p class="muted small">{{ clip.analysisNote }}</p>
              </div>
            }

            @if (clip.alertId) {
              <div class="card !mb-0">
                <p>An alert was created from this clip.</p>
                <a
                  class="mt-2 inline-block rounded-[6px] border border-border-strong px-2.5 py-1.5 text-[0.85rem] text-accent no-underline"
                  [routerLink]="['/app/alerts', clip.alertId]">View alert</a>
              </div>
            } @else if (clip.status === 'Analyzed' && (clip.riskScore ?? 0) < 40) {
              <div class="card !mb-0 !border-warning-soft">
                <h3>No alert yet</h3>
                <p class="muted small">
                  Alerts are created when the risk score reaches 40 or higher.
                  This clip scored {{ clip.riskScore ?? 0 }} — review the video and AI events above.
                </p>
              </div>
            }
          </div>
        </div>
      } @else if (error) {
        <app-error-banner [message]="error" />
      }
    </app-page-container>
  `,
  styles: [`
    .detail-item {
      display: flex; align-items: center; justify-content: space-between; gap: 1rem;
      padding: 0.5rem 0; border-bottom: 1px solid var(--border); font-size: 0.88rem;
    }
    .detail-item:last-child { border-bottom: none; }
    .dk { color: var(--text-muted); font-size: 0.8rem; }
    .table.compact th, .table.compact td { font-size: 0.82rem; padding: 0.35rem 0.5rem; }
    .video-shell {
      position: relative;
      width: 100%;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid var(--border-strong, var(--border));
      background: #0b0b0b;
    }
    .clip-video {
      display: block;
      width: 100%;
      vertical-align: top;
    }
    .track-overlay {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }
  `],
})
export class ClipDetailComponent implements OnInit, AfterViewChecked, OnDestroy {
  @ViewChild('clipVideo') videoRef?: ElementRef<HTMLVideoElement>;
  @ViewChild('trackCanvas') canvasRef?: ElementRef<HTMLCanvasElement>;
  @ViewChild('videoShell') shellRef?: ElementRef<HTMLDivElement>;

  clip?: ClipDetail;
  error = '';
  deleting = false;
  loading = true;
  trackOverlay: TrackOverlay | null = null;

  private resizeObserver?: ResizeObserver;
  private viewBound = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService,
    public auth: AuthService,
    private confirm: ConfirmDialogService,
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getClip(id).subscribe({
      next: (c) => {
        this.clip = c;
        this.trackOverlay = this.parseOverlay(c.trackOverlayJson);
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load clip';
      },
    });
  }

  ngAfterViewChecked(): void {
    if (this.viewBound || !this.shellRef?.nativeElement) return;
    this.viewBound = true;
    this.resizeObserver = new ResizeObserver(() => this.drawOverlay());
    this.resizeObserver.observe(this.shellRef.nativeElement);
    this.drawOverlay();
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
  }

  onVideoMeta(): void {
    this.drawOverlay();
  }

  onTimeUpdate(): void {
    this.drawOverlay();
  }

  private parseOverlay(raw?: string | null): TrackOverlay | null {
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as TrackOverlay;
      if (!parsed?.frames || !Array.isArray(parsed.frames)) return null;
      return {
        fps: Number(parsed.fps) || 10,
        stride: Math.max(1, Number(parsed.stride) || 1),
        frames: parsed.frames,
      };
    } catch {
      return null;
    }
  }

  private drawOverlay(): void {
    const video = this.videoRef?.nativeElement;
    const canvas = this.canvasRef?.nativeElement;
    if (!video || !canvas) return;

    const w = video.clientWidth;
    const h = video.clientHeight;
    if (w <= 0 || h <= 0) return;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);

    const overlay = this.trackOverlay;
    if (!overlay || overlay.frames.length === 0) return;

    const fps = overlay.fps || 10;
    const stride = overlay.stride || 1;
    const sourceFrame = Math.max(0, Math.floor(video.currentTime * fps));
    const overlayIdx = Math.min(
      overlay.frames.length - 1,
      Math.floor(sourceFrame / stride),
    );
    const boxes = overlay.frames[overlayIdx] || [];

    ctx.lineWidth = 2;
    ctx.font = '600 12px ui-sans-serif, system-ui, sans-serif';
    for (const box of boxes) {
      const x = box.x1 * w;
      const y = box.y1 * h;
      const bw = Math.max(1, (box.x2 - box.x1) * w);
      const bh = Math.max(1, (box.y2 - box.y1) * h);
      const color = trackColor(box.trackId);
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.strokeRect(x, y, bw, bh);
      const label = `ID ${box.trackId}`;
      const tw = ctx.measureText(label).width + 8;
      const th = 16;
      const ly = Math.max(0, y - th);
      ctx.globalAlpha = 0.85;
      ctx.fillRect(x, ly, tw, th);
      ctx.globalAlpha = 1;
      ctx.fillStyle = '#fff';
      ctx.fillText(label, x + 4, ly + 12);
    }
  }

  async deleteClip(): Promise<void> {
    if (!this.clip) return;
    const ok = await this.confirm.open({
      title: 'Delete clip',
      message: 'Delete this clip from cloud storage and remove all analysis?',
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;
    this.deleting = true;
    this.api.deleteClip(this.clip.id).subscribe({
      next: () => this.router.navigate(['/app/clips']),
      error: (e) => {
        this.deleting = false;
        this.error = e?.error?.error || 'Delete failed';
      },
    });
  }
}

function trackColor(trackId: number): string {
  const hue = ((Math.max(0, trackId) * 47) % 360);
  return `hsl(${hue} 78% 52%)`;
}
