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
        <div class="brand">ONEVO</div>
        <nav>
          <a routerLink="/alerts" routerLinkActive="active">Alerts</a>
          <a routerLink="/setup" routerLinkActive="active">Setup &amp; Zones</a>
          <a routerLink="/tuning" routerLinkActive="active">Tuning</a>
          <a routerLink="/health" routerLinkActive="active">Health</a>
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
    .layout { display:flex; min-height:100vh; }
    .sidebar { width:220px; background:#12161c; border-right:1px solid #222; display:flex; flex-direction:column; padding:1rem; }
    .brand { font-weight:700; font-size:1.3rem; margin-bottom:1.5rem; }
    nav { display:flex; flex-direction:column; gap:.25rem; }
    nav a { color:#cfd3d8; text-decoration:none; padding:.5rem .6rem; border-radius:6px; }
    nav a:hover { background:#1b2027; }
    nav a.active { background:#22303f; color:#8ab4f8; }
    .spacer { flex:1; }
    .user { font-size:.85rem; display:flex; flex-direction:column; gap:.25rem; }
    .role { color:#8ab4f8; text-transform:uppercase; font-size:.7rem; }
    .content { flex:1; padding:1.5rem 2rem; overflow:auto; }
  `],
})
export class ShellComponent {
  constructor(public auth: AuthService, private router: Router) {}
  logout(): void { this.auth.logout(); this.router.navigate(['/login']); }
}
