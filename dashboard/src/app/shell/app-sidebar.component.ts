import { Component, EventEmitter, Input, Output, computed } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { LiveAlertsService } from '../core/live-alerts.service';
import { navSectionsForRole } from '../shared/nav.config';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <aside class="sidebar" [class.open]="open" aria-label="Main navigation">
      <nav>
        @for (section of sections(); track section.label) {
          <div class="nav-section-label">{{ section.label }}</div>
          @for (item of section.items; track item.route) {
            <a [routerLink]="item.route" routerLinkActive="active" (click)="navigate.emit()">
                @switch (item.icon) {
                  @case ('bell') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
                  }
                  @case ('film') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
                  }
                  @case ('clock') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                  }
                  @case ('camera') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
                  }
                  @case ('sliders') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="21" x2="4" y2="14"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="20" y1="21" x2="20" y2="16"/></svg>
                  }
                  @case ('home') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                  }
                  @case ('chart') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                  }
                  @case ('file') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  }
                  @case ('pulse') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                  }
                  @case ('list') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/></svg>
                  }
                  @case ('settings') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/></svg>
                  }
                  @case ('flask') {
                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 2v6L4.5 18a2 2 0 0 0 1.7 3h11.6a2 2 0 0 0 1.7-3L14 8V2"/><line x1="8" y1="2" x2="16" y2="2"/><line x1="7" y1="14" x2="17" y2="14"/></svg>
                  }
                }
                <span class="nav-label">{{ item.label }}</span>
                @if (item.badgeKey === 'pending' && live.pendingCount() > 0) {
                  <span class="nav-badge">{{ live.pendingCount() }} pending</span>
                }
              </a>
          }
        }
      </nav>
    </aside>
  `,
  styles: [`
    /* Background lives on :host — flex stretch sizes the host, but % height
       on the inner aside often stays content-sized (height:auto parent). */
    :host {
      display: block;
      flex-shrink: 0;
      align-self: stretch;
      width: 240px;
      min-height: 0;
      background: var(--surface);
      border-right: 1px solid var(--border);
      overflow-y: auto;
    }
    .sidebar {
      /* .sidebar + .open class names are load-bearing: shell focus trap and
         e2e smoke tests query them. Layout via Tailwind-equivalent rules. */
      width: 100%;
      min-height: 100%;
      display: flex;
      flex-direction: column;
      padding: 12px 10px;
    }
    nav { display: flex; flex-direction: column; gap: 2px; }
    .nav-section-label {
      font-size: var(--fs-xs);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      padding: 8px 10px 4px;
      opacity: 0.85;
    }
    nav a {
      color: var(--text-muted);
      text-decoration: none;
      padding: 7px 12px;
      border-radius: var(--radius-sm);
      font-size: var(--fs-md);
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 10px;
      border-left: 2px solid transparent;
      transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
      min-height: 36px;
    }
    nav a:hover { background: var(--accent-soft); color: var(--text); }
    nav a.active {
      background: var(--accent-soft);
      color: var(--accent-2);
      border-left: 2px solid var(--accent);
    }
    .nav-label { flex: 1; }
    .nav-badge {
      font-size: var(--fs-xs);
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-2);
      white-space: nowrap;
    }
    .svg-icon { width: 16px; height: 16px; flex-shrink: 0; }
    @media (max-width: 1023.98px) {
      :host {
        /* Drawer is position:fixed on .sidebar; host should not reserve width. */
        width: 0;
        border-right: none;
        background: transparent;
        overflow: visible;
      }
      .sidebar {
        position: fixed;
        top: 56px;
        left: 0;
        bottom: 0;
        width: 240px;
        min-height: 0;
        height: auto;
        background: var(--surface);
        border-right: 1px solid var(--border);
        overflow-y: auto;
        z-index: 50;
        transform: translateX(-100%);
        transition: transform 0.2s ease;
        box-shadow: var(--shadow);
      }
      .sidebar.open { transform: translateX(0); }
      /* Touch targets stay 44px on mobile. */
      nav a { min-height: 44px; padding: 10px 12px; }
    }
  `],
})
export class AppSidebarComponent {
  @Input() open = false;
  @Output() navigate = new EventEmitter<void>();

  /* Reactive: recomputes when the auth role signal changes (e.g. sign-out →
     sign-in as a different role without a full page reload). */
  readonly sections = computed(() => navSectionsForRole(this.auth.isAdmin()));

  constructor(
    public auth: AuthService,
    public live: LiveAlertsService,
  ) {}
}
