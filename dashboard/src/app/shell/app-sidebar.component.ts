import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { NAV_SECTIONS, NavItem } from '../shared/nav.config';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <aside class="sidebar" [class.open]="open" aria-label="Main navigation">
      <nav>
        @for (section of sections; track section.label) {
          <div class="nav-section-label">{{ section.label }}</div>
          @for (item of section.items; track item.route) {
            @if (!item.adminOnly || auth.isAdmin()) {
              <a [routerLink]="item.route" routerLinkActive="active" (click)="navigate.emit()">
                <span class="icon" [attr.data-icon]="item.icon"></span>
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
                }
                {{ item.label }}
              </a>
            }
          }
        }
      </nav>
    </aside>
  `,
  styles: [`
    .sidebar {
      width: 240px;
      background: var(--surface);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 12px 10px;
      overflow-y: auto;
      flex-shrink: 0;
    }
    nav { display: flex; flex-direction: column; gap: 2px; }
    nav a {
      color: var(--text-muted);
      text-decoration: none;
      padding: 10px 12px;
      border-radius: var(--radius-sm);
      font-size: 0.92rem;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 10px;
      border-left: 2px solid transparent;
      transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
      min-height: 44px;
    }
    nav a:hover { background: var(--accent-soft); color: var(--text); }
    nav a.active {
      background: var(--accent-soft);
      color: var(--accent-2);
      border-left: 2px solid var(--accent);
    }
    .svg-icon { width: 16px; height: 16px; flex-shrink: 0; }
    .icon { display: none; }
    @media (max-width: 991px) {
      .sidebar {
        position: fixed;
        top: 56px;
        left: 0;
        bottom: 0;
        z-index: 50;
        transform: translateX(-100%);
        transition: transform 0.2s ease;
        box-shadow: var(--shadow);
      }
      .sidebar.open { transform: translateX(0); }
    }
  `],
})
export class AppSidebarComponent {
  @Input() open = false;
  @Output() navigate = new EventEmitter<void>();
  readonly sections = NAV_SECTIONS;

  constructor(public auth: AuthService) {}
}
