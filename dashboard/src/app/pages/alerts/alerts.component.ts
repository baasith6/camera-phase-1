import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { API_BASE } from '../../core/api.config';
import { Alert, Store } from '../../core/models';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe],
  template: `
    <div class="header-row">
      <div style="display:flex;align-items:center;gap:.75rem">
        <h2>Alerts</h2>
        <span class="live-badge" [class.connected]="sseConnected">
          <span class="dot"></span>{{ sseConnected ? 'Live' : 'Offline' }}
        </span>
      </div>
      <div class="filters">
        <select [(ngModel)]="storeId" (change)="load()">
          <option value="">All stores</option>
          @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
        </select>
        <select [(ngModel)]="status" (change)="load()">
          <option value="">All statuses</option>
          <option value="PendingReview">Pending review</option>
          <option value="Confirmed">Confirmed</option>
          <option value="Dismissed">Dismissed</option>
          <option value="FalsePositive">False positive</option>
          <option value="NeedsFollowUp">Needs follow-up</option>
        </select>
        <button class="ghost" (click)="load()">Refresh</button>
      </div>
    </div>

    @if (error) {
      <div class="err-banner">⚠ {{ error }} <button class="ghost small" (click)="load()">Retry</button></div>
    }

    @if (loading) {
      <div class="card"><p class="muted">Loading alerts…</p></div>
    } @else if (alerts.length === 0) {
      <div class="card"><p class="muted">No alerts visible. (Store may be in silent/manager-only pilot mode.)</p></div>
    } @else {
      @if (newCount > 0) {
        <div class="new-banner" (click)="dismissNewBanner()">
          🔔 {{ newCount }} new alert{{ newCount > 1 ? 's' : '' }} received — click to dismiss
        </div>
      }
      <table class="table">
        <thead>
          <tr><th>When</th><th>Type</th><th>Risk</th><th>Score</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          @for (a of alerts; track a.id) {
            <tr [class.new-row]="newIds.has(a.id)">
              <td>{{ a.createdAt | date:'short' }}</td>
              <td>{{ a.alertType }}</td>
              <td><span class="badge" [class]="a.riskLevel.toLowerCase()">{{ a.riskLevel }}</span></td>
              <td>{{ a.riskScore }}</td>
              <td>{{ a.status }}</td>
              <td><a [routerLink]="['/alerts', a.id]">Review</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; }
    .filters { display:flex; gap:.5rem; }
    .badge { padding:.15rem .5rem; border-radius:10px; font-size:.75rem; }
    .badge.high { background:#5a1e1e; color:#ff9f9f; }
    .badge.medium { background:#5a4a1e; color:#ffe08a; }
    .badge.low { background:#22303f; color:#8ab4f8; }
    .badge.none { background:#2a2a2a; color:#aaa; }
    .live-badge { display:inline-flex; align-items:center; gap:.3rem; font-size:.75rem;
                  padding:.2rem .55rem; border-radius:10px; background:#2a2a2a; color:#666; }
    .live-badge.connected { background:#1a3a2a; color:#5cdb7f; }
    .dot { width:7px; height:7px; border-radius:50%; background:currentColor; }
    .live-badge.connected .dot { animation: pulse 1.8s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
    .err-banner { background:#3a1a1a; color:#f07070; padding:.5rem .75rem; border-radius:6px;
                  margin-bottom:.75rem; display:flex; justify-content:space-between; align-items:center; }
    .new-banner { background:#1e3a2a; color:#5cdb7f; padding:.5rem .75rem; border-radius:6px;
                  margin-bottom:.5rem; cursor:pointer; font-size:.85rem; }
    .new-banner:hover { background:#224a34; }
    .new-row { animation: fadeIn .6s ease; }
    @keyframes fadeIn { from{background:#1e3a2a} to{background:transparent} }
    .small { font-size:.75rem; }
  `],
})
export class AlertsComponent implements OnInit, OnDestroy {
  stores: Store[] = [];
  alerts: Alert[] = [];
  storeId = '';
  status = '';
  loading = false;
  error = '';
  sseConnected = false;
  newIds = new Set<string>();
  newCount = 0;
  private es?: EventSource;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe({ next: s => this.stores = s });
    this.load();
    this.connectSse();
  }

  ngOnDestroy(): void { this.es?.close(); }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.listAlerts(this.storeId || undefined, this.status || undefined).subscribe({
      next: (a) => { this.alerts = a; this.loading = false; },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load alerts'; },
    });
  }

  dismissNewBanner(): void { this.newCount = 0; this.newIds.clear(); }

  private connectSse(): void {
    // SSE uses the JWT from localStorage (set by auth service).
    const token = localStorage.getItem('access_token') ?? '';
    const url = `${API_BASE}/api/alerts/stream?access_token=${encodeURIComponent(token)}`;
    this.es = new EventSource(url);

    this.es.addEventListener('connected', () => { this.sseConnected = true; });

    this.es.addEventListener('alert', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        // Only prepend if it matches current store filter (or no filter).
        if (this.storeId && data.storeId !== this.storeId) return;
        const newAlert: Alert = {
          id: data.alertId,
          alertType: data.alertType,
          riskLevel: data.riskLevel,
          riskScore: data.riskScore,
          status: 'PendingReview',
          createdAt: data.createdAt,
          storeId: data.storeId,
          evidenceJson: '[]',
          cameraId: '', clipId: '', modelVersion: '', ruleVersion: '',
        };
        this.alerts = [newAlert, ...this.alerts];
        this.newIds.add(newAlert.id);
        this.newCount++;
      } catch { /* ignore malformed events */ }
    });

    this.es.onerror = () => { this.sseConnected = false; };
  }
}

