import { Component, EventEmitter, Input, Output } from '@angular/core';

export { PageHeaderComponent } from './page-header.component';
export { StatusBadgeComponent } from './status-badge.component';
export { StatusPillComponent } from './status-pill.component';
export { ChartComponent } from './chart.component';
export { DataTableComponent } from './data-table.component';

@Component({
  selector: 'app-page-container',
  standalone: true,
  template: `<div class="page-container"><ng-content></ng-content></div>`,
})
export class PageContainerComponent {}

@Component({
  selector: 'app-empty-state',
  standalone: true,
  template: `
    <div class="card empty-state">
      <div class="empty-state-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      </div>
      <p>{{ title }}</p>
      @if (detail) { <p class="muted small">{{ detail }}</p> }
    </div>
  `,
})
export class EmptyStateComponent {
  @Input({ required: true }) title = '';
  @Input() detail = '';
}

@Component({
  selector: 'app-skeleton-list',
  standalone: true,
  template: `
    <div class="card">
      @for (i of rows; track i) { <div class="skeleton-row"></div> }
    </div>
  `,
})
export class SkeletonListComponent {
  @Input() count = 5;
  get rows(): number[] {
    return Array.from({ length: this.count }, (_, i) => i);
  }
}

@Component({
  selector: 'app-error-banner',
  standalone: true,
  template: `
    <div class="err-banner" role="alert">
      <span>{{ message }}</span>
      <ng-content></ng-content>
    </div>
  `,
})
export class ErrorBannerComponent {
  @Input({ required: true }) message = '';
}

@Component({
  selector: 'app-stat-card',
  standalone: true,
  template: `
    <div class="card stat-card">
      <div class="label">{{ label }}</div>
      <div class="value" [class.warn]="tone === 'warn'" [class.danger]="tone === 'danger'">{{ value }}</div>
    </div>
  `,
})
export class StatCardComponent {
  @Input({ required: true }) label = '';
  @Input({ required: true }) value: string | number = '';
  @Input() tone: 'default' | 'warn' | 'danger' = 'default';
}

@Component({
  selector: 'app-bulk-action-bar',
  standalone: true,
  template: `
    <div class="bulk-bar">
      <label class="select-all">
        <input type="checkbox" [checked]="allSelected" (change)="toggleAll.emit($event)" />
        Select all ({{ total }})
      </label>
      <span class="muted">{{ selectedCount }} selected</span>
      <ng-content></ng-content>
    </div>
  `,
})
export class BulkActionBarComponent {
  @Input() allSelected = false;
  @Input() total = 0;
  @Input() selectedCount = 0;
  @Output() toggleAll = new EventEmitter<Event>();
}

@Component({
  selector: 'app-filter-bar',
  standalone: true,
  template: `<div class="filters"><ng-content></ng-content></div>`,
})
export class FilterBarComponent {}

@Component({
  selector: 'app-toast',
  standalone: true,
  template: `
    @if (message) {
      <div class="toast" role="status" (click)="dismiss.emit()">{{ message }}</div>
    }
  `,
})
export class ToastComponent {
  @Input() message = '';
  @Output() dismiss = new EventEmitter<void>();
}
