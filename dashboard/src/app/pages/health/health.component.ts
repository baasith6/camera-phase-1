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
      <button class="ghost" (click)="load()">Refresh</button>
    </div>

    @if (connectors.length === 0) {
      <div class="card"><p class="muted">No connectors registered yet.</p></div>
    } @else {
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Status</th><th>Disk free</th><th>Queue</th><th>Last heartbeat</th><th>Degraded</th></tr>
        </thead>
        <tbody>
          @for (c of connectors; track c.id) {
            <tr>
              <td>{{ c.name }} <span class="muted small">v{{ c.version }}</span></td>
              <td><span class="badge" [class]="c.status.toLowerCase()">{{ c.status }}</span></td>
              <td [class.warn]="c.diskFreePct < 20" [class.crit]="c.diskFreePct < 10">{{ c.diskFreePct | number:'1.0-1' }}%</td>
              <td [class.warn]="c.uploadQueueDepth > 50">{{ c.uploadQueueDepth }}</td>
              <td>{{ c.lastHeartbeat ? (c.lastHeartbeat | date:'short') : '—' }}</td>
              <td>{{ c.degradedReason || '—' }}</td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; }
    .badge { padding:.15rem .5rem; border-radius:10px; font-size:.75rem; }
    .badge.healthy { background:#1e4a2a; color:#8ae0a0; }
    .badge.degraded { background:#5a4a1e; color:#ffe08a; }
    .badge.offline, .badge.unknown { background:#5a1e1e; color:#ff9f9f; }
    .warn { color:#ffe08a; } .crit { color:#ff6b6b; }
    .small { font-size:.75rem; }
  `],
})
export class HealthComponent implements OnInit, OnDestroy {
  connectors: Connector[] = [];
  private timer?: any;

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); this.timer = setInterval(() => this.load(), 8000); }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  load(): void { this.api.listConnectors().subscribe((c) => (this.connectors = c)); }
}
