import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { StoreContextService } from '../../core/store-context.service';
import { Alert } from '../../core/models';
import { alertTypeLabel } from '../../shared/alert-labels';
import { PageContainerComponent, PageHeaderComponent, DataTableComponent, ErrorBannerComponent, SkeletonListComponent } from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';
import { StatusPillComponent } from '../../shared/status-pill.component';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [
    FormsModule,
    PageHeaderComponent,
    PageContainerComponent,
    DataTableComponent,
    StatusBadgeComponent,
    StatusPillComponent,
    ErrorBannerComponent,
    SkeletonListComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header
        title="Reports & Export"
        subtitle="Audit-ready alert export for compliance review.">
        <div actions>
          <button class="ghost" type="button" (click)="exportCsv()" [disabled]="!alerts.length">Export CSV</button>
          <button class="ghost" type="button" (click)="load()">Refresh</button>
        </div>
      </app-page-header>

      @if (loading) {
        <app-skeleton-list />
      } @else if (error) {
        <app-error-banner [message]="error">
          <button class="ghost small" type="button" (click)="load()">Retry</button>
        </app-error-banner>
      } @else {
        <div class="card">
          <p class="muted">{{ alerts.length }} alert(s) ready for export.</p>
          <app-data-table>
            <table desktop class="table">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Type</th>
                  <th>Risk</th>
                  <th>Score</th>
                  <th>Status</th>
                  <th>Store</th>
                </tr>
              </thead>
              <tbody>
                @for (a of alerts; track a.id) {
                  <tr>
                    <td>{{ a.createdAt }}</td>
                    <td>{{ labelType(a.alertType) }}</td>
                    <td><app-status-badge [level]="a.riskLevel" /></td>
                    <td>{{ a.riskScore }}</td>
                    <td><app-status-pill [status]="a.status" /></td>
                    <td>{{ a.storeId }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </app-data-table>
        </div>
      }
    </app-page-container>
  `,
})
export class ReportsComponent implements OnInit {
  alerts: Alert[] = [];
  storeId = '';
  loading = false;
  error = '';

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
  }

  labelType(type: string): string {
    return alertTypeLabel(type);
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.listAlerts(this.storeId || undefined).subscribe({
      next: (a) => {
        this.alerts = a;
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load report data';
      },
    });
  }

  exportCsv(): void {
    const header = ['Created', 'Type', 'Risk', 'Score', 'Status', 'StoreId'];
    const rows = this.alerts.map((a) =>
      [a.createdAt, a.alertType, a.riskLevel, a.riskScore, a.status, a.storeId]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(','),
    );
    const csv = [header.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `onetix-alerts-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }
}
