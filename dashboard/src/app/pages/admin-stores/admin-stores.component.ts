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
    <div class="card flex flex-col gap-2">
        <h3 class="m-0 mb-1 text-[0.95rem]">Create store</h3>
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

        <button class="self-start" (click)="createStore()" [disabled]="!newStoreName || creatingStore">
          {{ creatingStore ? 'Creating…' : 'Create store' }}
        </button>
        @if (storeError) { <p class="m-0 text-[0.85rem] text-danger">{{ storeError }}</p> }
      </div>

    <div class="card">
      <h3 class="m-0 mb-3 text-[0.95rem]">Connector installer</h3>
      <div class="flex flex-wrap items-center gap-4">
        <button (click)="downloadInstaller()" [disabled]="downloadingInstaller || !installerInfo">
          {{ downloadingInstaller ? 'Downloading…' : 'Download Windows installer' }}
        </button>
        @if (installerInfo) {
          <span class="muted small">
            v{{ installerInfo.version }} · {{ installerInfo.sizeBytes / 1048576 | number:'1.1-1' }} MB
          </span>
        }
      </div>
      @if (installerError) { <p class="m-0 mt-2 text-[0.85rem] text-danger">{{ installerError }}</p> }
    </div>

    <div class="card">
      <h3 class="m-0 mb-3 text-[0.95rem]">Stores</h3>
      @if (!stores.length) {
        <p class="muted">No stores yet. Create one above.</p>
      }
      @for (s of stores; track s.id) {
        <div [class]="selectedStoreId === s.id ? 'flex items-start justify-between gap-4 border-b border-border rounded-ctl bg-accent-soft p-2.5' : 'flex items-start justify-between gap-4 border-b border-border py-2.5'">
          <div class="flex-1 cursor-pointer" (click)="selectStore(s)">
            <strong>{{ s.name }}</strong>
            <span class="muted small">{{ s.alertVisibilityMode }}</span>
            @if (s.notificationEmail) {
              <span class="muted small"> · {{ s.notificationEmail }}</span>
            }
            <div class="muted small">
              {{ s.cameraCount }} cameras ·
              {{ s.onlineConnectorCount }}/{{ s.connectorCount }} connectors online ·
              {{ s.pendingAlertCount }} pending alerts
            </div>
          </div>
          <div class="flex flex-col items-end gap-1.5">
            <button class="ghost small" (click)="generateCode(s.id)">Setup code</button>
            <a class="rounded-ctl border border-border-strong px-2 py-1 text-[0.78rem] text-accent-2 no-underline" [routerLink]="['/app/setup']" [queryParams]="{ storeId: s.id }">Cameras &amp; zones</a>
          </div>
        </div>
      }

      @if (setupCode) {
        <div class="mt-4 rounded-ctl border border-border-strong bg-surface-2 p-3">
          <div>Setup code for selected store</div>
          <div class="my-1 font-mono text-[1.2rem] tracking-[0.08em]">{{ setupCode }}</div>
          <div class="muted small">Expires {{ setupCodeExpires }}</div>
          <button class="ghost small mt-2" (click)="copyCode()">Copy</button>
        </div>
      }
    </div>
      }

      @if (tab === 'users') {
      <div class="card flex flex-col gap-2">
        <h3 class="m-0 mb-1 text-[0.95rem]">Create user</h3>
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

        <button class="self-start" (click)="createUser()" [disabled]="!userStoreId || !userEmail || !userPassword || creatingUser">
          {{ creatingUser ? 'Creating…' : 'Create user' }}
        </button>
        @if (userError) { <p class="m-0 text-[0.85rem] text-danger">{{ userError }}</p> }
        @if (userSuccess) { <p class="m-0 text-[0.85rem] text-success">{{ userSuccess }}</p> }
      </div>

    @if (storeUsers.length) {
      <div class="card">
        <h3 class="m-0 mb-3 text-[0.95rem]">Users — {{ selectedStoreName || 'select a store' }}</h3>
        @for (u of storeUsers; track u.id) {
          <div class="flex justify-between border-b border-border py-1.5">
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
