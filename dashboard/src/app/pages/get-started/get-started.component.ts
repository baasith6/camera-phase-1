import { DecimalPipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { InstallerInfo, SetupCodeResponse, Store, StoreOverview, UserAccount } from '../../core/models';
import { PageContainerComponent, PageHeaderComponent } from '../../shared/ui-components';

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
  imports: [RouterLink, DecimalPipe, FormsModule, PageContainerComponent, PageHeaderComponent],
  template: `
    <app-page-container>
      <app-page-header
        title="Get started"
        subtitle="Follow these steps to connect a store. Progress updates automatically when you refresh." />

    @if (auth.isAdmin() && stores.length > 1) {
      <div class="card mb-4 max-w-[360px] !px-4 !py-3">
        <label class="mb-1 block text-[0.78rem] text-ink-muted">Store</label>
        <select class="w-full !bg-surface-2" [(ngModel)]="selectedStoreId" (ngModelChange)="onStoreChange()">
          @for (s of stores; track s.id) {
            <option [value]="s.id">{{ s.name }}</option>
          }
        </select>
      </div>
    }

    @if (selectedStoreName) {
      <p class="muted mb-3 text-[0.9rem]">Checklist for <strong>{{ selectedStoreName }}</strong></p>
    }

    <div class="relative mb-5 h-7 max-w-[480px] overflow-hidden rounded-[6px] border border-border bg-surface-2">
      <div class="h-full bg-accent transition-[width] duration-200" [style.width.%]="progressPct"></div>
      <span class="absolute inset-0 flex items-center justify-center text-[0.78rem] font-semibold text-ink-muted">{{ doneCount }}/{{ visibleSteps.length }} complete</span>
    </div>

    <div class="flex max-w-[720px] flex-col gap-3">
      <!-- Iterate visibleSteps directly: same list drives progress math and the
           rendered cards, so role filtering can never disagree between them. -->
      @for (step of visibleSteps; track step.id) {
          <div class="step card !mb-0" [class.done]="step.done">
            <div class="flex items-start gap-3">
              <span class="status" [class.ok]="step.done" [attr.aria-label]="step.done ? 'Complete' : 'Incomplete'">
                @if (step.done) {
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                }
              </span>
              <div>
                <h3>{{ step.title }}</h3>
                <p class="muted small m-0">{{ step.detail }}</p>
              </div>
            </div>
            <div class="ml-9 mt-3 flex flex-wrap items-center gap-2">
              @if (step.inlineAction === 'download') {
                <button (click)="downloadInstaller()" [disabled]="downloadingInstaller || !installerInfo">
                  {{ downloadingInstaller ? 'Downloading…' : 'Download installer' }}
                </button>
                @if (installerInfo) {
                  <span class="muted small">v{{ installerInfo.version }} · {{ installerInfo.sizeBytes / 1048576 | number:'1.1-1' }} MB</span>
                }
                @if (installerError) {
                  <span class="text-[0.82rem] text-danger">{{ installerError }}</span>
                }
              } @else if (step.inlineAction === 'setupCode') {
                <button (click)="generateSetupCode()" [disabled]="!selectedStoreId || generatingCode">
                  {{ generatingCode ? 'Generating…' : 'Generate setup code' }}
                </button>
                @if (setupCode) {
                  <div class="flex w-full flex-wrap items-center gap-2 rounded-[6px] border border-border-strong bg-surface-2 px-2.5 py-2">
                    <code class="text-[1.1rem] tracking-[0.06em]">{{ setupCode }}</code>
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
    </div>

    @if (allComplete) {
      <div class="card mt-4 max-w-[720px] !border-success-soft">
        <p>Store setup looks complete. You can go to <a routerLink="/app/clips">Clips</a> to review uploads or <a routerLink="/app/alerts">Alerts</a> for day-to-day review.</p>
      </div>
    }
    </app-page-container>
  `,
  styles: [`
    .step.done { border-color: rgba(92, 219, 127, .35); }
    .status {
      width: 1.5rem; height: 1.5rem; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: .85rem; flex-shrink: 0;
      border: 1px solid var(--border-strong); color: var(--text-muted);
    }
    .status.ok { background: var(--success-soft); border-color: var(--success); color: var(--success); }
    h3 { margin: 0 0 .25rem; font-size: .95rem; }
    .btn-link {
      font-size: .85rem; color: var(--accent-2); text-decoration: none;
      border: 1px solid var(--border-strong); padding: .35rem .65rem; border-radius: var(--radius-sm);
    }
  `],
})
export class GetStartedComponent implements OnInit {
  stores: StoreOverview[] = [];
  simpleStores: Store[] = [];
  storeUsers: UserAccount[] = [];
  cameraCount = 0;
  onlineConnectorCount = 0;
  installedConnectorCount = 0;
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
      error: () => { this.installerInfo = null; this.installerError = 'Installer not built yet — contact onetix admin'; this.rebuildSteps(); },
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
        this.installedConnectorCount = conns.length;
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
    const registeredConnectors = overview?.connectorCount ?? this.installedConnectorCount;
    const alertsDone = overview
      ? !!(overview.lastAlertAt || overview.pendingAlertCount > 0)
      : this.hasAlerts;

    this.steps = this.buildStepList(
      hasStore, hasManager, cameras, registeredConnectors, onlineConnectors, alertsDone);
  }

  private buildStepList(
    hasStore: boolean,
    hasManager: boolean,
    cameraCount: number,
    registeredConnectors: number,
    onlineConnectors: number,
    hasAlerts: boolean,
  ): ChecklistStep[] {
    const storeQ = this.selectedStoreId
      ? { storeId: this.selectedStoreId }
      : undefined;
    const setupQ = (step: string) => storeQ ? { ...storeQ, step } : { step };
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
        title: onlineConnectors > 0
          ? 'Windows connector installed'
          : (registeredConnectors > 0 ? 'Connector offline or uninstalled' : 'Download Windows connector'),
        detail: onlineConnectors > 0
          ? 'The shop PC is online. Future code updates appear automatically in its tray.'
          : (registeredConnectors > 0
              ? 'No recent heartbeat was received. Download to reinstall, or start the connector on the shop PC.'
              : 'Download once on the shop PC that can reach your cameras and run as Administrator.'),
        done: onlineConnectors > 0,
        inlineAction: onlineConnectors > 0 ? undefined : 'download',
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
        queryParams: setupQ('2'),
      },
      {
        id: 'connector',
        title: 'Verify connector online',
        detail: 'After installing on the shop PC, the connector should show Installed · Online.',
        done: onlineConnectors > 0,
        actionLabel: 'Check status',
        actionLink: ['/app/setup'],
        queryParams: setupQ('1'),
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
    if (!this.installerInfo?.downloadPath) return;
    this.downloadingInstaller = true;
    this.installerError = '';
    try {
      this.api.startInstallerDownload(this.installerInfo.downloadPath);
    } catch {
      this.installerError = 'Download failed';
    } finally {
      // Browser owns the download; clear the button busy state shortly.
      setTimeout(() => (this.downloadingInstaller = false), 1500);
    }
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
