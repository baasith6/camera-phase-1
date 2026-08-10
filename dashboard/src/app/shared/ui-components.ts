import { Component, EventEmitter, Input, Output } from '@angular/core';

export { PageHeaderComponent } from './page-header.component';
export { StatusBadgeComponent } from './status-badge.component';
export { StatusPillComponent } from './status-pill.component';
export { ChartComponent } from './chart.component';
export { DataTableComponent } from './data-table.component';
export { BrandLogoComponent } from './brand-logo.component';

@Component({
  selector: 'app-page-container',
  standalone: true,
  template: `<div class="mx-auto max-w-7xl"><ng-content></ng-content></div>`,
})
export class PageContainerComponent {}

@Component({
  selector: 'app-empty-state',
  standalone: true,
  template: `
    <div class="card text-center py-10 px-4">
      <div
        class="w-13 h-13 mx-auto mb-3 rounded-full flex items-center justify-center bg-success-soft text-success border border-[rgba(52,211,153,0.3)]"
        aria-hidden="true">
        <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
    <div
      class="mb-3 flex items-center justify-between gap-3 rounded-[6px] border border-[rgba(248,113,113,0.3)] bg-danger-soft px-3 py-2.5 text-danger outline-none"
      role="alert">
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
    <div class="card">
      <div class="text-[0.8rem] text-ink-muted">{{ label }}</div>
      <div
        class="mt-1 text-[1.6rem] font-bold"
        [class.text-warning]="tone === 'warn'"
        [class.text-danger]="tone === 'danger'">{{ value }}</div>
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
    <div class="sticky top-0 z-[5] mb-3 flex flex-wrap items-center gap-3 rounded-[6px] border border-border bg-surface-2 px-3 py-2.5">
      <label class="flex cursor-pointer items-center gap-1.5 text-[0.85rem]">
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
  template: `<div class="flex flex-wrap items-center gap-2"><ng-content></ng-content></div>`,
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
  styles: [`
    /* Slide-in animation — keyframes stay as component CSS. */
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 100;
      background: var(--surface);
      border: 1px solid var(--accent);
      border-radius: var(--radius);
      padding: 12px 16px;
      font-size: 0.88rem;
      cursor: pointer;
      box-shadow: 0 0 24px var(--accent-glow), 0 8px 24px rgba(0, 0, 0, 0.4);
      animation: slideIn 0.3s ease;
    }
    @keyframes slideIn {
      from { transform: translateX(120%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
  `],
})
export class ToastComponent {
  @Input() message = '';
  @Output() dismiss = new EventEmitter<void>();
}
