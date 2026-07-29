import { Component, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { ConnectorLogEntry, Store, SystemLogs } from '../../core/models';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [FormsModule, DatePipe],
  template: `
    <div class="header-row">
      <h2>System Logs</h2>
      <div class="actions">
        <select [(ngModel)]="storeId" (change)="load()">
          <option value="">All stores</option>
          @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
        </select>
        <button class="ghost" (click)="load()">Refresh</button>
      </div>
    </div>

    @if (loading) { <div class="card muted">Loading…</div> }
    @else if (error) { <div class="err">{{ error }}</div> }
    @else if (logs) {
      <div class="grid">
        <div class="card stat"><div class="label">Redis queue</div><div class="value">{{ logs.redisQueueDepth }}</div></div>
        <div class="card stat"><div class="label">Failed jobs</div><div class="value" [class.danger]="logs.failedJobs > 0">{{ logs.failedJobs }}</div></div>
      </div>

      <div class="card">
        <h3>Connector status</h3>
        @if (!logs.connectors.length) {
          <p class="muted">No connectors registered.</p>
        } @else {
          <table class="table">
            <thead>
              <tr><th>Name</th><th>Status</th><th>Version</th><th>Last heartbeat</th><th>Degraded reason</th><th>Queue</th></tr>
            </thead>
            <tbody>
              @for (c of logs.connectors; track c.id) {
                <tr>
                  <td>{{ c.name }}</td>
                  <td>{{ c.status }}</td>
                  <td>{{ c.version }}</td>
                  <td>{{ c.lastHeartbeat ? (c.lastHeartbeat | date:'MMM d, h:mm a') : '—' }}</td>
                  <td>{{ c.degradedReason || '—' }}</td>
                  <td>{{ c.uploadQueueDepth }}</td>
                </tr>
              }
            </tbody>
          </table>
        }
      </div>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .actions { display:flex; gap:.5rem; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:.75rem; margin-bottom:1rem; }
    .stat .label { font-size:.8rem; color:var(--text-muted); }
    .stat .value { font-size:1.4rem; font-weight:700; }
    .value.danger { color:var(--danger); }
    .table { width:100%; border-collapse:collapse; font-size:.85rem; }
    .table th, .table td { text-align:left; padding:.4rem .5rem; border-bottom:1px solid var(--border); vertical-align:top; }
    button.ghost { background:transparent; border:1px solid var(--border-strong); color:var(--text-muted); padding:.35rem .65rem; border-radius:var(--radius-sm); cursor:pointer; }
    .err { color:var(--danger); }
    .muted { color:var(--text-muted); }
  `],
})
export class LogsComponent implements OnInit {
  stores: Store[] = [];
  storeId = '';
  logs: SystemLogs | null = null;
  loading = false;
  error = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => { this.stores = s; this.load(); });
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.getSystemLogs(this.storeId || undefined).subscribe({
      next: (l) => { this.logs = l; this.loading = false; },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load logs'; },
    });
  }
}
