import { Component, isDevMode } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="login-wrap">
      <form class="card login-card" (ngSubmit)="submit()">
        <h1>onetix</h1>
        <p class="muted">Sign in to review store alerts</p>
        <label for="email">Email</label>
        <input id="email" [(ngModel)]="email" name="email" type="email" autocomplete="username" />
        <label for="password">Password</label>
        <input id="password" [(ngModel)]="password" name="password" type="password" autocomplete="current-password" />
        <button type="submit" [disabled]="loading">{{ loading ? 'Signing in…' : 'Sign in' }}</button>
        @if (error) { <p class="error" role="alert">{{ error }}</p> }
        @if (showDevHint) {
          <p class="muted hint">Dev: admin&#64;onevo.local / Admin123!</p>
        }
        <p class="muted hint"><a class="back" href="/">Back to home</a></p>
      </form>
    </div>
  `,
  styles: [`
    .login-wrap {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: var(--bg);
      padding: 24px;
    }
    .login-card {
      width: 100%;
      max-width: 380px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 32px 28px;
      box-shadow: var(--shadow-md);
    }
    h1 {
      margin: 0;
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      color: var(--text);
    }
    .hint { font-size: 0.82rem; margin-top: 8px; }
    .back { color: var(--accent); text-decoration: none; }
    .error { color: var(--danger); font-size: 0.9rem; }
  `],
})
export class LoginComponent {
  email = isDevMode() ? 'admin@onevo.local' : '';
  password = isDevMode() ? 'Admin123!' : '';
  loading = false;
  error = '';
  showDevHint = isDevMode();

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  submit(): void {
    this.loading = true;
    this.error = '';
    this.auth.login(this.email, this.password).pipe(
      switchMap(() => of(['/app/alerts'] as [string])),
    ).subscribe({
      next: (route) => {
        this.loading = false;
        this.router.navigate(route);
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Login failed';
      },
    });
  }
}
