import { Component, Input } from '@angular/core';

/* Full literal class strings — Tailwind v4 scans source text, never concatenate. */
const BADGE_BASE = 'inline-block rounded-full px-2 py-0.5 text-xs font-semibold';
const BADGE_TONES: Record<string, string> = {
  high: 'bg-danger-soft text-danger border border-[rgba(248,113,113,0.3)]',
  medium: 'bg-warning-soft text-warning border border-[rgba(251,191,36,0.3)]',
  low: 'bg-info-soft text-info border border-[rgba(167,139,250,0.3)]',
  none: 'bg-warning-soft text-warning border border-[rgba(251,191,36,0.3)]',
  uploaded: 'bg-warning-soft text-warning border border-[rgba(251,191,36,0.3)]',
  analyzed: 'bg-success-soft text-success border border-[rgba(52,211,153,0.3)]',
  online: 'bg-success-soft text-success border border-[rgba(52,211,153,0.3)]',
  pending: 'bg-surface-2 text-ink-muted border border-border-strong',
  processing: 'bg-surface-2 text-ink-muted border border-border-strong',
  offline: 'bg-surface-2 text-ink-muted border border-border-strong',
};

@Component({
  selector: 'app-status-badge',
  standalone: true,
  template: `<span [class]="cls">{{ label || level }}</span>`,
})
export class StatusBadgeComponent {
  @Input({ required: true }) level = '';
  @Input() label = '';

  get cls(): string {
    const tone = BADGE_TONES[this.level.toLowerCase()] ?? BADGE_TONES['pending'];
    return `${BADGE_BASE} ${tone}`;
  }
}
