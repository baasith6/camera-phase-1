import { Component, isDevMode } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { AuthService } from '../../core/auth.service';
import { BrandLogoComponent } from '../../shared/brand-logo.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, BrandLogoComponent],
  template: `
    <div class="flex min-h-screen items-center justify-center bg-bg p-6">
      <form class="card flex w-full max-w-[380px] flex-col gap-2 !mb-0 !px-7 !py-8 shadow-pop" (ngSubmit)="submit()">
        <app-brand-logo size="lg" class="mb-1" />
        <p class="muted">Sign in to review store alerts</p>
        <label for="email">Email</label>
        <input id="email" [(ngModel)]="email" name="email" type="email" autocomplete="username" />
        <label for="password">Password</label>
        <input id="password" [(ngModel)]="password" name="password" type="password" autocomplete="current-password" />
        <button type="submit" [disabled]="loading">{{ loading ? 'Signing in…' : 'Sign in' }}</button>
        @if (error) { <p class="text-[0.9rem] text-danger" role="alert">{{ error }}</p> }
        @if (showDevHint) {
          <p class="muted mt-2 text-[0.82rem]">Dev: admin&#64;onevo.local / Admin123!</p>
        }
        <p class="muted mt-2 text-[0.82rem]"><a href="/">Back to home</a></p>
      </form>
    </div>
  `,
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
