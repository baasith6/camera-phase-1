import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-brand-logo',
  standalone: true,
  template: `
    <span
      class="brand-logo inline-flex items-center gap-2 select-none"
      [class.brand-logo--lg]="size === 'lg'"
      [class.brand-logo--sm]="size === 'sm'"
      [attr.aria-label]="ariaLabel">
      <svg
        class="brand-mark shrink-0"
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true">
        <!-- Outer ring — lens / focus -->
        <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2.25" class="text-accent" />
        <!-- Inner disc -->
        <circle cx="16" cy="16" r="7.5" fill="currentColor" class="text-accent" />
        <!-- Tick — “one tix” -->
        <path
          d="M12.2 16.2l2.4 2.4 5.2-5.6"
          stroke="white"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-linejoin="round" />
      </svg>
      <span class="brand-wordmark font-semibold tracking-tight text-ink leading-none">
        one<span class="text-accent">tix</span>
      </span>
    </span>
  `,
  styles: [`
    :host {
      display: inline-flex;
      line-height: 1;
      justify-content: inherit;
    }
    :host(.justify-center) { justify-content: center; width: 100%; }
    .brand-logo--sm .brand-mark { width: 22px; height: 22px; }
    .brand-logo--sm .brand-wordmark { font-size: var(--fs-xl); letter-spacing: -0.03em; }
    .brand-logo--lg .brand-mark { width: 34px; height: 34px; }
    .brand-logo--lg .brand-wordmark { font-size: var(--fs-2xl); letter-spacing: -0.035em; }
  `],
})
export class BrandLogoComponent {
  /** `sm` = top bar; `lg` = login / welcome hero. */
  @Input() size: 'sm' | 'lg' = 'sm';
  @Input() ariaLabel = 'onetix';
}
