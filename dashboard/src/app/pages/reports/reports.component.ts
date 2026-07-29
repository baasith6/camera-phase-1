import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { Alert, Store } from '../../core/models';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="header-row">
      <h2>Reports</h2>
      <div class="actions">
        <select [(ngModel)]="storeId" (change)="load()">
          <option value="">All stores</option>
          @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
        </select>
        <button class="ghost" (click)="exportCsv()" [disabled]="!alerts.length">Export CSV</button>
      </div>
    </div>

    @if (loading) { <div class="card muted">Loading…</div> }
    @else if (error) { <div class="err">{{ error }}</div> }
    @else {
      <div class="card">
        <p class="muted">{{ alerts.length }} alert(s) — export for audit or compliance review.</p>
        <table class="table">
          <thead>
            <tr>
              <th>Created</th><th>Type</th><th>Risk</th><th>Score</th><th>Status</th><th>Store</th>
            </tr>
          </thead>
          <tbody>
            @for (a of alerts; track a.id) {
              <tr>
                <td>{{ a.createdAt }}</td>
                <td>{{ a.alertType }}</td>
                <td>{{ a.riskLevel }}</td>
                <td>{{ a.riskScore }}</td>
                <td>{{ a.status }}</td>
                <td>{{ a.storeId }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .actions { display:flex; gap:.5rem; align-items:center; }
    .table { width:100%; border-collapse:collapse; font-size:.85rem; }
    .table th, .table td { text-align:left; padding:.4rem .5rem; border-bottom:1px solid var(--border); }
    button.ghost { background:transparent; border:1px solid var(--border-strong); color:var(--text-muted); padding:.35rem .65rem; border-radius:var(--radius-sm); cursor:pointer; }
    .err { color:var(--danger); }
    .muted { color:var(--text-muted); }
  `],
})
export class ReportsComponent implements OnInit {
  stores: Store[] = [];
  alerts: Alert[] = [];
  storeId = '';
  loading = false;
  error = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => { this.stores = s; this.load(); });
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.listAlerts(this.storeId || undefined).subscribe({
      next: (a) => { this.alerts = a; this.loading = false; },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load report data'; },
    });
  }

  exportCsv(): void {
    const header = ['createdAt', 'alertType', 'riskLevel', 'riskScore', 'status', 'storeId', 'id'];
    const rows = this.alerts.map((a) =>
      [a.createdAt, a.alertType, a.riskLevel, a.riskScore, a.status, a.storeId, a.id]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(','),
    );
    const blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `onevo-alerts-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
}
