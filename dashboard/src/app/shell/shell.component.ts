import { Component, HostListener, OnDestroy, OnInit } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, Subscription } from 'rxjs';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { LiveAlertsService } from '../core/live-alerts.service';
import { StoreContextService } from '../core/store-context.service';
import { ConfirmDialogComponent } from '../shared/confirm-dialog.component';
import { ToastComponent } from '../shared/ui-components';
import { AppSidebarComponent } from './app-sidebar.component';
import { AppTopBarComponent } from './app-top-bar.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, AppTopBarComponent, AppSidebarComponent, ToastComponent, ConfirmDialogComponent],
  template: `
    <a class="skip-link" href="#main-content">Skip to content</a>
    <div class="layout">
      <app-top-bar
        #topBar
        [sidebarOpen]="sidebarOpen"
        (menuToggle)="toggleSidebar()"
        (storeChange)="onGlobalStoreChange($event)" />
      <div class="body-row">
        <div
          class="sidebar-backdrop"
          [class.open]="sidebarOpen"
          (click)="closeSidebar()"
          aria-hidden="true"></div>
        <app-sidebar [open]="sidebarOpen" (navigate)="closeSidebar()" />
        <main id="main-content" class="content" tabindex="-1">
          <router-outlet />
        </main>
      </div>
    </div>
    <app-toast [message]="live.toastMessage()" (dismiss)="live.clearToast()" />
    <app-confirm-dialog />
  `,
  styles: [`
    .layout { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
    .body-row { display: flex; flex: 1; min-height: 0; position: relative; }
    .content { flex: 1; padding: 20px 24px; overflow: auto; min-height: 0; background: var(--bg); }
    @media (max-width: 768px) { .content { padding: 16px; } }
  `],
})
export class ShellComponent implements OnInit, OnDestroy {
  sidebarOpen = false;
  private sub?: Subscription;
  private lastFocused?: HTMLElement;

  constructor(
    private api: ApiService,
    private auth: AuthService,
    public live: LiveAlertsService,
    public storeCtx: StoreContextService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.live.connect();
    this.api.listStores().subscribe((stores) => {
      this.storeCtx.setStores(stores);
      if (!this.auth.isAdmin() && this.auth.storeId()) {
        this.storeCtx.setStoreId(this.auth.storeId()!);
      }
      this.syncStoreFromRoute();
    });
    this.sub = this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => {
        this.closeSidebar();
        this.syncStoreFromRoute();
      });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  toggleSidebar(): void {
    if (this.sidebarOpen) {
      this.closeSidebar();
      return;
    }
    this.lastFocused = document.activeElement as HTMLElement;
    this.sidebarOpen = true;
    requestAnimationFrame(() => this.focusSidebar());
  }

  closeSidebar(): void {
    if (!this.sidebarOpen) return;
    this.sidebarOpen = false;
    this.lastFocused?.focus();
    this.lastFocused = undefined;
  }

  @HostListener('document:keydown', ['$event'])
  onDocumentKeydown(event: KeyboardEvent): void {
    if (!this.sidebarOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      this.closeSidebar();
      return;
    }
    if (event.key === 'Tab') {
      this.trapFocusInSidebar(event);
    }
  }

  syncStoreFromRoute(): void {
    const tree = this.router.parseUrl(this.router.url);
    const fromRoute = tree.queryParams['storeId'] ?? '';
    if (fromRoute !== this.storeCtx.storeId()) {
      this.storeCtx.setStoreId(fromRoute);
    }
  }

  onGlobalStoreChange(storeId: string): void {
    this.storeCtx.setStoreId(storeId);
    const tree = this.router.parseUrl(this.router.url);
    if (storeId) tree.queryParams['storeId'] = storeId;
    else delete tree.queryParams['storeId'];
    this.router.navigateByUrl(tree);
  }

  private focusSidebar(): void {
    const sidebar = document.querySelector('.sidebar.open');
    const focusable = sidebar?.querySelector('a, button') as HTMLElement | null;
    focusable?.focus();
  }

  private trapFocusInSidebar(event: KeyboardEvent): void {
    const sidebar = document.querySelector('.sidebar.open');
    if (!sidebar) return;
    const focusable = Array.from(sidebar.querySelectorAll('a, button')) as HTMLElement[];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement as HTMLElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }
}
