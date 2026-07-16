import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';
import { ShellComponent } from './shell/shell.component';
import { LoginComponent } from './pages/login/login.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'alerts', pathMatch: 'full' },
      {
        path: 'alerts',
        loadComponent: () => import('./pages/alerts/alerts.component').then((m) => m.AlertsComponent),
      },
      {
        path: 'alerts/:id',
        loadComponent: () =>
          import('./pages/alert-detail/alert-detail.component').then((m) => m.AlertDetailComponent),
      },
      {
        path: 'setup',
        loadComponent: () => import('./pages/setup/setup.component').then((m) => m.SetupComponent),
      },
      {
        path: 'tuning',
        loadComponent: () => import('./pages/tuning/tuning.component').then((m) => m.TuningComponent),
      },
      {
        path: 'health',
        loadComponent: () => import('./pages/health/health.component').then((m) => m.HealthComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
