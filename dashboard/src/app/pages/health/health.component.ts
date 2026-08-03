import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Connector, PipelineHealth } from '../../core/models';
import { PageContainerComponent, PageHeaderComponent, ErrorBannerComponent, StatCardComponent } from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-health',
  standalone: true,
  imports: [DatePipe, DecimalPipe, PageContainerComponent, PageHeaderComponent, ErrorBannerComponent, StatCardComponent, StatusBadgeComponent],
  template: `
    <app-page-container>
      <app-page-header title="Connector Health">
        <div actions>
          @if (loading) { <span class="muted small">Refreshing…</span> }
          <button class="ghost" type="button" (click)="load()">Refresh</button>
        </div>
      </app-page-header>

      @if (error) {
        <app-error-banner [message]="error">
          <button class="ghost small" type="button" (click)="load()">Retry</button>
        </app-error-banner>
      }

      @if (auth.isAdmin() && pipeline) {
        <div class="grid-stats">
          <app-stat-card label="Redis queue depth" [value]="pipeline.redisQueueDepth" [tone]="pipeline.redisQueueDepth > 0 ? 'warn' : 'default'" />
          <app-stat-card label="Failed jobs" [value]="pipeline.failedJobs" [tone]="pipeline.failedJobs > 0 ? 'danger' : 'default'" />
        </div>
        <p class="muted small">cloud-ai consumes <code>onevo:clip-jobs</code>. Zero queue + zero failed = healthy.</p>
      }

      @if (!error && connectors.length === 0 && !loading) {
        <div class="card"><p class="muted">No connectors registered yet.</p></div>
      } @else if (connectors.length > 0) {
        <div class="data-table-wrap health-desktop">
          <table class="table">
            <thead>
              <tr>
                <th>Connector</th>
                <th>Status</th>
                <th>Disk free</th>
                <th>Queue</th>
                <th>RTSP reconnects</th>
                <th>Last heartbeat</th>
                <th>Degraded reason</th>
              </tr>
            </thead>
            <tbody>
              @for (c of connectors; track c.id) {
                <tr>
                  <td>{{ c.name }} <span class="muted small">v{{ c.version }}</span></td>
                  <td><app-status-badge [level]="c.status" [label]="c.status" /></td>
                  <td [class.warn]="c.diskFreePct < 20" [class.crit]="c.diskFreePct < 10">{{ c.diskFreePct | number:'1.0-1' }}%</td>
                  <td [class.warn]="c.uploadQueueDepth > 50">{{ c.uploadQueueDepth }}</td>
                  <td [class.warn]="(c.rtspReconnects || 0) > 0">{{ c.rtspReconnects ?? 0 }}</td>
                  <td>{{ c.lastHeartbeat ? (c.lastHeartbeat | date:'short') : '—' }}</td>
                  <td>{{ c.degradedReason || '—' }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>

        <div class="health-cards">
          @for (c of connectors; track c.id) {
            <div class="card health-card">
              <div class="health-card-head">
                <strong>{{ c.name }}</strong>
                <app-status-badge [level]="c.status" [label]="c.status" />
              </div>
              <p class="muted small">v{{ c.version }} · Disk {{ c.diskFreePct | number:'1.0-1' }}% · Queue {{ c.uploadQueueDepth }}</p>
              <p class="muted small">Heartbeat: {{ c.lastHeartbeat ? (c.lastHeartbeat | date:'short') : '—' }}</p>
              @if (c.degradedReason) { <p class="warn small">{{ c.degradedReason }}</p> }
            </div>
          }
        </div>
      }
    </app-page-container>
  `,
  styles: [`
    .warn { color: var(--warning); } .crit { color: var(--danger); }
    .health-cards { display: none; flex-direction: column; gap: 10px; }
    @media (max-width: 768px) {
      .health-desktop { display: none; }
      .health-cards { display: flex; }
    }
    .health-card-head { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  `],
})
export class HealthComponent implements OnInit, OnDestroy {
  connectors: Connector[] = [];
  pipeline: PipelineHealth | null = null;
  loading = false;
  error = '';
  private timer?: ReturnType<typeof setInterval>;

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit(): void { this.load(); this.timer = setInterval(() => this.load(), 8000); }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  load(): void {
    this.loading = true;
    this.api.listConnectors().subscribe({
      next: (c) => { this.connectors = c; this.loading = false; this.error = ''; },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load connectors'; },
    });
    if (this.auth.isAdmin()) {
      this.api.getPipelineHealth().subscribe({
        next: (p) => { this.pipeline = p; },
        error: () => { this.pipeline = null; },
      });
    }
  }
}
