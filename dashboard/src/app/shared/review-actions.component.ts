import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ErrorBannerComponent } from './ui-components';
import { alertTypeLabel } from './alert-labels';

export type ReviewAction = 'Confirm' | 'Dismiss' | 'FalsePositive' | 'NeedsFollowUp';

@Component({
  selector: 'app-review-actions',
  standalone: true,
  imports: [FormsModule, ErrorBannerComponent],
  template: `
    <div class="review-actions">
      @if (detectedPatterns.length) {
        <div class="ai-detected">
          <span class="ai-detected-label">AI detected</span>
          <div class="ai-detected-chips">
            @for (p of detectedPatterns; track p) {
              <span class="ai-chip" [title]="label(p)">{{ label(p) }}</span>
            }
          </div>
        </div>
      }

      @if (patterns.length) {
        <fieldset class="patterns">
          <legend title="AI-detected ones are pre-selected — untick anything wrong, tick anything missed.">
            Patterns you can see in this clip
          </legend>
          <div class="chip-grid">
            @for (p of patterns; track p) {
              <label class="chip" [class.on]="selected.has(p)" [title]="label(p)">
                <input
                  type="checkbox"
                  [checked]="selected.has(p)"
                  (change)="toggle(p)" />
                <span>{{ label(p) }}</span>
              </label>
            }
          </div>
        </fieldset>
      }

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
    .ai-detected { display: flex; flex-direction: column; gap: 6px; }
    .ai-detected-label {
      font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
      color: var(--accent);
    }
    .ai-detected-chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .ai-chip {
      display: inline-flex; align-items: center; max-width: 100%;
      padding: 3px 10px; border-radius: 999px; font-size: 0.78rem;
      border: 1px solid var(--accent); color: var(--accent);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .patterns {
      border: 1px solid var(--border, rgba(128, 128, 128, 0.25));
      border-radius: var(--radius-sm);
      padding: 10px 12px 12px;
      margin: 0;
    }
    .patterns legend { font-size: 0.85rem; font-weight: 600; padding: 0 4px; }
    .chip-grid { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 12px; border-radius: 999px; cursor: pointer;
      border: 1px solid var(--border, rgba(128, 128, 128, 0.35));
      font-size: 0.85rem; user-select: none;
      max-width: 100%; min-width: 0;
      transition: background 0.15s, border-color 0.15s;
    }
    .chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
    .chip input { position: absolute; opacity: 0; pointer-events: none; }
    .chip.on { background: var(--accent); border-color: var(--accent); color: white; }
    .chip:not(.on):hover { border-color: var(--accent); }
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
export class ReviewActionsComponent implements OnChanges {
  @Input() saving = false;
  @Input() error = '';
  @Input() saved = false;
  /** All supported patterns (from the backend enum). */
  @Input() patterns: string[] = [];
  /** Patterns the AI detected in this clip — pre-selected. */
  @Input() detectedPatterns: string[] = [];
  @Output() review = new EventEmitter<{
    action: ReviewAction; reasonCode?: string; notes?: string; confirmedPatterns?: string[];
  }>();

  showDetails = false;
  reasonCode = '';
  notes = '';

  validationError = '';

  selected = new Set<string>();

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['detectedPatterns'] || changes['patterns']) {
      // Rebuild selected as intersection of detectedPatterns and patterns
      const validDetected = this.detectedPatterns.filter(p => this.patterns.includes(p));
      this.selected = new Set(validDetected);
    }
  }

  label(pattern: string): string {
    return alertTypeLabel(pattern);
  }

  toggle(pattern: string): void {
    if (this.selected.has(pattern)) this.selected.delete(pattern);
    else this.selected.add(pattern);
    this.validationError = '';
  }

  submit(action: ReviewAction): void {
    if ((action === 'Dismiss' || action === 'FalsePositive') && !this.reasonCode.trim()) {
      this.showDetails = true;
      this.validationError = 'Please add a short reason for this decision.';
      return;
    }
    if (action === 'Confirm' && this.patterns.length && this.selected.size === 0) {
      this.validationError = 'Tick at least one pattern you actually saw in the clip.';
      return;
    }

    // Determine confirmed patterns based on action
    let confirmedPatterns: string[] | undefined;
    if (action === 'Confirm') {
      confirmedPatterns = this.patterns.length ? [...this.selected] : undefined;
    } else if (action === 'FalsePositive') {
      // False alarm means none of the detected patterns are real
      confirmedPatterns = [];
    } else if (action === 'Dismiss' || action === 'NeedsFollowUp') {
      // Dismiss and NeedsFollowUp must not send patterns
      confirmedPatterns = undefined;
    }

    this.validationError = '';
    this.review.emit({
      action,
      reasonCode: this.reasonCode.trim() || undefined,
      notes: this.notes.trim() || undefined,
      confirmedPatterns,
    });
  }
}
