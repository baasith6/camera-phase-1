import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { StoreContextService } from '../../core/store-context.service';
import { ConnectorLogEntry, SystemLogs } from '../../core/models';
import { PageContainerComponent, PageHeaderComponent, DataTableComponent, ErrorBannerComponent, SkeletonListComponent } from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [
    FormsModule,
    DatePipe,
    PageHeaderComponent,
    PageContainerComponent,
    DataTableComponent,
    StatusBadgeComponent,
    ErrorBannerComponent,
    SkeletonListComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header title="System logs" subtitle="Connector heartbeats and pipeline queue status.">
        <div actions>
          <select [(ngModel)]="levelFilter" aria-label="Status filter">
            <option value="">All statuses</option>
            <option value="Healthy">Healthy</option>
            <option value="Degraded">Degraded</option>
            <option value="Offline">Offline</option>
          </select>
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
              } @empty {
                <tr><td colspan="7" class="muted">No connector logs for this filter.</td></tr>
              }
            </tbody>
          </table>
        </app-data-table>
      }
    </app-page-container>
  `,
  styles: [`
    .meta-row { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
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
