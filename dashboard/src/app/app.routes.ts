import { Routes } from '@angular/router';
import { adminGuard } from './core/admin.guard';
import { authGuard } from './core/auth.guard';
import { ShellComponent } from './shell/shell.component';
import { LoginComponent } from './pages/login/login.component';
import { WelcomeComponent } from './pages/welcome/welcome.component';

export const routes: Routes = [
  { path: '', component: WelcomeComponent },
  { path: 'login', component: LoginComponent },
  {
    path: 'app',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'get-started', pathMatch: 'full' },
      {
        path: 'get-started',
        loadComponent: () =>
          import('./pages/get-started/get-started.component').then((m) => m.GetStartedComponent),
      },
      {
        path: 'admin',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./pages/admin-stores/admin-stores.component').then((m) => m.AdminStoresComponent),
      },
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
        path: 'clips',
        loadComponent: () => import('./pages/clips/clips.component').then((m) => m.ClipsComponent),
      },
      {
        path: 'clips/:id',
        loadComponent: () =>
          import('./pages/clip-detail/clip-detail.component').then((m) => m.ClipDetailComponent),
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
      {
        path: 'analytics',
        loadComponent: () =>
          import('./pages/analytics/analytics.component').then((m) => m.AnalyticsComponent),
      },
      {
        path: 'reports',
        loadComponent: () => import('./pages/reports/reports.component').then((m) => m.ReportsComponent),
      },
      {
        path: 'logs',
        loadComponent: () => import('./pages/logs/logs.component').then((m) => m.LogsComponent),
      },
      {
        path: 'settings',
        loadComponent: () => import('./pages/settings/settings.component').then((m) => m.SettingsComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
