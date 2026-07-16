import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="login-wrap">
      <form class="card login-card" (ngSubmit)="submit()">
        <h1>ONEVO</h1>
        <p class="muted">Retail Loss Prevention — Staff Console</p>
        <label>Email</label>
        <input [(ngModel)]="email" name="email" type="email" autocomplete="username" />
        <label>Password</label>
        <input [(ngModel)]="password" name="password" type="password" autocomplete="current-password" />
        <button type="submit" [disabled]="loading">{{ loading ? 'Signing in...' : 'Sign in' }}</button>
        @if (error) { <p class="error">{{ error }}</p> }
        <p class="muted hint">Default dev login: admin&#64;onevo.local / Admin123!</p>
      </form>
    </div>
  `,
  styles: [`
    .login-wrap { display:flex; justify-content:center; align-items:center; min-height:100vh; }
    .login-card { width: 340px; display:flex; flex-direction:column; gap:.5rem; }
    h1 { margin:0; }
    .hint { font-size:.8rem; margin-top:.5rem; }
    .error { color:#ff6b6b; }
  `],
})
export class LoginComponent {
  email = 'admin@onevo.local';
  password = 'Admin123!';
  loading = false;
  error = '';

  constructor(private auth: AuthService, private router: Router) {}

  submit(): void {
    this.loading = true;
    this.error = '';
    this.auth.login(this.email, this.password).subscribe({
      next: () => { this.loading = false; this.router.navigate(['/alerts']); },
      error: (e) => { this.loading = false; this.error = e?.error?.error || 'Login failed'; },
    });
  }
}
