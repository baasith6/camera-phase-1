import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';
import { ApiService } from '../../core/api.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h2>Account Settings</h2>
    <div class="card">
      <h3>Change password</h3>
      <label>Current password<input type="password" [(ngModel)]="currentPassword" /></label>
      <label>New password<input type="password" [(ngModel)]="newPassword" /></label>
      <button (click)="save()" [disabled]="saving">{{ saving ? 'Saving…' : 'Update password' }}</button>
      @if (message) { <p class="ok">{{ message }}</p> }
      @if (error) { <p class="err">{{ error }}</p> }
    </div>
    <div class="card muted">
      Signed in as <strong>{{ auth.email() }}</strong> ({{ auth.role() }}).
    </div>
  `,
  styles: [`
    .card { margin-bottom:1rem; display:flex; flex-direction:column; gap:.65rem; max-width:420px; }
    label { display:flex; flex-direction:column; gap:.25rem; font-size:.85rem; }
    input { padding:.45rem .55rem; border-radius:var(--radius-sm); border:1px solid var(--border-strong); background:var(--surface-2); color:var(--text); }
    button { align-self:flex-start; padding:.45rem .85rem; border-radius:var(--radius-sm); border:1px solid var(--accent); background:var(--accent-soft); color:var(--accent-2); cursor:pointer; }
    .ok { color:var(--success); }
    .err { color:var(--danger); }
    .muted { color:var(--text-muted); font-size:.9rem; }
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
