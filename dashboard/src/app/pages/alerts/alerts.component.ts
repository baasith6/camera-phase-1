import { Component, OnDestroy, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { BreakpointService } from '../../core/breakpoint.service';
import { LiveAlertsService } from '../../core/live-alerts.service';
import { StoreContextService } from '../../core/store-context.service';
import { Alert, Store } from '../../core/models';
import { alertTypeLabel, pillLabel, relativeTime } from '../../shared/alert-labels';
import { AlertReviewPaneComponent } from '../../shared/alert-review-pane.component';
import { ConfirmDialogService } from '../../shared/confirm-dialog.service';
import {
  BulkActionBarComponent,
  DataTableComponent,
  EmptyStateComponent,
  ErrorBannerComponent,
  FilterBarComponent,
  PageContainerComponent,
  PageHeaderComponent,
  SkeletonListComponent,
} from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';
import { StatusPillComponent } from '../../shared/status-pill.component';

type QuickFilter = '' | 'pending' | 'high' | 'today';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [
    FormsModule,
    DatePipe,
    PageHeaderComponent,
    PageContainerComponent,
    StatusBadgeComponent,
    StatusPillComponent,
    BulkActionBarComponent,
    DataTableComponent,
    EmptyStateComponent,
    FilterBarComponent,
    SkeletonListComponent,
    ErrorBannerComponent,
    AlertReviewPaneComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header title="Review" subtitle="Review flagged activity from your cameras">
        <div actions>
          <app-filter-bar>
            <select [(ngModel)]="status" (change)="load()" aria-label="Status filter">
              <option value="PendingReview">Needs review</option>
              <option value="">All statuses</option>
              <option value="Confirmed">Confirmed</option>
              <option value="Dismissed">Not suspicious</option>
              <option value="FalsePositive">False alarm</option>
              <option value="NeedsFollowUp">Follow-up</option>
            </select>
          </app-filter-bar>
          <button class="ghost" type="button" (click)="load()">Refresh</button>
        </div>
        <div below class="filter-chips">
          <button type="button" class="chip" [class.active]="quickFilter === ''" (click)="setQuick('')">All</button>
          <button type="button" class="chip" [class.active]="quickFilter === 'pending'" (click)="setQuick('pending')">Needs review</button>
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
          <button class="ghost !text-danger !border-danger/35" type="button" (click)="deleteSelected()" [disabled]="bulkDeleting || selectedIds.size === 0">
            Delete selected
          </button>
          @if (storeId) {
            <button class="ghost !text-danger !border-danger/35" type="button" (click)="deleteAllInStore()" [disabled]="bulkDeleting">
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
        <app-empty-state title="No alerts — all clear" detail="When the system flags activity, it will appear here for your review." />
      } @else {
        @if (newCount > 0) {
          <div
            class="mb-3 cursor-pointer rounded-[6px] border border-border-strong bg-accent-soft px-3 py-2.5 text-[0.85rem] font-medium text-accent-2"
            role="status"
            (click)="dismissNewBanner()">
            {{ newCount }} new alert{{ newCount > 1 ? 's' : '' }} received — click to dismiss
          </div>
        }

        <div
          class="block"
          [class]="bp.isLgUp() && selectedId ? 'lg:grid lg:grid-cols-[minmax(280px,38%)_1fr] lg:gap-4 lg:items-start' : ''">
          <div class="min-w-0 lg:max-h-[calc(100vh-220px)] lg:overflow-y-auto">
            <app-data-table>
              <table desktop class="table">
                <thead>
                  <tr>
                    <!-- Column always rendered for every role — only the input is gated,
                         so table geometry never shifts between roles. -->
                    <th class="w-10 text-center"></th>
                    <th>Alert</th>
                    <th>Risk</th>
                    <th>Status</th>
                    <th class="lg:hidden"></th>
                  </tr>
                </thead>
                <tbody>
                  @for (a of pagedAlerts(); track a.id) {
                    <tr
                      [class.selected-row]="selectedIds.has(a.id) || (bp.isLgUp() && selectedId === a.id)"
                      [class.new-row]="newIds.has(a.id)"
                      [class.active-row]="bp.isLgUp() && selectedId === a.id"
                      (click)="openAlert(a.id)"
                      tabindex="0"
                      (keydown.enter)="openAlert(a.id)">
                      <td class="w-10 text-center" (click)="$event.stopPropagation()">
                        @if (auth.isManagerOrAdmin()) {
                          <input type="checkbox" [checked]="selectedIds.has(a.id)" (change)="toggleSelect(a.id, $event)" aria-label="Select alert" />
                        }
                      </td>
                      <td>
                        <div class="text-[0.9rem] font-semibold">{{ labelType(a.alertType) }}</div>
                        <div class="muted small">{{ relative(a.createdAt) }} · {{ a.createdAt | date:'MMM d, h:mm a' }}</div>
                      </td>
                      <td><app-status-badge [level]="a.riskLevel" /></td>
                      <td><app-status-pill [status]="a.status" /></td>
                      <td class="lg:hidden" (click)="$event.stopPropagation()">
                        <button class="ghost small" type="button" (click)="openAlert(a.id)">Review</button>
                      </td>
                    </tr>
                  }
                </tbody>
              </table>

              <div mobile class="flex flex-col gap-2.5">
                @for (a of pagedAlerts(); track a.id) {
                  <div class="alert-card-mobile" (click)="openAlert(a.id)" tabindex="0" (keydown.enter)="openAlert(a.id)">
                    <div class="mb-2 flex items-start justify-between gap-2">
                      <strong>{{ labelType(a.alertType) }}</strong>
                      <app-status-badge [level]="a.riskLevel" />
                    </div>
                    <div class="flex flex-wrap gap-2 text-[0.82rem]">
                      <app-status-pill [status]="a.status" />
                      <span class="muted">{{ relative(a.createdAt) }}</span>
                    </div>
                  </div>
                }
              </div>
            </app-data-table>

            @if (totalPages() > 1) {
              <div class="mt-4 flex items-center justify-center gap-3">
                <button class="ghost min-h-11 px-4" type="button" (click)="prevPage()" [disabled]="page === 1">Prev</button>
                <span class="muted">{{ rangeStart() }}–{{ rangeEnd() }} of {{ filteredAlerts.length }}</span>
                <button class="ghost min-h-11 px-4" type="button" (click)="nextPage()" [disabled]="page === totalPages()">Next</button>
              </div>
            }
          </div>

          @if (bp.isLgUp()) {
            <div class="lg:sticky lg:top-0 lg:max-h-[calc(100vh-180px)] lg:overflow-y-auto lg:border-l lg:border-border lg:pl-4">
              <app-alert-review-pane
                [alertId]="selectedId"
                [showNav]="true"
                [hasPrev]="!!prevId"
                [hasNext]="!!nextId"
                (prev)="selectById(prevId)"
                (next)="selectById(nextId)"
                (reviewed)="onReviewed($event)" />
            </div>
          }
        </div>
      }
    </app-page-container>
  `,
  styles: [`
    .active-row td { background: var(--accent-soft) !important; }
    .new-row td { animation: fadeIn 0.8s ease; }
    @keyframes fadeIn { from { background: var(--accent-soft); } to { background: transparent; } }
  `],
})
export class AlertsComponent implements OnInit, OnDestroy {
  stores: Store[] = [];
  alerts: Alert[] = [];
  storeId = '';
  status = 'PendingReview';
  quickFilter: QuickFilter = '';
  loading = false;
  error = '';
  newIds = new Set<string>();
  newCount = 0;
  page = 1;
  readonly pageSize = 20;
  bulkDeleting = false;
  selectedIds = new Set<string>();
  selectedId = '';
  prevId = '';
  nextId = '';
  private liveSub?: { unsubscribe: () => void };

  constructor(
    private api: ApiService,
    public auth: AuthService,
    public bp: BreakpointService,
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
      const idParam = params.get('id') ?? '';
      if (this.bp.isLgUp() && idParam) this.selectedId = idParam;
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

  statusLabel(status: string): string {
    return pillLabel(status);
  }

  relative(iso: string): string {
    return relativeTime(iso);
  }

  setQuick(filter: QuickFilter): void {
    this.quickFilter = filter;
    this.page = 1;
  }

  openAlert(id: string): void {
    if (this.bp.isLgUp()) {
      this.selectById(id);
      return;
    }
    this.router.navigate(['/app/alerts', id], {
      queryParams: {
        storeId: this.storeId || null,
        status: this.status || null,
        quick: this.quickFilter || null,
      },
    });
  }

  selectById(id: string): void {
    if (!id) return;
    this.selectedId = id;
    this.updateQueueNav();
    const tree = this.router.parseUrl(this.router.url);
    tree.queryParams['id'] = id;
    if (this.storeId) tree.queryParams['storeId'] = this.storeId;
    this.router.navigateByUrl(tree, { replaceUrl: true });
  }

  onReviewed(alert: Alert): void {
    const idx = this.alerts.findIndex((a) => a.id === alert.id);
    if (idx >= 0) this.alerts[idx] = alert;
    this.live.refreshPendingCount(this.storeId || undefined);
    const pending = this.filteredAlerts.filter((a) => a.status === 'PendingReview' && a.id !== alert.id);
    if (pending.length) {
      setTimeout(() => this.selectById(pending[0].id), 500);
    }
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
        if (this.bp.isLgUp()) {
          const idFromRoute = this.route.snapshot.queryParamMap.get('id');
          const pending = a.find((x) => x.status === 'PendingReview');
          const pick = idFromRoute && a.some((x) => x.id === idFromRoute)
            ? idFromRoute
            : pending?.id ?? a[0]?.id ?? '';
          if (pick) this.selectById(pick);
          else this.selectedId = '';
        }
        this.updateQueueNav();
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load alerts';
      },
    });
  }

  private updateQueueNav(): void {
    const list = this.filteredAlerts;
    const idx = list.findIndex((a) => a.id === this.selectedId);
    this.prevId = idx > 0 ? list[idx - 1].id : '';
    this.nextId = idx >= 0 && idx < list.length - 1 ? list[idx + 1].id : '';
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
