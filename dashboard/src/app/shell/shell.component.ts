import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet, Router } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="layout">
      <aside class="sidebar">
        <div class="brand"><span class="brand-mark">◆</span> ONEVO</div>
        <nav>
          <a routerLink="/alerts" routerLinkActive="active">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            Alerts
          </a>
          <a routerLink="/setup" routerLinkActive="active">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
            Setup &amp; Zones
          </a>
          <a routerLink="/tuning" routerLinkActive="active">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
            Tuning
          </a>
          <a routerLink="/health" routerLinkActive="active">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            Health
          </a>
        </nav>
        <div class="spacer"></div>
        <div class="user">
          <div class="muted">{{ auth.email() }}</div>
          <div class="role">{{ auth.role() }}</div>
          <button class="ghost" (click)="logout()">Sign out</button>
        </div>
      </aside>
      <main class="content"><router-outlet></router-outlet></main>
    </div>
  `,
  styles: [`
    .layout { display:flex; height:100vh; overflow:hidden; }
    .sidebar {
      width:230px; background:var(--surface); border-right:1px solid var(--border);
      display:flex; flex-direction:column; padding:1.25rem 1rem;
    }
    .brand {
      font-weight:700; font-size:1.35rem; margin-bottom:1.75rem; letter-spacing:.04em;
      background:linear-gradient(120deg, var(--accent-2), var(--accent), #c4b5fd);
      -webkit-background-clip:text; background-clip:text; color:transparent;
      display:flex; align-items:center; gap:.4rem;
    }
    .brand-mark { font-size:1rem; filter:drop-shadow(0 0 8px var(--accent-glow)); }
    nav { display:flex; flex-direction:column; gap:.3rem; }
    nav a {
      color:var(--text-muted); text-decoration:none; padding:.55rem .7rem;
      border-radius:var(--radius-sm); font-size:.92rem; font-weight:500;
      display:flex; align-items:center; gap:.6rem;
      border-left:2px solid transparent;
      transition:background .15s ease, color .15s ease, border-color .15s ease;
    }
    nav a .icon { width:16px; height:16px; flex-shrink:0; opacity:.8; }
    nav a.active .icon { opacity:1; filter:drop-shadow(0 0 6px var(--accent-glow)); }
    nav a:hover { background:var(--accent-soft); color:var(--text); }
    nav a.active {
      background:var(--accent-soft); color:var(--accent-2);
      border-left:2px solid var(--accent);
      box-shadow:inset 0 0 20px rgba(139,92,246,.06);
    }
    .spacer { flex:1; }
    .user {
      font-size:.85rem; display:flex; flex-direction:column; gap:.3rem;
      padding-top:1rem; border-top:1px solid var(--border);
    }
    .role {
      color:var(--accent-2); text-transform:uppercase; font-size:.68rem;
      letter-spacing:.08em; font-weight:600;
    }
    .content { flex:1; padding:1.5rem 2rem; overflow:auto; min-height:0; }
  `],
})
export class ShellComponent {
  constructor(public auth: AuthService, private router: Router) {}
  logout(): void { this.auth.logout(); this.router.navigate(['/login']); }
}
