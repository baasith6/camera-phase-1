import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SetupContextService } from './setup-context.service';

@Component({
  selector: 'app-setup-verify-step',
  standalone: true,
  imports: [RouterLink],
  template: `
    <ul class="need-list muted small">
      <li>Connector online and at least one camera added</li>
      <li>Zones drawn on cameras you want monitored</li>
    </ul>

    <div class="card">
      <h3>Ready to go live?</h3>
      <p class="muted">Check each item below before staff start reviewing alerts.</p>
      <ul class="verify-list">
        <li [class.ok]="ctx.storeConnectorOnline">Shop PC connected {{ ctx.storeConnectorOnline ? '✓' : '— not yet' }}</li>
        <li [class.ok]="ctx.cameras.length > 0">{{ ctx.cameras.length }} camera(s) added</li>
        <li [class.ok]="ctx.zones.length > 0">{{ ctx.zones.length }} zone(s) on selected camera</li>
      </ul>
      <div class="verify-actions">
        <a class="btn-link" routerLink="/app/alerts">Go to Review</a>
        @if (ctx.auth.isAdmin()) {
          <a class="btn-link" routerLink="/app/health">View health</a>
          <a class="btn-link" routerLink="/app/tuning">Open tuning</a>
        }
        <button type="button" class="ghost" (click)="ctx.goToStep(1)">Back to connector</button>
      </div>
    </div>
  `,
  styles: [`
    .need-list { margin: 0 0 12px; padding-left: 18px; }
    .verify-list { list-style: none; padding: 0; margin: 0 0 1rem; }
    .verify-list li { padding: 8px 0; border-bottom: 1px solid var(--border); color: var(--text-muted); }
    .verify-list li.ok { color: var(--success); }
    .verify-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .btn-link {
      display: inline-block; padding: .3rem .65rem; border-radius: var(--radius-sm); font-size: .78rem;
      background: var(--accent-soft); color: var(--accent-2); text-decoration: none; border: 1px solid var(--border-strong);
    }
    .btn-link:hover { border-color: var(--accent); }
    .small { font-size: .8rem; }
  `],
})
export class SetupVerifyStepComponent {
  readonly ctx = inject(SetupContextService);
}
