import { Component, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { Alert } from '../../core/models';

@Component({
  selector: 'app-alert-detail',
  standalone: true,
  imports: [FormsModule, DatePipe, RouterLink],
  template: `
    @if (alert) {
      <div class="header-row">
        <div class="title-wrap">
          <button class="ghost back" routerLink="/alerts">← Alerts</button>
          <h2>{{ alert.alertType }}</h2>
        </div>
        <span class="badge" [class]="alert.riskLevel.toLowerCase()">{{ alert.riskLevel }} · {{ alert.riskScore }}</span>
      </div>

      <div class="detail-layout">
        <div class="col-main">
          <div class="card">
            <h3>Clip</h3>
            @if (alert.clipUrl) {
              <video class="clip" [src]="alert.clipUrl" controls width="100%"></video>
            } @else {
              <div class="no-clip">
                <div class="no-clip-icon">🎞</div>
                <p class="muted">Clip not available — it may have been removed by storage retention.</p>
              </div>
            }
          </div>

          <div class="card">
            <h3>Evidence</h3>
            <div class="evidence-list">
              @for (e of evidence(); track e; let i = $index) {
                <div class="evidence-item">
                  <span class="ev-num">{{ i + 1 }}</span>
                  <span>{{ e }}</span>
                </div>
              } @empty {
                <p class="muted">No evidence entries.</p>
              }
            </div>
            <p class="muted small">Evidence describes observable signals only — never a theft conclusion. Staff decide.</p>
          </div>
        </div>

        <div class="col-side">
          <div class="card">
            <h3>Details</h3>
            <div class="detail-list">
              <div class="detail-item"><span class="dk">Status</span><span class="pill" [class]="pillClass(alert.status)">{{ pillLabel(alert.status) }}</span></div>
              <div class="detail-item"><span class="dk">Created</span><span>{{ alert.createdAt | date:'medium' }}</span></div>
              <div class="detail-item"><span class="dk">Model version</span><span class="mono">{{ alert.modelVersion }}</span></div>
              <div class="detail-item"><span class="dk">Rule version</span><span class="mono">{{ alert.ruleVersion }}</span></div>
            </div>
          </div>

          <div class="card review-card">
            <h3>Review</h3>
            <label>Decision</label>
            <select [(ngModel)]="action">
              <option value="Confirm">Confirm</option>
              <option value="Dismiss">Dismiss</option>
              <option value="FalsePositive">False positive</option>
              <option value="NeedsFollowUp">Needs follow-up</option>
            </select>
            <label>Reason code <span class="muted small">(required for dismiss / false positive)</span></label>
            <input placeholder="e.g. staff-restock" [(ngModel)]="reasonCode" />
            <label>Notes <span class="muted small">(optional)</span></label>
            <textarea placeholder="Add context for the audit trail…" [(ngModel)]="notes" rows="3"></textarea>
            <button (click)="submit()" [disabled]="saving">{{ saving ? 'Submitting…' : 'Submit review' }}</button>
            @if (error) { <p class="error">⚠ {{ error }}</p> }
            @if (saved) { <p class="ok">✓ Review saved.</p> }
          </div>
        </div>
      </div>
    } @else { <p class="muted">Loading...</p> }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .title-wrap { display:flex; align-items:center; gap:.75rem; }
    .title-wrap h2 { margin:0; }
    .back { font-size:.82rem; padding:.35rem .75rem; white-space:nowrap; }
    .detail-layout { display:grid; grid-template-columns:1.4fr 1fr; gap:1rem; align-items:start; }
    @media (max-width: 980px) { .detail-layout { grid-template-columns:1fr; } }
    .col-main, .col-side { display:flex; flex-direction:column; min-width:0; }
    .review-card { display:flex; flex-direction:column; gap:.35rem; }
    .review-card label { margin-top:.35rem; }
    .review-card button { margin-top:.6rem; align-self:flex-start; }
    textarea { width:100%; }
    .badge { padding:.2rem .6rem; border-radius:999px; font-weight:600; }
    .badge.high { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3); }
    .badge.medium { background:var(--warning-soft); color:var(--warning); border:1px solid rgba(251,191,36,.3); }
    .badge.low { background:var(--info-soft); color:var(--info); border:1px solid rgba(167,139,250,.3); }
    .badge.none { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .error { color:var(--danger); } .ok { color:var(--success); } .small { font-size:.8rem; }
    .clip { border-radius:var(--radius-sm); border:1px solid var(--border-strong); box-shadow:0 0 20px rgba(139,92,246,.1); }
    .no-clip { text-align:center; padding:1.5rem 1rem; }
    .no-clip-icon {
      width:48px; height:48px; margin:0 auto .6rem; border-radius:50%;
      display:flex; align-items:center; justify-content:center; font-size:1.3rem;
      background:var(--surface-2); border:1px solid var(--border-strong);
    }
    .evidence-list { display:flex; flex-direction:column; gap:.4rem; margin-bottom:.75rem; }
    .evidence-item {
      display:flex; align-items:flex-start; gap:.6rem; font-size:.88rem;
      padding:.5rem .65rem; border-radius:var(--radius-sm);
      background:var(--surface-2); border:1px solid var(--border);
    }
    .ev-num {
      flex-shrink:0; width:20px; height:20px; border-radius:50%;
      display:flex; align-items:center; justify-content:center;
      font-size:.68rem; font-weight:700;
      background:var(--accent-soft); color:var(--accent-2);
    }
    .detail-list { display:flex; flex-direction:column; }
    .detail-item {
      display:flex; align-items:center; justify-content:space-between; gap:1rem;
      padding:.5rem 0; border-bottom:1px solid var(--border); font-size:.88rem;
    }
    .detail-item:last-child { border-bottom:none; }
    .dk { color:var(--text-muted); font-size:.8rem; }
    .mono { font-family:ui-monospace, monospace; font-size:.8rem; }
    .pill { padding:.16rem .55rem; border-radius:999px; font-size:.72rem; font-weight:600; white-space:nowrap; }
    .pill.pending { background:var(--warning-soft); color:var(--warning); border:1px solid rgba(251,191,36,.3); }
    .pill.confirmed { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3); }
    .pill.dismissed, .pill.falsepos { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .pill.followup { background:var(--accent-soft); color:var(--accent-2); border:1px solid rgba(139,92,246,.35); }
  `],
})
export class AlertDetailComponent implements OnInit {
  alert?: Alert;
  action = 'Confirm';
  reasonCode = '';
  notes = '';
  saving = false;
  saved = false;
  error = '';

