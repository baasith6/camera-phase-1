import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { LiveAlertsService } from '../../core/live-alerts.service';
import { StoreContextService } from '../../core/store-context.service';
import { Alert, Store } from '../../core/models';
import { alertTypeLabel } from '../../shared/alert-labels';
import { ConfirmDialogService } from '../../shared/confirm-dialog.service';
import {
  BulkActionBarComponent,
  DataTableComponent,
  EmptyStateComponent,
  ErrorBannerComponent,
  PageContainerComponent,
  SkeletonListComponent,
} from '../../shared/ui-components';
import { PageHeaderComponent } from '../../shared/page-header.component';
import { StatusBadgeComponent } from '../../shared/status-badge.component';
import { StatusPillComponent } from '../../shared/status-pill.component';

type QuickFilter = '' | 'pending' | 'high' | 'today';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    DatePipe,
    PageHeaderComponent,
    PageContainerComponent,
    StatusBadgeComponent,
    StatusPillComponent,
    BulkActionBarComponent,
    DataTableComponent,
    EmptyStateComponent,
    SkeletonListComponent,
    ErrorBannerComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header title="Alerts">
        <div actions class="filters">
          <select [(ngModel)]="status" (change)="load()" aria-label="Status filter">
            <option value="">All statuses</option>
            <option value="PendingReview">Pending review</option>
            <option value="Confirmed">Confirmed</option>
            <option value="Dismissed">Dismissed</option>
            <option value="FalsePositive">False positive</option>
            <option value="NeedsFollowUp">Needs follow-up</option>
          </select>
          <button class="ghost" type="button" (click)="load()">Refresh</button>
        </div>
        <div below class="filter-chips">
          <button type="button" class="chip" [class.active]="quickFilter === ''" (click)="setQuick('')">All</button>
          <button type="button" class="chip" [class.active]="quickFilter === 'pending'" (click)="setQuick('pending')">Pending</button>
          <button type="button" class="chip" [class.active]="quickFilter === 'high'" (click)="setQuick('high')">High risk</button>
          <button type="button" class="chip" [class.active]="quickFilter === 'today'" (click)="setQuick('today')">Today</button>
        </div>
      </app-page-header>

      @if (auth.isManagerOrAdmin() && filteredAlerts.length > 0) {
        <app-bulk-action-bar
          [allSelected]="allSelected"
          [total]="filteredAlerts.length"
          [selectedCount]="selectedIds.size"
          (toggleAll)="toggleSelectAll($event)">
          <button class="ghost danger" type="button" (click)="deleteSelected()" [disabled]="bulkDeleting || selectedIds.size === 0">
            Delete selected
          </button>
          @if (storeId) {
            <button class="ghost danger" type="button" (click)="deleteAllInStore()" [disabled]="bulkDeleting">
              Delete all in store
            </button>
          }
        </app-bulk-action-bar>
      }

      @if (error) {
        <app-error-banner [message]="error">
          <button class="ghost small" type="button" (click)="load()">Retry</button>
        </app-error-banner>
      }

      @if (loading) {
        <app-skeleton-list />
      } @else if (filteredAlerts.length === 0) {
        <app-empty-state title="No alerts — all clear" detail="Store may be in silent or manager-only pilot mode." />
      } @else {
        @if (newCount > 0) {
          <div class="new-banner" role="status" (click)="dismissNewBanner()">
            {{ newCount }} new alert{{ newCount > 1 ? 's' : '' }} received — click to dismiss
          </div>
        }

        <app-data-table>
          <table desktop class="table">
            <thead>
              <tr>
                @if (auth.isManagerOrAdmin()) { <th class="chk-col"></th> }
                <th>Alert</th>
                <th>Risk</th>
                <th>Score</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (a of pagedAlerts(); track a.id) {
                <tr
                  [class.selected-row]="selectedIds.has(a.id)"
                  [class.new-row]="newIds.has(a.id)"
                  (click)="openAlert(a.id)"
                  tabindex="0"
                  (keydown.enter)="openAlert(a.id)">
                  @if (auth.isManagerOrAdmin()) {
                    <td class="chk-col" (click)="$event.stopPropagation()">
                      <input type="checkbox" [checked]="selectedIds.has(a.id)" (change)="toggleSelect(a.id, $event)" aria-label="Select alert" />
                    </td>
                  }
                  <td>
                    <div class="alert-type">{{ labelType(a.alertType) }}</div>
                    <div class="muted small">{{ a.createdAt | date:'MMM d, h:mm a' }}</div>
                  </td>
                  <td><app-status-badge [level]="a.riskLevel" /></td>
                  <td><span class="score-num">{{ a.riskScore }}</span></td>
                  <td><app-status-pill [status]="a.status" /></td>
                  <td (click)="$event.stopPropagation()">
                    <button class="ghost small" type="button" [routerLink]="['/app/alerts', a.id]">Review</button>
                  </td>
                </tr>
              }
            </tbody>
          </table>

          <div mobile class="alert-cards">
          @for (a of pagedAlerts(); track a.id) {
            <div class="alert-card-mobile" (click)="openAlert(a.id)" tabindex="0" (keydown.enter)="openAlert(a.id)">
              <div class="alert-card-mobile-head">
                <strong>{{ labelType(a.alertType) }}</strong>
                <app-status-badge [level]="a.riskLevel" />
              </div>
              <div class="alert-card-mobile-meta">
                <app-status-pill [status]="a.status" />
                <span class="muted">Score {{ a.riskScore }}</span>
                <span class="muted">{{ a.createdAt | date:'MMM d, h:mm a' }}</span>
              </div>
            </div>
          }
        </div>
        </app-data-table>

        @if (totalPages() > 1) {
          <div class="pagination">
            <button class="ghost pg-btn" type="button" (click)="prevPage()" [disabled]="page === 1">Prev</button>
            <span class="pg-info muted">{{ rangeStart() }}–{{ rangeEnd() }} of {{ filteredAlerts.length }}</span>
            <button class="ghost pg-btn" type="button" (click)="nextPage()" [disabled]="page === totalPages()">Next</button>
          </div>
        }
      }
    </app-page-container>
  `,
  styles: [`
    .new-banner {
      background: var(--accent-soft);
      color: var(--accent-2);
      border: 1px solid var(--border-strong);
      padding: 10px 12px;
      border-radius: var(--radius-sm);
      margin-bottom: 12px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 500;
    }
    .chk-col { width: 40px; text-align: center; }
    .score-num { font-variant-numeric: tabular-nums; font-weight: 700; }
    .alert-type { font-weight: 600; }
    .new-row td { animation: fadeIn 0.8s ease; }
    @keyframes fadeIn { from { background: var(--accent-soft); } to { background: transparent; } }
    .pagination { display: flex; align-items: center; gap: 12px; margin-top: 16px; justify-content: center; }
    .pg-btn { min-height: 44px; padding: 0 16px; }
    button.danger { color: var(--danger); border-color: rgba(248, 113, 113, 0.35); }
  `],
})
export class AlertsComponent implements OnInit, OnDestroy {
  stores: Store[] = [];
  alerts: Alert[] = [];
  storeId = '';
  status = '';
  quickFilter: QuickFilter = '';
  loading = false;
  error = '';
  newIds = new Set<string>();
  newCount = 0;
  page = 1;
  readonly pageSize = 20;
  bulkDeleting = false;
  selectedIds = new Set<string>();
  private liveSub?: { unsubscribe: () => void };

  constructor(
    private api: ApiService,
    public auth: AuthService,
    private route: ActivatedRoute,
    private router: Router,
    private live: LiveAlertsService,
    private storeCtx: StoreContextService,
    private confirm: ConfirmDialogService,
  ) {}

  get filteredAlerts(): Alert[] {
    let list = this.alerts;
    if (this.quickFilter === 'pending') {
      list = list.filter((a) => a.status === 'PendingReview');
    } else if (this.quickFilter === 'high') {
      list = list.filter((a) => a.riskLevel === 'High');
    } else if (this.quickFilter === 'today') {
      const today = new Date().toDateString();
      list = list.filter((a) => new Date(a.createdAt).toDateString() === today);
    }
    return list;
  }

  get allSelected(): boolean {
    return this.filteredAlerts.length > 0 && this.filteredAlerts.every((a) => this.selectedIds.has(a.id));
  }

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => (this.stores = s));
    this.route.queryParamMap.subscribe((params) => {
      const fromQuery = params.get('storeId') ?? this.storeCtx.storeId();
      if (fromQuery) this.storeId = fromQuery;
      this.load();
    });
    this.liveSub = this.live.newAlert$.subscribe(({ alert }) => {
      if (this.storeId && alert.storeId !== this.storeId) return;
      this.alerts = [alert, ...this.alerts];
      this.newIds.add(alert.id);
      this.newCount++;
    });
  }

  ngOnDestroy(): void {
    this.liveSub?.unsubscribe();
  }

  labelType(type: string): string {
    return alertTypeLabel(type);
  }

  setQuick(filter: QuickFilter): void {
    this.quickFilter = filter;
    this.page = 1;
  }

  openAlert(id: string): void {
    this.router.navigate(['/app/alerts', id], {
      queryParams: {
        storeId: this.storeId || null,
        status: this.status || null,
        quick: this.quickFilter || null,
      },
    });
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.selectedIds.clear();
    this.api.listAlerts(this.storeId || undefined, this.status || undefined).subscribe({
      next: (a) => {
        this.alerts = a;
        this.loading = false;
        this.page = 1;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load alerts';
      },
    });
  }

  pagedAlerts(): Alert[] {
    const start = (this.page - 1) * this.pageSize;
    return this.filteredAlerts.slice(start, start + this.pageSize);
  }

  totalPages(): number {
    return Math.max(1, Math.ceil(this.filteredAlerts.length / this.pageSize));
  }

  rangeStart(): number {
    return (this.page - 1) * this.pageSize + 1;
  }

  rangeEnd(): number {
    return Math.min(this.page * this.pageSize, this.filteredAlerts.length);
  }

  prevPage(): void {
    if (this.page > 1) this.page--;
  }

  nextPage(): void {
    if (this.page < this.totalPages()) this.page++;
  }

  dismissNewBanner(): void {
    this.newCount = 0;
    this.newIds.clear();
  }

  toggleSelect(id: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    if (checked) this.selectedIds.add(id);
    else this.selectedIds.delete(id);
  }

  toggleSelectAll(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.selectedIds.clear();
    if (checked) this.filteredAlerts.forEach((a) => this.selectedIds.add(a.id));
  }

  async deleteSelected(): Promise<void> {
    const ids = [...this.selectedIds];
    if (!ids.length) return;
    const ok = await this.confirm.open({
      title: 'Delete alerts',
      message: `Delete ${ids.length} selected alert(s)? Clips will remain in storage.`,
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;
    this.runBulkDelete({ ids });
  }

  async deleteAllInStore(): Promise<void> {
    if (!this.storeId) return;
    const name = this.stores.find((s) => s.id === this.storeId)?.name || 'this store';
    const ok = await this.confirm.open({
      title: 'Delete all alerts',
      message: `Delete ALL alerts in ${name}? Clips will remain in storage.`,
      confirmLabel: 'Delete all',
      danger: true,
    });
    if (!ok) return;
    this.runBulkDelete({ storeId: this.storeId, deleteAllInStore: true });
  }

  private runBulkDelete(body: { storeId?: string; ids?: string[]; deleteAllInStore?: boolean }): void {
    this.bulkDeleting = true;
    this.error = '';
    this.api.bulkDeleteAlerts(body).subscribe({
      next: (res) => {
        this.bulkDeleting = false;
        this.selectedIds.clear();
        this.live.showToast(`Deleted ${res.deleted} alert(s)`);
        this.load();
      },
      error: (e) => {
        this.bulkDeleting = false;
        this.error = e?.error?.error || 'Bulk delete failed';
      },
    });
  }
}
