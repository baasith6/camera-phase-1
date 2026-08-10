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
    <div class="flex flex-col gap-2.5">
      @if (detectedPatterns.length) {
        <div class="flex flex-col gap-1.5">
          <span class="text-[0.72rem] font-semibold uppercase tracking-[0.05em] text-accent">AI detected</span>
          <div class="flex flex-wrap gap-1.5">
            @for (p of detectedPatterns; track p) {
              <span
                class="inline-flex max-w-full items-center overflow-hidden text-ellipsis whitespace-nowrap rounded-full border border-accent px-2.5 py-[3px] text-[0.78rem] text-accent"
                [title]="label(p)">{{ label(p) }}</span>
            }
          </div>
        </div>
      }

      @if (patterns.length) {
        <!-- .patterns/.chip-grid are marker classes only (e2e queries them). -->
        <fieldset class="patterns m-0 rounded-ctl border border-border px-3 pb-3 pt-2.5">
          <legend class="px-1 text-[0.85rem] font-semibold" title="AI-detected ones are pre-selected — untick anything wrong, tick anything missed.">
            Patterns you can see in this clip
          </legend>
          <div class="chip-grid flex flex-wrap gap-2">
            @for (p of patterns; track p) {
              <!-- .chip/.on are marker classes only (e2e verify-training.spec.ts queries them). -->
              <label
                class="chip inline-flex min-w-0 max-w-full cursor-pointer select-none items-center gap-1.5 rounded-full border px-3 py-1.5 text-[0.85rem] transition-colors"
                [class.on]="selected.has(p)"
                [class]="selected.has(p)
                  ? 'border-accent bg-accent text-white'
                  : 'border-border-strong hover:border-accent'"
                [title]="label(p)">
                <input
                  class="sr-only"
                  type="checkbox"
                  [checked]="selected.has(p)"
                  (change)="toggle(p)" />
                <span class="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{{ label(p) }}</span>
              </label>
            }
          </div>
        </fieldset>
      }

      <div class="flex flex-wrap gap-2">
        <button type="button" class="min-h-11 px-4 font-semibold" (click)="submit('Confirm')" [disabled]="saving">
          Confirm incident
        </button>
        <button type="button" class="ghost min-h-11" (click)="submit('Dismiss')" [disabled]="saving">
          Not suspicious
        </button>
        <button type="button" class="ghost min-h-11" (click)="submit('FalsePositive')" [disabled]="saving">
          False alarm
        </button>
        <button type="button" class="ghost min-h-11 !text-ink-muted" (click)="submit('NeedsFollowUp')" [disabled]="saving">
          Needs follow-up
        </button>
      </div>

      <button
        type="button"
        class="w-fit border-none !bg-transparent !p-0 text-left text-[0.85rem] !text-accent"
        (click)="showDetails = !showDetails">
        {{ showDetails ? 'Hide details' : 'Add details (optional)' }}
      </button>

      @if (showDetails) {
        <div class="flex flex-col gap-2">
          <label for="reason">Reason <span class="muted small">(for not suspicious / false alarm)</span></label>
          <input id="reason" placeholder="e.g. staff restocking shelves" [(ngModel)]="reasonCode" />
          <label for="notes">Notes</label>
          <textarea id="notes" class="w-full" placeholder="Anything else for the record…" [(ngModel)]="notes" rows="2"></textarea>
        </div>
      }

      @if (validationError || error) {
        <app-error-banner [message]="validationError || error" />
      }
      @if (saved) {
        <p class="m-0 text-[0.9rem] text-success" role="status">Review saved.</p>
      }
    </div>
  `,
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
