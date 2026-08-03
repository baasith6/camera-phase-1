import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { StoreContextService } from '../../core/store-context.service';
import { ConnectorLogEntry, SystemLogs } from '../../core/models';
import {
  EmptyStateComponent,
  FilterBarComponent,
  PageContainerComponent,
  PageHeaderComponent,
  DataTableComponent,
  ErrorBannerComponent,
  SkeletonListComponent,
} from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [
    FormsModule,
    DatePipe,
    PageHeaderComponent,
    PageContainerComponent,
    FilterBarComponent,
    DataTableComponent,
    StatusBadgeComponent,
    ErrorBannerComponent,
    SkeletonListComponent,
    EmptyStateComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header title="System logs" subtitle="Connector heartbeats and pipeline queue status.">
        <div actions>
          <app-filter-bar>
            <select [(ngModel)]="levelFilter" aria-label="Status filter">
              <option value="">All statuses</option>
              <option value="Healthy">Healthy</option>
              <option value="Degraded">Degraded</option>
              <option value="Offline">Offline</option>
            </select>
          </app-filter-bar>
          <button class="ghost" type="button" (click)="load()">Refresh</button>
        </div>
      </app-page-header>

      @if (error) {
        <app-error-banner [message]="error">
          <button class="ghost small" type="button" (click)="load()">Retry</button>
        </app-error-banner>
      }

      @if (loading) {
        <app-skeleton-list />
      } @else if (logs) {
        <div class="card meta-row">
          <span class="muted small">Generated {{ logs.generatedAt | date:'medium' }}</span>
          <span class="muted small">Queue depth: {{ logs.redisQueueDepth }} · Failed jobs: {{ logs.failedJobs }}</span>
        </div>

        @if (filteredConnectors().length === 0) {
          <app-empty-state title="No connector logs" detail="Try changing the status filter or check that connectors are registered." />
        } @else {
          <app-data-table>
            <table desktop class="table">
              <thead>
                <tr>
                  <th>Connector</th>
                  <th>Status</th>
                  <th>Version</th>
                  <th>Queue</th>
                  <th>Disk free</th>
                  <th>Heartbeat</th>
                  <th>Degraded reason</th>
                </tr>
              </thead>
              <tbody>
                @for (c of filteredConnectors(); track c.id) {
                  <tr>
                    <td>{{ c.name }}</td>
                    <td><app-status-badge [level]="c.status" [label]="c.status" /></td>
                    <td class="mono">{{ c.version }}</td>
                    <td>{{ c.uploadQueueDepth }}</td>
                    <td>{{ c.diskFreePct }}%</td>
                    <td>{{ c.lastHeartbeat ? (c.lastHeartbeat | date:'MMM d, h:mm a') : '—' }}</td>
                    <td class="muted small">{{ c.degradedReason || '—' }}</td>
                  </tr>
                }
              </tbody>
            </table>

            <div mobile class="alert-cards">
              @for (c of filteredConnectors(); track c.id) {
                <div class="alert-card-mobile">
                  <div class="alert-card-mobile-head">
                    <strong>{{ c.name }}</strong>
                    <app-status-badge [level]="c.status" [label]="c.status" />
                  </div>
                  <div class="alert-card-mobile-meta">
                    <span class="muted">v{{ c.version }}</span>
                    <span class="muted">Queue {{ c.uploadQueueDepth }}</span>
                    <span class="muted">Disk {{ c.diskFreePct }}%</span>
                  </div>
                  <div class="alert-card-mobile-meta">
                    <span class="muted">{{ c.lastHeartbeat ? (c.lastHeartbeat | date:'MMM d, h:mm a') : 'No heartbeat' }}</span>
                  </div>
                  @if (c.degradedReason) {
                    <p class="muted small card-note">{{ c.degradedReason }}</p>
                  }
                </div>
              }
            </div>
          </app-data-table>
        }
      }
    </app-page-container>
  `,
  styles: [`
    .meta-row { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .mono { font-family: ui-monospace, monospace; font-size: 0.82rem; }
    .card-note { margin: 8px 0 0; }
  `],
})
export class LogsComponent implements OnInit, OnDestroy {
  logs: SystemLogs | null = null;
  loading = false;
  error = '';
  levelFilter = '';
  storeId = '';
  private timer?: ReturnType<typeof setInterval>;

  constructor(
    private api: ApiService,
    private route: ActivatedRoute,
    private storeCtx: StoreContextService,
  ) {}

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((params) => {
      this.storeId = params.get('storeId') ?? this.storeCtx.storeId() ?? '';
      this.load();
    });
    this.timer = setInterval(() => this.load(true), 30000);
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }

  filteredConnectors(): ConnectorLogEntry[] {
    if (!this.logs) return [];
    let list = this.logs.connectors;
    if (this.levelFilter) list = list.filter((c) => c.status === this.levelFilter);
    return list;
  }

  load(silent = false): void {
    if (!silent) this.loading = true;
    this.error = '';
    this.api.getSystemLogs(this.storeId || undefined).subscribe({
      next: (l) => {
        this.logs = l;
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load logs';
      },
    });
  }
}
