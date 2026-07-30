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
        <h2>{{ title }}</h2>
        <div class="actions"><ng-content select="[actions]"></ng-content></div>
      </div>
      @if (subtitle) {
        <p class="muted small subtitle">{{ subtitle }}</p>
      }
      <ng-content select="[below]"></ng-content>
    </header>
  `,
  styles: [`
    .page-header { margin-bottom: 16px; }
    .page-header h2 { margin: 0; }
    .breadcrumb { margin-bottom: 4px; }
    .subtitle { margin: 6px 0 0; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  `],
})
export class PageHeaderComponent {
  @Input({ required: true }) title = '';
  @Input() breadcrumb = '';
  @Input() subtitle = '';
}
