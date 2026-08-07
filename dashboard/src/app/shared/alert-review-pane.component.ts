import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ApiService } from '../core/api.service';
import { Alert } from '../core/models';
import { alertTypeLabel } from './alert-labels';
import { ReviewActionsComponent, ReviewAction } from './review-actions.component';
import {
  ErrorBannerComponent,
  SkeletonListComponent,
} from './ui-components';
import { StatusBadgeComponent } from './status-badge.component';
import { StatusPillComponent } from './status-pill.component';

@Component({
  selector: 'app-alert-review-pane',
  standalone: true,
  imports: [
    DatePipe,
    SkeletonListComponent,
    ErrorBannerComponent,
    StatusBadgeComponent,
    StatusPillComponent,
    ReviewActionsComponent,
  ],
  template: `
    @if (loadError) {
      <app-error-banner [message]="loadError" />
    } @else if (loading) {
      <app-skeleton-list [count]="3" />
    } @else if (alert) {
      <div class="mb-2 flex items-start justify-between gap-3">
        <div>
          <h3 class="m-0 mb-1.5 text-[1.1rem]">{{ labelType(alert.alertType) }}</h3>
          <app-status-badge [level]="alert.riskLevel" [label]="alert.riskLevel + ' · ' + alert.riskScore" />
        </div>
        @if (showNav) {
          <div class="flex gap-2">
            <button class="ghost min-h-11" type="button" (click)="prev.emit()" [disabled]="!hasPrev">Previous</button>
            <button class="ghost min-h-11" type="button" (click)="next.emit()" [disabled]="!hasNext">Next</button>
          </div>
        }
      </div>

      <div class="grid items-start gap-4 lg:grid-cols-[1fr_280px]">
        <div class="flex min-w-0 flex-col gap-3">
          <div class="card">
            <h4>Clip</h4>
            @if (alert.clipUrl) {
              <video class="rounded-[6px] border border-border-strong" [src]="alert.clipUrl" controls width="100%"></video>
            } @else {
              <p class="muted">Clip not available — it may have been removed by storage retention.</p>
            }
          </div>

          <div class="card">
            <h4>Evidence timeline</h4>
            <div class="flex flex-col gap-2">
              @for (e of evidence(); track e) {
                <div class="flex gap-3 rounded-[6px] border border-border border-l-[3px] border-l-accent bg-surface-2 px-3 py-2.5">
                  <span class="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden="true"></span>
                  <span>{{ e }}</span>
                </div>
              } @empty {
                <p class="muted">No evidence entries.</p>
              }
            </div>
          </div>
        </div>

        <div class="flex min-w-0 flex-col gap-3">
          <div class="card">
            <h4>Details</h4>
            <div class="flex flex-col">
              <div class="flex items-center justify-between gap-2 border-b border-border py-1.5 last:border-b-0"><span class="text-[0.8rem] text-ink-muted">Status</span><app-status-pill [status]="alert.status" /></div>
              <div class="flex items-center justify-between gap-2 border-b border-border py-1.5 last:border-b-0"><span class="text-[0.8rem] text-ink-muted">Created</span><span>{{ alert.createdAt | date:'medium' }}</span></div>
            </div>
          </div>

          <div class="card">
            <h4>Your review</h4>
            <app-review-actions
              [saving]="saving"
              [error]="reviewError"
              [saved]="saved"
              [patterns]="patterns"
              [detectedPatterns]="detectedPatterns"
              (review)="onReview($event)" />
          </div>
        </div>
      </div>
    } @else {
      <div class="muted px-6 py-12 text-center">
        <p>Select an alert from the list to review it here.</p>
      </div>
    }
  `,
  styles: [`
    h4 { margin: 0 0 8px; font-size: 0.95rem; }
  `],
})
export class AlertReviewPaneComponent implements OnChanges {
  @Input({ required: true }) alertId = '';
  @Input() showNav = false;
  @Input() hasPrev = false;
  @Input() hasNext = false;
  @Output() prev = new EventEmitter<void>();
  @Output() next = new EventEmitter<void>();
  @Output() reviewed = new EventEmitter<Alert>();

  alert?: Alert;
  loading = false;
  loadError = '';
  saving = false;
  saved = false;
  reviewError = '';
  patterns: string[] = [];
  detectedPatterns: string[] = [];

  constructor(private api: ApiService) {
    this.api.getPatterns().subscribe({
      next: (p) => (this.patterns = p),
      error: () => (this.patterns = []),  // checkboxes hidden; review still works
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['alertId']) {
      this.loadAlert();
    }
  }

  labelType(type: string): string {
    return alertTypeLabel(type);
  }

  evidence(): string[] {
    try {
      return JSON.parse(this.alert?.evidenceJson || '[]');
    } catch {
      return [];
    }
  }

  onReview(payload: {
    action: ReviewAction; reasonCode?: string; notes?: string; confirmedPatterns?: string[];
  }): void {
    if (!this.alert) return;
    this.saving = true;
    this.reviewError = '';
    this.saved = false;
    this.api.reviewAlert(
      this.alert.id, payload.action, payload.reasonCode, payload.notes, payload.confirmedPatterns,
    ).subscribe({
      next: (a) => {
        this.alert = a;
        this.saving = false;
        this.saved = true;
        this.reviewed.emit(a);
      },
      error: (e) => {
        this.saving = false;
        this.reviewError = e?.error?.error || 'Review failed';
      },
    });
  }

  private loadAlert(): void {
    if (!this.alertId) {
      this.alert = undefined;
      this.loadError = '';
      return;
    }
    this.loading = true;
    this.loadError = '';
    this.saved = false;
    this.api.getAlert(this.alertId).subscribe({
      next: (a) => {
        this.alert = a;
        this.detectedPatterns = this.computeDetected(a);
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.loadError = e?.error?.error || 'Failed to load alert';
      },
    });
  }

  /** AI-detected patterns for pre-selection: clip AI events ∪ the alert's own type. */
  private computeDetected(alert: Alert): string[] {
    const set = new Set<string>((alert.aiEvents ?? []).map((e) => e.eventType));
    if (alert.alertType) set.add(alert.alertType);
    return [...set];
  }
}
