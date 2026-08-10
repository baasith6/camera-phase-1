import { DecimalPipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { InstallerInfo, SetupCodeResponse, StoreOverview, UserAccount } from '../../core/models';

import { PageContainerComponent, PageHeaderComponent } from '../../shared/ui-components';

@Component({
  selector: 'app-admin-stores',
  standalone: true,
  imports: [FormsModule, DecimalPipe, RouterLink, PageContainerComponent, PageHeaderComponent],
  template: `
    <app-page-container>
      <app-page-header title="Admin" subtitle="Manage stores, users, and connector installer." />

      <div class="stepper" role="tablist">
        <button type="button" class="stepper-btn" [class.active]="tab === 'stores'" (click)="tab = 'stores'">Stores</button>
        <button type="button" class="stepper-btn" [class.active]="tab === 'users'" (click)="tab = 'users'">Users</button>
      </div>

      @if (tab === 'stores') {
    <div class="card">
        <h3>Create store</h3>
        <label>Store name</label>
        <input [(ngModel)]="newStoreName" placeholder="Downtown Market" />

        <label>Notification email (Gmail)</label>
        <input [(ngModel)]="newStoreEmail" type="email" placeholder="manager@store.com" />

        <label>Alert visibility</label>
        <select [(ngModel)]="newStoreVisibility">
          <option value="ManagerOnly">Manager only</option>
          <option value="All">All staff</option>
          <option value="Silent">Silent (admin only)</option>
        </select>

        <button (click)="createStore()" [disabled]="!newStoreName || creatingStore">
          {{ creatingStore ? 'Creating…' : 'Create store' }}
        </button>
        @if (storeError) { <p class="err">{{ storeError }}</p> }
      </div>

    <div class="card">
      <h3>Connector installer</h3>
      <div class="row">
        <button (click)="downloadInstaller()" [disabled]="downloadingInstaller || !installerInfo">
          {{ downloadingInstaller ? 'Downloading…' : 'Download Windows installer' }}
        </button>
        @if (installerInfo) {
          <span class="muted small">
            v{{ installerInfo.version }} · {{ installerInfo.sizeBytes / 1048576 | number:'1.1-1' }} MB
          </span>
        }
      </div>
      @if (installerError) { <p class="err">{{ installerError }}</p> }
    </div>

    <div class="card">
      <h3>Stores</h3>
      @if (!stores.length) {
        <p class="muted">No stores yet. Create one above.</p>
      }
      @for (s of stores; track s.id) {
        <div class="store-row" [class.sel]="selectedStoreId === s.id">
          <div class="store-main" (click)="selectStore(s)">
            <strong>{{ s.name }}</strong>
            <span class="muted small">{{ s.alertVisibilityMode }}</span>
            @if (s.notificationEmail) {
              <span class="muted small"> · {{ s.notificationEmail }}</span>
            }
            <div class="stats muted small">
              {{ s.cameraCount }} cameras ·
              {{ s.onlineConnectorCount }}/{{ s.connectorCount }} connectors online ·
              {{ s.pendingAlertCount }} pending alerts
            </div>
          </div>
          <div class="store-actions">
            <button class="ghost small" (click)="generateCode(s.id)">Setup code</button>
            <a class="btn-link" [routerLink]="['/app/setup']" [queryParams]="{ storeId: s.id }">Cameras &amp; zones</a>
          </div>
        </div>
      }

      @if (setupCode) {
        <div class="code-box">
          <div class="code-label">Setup code for selected store</div>
          <div class="code-value">{{ setupCode }}</div>
          <div class="muted small">Expires {{ setupCodeExpires }}</div>
          <button class="ghost small" (click)="copyCode()">Copy</button>
        </div>
      }
    </div>
      }

      @if (tab === 'users') {
      <div class="card">
        <h3>Create user</h3>
        <label>Store</label>
        <select [(ngModel)]="userStoreId">
          <option value="">Select store…</option>
          @for (s of stores; track s.id) {
            <option [value]="s.id">{{ s.name }}</option>
          }
        </select>

        <label>Email</label>
        <input [(ngModel)]="userEmail" type="email" placeholder="manager@store.com" />

        <label>Temporary password</label>
        <input [(ngModel)]="userPassword" type="password" />

        <label>Role</label>
        <select [(ngModel)]="userRole">
          <option value="Manager">Manager</option>
          <option value="Reviewer">Reviewer</option>
          <option value="Installer">Installer</option>
        </select>

        <button (click)="createUser()" [disabled]="!userStoreId || !userEmail || !userPassword || creatingUser">
          {{ creatingUser ? 'Creating…' : 'Create user' }}
        </button>
        @if (userError) { <p class="err">{{ userError }}</p> }
        @if (userSuccess) { <p class="ok">{{ userSuccess }}</p> }
      </div>

    @if (storeUsers.length) {
      <div class="card">
        <h3>Users — {{ selectedStoreName || 'select a store' }}</h3>
        @for (u of storeUsers; track u.id) {
          <div class="user-row">
            <span>{{ u.email }}</span>
            <span class="badge">{{ u.role }}</span>
          </div>
        }
      </div>
    } @else {
      <p class="muted">Select a store under Stores tab to view users, or create a user above.</p>
    }
      }
    </app-page-container>
  `,
  styles: [`
    .muted { color: var(--text-muted); }
    .small { font-size: .82rem; }
    .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem; }
    @media (max-width:900px) { .grid2 { grid-template-columns:1fr; } }
    .card {
      background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
      padding:1rem; margin-bottom:1rem;
    }
    h3 { margin:0 0 .75rem; font-size:.95rem; }
    label { display:block; font-size:.78rem; color:var(--text-muted); margin:.5rem 0 .2rem; }
    input, select {
      width:100%; padding:.45rem .55rem; border-radius:var(--radius-sm);
      border:1px solid var(--border-strong); background:var(--surface-2); color:var(--text);
      margin-bottom:.35rem;
    }
    button {
      margin-top:.5rem; padding:.45rem .85rem; border-radius:var(--radius-sm);
      border:1px solid var(--accent); background:var(--accent-soft); color:var(--accent-2);
      cursor:pointer; font-weight:600;
    }
    button.ghost { background:transparent; border-color:var(--border-strong); color:var(--text-muted); }
    button.small { font-size:.78rem; padding:.25rem .55rem; margin-top:0; }
    button:disabled { opacity:.5; cursor:not-allowed; }
    .err { color: var(--danger); font-size: .85rem; }
    .ok { color: var(--success); font-size: .85rem; }
    .row { display:flex; align-items:center; gap:1rem; flex-wrap:wrap; }
    .store-row {
      display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;
      padding:.65rem 0; border-bottom:1px solid var(--border);
    }
    .store-row.sel { background:var(--accent-soft); border-radius:var(--radius-sm); padding:.65rem; }
    .store-main { flex:1; cursor:pointer; }
    .store-actions { display:flex; flex-direction:column; gap:.35rem; align-items:flex-end; }
    .btn-link {
      font-size:.78rem; color:var(--accent-2); text-decoration:none;
      border:1px solid var(--border-strong); padding:.25rem .55rem; border-radius:var(--radius-sm);
    }
    .code-box {
      margin-top:1rem; padding:.75rem; background:var(--surface-2);
      border-radius:var(--radius-sm); border:1px solid var(--border-strong);
    }
    .code-value { font-family:monospace; font-size:1.2rem; letter-spacing:.08em; margin:.25rem 0; }
    .user-row { display:flex; justify-content:space-between; padding:.35rem 0; border-bottom:1px solid var(--border); }
    .badge {
      font-size:.7rem; text-transform:uppercase; letter-spacing:.06em;
      color:var(--accent-2); background:var(--accent-soft); padding:.1rem .45rem; border-radius:10px;
    }
  `],
})
export class AdminStoresComponent implements OnInit {
  tab: 'stores' | 'users' = 'stores';
  stores: StoreOverview[] = [];
  storeUsers: UserAccount[] = [];

  newStoreName = '';
  newStoreEmail = '';
  newStoreVisibility = 'ManagerOnly';
  creatingStore = false;
  storeError = '';

  userStoreId = '';
  userEmail = '';
  userPassword = '';
  userRole = 'Manager';
  creatingUser = false;
  userError = '';
  userSuccess = '';

  selectedStoreId = '';
  selectedStoreName = '';
  setupCode = '';
  setupCodeExpires = '';
  generatingCode = false;

  installerInfo: InstallerInfo | null = null;
  downloadingInstaller = false;
  installerError = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadStores();
    this.api.getInstallerInfo().subscribe({
      next: (info) => (this.installerInfo = info),
      error: () => (this.installerError = 'Installer not available — build connector/dist first'),
    });
  }

  loadStores(): void {
    this.api.listStoreOverview().subscribe((s) => (this.stores = s));
  }

  createStore(): void {
    this.creatingStore = true;
    this.storeError = '';
    this.api.createStore({
      name: this.newStoreName.trim(),
      notificationEmail: this.newStoreEmail.trim() || undefined,
      alertVisibilityMode: this.newStoreVisibility,
    }).subscribe({
      next: () => {
        this.newStoreName = '';
        this.newStoreEmail = '';
        this.creatingStore = false;
        this.loadStores();
      },
      error: (err) => {
        this.creatingStore = false;
        this.storeError = err?.error?.error || 'Could not create store';
      },
    });
  }

  createUser(): void {
    this.creatingUser = true;
    this.userError = '';
    this.userSuccess = '';
    this.api.createUser({
      email: this.userEmail.trim(),
      password: this.userPassword,
      role: this.userRole,
      storeId: this.userStoreId,
    }).subscribe({
      next: () => {
        this.userEmail = '';
        this.userPassword = '';
        this.creatingUser = false;
        this.userSuccess = 'User created. Share credentials securely with the store.';
        if (this.selectedStoreId === this.userStoreId) this.loadUsers(this.userStoreId);
      },
      error: (err) => {
        this.creatingUser = false;
        this.userError = err?.error?.error || 'Could not create user';
      },
    });
  }

  selectStore(s: StoreOverview): void {
    this.selectedStoreId = s.id;
    this.selectedStoreName = s.name;
    this.userStoreId = s.id;
    this.setupCode = '';
    this.loadUsers(s.id);
  }

  loadUsers(storeId: string): void {
    this.api.listUsers(storeId).subscribe((u) => (this.storeUsers = u));
  }

  generateCode(storeId: string): void {
    this.selectedStoreId = storeId;
    this.generatingCode = true;
    this.api.createSetupCode(storeId).subscribe({
      next: (res: SetupCodeResponse) => {
        this.setupCode = res.code;
        this.setupCodeExpires = new Date(res.expiresAt).toLocaleString();
        this.generatingCode = false;
      },
      error: () => { this.generatingCode = false; },
    });
  }

  copyCode(): void {
    if (this.setupCode) navigator.clipboard?.writeText(this.setupCode);
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
      setTimeout(() => (this.downloadingInstaller = false), 1500);
    }
  }
}
