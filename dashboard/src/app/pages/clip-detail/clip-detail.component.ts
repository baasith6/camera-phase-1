import { Component, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { ClipDetail } from '../../core/models';

@Component({
  selector: 'app-clip-detail',
  standalone: true,
  imports: [DatePipe, DecimalPipe, RouterLink],
  template: `
    @if (clip) {
      <div class="header-row">
        <div class="title-wrap">
          <button class="ghost back" routerLink="/app/clips">← Clips</button>
          <h2>{{ clip.cameraName }}</h2>
        </div>
        <span class="badge" [class]="statusClass(clip.status)">{{ clip.status }}</span>
        @if (auth.isManagerOrAdmin()) {
          <button class="ghost danger" (click)="deleteClip()" [disabled]="deleting">Delete</button>
        }
      </div>

      <div class="detail-layout">
        <div class="col-main">
          <div class="card">
            <h3>Video</h3>
            @if (clip.clipUrl) {
              <video class="clip" [src]="clip.clipUrl" controls width="100%"></video>
            } @else {
              <div class="no-clip">
                <div class="no-clip-icon">🎞</div>
                <p class="muted">Clip not available yet — it may still be uploading or processing.</p>
              </div>
            }
          </div>

          <div class="card">
            <h3>AI events ({{ clip.eventCount }})</h3>
            @if (clip.aiEvents.length === 0) {
              <p class="muted">No AI events recorded for this clip.</p>
            } @else {
              <table class="table compact">
                <thead>
                  <tr>
                    <th>Type</th>
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

        <div class="col-side">
          <div class="card">
            <h3>Analysis</h3>
            <div class="detail-list">
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
                <span class="score" [class.warn]="(clip.riskScore ?? 0) >= 40">
                  {{ clip.riskScore ?? '—' }}
                </span>
              </div>
            </div>
          </div>

          @if (clip.analysisNote) {
            <div class="card note-card">
              <p class="muted small">{{ clip.analysisNote }}</p>
            </div>
          }

          @if (clip.alertId) {
            <div class="card">
              <p>An alert was created from this clip.</p>
              <a class="btn-link" [routerLink]="['/app/alerts', clip.alertId]">View alert →</a>
            </div>
          } @else if (clip.status === 'Analyzed' && (clip.riskScore ?? 0) < 40) {
            <div class="card note-card">
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
      <p class="error">⚠ {{ error }}</p>
    } @else {
      <p class="muted">Loading...</p>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .title-wrap { display:flex; align-items:center; gap:.75rem; }
    .title-wrap h2 { margin:0; }
    .back { font-size:.82rem; padding:.35rem .75rem; white-space:nowrap; background:transparent; border:1px solid var(--border-strong); color:var(--text-muted); border-radius:var(--radius-sm); cursor:pointer; text-decoration:none; }
    .detail-layout { display:grid; grid-template-columns:1.4fr 1fr; gap:1rem; align-items:start; }
    @media (max-width: 980px) { .detail-layout { grid-template-columns:1fr; } }
    .col-main, .col-side { display:flex; flex-direction:column; gap:1rem; min-width:0; }
    .clip { border-radius:var(--radius-sm); border:1px solid var(--border-strong); box-shadow:0 0 20px rgba(139,92,246,.1); }
    .no-clip { text-align:center; padding:1.5rem 1rem; }
    .no-clip-icon { font-size:1.5rem; margin-bottom:.5rem; }
    .detail-list { display:flex; flex-direction:column; }
    .detail-item {
      display:flex; align-items:center; justify-content:space-between; gap:1rem;
      padding:.5rem 0; border-bottom:1px solid var(--border); font-size:.88rem;
    }
    .detail-item:last-child { border-bottom:none; }
    .dk { color:var(--text-muted); font-size:.8rem; }
    .mono { font-family:ui-monospace, monospace; font-size:.8rem; }
    .badge { padding:.2rem .6rem; border-radius:999px; font-weight:600; font-size:.78rem; }
    .badge.uploaded { background:var(--warning-soft); color:var(--warning); border:1px solid rgba(251,191,36,.3); }
    .badge.analyzed { background:var(--success-soft); color:var(--success); border:1px solid rgba(52,211,153,.3); }
    .badge.pending, .badge.processing { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .score { font-weight:600; }
    .score.warn { color:var(--warning); }
    .note-card { border-color:rgba(251,191,36,.25); }
    .btn-link {
      display:inline-block; margin-top:.5rem; font-size:.85rem; color:var(--accent-2); text-decoration:none;
      border:1px solid var(--border-strong); padding:.35rem .65rem; border-radius:var(--radius-sm);
    }
    .table.compact th, .table.compact td { font-size:.82rem; padding:.35rem .5rem; }
    .muted { color:var(--text-muted); }
    .small { font-size:.82rem; }
    .error { color:var(--danger); }
    button.danger { color:var(--danger); border-color:rgba(248,113,113,.35); }
  `],
})
export class ClipDetailComponent implements OnInit {
  clip?: ClipDetail;
  error = '';
  deleting = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getClip(id).subscribe({
      next: (c) => { this.clip = c; },
      error: (e) => { this.error = e?.error?.error || 'Failed to load clip'; },
    });
  }

  statusClass(status: string): string {
    return status.toLowerCase();
  }

  deleteClip(): void {
    if (!this.clip) return;
    if (!confirm('Delete this clip from cloud storage and remove all analysis?')) return;
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
