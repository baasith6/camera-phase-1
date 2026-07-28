import { DecimalPipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { InstallerInfo, SetupCodeResponse, Store, StoreOverview, UserAccount } from '../../core/models';

interface ChecklistStep {
  id: string;
  title: string;
  detail: string;
  done: boolean;
  adminOnly?: boolean;
  actionLabel?: string;
  actionLink?: string | any[];
  queryParams?: Record<string, string>;
  inlineAction?: 'download' | 'setupCode';
}

@Component({
  selector: 'app-get-started',
  standalone: true,
  imports: [RouterLink, DecimalPipe, FormsModule],
  template: `
    <h2>Get started</h2>
    <p class="muted intro">
      Follow these steps to connect a store. Progress updates automatically when you refresh.
    </p>

    @if (auth.isAdmin() && stores.length > 1) {
      <div class="card store-pick">
        <label>Store</label>
        <select [(ngModel)]="selectedStoreId" (ngModelChange)="onStoreChange()">
          @for (s of stores; track s.id) {
            <option [value]="s.id">{{ s.name }}</option>
          }
        </select>
      </div>
    }

    @if (selectedStoreName) {
      <p class="store-label muted">Checklist for <strong>{{ selectedStoreName }}</strong></p>
    }

    <div class="progress-bar">
      <div class="fill" [style.width.%]="progressPct"></div>
      <span class="pct">{{ doneCount }}/{{ visibleSteps.length }} complete</span>
    </div>

    <div class="steps">
      @for (step of steps; track step.id) {
        @if (!step.adminOnly || auth.isAdmin()) {
          <div class="step card" [class.done]="step.done">
            <div class="step-head">
              <span class="status" [class.ok]="step.done">{{ step.done ? '✓' : '○' }}</span>
              <div>
                <h3>{{ step.title }}</h3>
                <p class="muted small">{{ step.detail }}</p>
              </div>
            </div>
            <div class="step-actions">
              @if (step.inlineAction === 'download') {
                <button (click)="downloadInstaller()" [disabled]="downloadingInstaller || !installerInfo">
                  {{ downloadingInstaller ? 'Downloading…' : 'Download installer' }}
                </button>
                @if (installerInfo) {
                  <span class="muted small">v{{ installerInfo.version }} · {{ installerInfo.sizeBytes / 1048576 | number:'1.1-1' }} MB</span>
                }
                @if (installerError) {
                  <span class="err">{{ installerError }}</span>
                }
              } @else if (step.inlineAction === 'setupCode') {
                <button (click)="generateSetupCode()" [disabled]="!selectedStoreId || generatingCode">
                  {{ generatingCode ? 'Generating…' : 'Generate setup code' }}
                </button>
                @if (setupCode) {
                  <div class="code-box">
                    <code>{{ setupCode }}</code>
                    <span class="muted small">Expires {{ setupCodeExpires }}</span>
                    <button class="ghost small" (click)="copyCode()">Copy</button>
                  </div>
                }
              } @else if (step.actionLink) {
                <a class="btn-link" [routerLink]="step.actionLink" [queryParams]="step.queryParams || null">
                  {{ step.actionLabel }}
                </a>
              }
            </div>
          </div>
        }
      }
    </div>

    @if (allComplete) {
      <div class="card complete-box">
        <p>Store setup looks complete. You can go to <a routerLink="/app/clips">Clips</a> to review uploads or <a routerLink="/app/alerts">Alerts</a> for day-to-day review.</p>
      </div>
    }
  `,
  styles: [`
    .intro { margin: 0 0 1.25rem; max-width: 560px; }
    .store-pick { max-width: 360px; margin-bottom: 1rem; padding: .75rem 1rem; }
    .store-pick label { display: block; font-size: .78rem; color: var(--text-muted); margin-bottom: .25rem; }
    .store-pick select {
      width: 100%; padding: .45rem .55rem; border-radius: var(--radius-sm);
      border: 1px solid var(--border-strong); background: var(--surface-2); color: var(--text);
    }
    .store-label { margin-bottom: .75rem; font-size: .9rem; }
    .progress-bar {
      position: relative; height: 28px; background: var(--surface-2);
      border-radius: var(--radius-sm); border: 1px solid var(--border);
      margin-bottom: 1.25rem; overflow: hidden; max-width: 480px;
    }
    .fill {
      height: 100%; background: linear-gradient(90deg, var(--accent-soft), rgba(139,92,246,.35));
      transition: width .25s ease;
    }
    .pct {
      position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
      font-size: .78rem; font-weight: 600; color: var(--text-muted);
    }
    .steps { display: flex; flex-direction: column; gap: .75rem; max-width: 720px; }
    .step {
      padding: 1rem; border: 1px solid var(--border);
      background: var(--surface); border-radius: var(--radius);
    }
    .step.done { border-color: rgba(92, 219, 127, .35); }
    .step-head { display: flex; gap: .75rem; align-items: flex-start; }
    .status {
      width: 1.5rem; height: 1.5rem; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: .85rem; flex-shrink: 0;
      border: 1px solid var(--border-strong); color: var(--text-muted);
    }
    .status.ok { background: rgba(92,219,127,.15); border-color: #5cdb7f; color: #5cdb7f; }
    h3 { margin: 0 0 .25rem; font-size: .95rem; }
    .small { font-size: .82rem; margin: 0; }
    .muted { color: var(--text-muted); }
    .step-actions {
      margin-top: .75rem; margin-left: 2.25rem;
      display: flex; flex-wrap: wrap; align-items: center; gap: .5rem;
    }
    button {
      padding: .4rem .75rem; border-radius: var(--radius-sm);
      border: 1px solid var(--accent); background: var(--accent-soft);
      color: var(--accent-2); cursor: pointer; font-weight: 600; font-size: .85rem;
    }
    button.ghost { background: transparent; border-color: var(--border-strong); color: var(--text-muted); }
    button.small { font-size: .78rem; padding: .25rem .5rem; }
    button:disabled { opacity: .5; cursor: not-allowed; }
    .btn-link {
      font-size: .85rem; color: var(--accent-2); text-decoration: none;
      border: 1px solid var(--border-strong); padding: .35rem .65rem; border-radius: var(--radius-sm);
    }
    .code-box {
      display: flex; flex-wrap: wrap; align-items: center; gap: .5rem;
      padding: .5rem .65rem; background: var(--surface-2); border-radius: var(--radius-sm);
      border: 1px solid var(--border-strong); width: 100%;
    }
    code { font-size: 1.1rem; letter-spacing: .06em; }
    .err { color: #f07070; font-size: .82rem; }
    .complete-box { max-width: 720px; margin-top: 1rem; border-color: rgba(92,219,127,.35); }
    .complete-box a { color: var(--accent-2); }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
  `],
})
export class GetStartedComponent implements OnInit {
  stores: StoreOverview[] = [];
  simpleStores: Store[] = [];
  storeUsers: UserAccount[] = [];
  cameraCount = 0;
  onlineConnectorCount = 0;
  hasAlerts = false;

  selectedStoreId = '';
  selectedStoreName = '';

  installerInfo: InstallerInfo | null = null;
  installerError = '';
  downloadingInstaller = false;

  setupCode = '';
  setupCodeExpires = '';
  generatingCode = false;

  steps: ChecklistStep[] = [];

  constructor(public auth: AuthService, private api: ApiService) {}

  ngOnInit(): void {
    this.api.getInstallerInfo().subscribe({
      next: (info) => { this.installerInfo = info; this.installerError = ''; this.rebuildSteps(); },
      error: () => { this.installerInfo = null; this.installerError = 'Installer not built yet — contact ONEVO admin'; this.rebuildSteps(); },
    });

    if (this.auth.isAdmin()) {
      this.api.listStoreOverview().subscribe((s) => {
        this.stores = s;
        if (s.length && !this.selectedStoreId) {
          this.selectedStoreId = s[0].id;
          this.selectedStoreName = s[0].name;
        }
        this.loadUsersAndRebuild();
      });
    } else {
      this.api.listStores().subscribe((s) => {
        this.simpleStores = s;
        const sid = this.auth.storeId() || s[0]?.id || '';
        this.selectedStoreId = sid;
        this.selectedStoreName = s.find((x) => x.id === sid)?.name || s[0]?.name || '';
        this.loadStoreMetrics();
      });
    }
  }

  loadStoreMetrics(): void {
    if (!this.selectedStoreId) {
      this.rebuildSteps();
      return;
    }
    this.api.listCameras(this.selectedStoreId).subscribe((cams) => {
      this.cameraCount = cams.length;
      this.api.listConnectors(this.selectedStoreId).subscribe((conns) => {
        this.onlineConnectorCount = conns.filter((c) =>
          (c.status === 'Healthy' || c.status === 'Degraded') && c.lastHeartbeat).length;
        this.api.listAlerts(this.selectedStoreId).subscribe((alerts) => {
          this.hasAlerts = alerts.length > 0;
          this.rebuildSteps();
        });
      });
    });
  }

  onStoreChange(): void {
    const s = this.stores.find((x) => x.id === this.selectedStoreId);
    this.selectedStoreName = s?.name || '';
    this.setupCode = '';
    this.loadUsersAndRebuild();
  }

  loadUsersAndRebuild(): void {
    if (!this.selectedStoreId) {
      this.storeUsers = [];
      this.rebuildSteps();
      return;
    }
    if (this.auth.isAdmin()) {
      this.api.listUsers(this.selectedStoreId).subscribe((u) => {
        this.storeUsers = u;
        this.rebuildSteps();
      });
    } else {
      this.rebuildSteps();
    }
  }

  rebuildSteps(): void {
    const overview = this.auth.isAdmin()
      ? this.stores.find((s) => s.id === this.selectedStoreId)
      : null;

    const hasStore = this.auth.isAdmin()
      ? this.stores.some((s) => s.id === this.selectedStoreId)
      : this.simpleStores.length > 0 || !!this.auth.storeId();

    const hasManager = this.storeUsers.some((u) =>
      u.role.toLowerCase() === 'manager' && u.storeId === this.selectedStoreId);

    const cameras = overview?.cameraCount ?? this.cameraCount;
    const onlineConnectors = overview?.onlineConnectorCount ?? this.onlineConnectorCount;
    const alertsDone = overview
      ? !!(overview.lastAlertAt || overview.pendingAlertCount > 0)
      : this.hasAlerts;

    this.steps = this.buildStepList(hasStore, hasManager, cameras, onlineConnectors, alertsDone);
  }

  private buildStepList(
    hasStore: boolean,
    hasManager: boolean,
    cameraCount: number,
    onlineConnectors: number,
    hasAlerts: boolean,
  ): ChecklistStep[] {
    const storeQ = this.selectedStoreId ? { storeId: this.selectedStoreId } : undefined;
    return [
      {
        id: 'store',
        title: 'Create store',
        detail: 'Add the store name, notification email, and alert visibility settings.',
        done: hasStore,
        adminOnly: true,
        actionLabel: 'Open Admin',
        actionLink: ['/app/admin'],
      },
      {
        id: 'manager',
        title: 'Create manager user',
        detail: 'Assign a Manager login so store staff can review alerts.',
        done: hasManager,
        adminOnly: true,
        actionLabel: 'Create user',
        actionLink: ['/app/admin'],
      },
      {
        id: 'installer',
        title: 'Download Windows connector',
        detail: 'Copy the installer to the shop PC that can reach your cameras (run as Administrator).',
        done: !!this.installerInfo,
        inlineAction: 'download',
      },
      {
        id: 'code',
        title: 'Generate setup code',
        detail: 'Send this one-time code to the shop technician — it expires in 24 hours.',
        done: !!this.setupCode,
        inlineAction: 'setupCode',
      },
      {
        id: 'cameras',
        title: 'Configure cameras & zones',
        detail: 'Draw Shelf, HighValue, Checkout, and Exit zones on each camera feed.',
        done: cameraCount > 0,
        actionLabel: 'Open Setup & Zones',
        actionLink: ['/app/setup'],
        queryParams: storeQ,
      },
      {
        id: 'connector',
        title: 'Verify connector online',
        detail: 'After installing on the shop PC, the connector should show Installed · Online.',
        done: onlineConnectors > 0,
        actionLabel: 'Check status',
        actionLink: ['/app/setup'],
        queryParams: storeQ,
      },
      {
        id: 'clips',
        title: 'Review uploaded clips',
        detail: 'Open Clips to watch uploaded video and see AI analysis status, events, and risk scores.',
        done: onlineConnectors > 0,
        actionLabel: 'Open Clips',
        actionLink: ['/app/clips'],
        queryParams: storeQ,
      },
      {
        id: 'alerts',
        title: 'Test alerts & email',
        detail: 'Confirm alerts appear in the dashboard and email (requires SMTP_ENABLE on the server).',
        done: hasAlerts,
        actionLabel: 'View Alerts',
        actionLink: ['/app/alerts'],
        queryParams: storeQ,
      },
    ];
  }

  get visibleSteps(): ChecklistStep[] {
    return this.steps.filter((s) => !s.adminOnly || this.auth.isAdmin());
  }

  get doneCount(): number {
    return this.visibleSteps.filter((s) => s.done).length;
  }

  get progressPct(): number {
    const total = this.visibleSteps.length;
    return total ? Math.round((this.doneCount / total) * 100) : 0;
  }

  get allComplete(): boolean {
    const required = this.visibleSteps.filter((s) => s.id !== 'alerts');
    return required.length > 0 && required.every((s) => s.done);
  }

  downloadInstaller(): void {
    if (!this.installerInfo) return;
    this.downloadingInstaller = true;
    this.api.downloadInstaller().subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = this.installerInfo!.fileName;
        a.click();
        URL.revokeObjectURL(url);
        this.downloadingInstaller = false;
      },
      error: () => {
        this.downloadingInstaller = false;
        this.installerError = 'Download failed';
      },
    });
  }

  generateSetupCode(): void {
    if (!this.selectedStoreId) return;
    this.generatingCode = true;
    this.api.createSetupCode(this.selectedStoreId).subscribe({
      next: (res: SetupCodeResponse) => {
        this.setupCode = res.code;
        this.setupCodeExpires = new Date(res.expiresAt).toLocaleString();
        this.generatingCode = false;
        this.rebuildSteps();
      },
      error: () => { this.generatingCode = false; },
    });
  }

  copyCode(): void {
    if (this.setupCode) navigator.clipboard?.writeText(this.setupCode);
  }
}
