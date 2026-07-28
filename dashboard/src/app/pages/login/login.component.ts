import { Component, isDevMode } from '@angular/core';

import { FormsModule } from '@angular/forms';

import { Router } from '@angular/router';

import { forkJoin, of } from 'rxjs';

import { catchError, switchMap } from 'rxjs/operators';

import { AuthService } from '../../core/auth.service';

import { ApiService } from '../../core/api.service';



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

        @if (showDevHint) {

          <p class="muted hint">Default dev login: admin&#64;onevo.local / Admin123!</p>

        }

        <p class="muted hint"><a class="back" href="/">← Back to home</a></p>

      </form>

    </div>

  `,

  styles: [`

    .login-wrap { display:flex; justify-content:center; align-items:center; min-height:100vh; }

    .login-card {

      width: 350px; display:flex; flex-direction:column; gap:.5rem;

      border:1px solid var(--border-strong);

      box-shadow: 0 0 40px rgba(139,92,246,.12), 0 8px 32px rgba(0,0,0,.4);

      padding:1.75rem 1.5rem;

    }

    h1 {

      margin:0; letter-spacing:.04em;

      background:linear-gradient(120deg, var(--accent-2), var(--accent), #c4b5fd);

      -webkit-background-clip:text; background-clip:text; color:transparent;

    }

    .hint { font-size:.8rem; margin-top:.5rem; }

    .back { color: var(--accent-2); text-decoration: none; }

    .error { color:var(--danger); }

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

    private api: ApiService,

    private router: Router,

  ) {}



  submit(): void {

    this.loading = true;

    this.error = '';

    this.auth.login(this.email, this.password).pipe(

      switchMap(() => this.resolvePostLoginRoute()),

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



  /** Admin/Installer always land on onboarding; Managers skip if store is already wired up. */

  private resolvePostLoginRoute() {

    const role = (this.auth.role() ?? '').toLowerCase();

    if (role === 'admin' || role === 'installer') {

      return of(['/app/get-started']);

    }

    if (role !== 'manager') {

      return of(['/app/get-started']);

    }



    const storeId = this.auth.storeId();

    if (!storeId) return of(['/app/get-started']);



    return forkJoin({

      cameras: this.api.listCameras(storeId).pipe(catchError(() => of([]))),

      connectors: this.api.listConnectors(storeId).pipe(catchError(() => of([]))),

    }).pipe(

      switchMap(({ cameras, connectors }) => {

        const online = connectors.some((c) =>

          (c.status === 'Healthy' || c.status === 'Degraded') && c.lastHeartbeat);

        const complete = cameras.length > 0 && online;

        return of(complete ? ['/app/alerts'] : ['/app/get-started']);

      }),

    );

  }

}

