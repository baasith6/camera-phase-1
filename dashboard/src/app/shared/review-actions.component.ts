import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ErrorBannerComponent } from './ui-components';

export type ReviewAction = 'Confirm' | 'Dismiss' | 'FalsePositive' | 'NeedsFollowUp';

@Component({
  selector: 'app-review-actions',
  standalone: true,
  imports: [FormsModule, ErrorBannerComponent],
  template: `
    <div class="review-actions">
      <p class="hint muted small">What do you think happened?</p>
      <div class="action-row">
        <button type="button" class="primary" (click)="submit('Confirm')" [disabled]="saving">
          Confirm incident
        </button>
        <button type="button" class="ghost" (click)="submit('Dismiss')" [disabled]="saving">
          Not suspicious
        </button>
        <button type="button" class="ghost" (click)="submit('FalsePositive')" [disabled]="saving">
          False alarm
        </button>
        <button type="button" class="ghost subtle" (click)="submit('NeedsFollowUp')" [disabled]="saving">
          Needs follow-up
        </button>
      </div>

      <button type="button" class="link-toggle" (click)="showDetails = !showDetails">
        {{ showDetails ? 'Hide details' : 'Add details (optional)' }}
      </button>

      @if (showDetails) {
        <div class="details">
          <label for="reason">Reason <span class="muted small">(for not suspicious / false alarm)</span></label>
          <input id="reason" placeholder="e.g. staff restocking shelves" [(ngModel)]="reasonCode" />
          <label for="notes">Notes</label>
          <textarea id="notes" placeholder="Anything else for the record…" [(ngModel)]="notes" rows="2"></textarea>
        </div>
      }

      @if (validationError || error) {
        <app-error-banner [message]="validationError || error" />
      }
      @if (saved) {
        <p class="ok" role="status">Review saved.</p>
      }
    </div>
  `,
  styles: [`
    .review-actions { display: flex; flex-direction: column; gap: 10px; }
    .hint { margin: 0; }
    .action-row { display: flex; flex-wrap: wrap; gap: 8px; }
    .action-row button { min-height: 44px; }
    button.primary { background: var(--accent); color: white; border: none; border-radius: var(--radius-sm); padding: 0.5rem 1rem; font-weight: 600; cursor: pointer; }
    button.primary:hover { background: var(--accent-2); }
    button.primary:disabled { opacity: 0.6; cursor: not-allowed; }
    button.subtle { color: var(--text-muted); }
    .link-toggle {
      background: none; border: none; color: var(--accent); padding: 0; font-size: 0.85rem; cursor: pointer; text-align: left; width: fit-content;
    }
    .details { display: flex; flex-direction: column; gap: 8px; }
    .details label { font-size: 0.85rem; color: var(--text-muted); }
    textarea { width: 100%; }
    .ok { color: var(--success); margin: 0; font-size: 0.9rem; }
  `],
})
export class ReviewActionsComponent {
  @Input() saving = false;
  @Input() error = '';
  @Input() saved = false;
  @Output() review = new EventEmitter<{ action: ReviewAction; reasonCode?: string; notes?: string }>();

  showDetails = false;
  reasonCode = '';
  notes = '';

  validationError = '';

  submit(action: ReviewAction): void {
    if ((action === 'Dismiss' || action === 'FalsePositive') && !this.reasonCode.trim()) {
      this.showDetails = true;
      this.validationError = 'Please add a short reason for this decision.';
      return;
    }
    this.validationError = '';
    this.review.emit({
      action,
      reasonCode: this.reasonCode.trim() || undefined,
      notes: this.notes.trim() || undefined,
    });
  }
}
