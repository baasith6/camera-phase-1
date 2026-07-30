import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-page-header',
  standalone: true,
  template: `
    <header class="page-header">
      @if (breadcrumb) {
        <nav class="breadcrumb muted small" aria-label="Breadcrumb">{{ breadcrumb }}</nav>
      }
      <div class="header-row">
        <div class="title-block">
          <h2>{{ title }}</h2>
          @if (subtitle) {
            <p class="muted subtitle">{{ subtitle }}</p>
          }
        </div>
        <div class="actions"><ng-content select="[actions]"></ng-content></div>
      </div>
      <ng-content select="[hint]"></ng-content>
      <ng-content select="[below]"></ng-content>
    </header>
  `,
  styles: [`
    .page-header { margin-bottom: var(--space-md, 16px); }
    .page-header h2 { margin: 0; font-size: 1.35rem; letter-spacing: -0.02em; }
    .title-block { flex: 1; min-width: 0; }
    .breadcrumb { margin-bottom: 4px; }
    .subtitle { margin: 6px 0 0; font-size: 0.9rem; line-height: var(--line-height, 1.55); }
    .header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: var(--space-md, 16px);
      flex-wrap: wrap;
    }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  `],
})
export class PageHeaderComponent {
  @Input({ required: true }) title = '';
  @Input() breadcrumb = '';
  @Input() subtitle = '';
}
