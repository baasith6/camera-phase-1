import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-page-header',
  standalone: true,
  template: `
    <header class="mb-4">
      @if (breadcrumb) {
        <nav class="muted small mb-1" aria-label="Breadcrumb">{{ breadcrumb }}</nav>
      }
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0 flex-1">
          <h2 class="m-0 text-lg tracking-tight">{{ title }}</h2>
          @if (subtitle) {
            <p class="muted mt-1.5 mb-0 text-sm">{{ subtitle }}</p>
          }
        </div>
        <div class="flex flex-wrap items-center gap-2"><ng-content select="[actions]"></ng-content></div>
      </div>
      <ng-content select="[hint]"></ng-content>
      <ng-content select="[below]"></ng-content>
    </header>
  `,
})
export class PageHeaderComponent {
  @Input({ required: true }) title = '';
  @Input() breadcrumb = '';
  @Input() subtitle = '';
}
