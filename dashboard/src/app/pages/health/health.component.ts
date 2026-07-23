import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ApiService } from '../../core/api.service';
import { Connector } from '../../core/models';

@Component({
  selector: 'app-health',
  standalone: true,
  imports: [DatePipe, DecimalPipe],
  template: `
    <div class="header-row">
      <h2>Connector Health</h2>
      <div style="display:flex;gap:.5rem;align-items:center">
        @if (loading) { <span class="muted small">Refreshing…</span> }
        <button class="ghost" (click)="load()">Refresh</button>
      </div>
    </div>

    @if (error) {
      <div class="err-banner">
        ⚠ {{ error }}
        <button class="ghost small" (click)="load()">Retry</button>
      </div>
    }

    @if (!error && connectors.length === 0 && !loading) {
      <div class="card"><p class="muted">No connectors registered yet.</p></div>
    } @else if (connectors.length > 0) {
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
              <td><span class="badge" [class]="c.status.toLowerCase()">{{ c.status }}</span></td>
              <td [class.warn]="c.diskFreePct < 20" [class.crit]="c.diskFreePct < 10">{{ c.diskFreePct | number:'1.0-1' }}%</td>
              <td [class.warn]="c.uploadQueueDepth > 50">{{ c.uploadQueueDepth }}</td>
              <td [class.warn]="(c.rtspReconnects || 0) > 0">{{ c.rtspReconnects ?? 0 }}</td>
              <td>{{ c.lastHeartbeat ? (c.lastHeartbeat | date:'short') : '—' }}</td>
              <td>{{ c.degradedReason || '—' }}</td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .badge { padding:.18rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600; }
    .badge.healthy { background:var(--success-soft); color:var(--success); border:1px solid rgba(52,211,153,.3); }
    .badge.degraded { background:var(--warning-soft); color:var(--warning); border:1px solid rgba(251,191,36,.3); }
    .badge.offline, .badge.unknown { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3); }
    .warn { color:var(--warning); } .crit { color:var(--danger); }
    .small { font-size:.75rem; }
    .err-banner { background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3);
                  padding:.5rem .75rem; border-radius:var(--radius-sm);
                  margin-bottom:.75rem; display:flex; justify-content:space-between; align-items:center; }
  `],
})
export class HealthComponent implements OnInit, OnDestroy {
  connectors: Connector[] = [];
  loading = false;
  error = '';
  private timer?: any;

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); this.timer = setInterval(() => this.load(), 8000); }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  load(): void {
    this.loading = true;
    this.api.listConnectors().subscribe({
      next: (c) => { this.connectors = c; this.loading = false; this.error = ''; },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load connectors'; },
    });
  }
}

