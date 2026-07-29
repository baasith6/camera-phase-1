import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { AnalyticsSummary, Store } from '../../core/models';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="header-row">
      <h2>Analytics</h2>
      <select [(ngModel)]="storeId" (change)="load()">
        <option value="">All stores</option>
        @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
      </select>
    </div>

    @if (loading) { <div class="card muted">Loading…</div> }
    @else if (error) { <div class="err">{{ error }}</div> }
    @else if (summary) {
      <div class="grid">
        <div class="card stat"><div class="label">Total alerts</div><div class="value">{{ summary.totalAlerts }}</div></div>
        <div class="card stat"><div class="label">Pending review</div><div class="value warn">{{ summary.pendingAlerts }}</div></div>
        <div class="card stat"><div class="label">High risk</div><div class="value danger">{{ summary.highRiskAlerts }}</div></div>
        <div class="card stat"><div class="label">False positives</div><div class="value">{{ summary.falsePositives }}</div></div>
        <div class="card stat"><div class="label">Clips analyzed</div><div class="value">{{ summary.analyzedClips }} / {{ summary.totalClips }}</div></div>
      </div>

      @if (typeEntries.length) {
        <div class="card">
          <h3>Alerts by type</h3>
          <table class="table">
            <thead><tr><th>Type</th><th>Count</th></tr></thead>
            <tbody>
              @for (row of typeEntries; track row.type) {
                <tr><td>{{ row.type }}</td><td>{{ row.count }}</td></tr>
              }
            </tbody>
          </table>
        </div>
      }
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:.75rem; margin-bottom:1rem; }
    .stat .label { font-size:.8rem; color:var(--text-muted); }
    .stat .value { font-size:1.6rem; font-weight:700; margin-top:.25rem; }
    .value.warn { color:var(--warning); }
    .value.danger { color:var(--danger); }
    .table { width:100%; border-collapse:collapse; }
    .table th, .table td { text-align:left; padding:.45rem .5rem; border-bottom:1px solid var(--border); }
    .err { color:var(--danger); }
    .muted { color:var(--text-muted); }
  `],
})
export class AnalyticsComponent implements OnInit {
  stores: Store[] = [];
  storeId = '';
  summary: AnalyticsSummary | null = null;
  loading = false;
  error = '';
  typeEntries: { type: string; count: number }[] = [];

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => { this.stores = s; this.load(); });
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.getAnalyticsSummary(this.storeId || undefined).subscribe({
      next: (s) => {
        this.summary = s;
        this.typeEntries = Object.entries(s.alertsByType || {}).map(([type, count]) => ({ type, count }));
        this.loading = false;
      },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load analytics'; },
    });
  }
}
