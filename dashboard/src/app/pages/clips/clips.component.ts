import { Component, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { ClipListItem, Store } from '../../core/models';

@Component({
  selector: 'app-clips',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe, DecimalPipe],
  template: `
    <div class="header-row">
      <h2>Clips</h2>
      <div class="filters">
        <select [(ngModel)]="storeId" (change)="load()">
          <option value="">All stores</option>
          @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
        </select>
        <button class="ghost" (click)="load()">Refresh</button>
      </div>
    </div>

    @if (error) {
      <div class="err-banner">⚠ {{ error }} <button class="ghost small" (click)="load()">Retry</button></div>
    }

    @if (loading) {
      <div class="card">
        @for (i of [1,2,3,4,5]; track i) { <div class="skeleton-row"></div> }
      </div>
    } @else if (clips.length === 0) {
      <div class="card empty-state">
        <div class="empty-icon">🎞</div>
        <p>No clips uploaded yet</p>
        <p class="muted small">
          Clips appear here after the connector detects motion and uploads video.
          Test MP4 footage may show as Analyzed with 0 AI events — that is normal.
        </p>
      </div>
    } @else {
      <table class="table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Camera</th>
            <th>Status</th>
            <th>Duration</th>
            <th>AI events</th>
            <th>Risk score</th>
            <th></th>
            @if (auth.isManagerOrAdmin()) { <th></th> }
          </tr>
        </thead>
        <tbody>
          @for (c of clips; track c.id) {
            <tr>
              <td>{{ c.createdAt | date:'MMM d, h:mm a' }}</td>
              <td>{{ c.cameraName }}</td>
              <td><span class="badge" [class]="statusClass(c.status)">{{ c.status }}</span></td>
              <td>{{ c.durationSec | number:'1.0-1' }}s</td>
              <td>{{ c.eventCount }}</td>
              <td>
                @if (c.riskScore != null) {
                  <span class="score" [class.warn]="c.riskScore >= 40">{{ c.riskScore }}</span>
                } @else {
                  <span class="muted">—</span>
                }
              </td>
              <td>
                <button class="ghost small" [routerLink]="['/app/clips', c.id]">View</button>
                @if (c.alertId) {
                  <a class="alert-link" [routerLink]="['/app/alerts', c.alertId]">Alert →</a>
                }
              </td>
              @if (auth.isManagerOrAdmin()) {
                <td>
                  <button class="ghost small danger" (click)="deleteClip(c)" [disabled]="deletingId === c.id">
                    {{ deletingId === c.id ? '…' : 'Delete' }}
                  </button>
                </td>
              }
            </tr>
          }
        </tbody>
      </table>
    }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem; flex-wrap:wrap; gap:.5rem; }
    .filters { display:flex; gap:.5rem; align-items:center; }
    .filters select {
      padding:.4rem .55rem; border-radius:var(--radius-sm);
      border:1px solid var(--border-strong); background:var(--surface-2); color:var(--text);
    }
    .err-banner {
      background:var(--danger-soft); color:var(--danger); border:1px solid rgba(248,113,113,.3);
      padding:.5rem .75rem; border-radius:var(--radius-sm); margin-bottom:.75rem;
      display:flex; justify-content:space-between; align-items:center;
    }
    .empty-state { text-align:center; padding:2rem 1rem; }
    .empty-icon { font-size:2rem; margin-bottom:.5rem; }
    .muted { color:var(--text-muted); }
    .small { font-size:.82rem; }
    .skeleton-row {
      height:40px; margin:.4rem 0; border-radius:var(--radius-sm);
      background:linear-gradient(90deg, var(--surface-2) 25%, var(--surface) 50%, var(--surface-2) 75%);
      background-size:200% 100%; animation:shimmer 1.2s infinite;
    }
    @keyframes shimmer { 0% { background-position:200% 0; } 100% { background-position:-200% 0; } }
    .badge { padding:.16rem .5rem; border-radius:999px; font-size:.72rem; font-weight:600; }
    .badge.uploaded { background:var(--warning-soft); color:var(--warning); border:1px solid rgba(251,191,36,.3); }
    .badge.analyzed { background:var(--success-soft); color:var(--success); border:1px solid rgba(52,211,153,.3); }
    .badge.pending, .badge.processing { background:var(--surface-2); color:var(--text-muted); border:1px solid var(--border-strong); }
    .score { font-weight:600; }
    .score.warn { color:var(--warning); }
    .alert-link { margin-left:.35rem; font-size:.78rem; color:var(--accent-2); text-decoration:none; }
    button.ghost { background:transparent; border:1px solid var(--border-strong); color:var(--text-muted); padding:.3rem .55rem; border-radius:var(--radius-sm); cursor:pointer; }
    button.small { font-size:.78rem; }
    button.danger { color:var(--danger); border-color:rgba(248,113,113,.35); }
  `],
})
export class ClipsComponent implements OnInit {
  clips: ClipListItem[] = [];
  stores: Store[] = [];
  storeId = '';
  loading = false;
  error = '';
  deletingId = '';

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => {
      this.stores = s;
      if (!this.auth.isAdmin() && this.auth.storeId()) {
        this.storeId = this.auth.storeId()!;
      }
      this.load();
    });
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.listClips(this.storeId || undefined).subscribe({
      next: (c) => { this.clips = c; this.loading = false; },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Failed to load clips'; },
    });
  }

  statusClass(status: string): string {
    return status.toLowerCase();
  }

  deleteClip(c: ClipListItem): void {
    if (!confirm(`Delete clip from ${c.cameraName}? This removes cloud storage and analysis.`)) return;
    this.deletingId = c.id;
    this.api.deleteClip(c.id).subscribe({
      next: () => {
        this.deletingId = '';
        this.clips = this.clips.filter((x) => x.id !== c.id);
      },
      error: (e) => {
        this.deletingId = '';
        this.error = e?.error?.error || 'Delete failed';
      },
    });
  }
}
