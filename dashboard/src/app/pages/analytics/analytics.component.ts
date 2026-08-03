import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import type { ChartConfiguration } from 'chart.js';
import { forkJoin } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { StoreContextService } from '../../core/store-context.service';
import { Alert, AnalyticsSummary } from '../../core/models';
import { alertTypeLabel } from '../../shared/alert-labels';
import { countByRisk, countReviewOutcomes } from '../../shared/analytics.utils';
import { ChartComponent } from '../../shared/chart.component';
import { PageContainerComponent, PageHeaderComponent, StatCardComponent, ErrorBannerComponent, SkeletonListComponent, EmptyStateComponent } from '../../shared/ui-components';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
    FormsModule,
    PageHeaderComponent,
    PageContainerComponent,
    StatCardComponent,
    ChartComponent,
    ErrorBannerComponent,
    SkeletonListComponent,
    EmptyStateComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header title="Overview" subtitle="Store performance and alert trends.">
        <div actions>
          <select [(ngModel)]="days" (change)="load()" aria-label="Date range">
            <option [ngValue]="7">Last 7 days</option>
            <option [ngValue]="30">Last 30 days</option>
          </select>
          <button class="ghost" type="button" (click)="load()">Refresh</button>
        </div>
      </app-page-header>

      @if (loading) {
        <app-skeleton-list />
      } @else if (error) {
        <app-error-banner [message]="error">
          <button class="ghost small" type="button" (click)="load()">Retry</button>
        </app-error-banner>
      } @else if (summary) {
        @if (summary.totalAlerts === 0 && summary.totalClips === 0) {
          <app-empty-state
            title="No activity yet"
            detail="Charts will populate once clips are uploaded and alerts are generated for this store." />
        } @else {
        <div class="grid-stats">
          <app-stat-card label="Total alerts" [value]="summary.totalAlerts" />
          <app-stat-card label="Pending review" [value]="summary.pendingAlerts" tone="warn" />
          <app-stat-card label="High risk" [value]="summary.highRiskAlerts" tone="danger" />
          <app-stat-card label="False positives" [value]="summary.falsePositives" />
          <app-stat-card label="Clips analyzed" [value]="summary.analyzedClips + ' / ' + summary.totalClips" />
        </div>

        <div class="grid-2">
          <div class="card chart-card">
            <h3>Alerts over time</h3>
            @if (trendConfig) { <app-chart [config]="trendConfig" /> }
          </div>
          <div class="card chart-card">
            <h3>Risk distribution</h3>
            @if (riskConfig) { <app-chart [config]="riskConfig" /> }
          </div>
        </div>

        <div class="grid-2">
          <div class="card chart-card">
            <h3>Alerts by type</h3>
            @if (typeConfig) { <app-chart [config]="typeConfig" /> }
          </div>
          <div class="card chart-card">
            <h3>Review outcomes</h3>
            @if (outcomeConfig) { <app-chart [config]="outcomeConfig" /> }
          </div>
        </div>
        }
      }
    </app-page-container>
  `,
})
export class AnalyticsComponent implements OnInit {
  storeId = '';
  days = 7;
  summary: AnalyticsSummary | null = null;
  loading = false;
  error = '';
  trendConfig?: ChartConfiguration;
  riskConfig?: ChartConfiguration;
  typeConfig?: ChartConfiguration;
  outcomeConfig?: ChartConfiguration;

  private readonly tickColor = '#71717a';
  private readonly gridColor = '#e4e4e7';
  private readonly chartColors = ['#2563eb', '#60a5fa', '#f87171', '#fbbf24', '#34d399', '#71717a'];

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

  load(): void {
    this.loading = true;
    this.error = '';
    forkJoin({
      summary: this.api.getAnalyticsSummary(this.storeId || undefined),
      alerts: this.api.listAlerts(this.storeId || undefined),
      trends: this.api.getAnalyticsTrends(this.storeId || undefined, this.days),
    }).subscribe({
      next: ({ summary, alerts, trends }) => {
        this.summary = summary;
        const recent = alerts.filter((a) => {
          const age = Date.now() - new Date(a.createdAt).getTime();
          return age <= this.days * 86400000;
        });
        this.buildCharts(recent, trends.points);
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load overview';
      },
    });
  }

  private buildCharts(alerts: Alert[], trendPoints: { date: string; count: number }[]): void {
    const labels = trendPoints.map((p) => {
      const d = new Date(p.date);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    });
    const counts = trendPoints.map((p) => p.count);

    this.trendConfig = {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Alerts',
          data: counts,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.1)',
          fill: true,
          tension: 0.3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: this.tickColor }, grid: { color: this.gridColor } },
          y: { ticks: { color: this.tickColor }, grid: { color: this.gridColor }, beginAtZero: true },
        },
      },
    };

    const risk = countByRisk(alerts);
    this.riskConfig = {
      type: 'doughnut',
      data: {
        labels: Object.keys(risk),
        datasets: [{ data: Object.values(risk), backgroundColor: this.chartColors }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: this.tickColor } } },
      },
    };

    const typeEntries = summaryTypes(this.summary!, alerts);
    const typeLabels = typeEntries.map(([k]) => alertTypeLabel(k));
    const typeCounts: number[] = typeEntries.map(([, count]) => count);
    this.typeConfig = {
      type: 'bar',
      data: {
        labels: typeLabels,
        datasets: [{ label: 'Count', data: typeCounts, backgroundColor: '#2563eb' }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: this.tickColor }, grid: { color: this.gridColor } },
          y: { ticks: { color: this.tickColor }, grid: { display: false } },
        },
      },
    };

    const outcomes = countReviewOutcomes(alerts);
    this.outcomeConfig = {
      type: 'bar',
      data: {
        labels: Object.keys(outcomes),
        datasets: [{ data: Object.values(outcomes), backgroundColor: this.chartColors }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: this.tickColor }, grid: { display: false } },
          y: { ticks: { color: this.tickColor }, grid: { color: this.gridColor }, beginAtZero: true },
        },
      },
    };
  }
}

function summaryTypes(summary: AnalyticsSummary, alerts: Alert[]): [string, number][] {
  if (Object.keys(summary.alertsByType || {}).length) {
    return Object.entries(summary.alertsByType).sort((a, b) => b[1] - a[1]);
  }
  const map: Record<string, number> = {};
  for (const a of alerts) map[a.alertType] = (map[a.alertType] ?? 0) + 1;
  return Object.entries(map).sort((a, b) => b[1] - a[1]);
}
