import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { API_BASE } from '../../core/api.config';
import { Alert, Store } from '../../core/models';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe],
  template: `
    <div class="header-row">
      <div style="display:flex;align-items:center;gap:.75rem">
        <h2>Alerts</h2>
        <span class="live-badge" [class.connected]="sseConnected">
          <span class="dot"></span>{{ sseConnected ? 'Live' : 'Offline' }}
        </span>
      </div>
      <div class="filters">
        <select [(ngModel)]="storeId" (change)="load()">
          <option value="">All stores</option>
          @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
        </select>
        <select [(ngModel)]="status" (change)="load()">
          <option value="">All statuses</option>
          <option value="PendingReview">Pending review</option>
          <option value="Confirmed">Confirmed</option>
          <option value="Dismissed">Dismissed</option>
          <option value="FalsePositive">False positive</option>
          <option value="NeedsFollowUp">Needs follow-up</option>
        </select>
        <button class="ghost" (click)="load()">Refresh</button>
      </div>
    </div>

    @if (error) {
      <div class="err-banner">⚠ {{ error }} <button class="ghost small" (click)="load()">Retry</button></div>
    }

    @if (loading) {
      <div class="card">
        @for (i of [1,2,3,4,5]; track i) { <div class="skeleton-row"></div> }
      </div>
    } @else if (alerts.length === 0) {
      <div class="card empty-state">
        <div class="empty-icon">✓</div>
        <p>No alerts — all clear</p>
        <p class="muted small">(Store may be in silent/manager-only pilot mode.)</p>
      </div>
    } @else {
      @if (newCount > 0) {
        <div class="new-banner" (click)="dismissNewBanner()">
          🔔 {{ newCount }} new alert{{ newCount > 1 ? 's' : '' }} received — click to dismiss
        </div>
      }
      <div class="alert-list">
        <div class="list-header">
          <div></div>
          <div class="col-type-h">Alert</div>
          <div class="col-h">Risk</div>
          <div class="col-h">Score</div>
          <div class="col-h">Status</div>
          <div class="col-h"></div>
        </div>
        @for (a of pagedAlerts(); track a.id) {
          <div class="alert-card" [class.new-row]="newIds.has(a.id)">
            <div class="risk-strip" [class]="a.riskLevel.toLowerCase()"></div>
            <div class="col-type">
              <span class="alert-type">{{ a.alertType }}</span>
              <span class="alert-sub muted">{{ a.createdAt | date:'MMM d, h:mm a' }}</span>
            </div>
            <div class="col-risk"><span class="badge" [class]="a.riskLevel.toLowerCase()">{{ a.riskLevel }}</span></div>
            <div class="col-score"><span class="score-num">{{ a.riskScore }}</span></div>
            <div class="col-status"><span class="pill" [class]="pillClass(a.status)">{{ pillLabel(a.status) }}</span></div>
            <div class="col-action"><button class="ghost review-btn" [routerLink]="['/alerts', a.id]">Review</button></div>
          </div>
        }
      </div>

      @if (totalPages() > 1) {
        <div class="pagination">
          <button class="ghost pg-btn" (click)="prevPage()" [disabled]="page === 1">‹ Prev</button>
          <div class="pg-pages">
            @for (p of pageNumbers(); track p) {
              <button class="ghost pg-num" [class.current]="p === page" (click)="goToPage(p)">{{ p }}</button>
            }
          </div>
          <span class="pg-info muted">{{ rangeStart() }}–{{ rangeEnd() }} of {{ alerts.length }}</span>
          <button class="ghost pg-btn" (click)="nextPage()" [disabled]="page === totalPages()">Next ›</button>
        </div>
      }
    }

    @if (toast) {
      <div class="toast" (click)="toast = ''">🔔 {{ toast }}</div>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .filters { display:flex; gap:.5rem; }
    .badge { padding:.18rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600; }
    .badge.high { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3); }
    .badge.medium { background:var(--warning-soft); color:var(--warning); border:1px solid rgba(251,191,36,.3); }
    .badge.low { background:var(--info-soft); color:var(--info); border:1px solid rgba(167,139,250,.3); }
    .badge.none { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .live-badge { display:inline-flex; align-items:center; gap:.3rem; font-size:.75rem; font-weight:600;
                  padding:.2rem .6rem; border-radius:999px; background:var(--surface-2); color:var(--text-muted);
                  border:1px solid var(--border-strong); }
    .live-badge.connected { background:var(--success-soft); color:var(--success); border-color:rgba(52,211,153,.3); }
    .dot { width:7px; height:7px; border-radius:50%; background:currentColor; }
    .live-badge.connected .dot { animation: pulse 1.8s infinite; box-shadow:0 0 6px currentColor; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
    .err-banner { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3);
                  padding:.5rem .75rem; border-radius:var(--radius-sm);
                  margin-bottom:.75rem; display:flex; justify-content:space-between; align-items:center; }
    .new-banner { background:var(--accent-soft); color:var(--accent-2); border:1px solid rgba(139,92,246,.35);
                  padding:.5rem .75rem; border-radius:var(--radius-sm);
                  margin-bottom:.5rem; cursor:pointer; font-size:.85rem; font-weight:500; }
    .new-banner:hover { background:rgba(139,92,246,.22); box-shadow:0 0 14px var(--accent-glow); }
    .new-row { animation: fadeIn .8s ease; }
    @keyframes fadeIn { from{background:var(--accent-soft)} to{background:transparent} }
    .small { font-size:.75rem; }

    .skeleton-row {
      height:38px; border-radius:var(--radius-sm); margin-bottom:.5rem;
      background:linear-gradient(90deg, var(--surface-2) 25%, var(--border) 50%, var(--surface-2) 75%);
      background-size:200% 100%; animation:shimmer 1.4s infinite;
    }
    .skeleton-row:last-child { margin-bottom:0; }
    @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

    .empty-state { text-align:center; padding:2.5rem 1rem; }
    .empty-icon {
      width:52px; height:52px; margin:0 auto .75rem; border-radius:50%;
      display:flex; align-items:center; justify-content:center; font-size:1.5rem;
      background:var(--success-soft); color:var(--success); border:1px solid rgba(52,211,153,.3);
    }

    .alert-list { display:flex; flex-direction:column; gap:.6rem; }
    .list-header {
      display:grid; grid-template-columns:4px 1fr 110px 70px 150px 100px;
      gap:1rem; padding:0 1rem 0 0;
      font-size:.72rem; font-weight:600; text-transform:uppercase; letter-spacing:.07em;
      color:var(--text-muted);
    }
    .col-type-h { padding-left:.2rem; }
    .col-h { text-align:center; }
    .alert-card {
      display:grid; grid-template-columns:4px 1fr 110px 70px 150px 100px;
      align-items:center; gap:1rem;
      background:linear-gradient(180deg, var(--surface-2), var(--surface));
      border:1px solid var(--border); border-radius:var(--radius);
      padding:.8rem 1rem .8rem 0; overflow:hidden;
      transition:border-color .15s ease, box-shadow .15s ease;
    }
    .alert-card:hover { border-color:var(--accent); box-shadow:0 0 16px rgba(139,92,246,.12); }
    .risk-strip { align-self:stretch; width:4px; border-radius:0 4px 4px 0; }
    .risk-strip.high { background:var(--danger); box-shadow:0 0 8px rgba(248,113,113,.5); }
    .risk-strip.medium { background:var(--warning); }
    .risk-strip.low { background:var(--info); }
    .risk-strip.none { background:var(--border-strong); }
    .col-type { display:flex; flex-direction:column; gap:.2rem; min-width:0; }
    .alert-type { font-weight:600; font-size:.95rem; }
    .alert-sub { font-size:.78rem; }
    .col-risk, .col-score, .col-status, .col-action { display:flex; justify-content:center; }
    .score-num { font-variant-numeric:tabular-nums; font-weight:700; font-size:1.05rem; }
    .review-btn { font-size:.82rem; padding:.35rem .8rem; white-space:nowrap; }

    .pagination { display:flex; align-items:center; gap:.75rem; margin-top:1rem; justify-content:center; }
    .pg-btn { font-size:.8rem; padding:.35rem .8rem; }
    .pg-pages { display:flex; gap:.3rem; }
    .pg-num { font-size:.8rem; padding:.35rem .65rem; min-width:34px; }
    .pg-num.current { background:var(--accent-soft); border-color:var(--accent); color:var(--accent-2); font-weight:700; }
    .pg-info { font-size:.78rem; }

    .pill { padding:.16rem .55rem; border-radius:999px; font-size:.72rem; font-weight:600; white-space:nowrap; }
    .pill.pending { background:var(--warning-soft); color:var(--warning); border:1px solid rgba(251,191,36,.3); }
    .pill.confirmed { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3); }
    .pill.dismissed { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .pill.falsepos { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .pill.followup { background:var(--accent-soft); color:var(--accent-2); border:1px solid rgba(139,92,246,.35); }

    .toast {
      position:fixed; bottom:1.5rem; right:1.5rem; z-index:100;
      background:linear-gradient(180deg, var(--surface-2), var(--surface));
      border:1px solid var(--accent); border-radius:var(--radius);
      padding:.75rem 1.1rem; font-size:.88rem; cursor:pointer;
      box-shadow:0 0 24px var(--accent-glow), 0 8px 24px rgba(0,0,0,.4);
      animation:slideIn .3s ease;
    }
    @keyframes slideIn { from{transform:translateX(120%); opacity:0} to{transform:translateX(0); opacity:1} }
  `],
})
export class AlertsComponent implements OnInit, OnDestroy {
  stores: Store[] = [];
  alerts: Alert[] = [];
  storeId = '';
  status = '';
  loading = false;
  error = '';
  sseConnected = false;
  newIds = new Set<string>();
  newCount = 0;
  toast = '';
  page = 1;
  readonly pageSize = 7;
  private toastTimer?: any;
  private es?: EventSource;

