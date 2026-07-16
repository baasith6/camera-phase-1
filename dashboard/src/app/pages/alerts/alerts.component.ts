import { Component, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { Alert, Store } from '../../core/models';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe],
  template: `
    <div class="header-row">
      <h2>Alerts</h2>
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

    @if (loading) { <p class="muted">Loading...</p> }
    @else if (alerts.length === 0) {
      <div class="card"><p class="muted">No alerts visible. (Store may be in silent/manager-only pilot mode.)</p></div>
    } @else {
      <table class="table">
        <thead>
          <tr><th>When</th><th>Type</th><th>Risk</th><th>Score</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          @for (a of alerts; track a.id) {
            <tr>
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
    .header-row { display:flex; justify-content:space-between; align-items:center; }
    .filters { display:flex; gap:.5rem; }
    .badge { padding:.15rem .5rem; border-radius:10px; font-size:.75rem; }
    .badge.high { background:#5a1e1e; color:#ff9f9f; }
    .badge.medium { background:#5a4a1e; color:#ffe08a; }
    .badge.low { background:#22303f; color:#8ab4f8; }
    .badge.none { background:#2a2a2a; color:#aaa; }
  `],
})
export class AlertsComponent implements OnInit {
  stores: Store[] = [];
  alerts: Alert[] = [];
  storeId = '';
  status = '';
  loading = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => (this.stores = s));
    this.load();
  }

  load(): void {
    this.loading = true;
    this.api.listAlerts(this.storeId || undefined, this.status || undefined).subscribe({
      next: (a) => { this.alerts = a; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }
}
