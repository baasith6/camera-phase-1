import { Component, Input } from '@angular/core';
import { pillClass, pillLabel } from './alert-labels';

/* Full literal class strings — Tailwind v4 scans source text, never concatenate. */
const PILL_BASE = 'inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[0.72rem] font-semibold';
const PILL_TONES: Record<string, string> = {
  pending: 'bg-warning-soft text-warning border border-[rgba(251,191,36,0.3)]',
  confirmed: 'bg-danger-soft text-danger border border-[rgba(248,113,113,0.3)]',
  dismissed: 'bg-surface-2 text-ink-muted border border-border-strong',
  falsepos: 'bg-surface-2 text-ink-muted border border-border-strong',
  followup: 'bg-accent-soft text-accent-2 border border-accent-soft',
};

@Component({
  selector: 'app-status-pill',
  standalone: true,
  template: `<span [class]="cls">{{ text }}</span>`,
})
export class StatusPillComponent {
  @Input({ required: true }) status = '';

  get cls(): string {
    const tone = PILL_TONES[pillClass(this.status)] ?? PILL_TONES['dismissed'];
    return `${PILL_BASE} ${tone}`;
  }

  get text(): string {
    return pillLabel(this.status);
  }
}