  constructor(private route: ActivatedRoute, private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getAlert(id).subscribe((a) => (this.alert = a));
  }

  evidence(): string[] {
    try { return JSON.parse(this.alert?.evidenceJson || '[]'); } catch { return []; }
  }

  pillClass(status: string): string {
    switch (status) {
      case 'PendingReview': return 'pending';
      case 'Confirmed': return 'confirmed';
      case 'Dismissed': return 'dismissed';
      case 'FalsePositive': return 'falsepos';
      case 'NeedsFollowUp': return 'followup';
      default: return 'dismissed';
    }
  }

  pillLabel(status: string): string {
    switch (status) {
      case 'PendingReview': return '● Pending';
      case 'Confirmed': return '✓ Confirmed';
      case 'Dismissed': return '✕ Dismissed';
      case 'FalsePositive': return '✕ False positive';
      case 'NeedsFollowUp': return '⚑ Follow-up';
      default: return status;
    }
  }

  submit(): void {
    if (!this.alert) return;
    this.saving = true; this.error = ''; this.saved = false;
    this.api.reviewAlert(this.alert.id, this.action, this.reasonCode || undefined, this.notes || undefined).subscribe({
      next: (a) => { this.alert = a; this.saving = false; this.saved = true; },
      error: (e) => { this.saving = false; this.error = e?.error?.error || 'Review failed'; },
    });
  }
}
