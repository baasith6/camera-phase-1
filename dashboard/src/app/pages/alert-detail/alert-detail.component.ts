import { Component, HostListener, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { Alert } from '../../core/models';
import { alertTypeLabel } from '../../shared/alert-labels';
import { PageContainerComponent } from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';
import { StatusPillComponent } from '../../shared/status-pill.component';

@Component({
  selector: 'app-alert-detail',
  standalone: true,
  imports: [FormsModule, DatePipe, RouterLink, PageContainerComponent, StatusBadgeComponent, StatusPillComponent],
  template: `
    <app-page-container>
      @if (alert) {
        <div class="header-row">
          <div class="title-wrap">
            <button class="ghost back" type="button" routerLink="/app/alerts" [queryParams]="backQuery">Back to Alerts</button>
            <h2>{{ labelType(alert.alertType) }}</h2>
          </div>
          <div class="queue-nav">
            <button class="ghost" type="button" (click)="goPrev()" [disabled]="!prevId">Previous</button>
            <button class="ghost" type="button" (click)="goNext()" [disabled]="!nextId">Next</button>
            <app-status-badge [level]="alert.riskLevel" [label]="alert.riskLevel + ' · ' + alert.riskScore" />
          </div>
        </div>

        <div class="disclaimer" role="note">AI evidence only — staff decides. Never auto-confirms theft.</div>

        <div class="detail-layout">
          <div class="col-main">
            <div class="card">
              <h3>Clip</h3>
              @if (alert.clipUrl) {
                <video class="clip" [src]="alert.clipUrl" controls width="100%"></video>
              } @else {
                <p class="muted">Clip not available — it may have been removed by storage retention.</p>
              }
            </div>

            <div class="card">
              <h3>Evidence timeline</h3>
              <div class="evidence-timeline">
                @for (e of evidence(); track e) {
                  <div class="evidence-timeline-item">
                    <span class="ev-marker" aria-hidden="true"></span>
                    <span>{{ e }}</span>
                  </div>
                } @empty {
                  <p class="muted">No evidence entries.</p>
                }
              </div>
            </div>
          </div>

          <div class="col-side review-sticky">
            <div class="card">
              <h3>Details</h3>
              <div class="detail-list">
                <div class="detail-item"><span class="dk">Status</span><app-status-pill [status]="alert.status" /></div>
                <div class="detail-item"><span class="dk">Created</span><span>{{ alert.createdAt | date:'medium' }}</span></div>
                <div class="detail-item"><span class="dk">Model</span><span class="mono">{{ alert.modelVersion }}</span></div>
                <div class="detail-item"><span class="dk">Rules</span><span class="mono">{{ alert.ruleVersion }}</span></div>
              </div>
            </div>

            <div class="card review-card">
              <h3>Review</h3>
              <label for="decision">Decision</label>
              <select id="decision" [(ngModel)]="action">
                <option value="Confirm">Confirm</option>
                <option value="Dismiss">Dismiss</option>
                <option value="FalsePositive">False positive</option>
                <option value="NeedsFollowUp">Needs follow-up</option>
              </select>
              <label for="reason">Reason code <span class="muted small">(required for dismiss / false positive)</span></label>
              <input id="reason" placeholder="e.g. staff-restock" [(ngModel)]="reasonCode" />
              <label for="notes">Notes</label>
              <textarea id="notes" placeholder="Add context for the audit trail…" [(ngModel)]="notes" rows="3"></textarea>
              <p class="muted small">Shortcuts: C confirm · D dismiss · F false positive</p>
              <button type="button" (click)="submit()" [disabled]="saving">{{ saving ? 'Submitting…' : 'Submit review' }}</button>
              @if (error) { <p class="error" role="alert">{{ error }}</p> }
              @if (saved) { <p class="ok" role="status">Review saved.</p> }
            </div>
          </div>
        </div>
      } @else {
        <p class="muted">Loading…</p>
      }
    </app-page-container>
  `,
  styles: [`
    .title-wrap { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .title-wrap h2 { margin: 0; }
    .back { font-size: 0.82rem; padding: 8px 12px; min-height: 44px; }
    .detail-layout { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; align-items: start; }
    @media (max-width: 980px) { .detail-layout { grid-template-columns: 1fr; } .review-sticky { position: static; } }
    .col-main, .col-side { display: flex; flex-direction: column; min-width: 0; gap: 0; }
    .review-card { display: flex; flex-direction: column; gap: 8px; }
    .review-card button { margin-top: 8px; align-self: flex-start; min-height: 44px; }
    textarea { width: 100%; }
    .clip { border-radius: var(--radius-sm); border: 1px solid var(--border-strong); }
    .detail-list { display: flex; flex-direction: column; }
    .detail-item {
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 0.88rem;
    }
    .detail-item:last-child { border-bottom: none; }
    .dk { color: var(--text-muted); font-size: 0.8rem; }
    .error { color: var(--danger); } .ok { color: var(--success); }
  `],
})
export class AlertDetailComponent implements OnInit {
  alert?: Alert;
  queue: Alert[] = [];
  prevId = '';
  nextId = '';
  action = 'Confirm';
  reasonCode = '';
  notes = '';
  saving = false;
  saved = false;
  error = '';
  backQuery: Record<string, string | null> = {};

  constructor(private route: ActivatedRoute, private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    const storeId = this.route.snapshot.queryParamMap.get('storeId') ?? undefined;
    const status = this.route.snapshot.queryParamMap.get('status') ?? undefined;
    this.backQuery = { storeId: storeId ?? null, status: status ?? null };

    this.api.listAlerts(storeId, status).subscribe((list) => {
      this.queue = list;
      const idx = list.findIndex((a) => a.id === id);
      this.prevId = idx > 0 ? list[idx - 1].id : '';
      this.nextId = idx >= 0 && idx < list.length - 1 ? list[idx + 1].id : '';
    });

    this.api.getAlert(id).subscribe((a) => (this.alert = a));
  }

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    if (!this.alert || this.saving) return;
    const tag = (ev.target as HTMLElement)?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (ev.key === 'c' || ev.key === 'C') { this.action = 'Confirm'; this.submit(); }
    if (ev.key === 'd' || ev.key === 'D') { this.action = 'Dismiss'; }
    if (ev.key === 'f' || ev.key === 'F') { this.action = 'FalsePositive'; }
  }

  labelType(type: string): string {
    return alertTypeLabel(type);
  }

  evidence(): string[] {
    try {
      return JSON.parse(this.alert?.evidenceJson || '[]');
    } catch {
      return [];
    }
  }

  goPrev(): void {
    if (this.prevId) this.router.navigate(['/app/alerts', this.prevId], { queryParams: this.backQuery });
  }

  goNext(): void {
    if (this.nextId) this.router.navigate(['/app/alerts', this.nextId], { queryParams: this.backQuery });
  }

  submit(): void {
    if (!this.alert) return;
    this.saving = true;
    this.error = '';
    this.saved = false;
    this.api.reviewAlert(this.alert.id, this.action, this.reasonCode || undefined, this.notes || undefined).subscribe({
      next: (a) => {
        this.alert = a;
        this.saving = false;
        this.saved = true;
        if (this.nextId) setTimeout(() => this.goNext(), 600);
      },
      error: (e) => {
        this.saving = false;
        this.error = e?.error?.error || 'Review failed';
      },
    });
  }
}
