import { Component, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { Alert } from '../../core/models';

@Component({
  selector: 'app-alert-detail',
  standalone: true,
  imports: [FormsModule, DatePipe],
  template: `
    @if (alert) {
      <div class="header-row">
        <h2>{{ alert.alertType }}</h2>
        <span class="badge" [class]="alert.riskLevel.toLowerCase()">{{ alert.riskLevel }} · {{ alert.riskScore }}</span>
      </div>

      <div class="grid2">
        <div class="card">
          <h3>Evidence</h3>
          <ul>
            @for (e of evidence(); track e) { <li>{{ e }}</li> }
          </ul>
          <p class="muted small">Evidence describes observable signals only — never a theft conclusion. Staff decide.</p>
        </div>
        <div class="card">
          <h3>Clip</h3>
          @if (alert.clipUrl) {
            <video [src]="alert.clipUrl" controls width="100%"></video>
          } @else { <p class="muted">Clip not available.</p> }
        </div>
      </div>

      <div class="card">
        <h3>Details</h3>
        <div class="kv">
          <div class="k">Status</div><div>{{ alert.status }}</div>
          <div class="k">Created</div><div>{{ alert.createdAt | date:'medium' }}</div>
          <div class="k">Model version</div><div>{{ alert.modelVersion }}</div>
          <div class="k">Rule version</div><div>{{ alert.ruleVersion }}</div>
        </div>
      </div>

      <div class="card">
        <h3>Review</h3>
        <div class="review-row">
          <select [(ngModel)]="action">
            <option value="Confirm">Confirm</option>
            <option value="Dismiss">Dismiss</option>
            <option value="FalsePositive">False positive</option>
            <option value="NeedsFollowUp">Needs follow-up</option>
          </select>
          <input placeholder="Reason code (required for dismiss / false positive)" [(ngModel)]="reasonCode" />
        </div>
        <textarea placeholder="Notes (optional)" [(ngModel)]="notes" rows="3"></textarea>
        <button (click)="submit()" [disabled]="saving">Submit review</button>
        @if (error) { <p class="error">{{ error }}</p> }
        @if (saved) { <p class="ok">Review saved.</p> }
      </div>
    } @else { <p class="muted">Loading...</p> }
  `,
  styles: [`
    .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:1rem; }
    .kv { display:grid; grid-template-columns:160px 1fr; gap:.3rem; }
    .k { color:#8ab4f8; }
    .review-row { display:flex; gap:.5rem; margin-bottom:.5rem; }
    .review-row input { flex:1; }
    textarea { width:100%; margin-bottom:.5rem; }
    .badge { padding:.2rem .6rem; border-radius:10px; }
    .badge.high { background:#5a1e1e; color:#ff9f9f; }
    .badge.medium { background:#5a4a1e; color:#ffe08a; }
    .badge.low { background:#22303f; color:#8ab4f8; }
    .badge.none { background:#2a2a2a; color:#aaa; }
    .error { color:#ff6b6b; } .ok { color:#7bd88f; } .small { font-size:.8rem; }
  `],
})
export class AlertDetailComponent implements OnInit {
  alert?: Alert;
  action = 'Confirm';
  reasonCode = '';
  notes = '';
  saving = false;
  saved = false;
  error = '';

  constructor(private route: ActivatedRoute, private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getAlert(id).subscribe((a) => (this.alert = a));
  }

  evidence(): string[] {
    try { return JSON.parse(this.alert?.evidenceJson || '[]'); } catch { return []; }
  }

  submit(): void {
    if (!this.alert) return;
    this.saving = true; this.error = ''; this.saved = false;
    this.api.reviewAlert(this.alert.id, this.action, this.reasonCode || undefined, this.notes || undefined).subscribe({
      next: (a) => { this.alert = a; this.saving = false; this.saved = true; },
      error: (e) => { this.saving = false; this.error = e?.error?.error || 'Review failed'; },
    });
  }
}