  constructor(private api: ApiService, private auth: AuthService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe({ next: s => this.stores = s });
    this.load();
    this.connectSse();
  }

  ngOnDestroy(): void { this.es?.close(); clearTimeout(this.toastTimer); }

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

  private showToast(msg: string): void {
    this.toast = msg;
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => (this.toast = ''), 5000);
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.listAlerts(this.storeId || undefined, this.status || undefined).subscribe({
      next: (a) => { this.alerts = a; this.loading = false; this.page = 1; },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load alerts'; },
    });
  }

  // ---- pagination ----
  pagedAlerts(): Alert[] {
    const start = (this.page - 1) * this.pageSize;
    return this.alerts.slice(start, start + this.pageSize);
  }
  totalPages(): number { return Math.max(1, Math.ceil(this.alerts.length / this.pageSize)); }
  rangeStart(): number { return (this.page - 1) * this.pageSize + 1; }
  rangeEnd(): number { return Math.min(this.page * this.pageSize, this.alerts.length); }
  prevPage(): void { if (this.page > 1) this.page--; }
  nextPage(): void { if (this.page < this.totalPages()) this.page++; }
  goToPage(p: number): void { this.page = p; }
  pageNumbers(): number[] {
    const total = this.totalPages();
    // Show at most 5 page buttons centred on the current page.
    const start = Math.max(1, Math.min(this.page - 2, total - 4));
    const end = Math.min(total, start + 4);
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }

  dismissNewBanner(): void { this.newCount = 0; this.newIds.clear(); }

  private connectSse(): void {
    // SSE uses the JWT from localStorage (set by auth service).
    const token = this.auth.token ?? '';
    const url = `${API_BASE}/api/alerts/stream?access_token=${encodeURIComponent(token)}`;
    this.es = new EventSource(url);

    this.es.addEventListener('connected', () => { this.sseConnected = true; });

    this.es.addEventListener('alert', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        // Only prepend if it matches current store filter (or no filter).
        if (this.storeId && data.storeId !== this.storeId) return;
        const newAlert: Alert = {
          id: data.alertId,
          alertType: data.alertType,
          riskLevel: data.riskLevel,
          riskScore: data.riskScore,
          status: 'PendingReview',
          createdAt: data.createdAt,
          storeId: data.storeId,
          evidenceJson: '[]',
          cameraId: '', clipId: '', modelVersion: '', ruleVersion: '',
        };
        this.alerts = [newAlert, ...this.alerts];
        this.newIds.add(newAlert.id);
        this.newCount++;
        this.showToast(`New ${data.riskLevel} risk alert — ${data.alertType}`);
      } catch { /* ignore malformed events */ }
    });

    this.es.onerror = () => { this.sseConnected = false; };
  }
}

