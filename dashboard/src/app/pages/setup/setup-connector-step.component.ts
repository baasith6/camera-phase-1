import { Component, inject } from '@angular/core';
import { SetupContextService } from './setup-context.service';

@Component({
  selector: 'app-setup-connector-step',
  standalone: true,
  template: `
    <ul class="need-list muted small">
      <li>A Windows PC in your shop that can reach the cameras</li>
      <li>About 5 minutes to run the installer</li>
    </ul>

    <div class="card connector-card">
      <div class="conn-header">
        <div>
          <h3>Local connector</h3>
          <p class="muted small">Install the connector on the camera network, then manage motion uploads from the tray.</p>
        </div>
        <div class="conn-status" [class.on]="ctx.storeConnectorOnline" [class.off]="!ctx.storeConnectorOnline">
          <span class="dot"></span>
          {{ ctx.storeConnectorOnline ? 'Connected · Online' : (ctx.storeConnectors.length ? 'Offline' : 'Not connected yet') }}
        </div>
      </div>

      <div class="conn-actions">
        @if (!ctx.storeConnectorOnline) {
          <button (click)="ctx.downloadInstaller()" [disabled]="!ctx.installerInfo">
            {{ ctx.storeConnectors.length ? 'Download / reinstall' : 'Download for Windows' }}
          </button>
          <button class="ghost" (click)="ctx.generateSetupCode()" [disabled]="!ctx.storeId || ctx.generatingCode">
            {{ ctx.generatingCode ? 'Generating…' : 'Get setup code' }}
          </button>
        } @else {
          @if (ctx.connectorUpdateAvailable) {
            <span class="update-note">Update v{{ ctx.installerInfo?.version }} available in the shop PC tray</span>
          } @else {
            <span class="muted small">Updates appear automatically in the shop PC tray.</span>
          }
        }
        <button class="ghost" (click)="ctx.refreshConnectors()" [disabled]="!ctx.storeId">Refresh status</button>
      </div>

      @if (ctx.installerInfo) {
        <p class="muted small meta">
          Latest v{{ ctx.installerInfo.version }} · {{ ctx.installerSizeMb }} MB
        </p>
      } @else if (ctx.installerError) {
        <p class="err-text">{{ ctx.installerError }}</p>
      }

      @if (ctx.setupCodeError) {
        <p class="err-text">{{ ctx.setupCodeError }}</p>
      }

      @if (ctx.setupCode) {
        <div class="code-box">
          <div>
            <div class="code-label">Setup code — enter this in the installer</div>
            <div class="code-value">{{ ctx.setupCode }}</div>
            <div class="muted small">Expires {{ ctx.setupCodeExpires }}</div>
          </div>
          <button class="ghost small" (click)="ctx.copySetupCode()">Copy</button>
        </div>
      }

      @if (ctx.storeConnectors.length) {
        <div class="conn-list">
          @for (c of ctx.storeConnectors; track c.id) {
            <div class="conn-row">
              <span>{{ c.name }} <span class="muted small">v{{ c.version }}</span></span>
              <span class="badge" [class]="c.status.toLowerCase()">{{ c.status }}</span>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .need-list { margin: 0 0 12px; padding-left: 18px; }
    .connector-card { margin-bottom: 1rem; }
    .conn-header { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; margin-bottom: .75rem; }
    .conn-header h3 { margin: 0 0 .25rem; }
    .conn-actions { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .5rem; }
    .conn-status { display: flex; align-items: center; gap: .4rem; font-size: .82rem; font-weight: 600; white-space: nowrap;
                   padding: .35rem .65rem; border-radius: 999px; border: 1px solid var(--border-strong); }
    .conn-status .dot { width: .55rem; height: .55rem; border-radius: 50%; background: var(--text-muted); }
    .conn-status.on { color: var(--success); border-color: rgba(52,211,153,.35); background: var(--success-soft); }
    .conn-status.on .dot { background: var(--success); }
    .conn-status.off { color: var(--text-muted); }
    .meta { margin: .25rem 0 0; }
    .err-text { color: var(--danger); font-size: .82rem; margin: .35rem 0 0; }
    .code-box { margin-top: .75rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem;
                padding: .75rem .9rem; border: 1px dashed var(--border-strong); border-radius: var(--radius-sm);
                background: var(--surface-2); }
    .code-label { font-size: .75rem; color: var(--accent-2); margin-bottom: .2rem; }
    .code-value { font-family: ui-monospace, Consolas, monospace; font-size: 1.35rem; letter-spacing: .12em; font-weight: 700; }
    .conn-list { margin-top: .75rem; display: flex; flex-direction: column; gap: .35rem; }
    .conn-row { display: flex; justify-content: space-between; align-items: center; font-size: .85rem; }
    .badge { padding: .18rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 600; }
    .badge.online, .badge.healthy { background: var(--success-soft); color: var(--success); }
    .badge.offline, .badge.degraded { background: var(--danger-soft); color: var(--danger); }
    .update-note { color: var(--warning); font-size: .82rem; font-weight: 600; align-self: center; }
    .small { font-size: .8rem; }
  `],
})
export class SetupConnectorStepComponent {
  readonly ctx = inject(SetupContextService);
}
