import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { LiveAlertsService } from '../core/live-alerts.service';
import { StoreContextService } from '../core/store-context.service';

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [FormsModule],
  template: `
    <header class="topbar">
      <div class="left">
        <button
          class="ghost menu-btn"
          type="button"
          aria-label="Toggle menu"
          [attr.aria-expanded]="sidebarOpen"
          (click)="menuToggle.emit()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <div class="brand">onetix</div>
      </div>
      <div class="center">
        <label class="store-label muted small" for="store-select">Store:</label>
        <select
          id="store-select"
          [ngModel]="storeCtx.storeId()"
          (ngModelChange)="onStoreChange($event)"
          aria-label="Store filter">
          <option value="">All stores</option>
          @for (s of storeCtx.stores(); track s.id) {
            <option [value]="s.id">{{ s.name }}</option>
          }
        </select>
        <span class="live-badge" [class.connected]="live.connected()" aria-live="polite">
          <span class="dot"></span>{{ live.connected() ? 'Live' : 'Offline' }}
        </span>
      </div>
      <div class="right">
        <span class="role-mobile">{{ auth.role() }}</span>
        <div class="user-block">
          <span class="email muted">{{ auth.email() }}</span>
          <span class="role">{{ auth.role() }}</span>
        </div>
        <button class="ghost" type="button" (click)="logout()">Sign out</button>
      </div>
    </header>
  `,
  styles: [`
    .topbar {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 0 16px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      flex-shrink: 0;
    }
    .left, .center, .right { display: flex; align-items: center; gap: 12px; }
    .center { flex: 1; justify-content: center; }
    .menu-btn { display: none; padding: 8px; min-width: 44px; min-height: 44px; }
    .brand {
      font-weight: 700;
      font-size: 1.15rem;
      letter-spacing: -0.02em;
      color: var(--text);
    }
    .store-label { white-space: nowrap; }
    .user-block { display: flex; flex-direction: column; align-items: flex-end; line-height: 1.2; }
    .email { font-size: 0.78rem; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .role {
      color: var(--text-muted);
      text-transform: uppercase;
      font-size: 0.65rem;
      letter-spacing: 0.08em;
      font-weight: 600;
    }
    select { min-width: 140px; max-width: 220px; }
    .role-mobile {
      display: none;
      color: var(--text-muted);
      text-transform: uppercase;
      font-size: 0.65rem;
      letter-spacing: 0.08em;
      font-weight: 600;
    }
    @media (max-width: 991px) {
      .menu-btn { display: inline-flex; align-items: center; justify-content: center; }
      .center { justify-content: flex-start; }
      .user-block { display: none; }
      .role-mobile { display: inline-block; }
    }
    @media (max-width: 600px) {
      .center select { max-width: 120px; }
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
