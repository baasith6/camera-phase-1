import { Component, inject } from '@angular/core';
import { SetupContextService } from './setup-context.service';

@Component({
  selector: 'app-setup-connector-step',
  standalone: true,
  template: `
    <ul class="muted small m-0 mb-3 pl-[18px]">
      <li>A Windows PC in your shop that can reach the cameras</li>
      <li>About 5 minutes to run the installer</li>
    </ul>

    <div class="card">
      <div class="mb-3 flex items-start justify-between gap-4">
        <div>
          <h3 class="m-0 mb-1">Connect your shop PC</h3>
          <p class="muted small">Download the installer, run it on the shop computer, and enter the setup code when prompted.</p>
        </div>
        <div [class]="ctx.storeConnectorOnline
               ? 'flex items-center gap-1.5 whitespace-nowrap rounded-full border border-success/35 bg-success-soft px-2.5 py-1.5 text-[0.82rem] font-semibold text-success'
               : 'flex items-center gap-1.5 whitespace-nowrap rounded-full border border-border-strong px-2.5 py-1.5 text-[0.82rem] font-semibold text-ink-muted'">
          <span class="h-2 w-2 rounded-full" [class]="ctx.storeConnectorOnline ? 'h-2 w-2 rounded-full bg-success' : 'h-2 w-2 rounded-full bg-ink-muted'"></span>
          {{ ctx.storeConnectorOnline ? 'Connected · Online' : (ctx.storeConnectors.length ? 'Offline' : 'Not connected yet') }}
        </div>
      </div>

      <div class="mb-2 flex flex-wrap gap-2">
        @if (!ctx.storeConnectorOnline) {
          <button (click)="ctx.downloadInstaller()" [disabled]="!ctx.installerInfo">
            {{ ctx.storeConnectors.length ? 'Download / reinstall' : 'Download for Windows' }}
          </button>
          <button class="ghost" (click)="ctx.generateSetupCode()" [disabled]="!ctx.storeId || ctx.generatingCode">
            {{ ctx.generatingCode ? 'Generating…' : 'Get setup code' }}
          </button>
        } @else {
          @if (ctx.connectorUpdateAvailable) {
            <span class="self-center text-[0.82rem] font-semibold text-warning">Update v{{ ctx.installerInfo?.version }} available in the shop PC tray</span>
          } @else {
            <span class="muted small">Updates appear automatically in the shop PC tray.</span>
          }
        }
        <button class="ghost" (click)="ctx.refreshConnectors()" [disabled]="!ctx.storeId">Refresh status</button>
      </div>

      @if (ctx.installerInfo) {
        <p class="muted small m-0 mt-1">
          Latest v{{ ctx.installerInfo.version }} · {{ ctx.installerSizeMb }} MB
        </p>
      } @else if (ctx.installerError) {
        <p class="m-0 mt-1.5 text-[0.82rem] text-danger">{{ ctx.installerError }}</p>
      }

      @if (ctx.setupCodeError) {
        <p class="m-0 mt-1.5 text-[0.82rem] text-danger">{{ ctx.setupCodeError }}</p>
      }

      @if (ctx.setupCode) {
        <div class="mt-3 flex items-center justify-between gap-4 rounded-ctl border border-dashed border-border-strong bg-surface-2 px-3.5 py-3">
          <div>
            <div class="mb-0.5 text-xs text-accent-2">Setup code — enter this in the installer</div>
            <div class="font-mono text-[1.35rem] font-bold tracking-[0.12em]">{{ ctx.setupCode }}</div>
            <div class="muted small">Expires {{ ctx.setupCodeExpires }}</div>
          </div>
          <button class="ghost small" (click)="ctx.copySetupCode()">Copy</button>
        </div>
      }

      @if (ctx.storeConnectors.length) {
        <div class="mt-3 flex flex-col gap-1.5">
          @for (c of ctx.storeConnectors; track c.id) {
            <div class="flex items-center justify-between text-[0.85rem]">
              <span>{{ c.name }} <span class="muted small">v{{ c.version }}</span></span>
              <span class="badge" [class]="c.status.toLowerCase()">{{ c.status }}</span>
            </div>
          }
        </div>
      }
    </div>
  `,
})
export class SetupConnectorStepComponent {
  readonly ctx = inject(SetupContextService);
}
