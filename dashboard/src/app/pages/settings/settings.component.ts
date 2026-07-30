import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { PageContainerComponent, PageHeaderComponent } from '../../shared/ui-components';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule, PageContainerComponent, PageHeaderComponent],
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
    </app-page-container>
  `,
  styles: [`
    .form-card { max-width: 420px; display: flex; flex-direction: column; gap: 8px; }
    .form-card h3 { margin: 0 0 8px; font-size: 0.95rem; }
    label { display: flex; flex-direction: column; gap: 4px; }
    .ok { color: var(--success); font-size: 0.9rem; }
    .err { color: var(--danger); font-size: 0.9rem; }
    .muted { color: var(--text-muted); font-size: 0.9rem; }
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
