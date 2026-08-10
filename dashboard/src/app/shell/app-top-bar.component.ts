import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { LiveAlertsService } from '../core/live-alerts.service';
import { StoreContextService } from '../core/store-context.service';
import { BrandLogoComponent } from '../shared/brand-logo.component';

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [FormsModule, BrandLogoComponent],
  template: `
    <header class="h-14 shrink-0 flex items-center justify-between gap-3 px-4 border-b border-border bg-surface">
      <div class="flex items-center gap-3">
        <button
          class="ghost hidden max-lg:inline-flex items-center justify-center !p-2 min-w-11 min-h-11"
          type="button"
          aria-label="Toggle menu"
          [attr.aria-expanded]="sidebarOpen"
          (click)="menuToggle.emit()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <app-brand-logo size="sm" />
      </div>
      <div class="flex flex-1 items-center gap-3 max-lg:justify-start lg:justify-center">
        <label class="muted small whitespace-nowrap" for="store-select">Store:</label>
        <select
          id="store-select"
          class="min-w-[140px] max-w-[220px] max-sm:max-w-[120px]"
          [ngModel]="storeCtx.storeId()"
          (ngModelChange)="onStoreChange($event)"
          aria-label="Store filter">
          <option value="">All stores</option>
          @for (s of storeCtx.stores(); track s.id) {
            <option [value]="s.id">{{ s.name }}</option>
          }
        </select>
        <span
          class="live-badge inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border"
          [class.connected]="live.connected()"
          [class]="live.connected()
            ? 'bg-success-soft text-success border-success/30'
            : 'bg-surface-2 text-ink-muted border-border-strong'"
          aria-live="polite">
          <span class="dot w-[7px] h-[7px] rounded-full bg-current"></span>{{ live.connected() ? 'Live' : 'Offline' }}
        </span>
      </div>
      <div class="flex items-center gap-3">
        <span class="lg:hidden text-ink-muted uppercase text-[0.65rem] tracking-[0.08em] font-semibold">{{ auth.role() }}</span>
        <div class="max-lg:hidden flex flex-col items-end leading-tight">
          <span class="muted text-[0.78rem] max-w-40 overflow-hidden text-ellipsis whitespace-nowrap">{{ auth.email() }}</span>
          <span class="text-ink-muted uppercase text-[0.65rem] tracking-[0.08em] font-semibold">{{ auth.role() }}</span>
        </div>
        <button class="ghost" type="button" (click)="logout()">Sign out</button>
      </div>
    </header>
  `,
  styles: [`
    /* Pulse animation for the live dot — keyframes stay as component CSS. */
    .live-badge.connected .dot {
      animation: pulse 1.8s infinite;
      box-shadow: 0 0 6px currentColor;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
  `],
})
export class AppTopBarComponent {
  @Input() sidebarOpen = false;
  @Output() menuToggle = new EventEmitter<void>();
  @Output() storeChange = new EventEmitter<string>();

  constructor(
    public auth: AuthService,
    public storeCtx: StoreContextService,
    public live: LiveAlertsService,
    private router: Router,
  ) {}

  onStoreChange(id: string): void {
    this.storeCtx.setStoreId(id);
    this.storeChange.emit(id);
  }

  logout(): void {
    this.live.disconnect();
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
