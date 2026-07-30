import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { PageContainerComponent, PageHeaderComponent } from '../../shared/ui-components';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule, RouterLink, PageContainerComponent, PageHeaderComponent],
  template: `
    <app-page-container>
      <app-page-header title="Settings" subtitle="Account and security." />
      <div class="card form-card">
        <h3>Change password</h3>
        <label for="cur">Current password</label>
        <input id="cur" type="password" [(ngModel)]="currentPassword" />
        <label for="new">New password</label>
        <input id="new" type="password" [(ngModel)]="newPassword" />
        <button type="button" (click)="save()" [disabled]="saving">{{ saving ? 'Saving…' : 'Update password' }}</button>
        @if (message) { <p class="ok" role="status">{{ message }}</p> }
        @if (error) { <p class="err" role="alert">{{ error }}</p> }
      </div>
      <div class="card muted">
        Signed in as <strong>{{ auth.email() }}</strong> ({{ auth.role() }}).
      </div>
      @if (auth.isAdmin()) {
        <div class="card advanced-links">
          <h3>Advanced</h3>
          <p class="muted small">Admin-only tools for setup, tuning, and system health.</p>
          <nav class="link-grid">
            <a routerLink="/app/setup">Setup &amp; Zones</a>
            <a routerLink="/app/admin">Admin</a>
            <a routerLink="/app/reports">Reports</a>
            <a routerLink="/app/health">Health</a>
            <a routerLink="/app/logs">Logs</a>
            <a routerLink="/app/tuning">Tuning</a>
          </nav>
        </div>
      }
    </app-page-container>
  `,
  styles: [`
    .form-card { max-width: 420px; display: flex; flex-direction: column; gap: 8px; }
    .form-card h3 { margin: 0 0 8px; font-size: 0.95rem; }
    label { display: flex; flex-direction: column; gap: 4px; }
    .ok { color: var(--success); font-size: 0.9rem; }
    .err { color: var(--danger); font-size: 0.9rem; }
    .muted { color: var(--text-muted); font-size: 0.9rem; }
    .advanced-links h3 { margin: 0 0 4px; font-size: 0.95rem; }
    .link-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; margin-top: 12px; }
    .link-grid a {
      padding: 10px 12px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border);
      text-decoration: none;
      color: var(--text);
      font-size: 0.9rem;
      background: var(--surface-2);
    }
    .link-grid a:hover { border-color: var(--accent); color: var(--accent-2); }
  `],
})
export class SettingsComponent {
  currentPassword = '';
  newPassword = '';
  saving = false;
  message = '';
  error = '';

  constructor(public auth: AuthService, private api: ApiService) {}

  save(): void {
    this.saving = true;
    this.message = '';
    this.error = '';
    this.api.changePassword(this.currentPassword, this.newPassword).subscribe({
      next: () => {
        this.saving = false;
        this.message = 'Password updated successfully.';
        this.currentPassword = '';
        this.newPassword = '';
      },
      error: (e) => {
        this.saving = false;
        this.error = e?.error?.error || 'Failed to update password';
      },
    });
  }
}
