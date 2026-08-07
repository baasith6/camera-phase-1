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
      <div class="card flex max-w-[420px] flex-col gap-2">
        <h3 class="m-0 mb-2 text-[0.95rem]">Change password</h3>
        <label class="flex flex-col gap-1" for="cur">Current password
          <input id="cur" type="password" [(ngModel)]="currentPassword" />
        </label>
        <label class="flex flex-col gap-1" for="new">New password
          <input id="new" type="password" [(ngModel)]="newPassword" />
        </label>
        <button type="button" (click)="save()" [disabled]="saving">{{ saving ? 'Saving…' : 'Update password' }}</button>
        @if (message) { <p class="m-0 text-[0.9rem] text-success" role="status">{{ message }}</p> }
        @if (error) { <p class="m-0 text-[0.9rem] text-danger" role="alert">{{ error }}</p> }
      </div>
      <div class="card muted text-[0.9rem]">
        Signed in as <strong>{{ auth.email() }}</strong> ({{ auth.role() }}).
      </div>
      @if (auth.isAdmin()) {
        <div class="card">
          <h3 class="m-0 mb-1 text-[0.95rem]">Advanced</h3>
          <p class="muted small">Admin-only tools for setup, tuning, and system health.</p>
          <nav class="mt-3 grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-2">
            <a class="adv-link" routerLink="/app/setup">Setup &amp; Zones</a>
            <a class="adv-link" routerLink="/app/admin">Admin</a>
            <a class="adv-link" routerLink="/app/reports">Reports</a>
            <a class="adv-link" routerLink="/app/health">Health</a>
            <a class="adv-link" routerLink="/app/logs">Logs</a>
            <a class="adv-link" routerLink="/app/tuning">Tuning</a>
          </nav>
        </div>
      }
    </app-page-container>
  `,
  styles: [`
    .adv-link {
      padding: 10px 12px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border);
      text-decoration: none;
      color: var(--text);
      font-size: 0.9rem;
      background: var(--surface-2);
    }
    .adv-link:hover { border-color: var(--accent); color: var(--accent-2); }
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
