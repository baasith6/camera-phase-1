import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SetupContextService } from './setup-context.service';

@Component({
  selector: 'app-setup-verify-step',
  standalone: true,
  imports: [RouterLink],
  template: `
    <ul class="muted small m-0 mb-3 pl-[18px]">
      <li>Connector online and at least one camera added</li>
      <li>Zones drawn on cameras you want monitored</li>
    </ul>

    <div class="card">
      <h3>Ready to go live?</h3>
      <p class="muted">Check each item below before staff start reviewing alerts.</p>
      <ul class="m-0 mb-4 list-none p-0">
        <li class="border-b border-border py-2" [class]="ctx.storeConnectorOnline ? 'border-b border-border py-2 text-success' : 'border-b border-border py-2 text-ink-muted'">Shop PC connected {{ ctx.storeConnectorOnline ? '✓' : '— not yet' }}</li>
        <li class="border-b border-border py-2" [class]="ctx.cameras.length > 0 ? 'border-b border-border py-2 text-success' : 'border-b border-border py-2 text-ink-muted'">{{ ctx.cameras.length }} camera(s) added</li>
        <li class="border-b border-border py-2" [class]="ctx.zones.length > 0 ? 'border-b border-border py-2 text-success' : 'border-b border-border py-2 text-ink-muted'">{{ ctx.zones.length }} zone(s) on selected camera</li>
      </ul>
      <div class="flex flex-wrap items-center gap-2">
        <a class="inline-block rounded-ctl border border-border-strong bg-accent-soft px-2.5 py-1.5 text-[0.78rem] text-accent-2 no-underline hover:border-accent" routerLink="/app/alerts">Go to Review</a>
        @if (ctx.auth.isAdmin()) {
          <a class="inline-block rounded-ctl border border-border-strong bg-accent-soft px-2.5 py-1.5 text-[0.78rem] text-accent-2 no-underline hover:border-accent" routerLink="/app/health">View health</a>
          <a class="inline-block rounded-ctl border border-border-strong bg-accent-soft px-2.5 py-1.5 text-[0.78rem] text-accent-2 no-underline hover:border-accent" routerLink="/app/tuning">Open tuning</a>
        }
        <button type="button" class="ghost" (click)="ctx.goToStep(1)">Back to connector</button>
      </div>
    </div>
  `,
})
export class SetupVerifyStepComponent {
  readonly ctx = inject(SetupContextService);
}
