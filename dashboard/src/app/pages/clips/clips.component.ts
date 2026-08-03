import { Component, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink, ActivatedRoute, Router } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { StoreContextService } from '../../core/store-context.service';
import { ClipListItem, Store } from '../../core/models';
import { ConfirmDialogService } from '../../shared/confirm-dialog.service';
import { PageContainerComponent, PageHeaderComponent, BulkActionBarComponent, DataTableComponent, EmptyStateComponent, ErrorBannerComponent, SkeletonListComponent } from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-clips',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    DatePipe,
    PageHeaderComponent,
    PageContainerComponent,
    DataTableComponent,
    StatusBadgeComponent,
    BulkActionBarComponent,
    EmptyStateComponent,
    ErrorBannerComponent,
    SkeletonListComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header title="Clips">
        <div actions>
          <button class="ghost" type="button" (click)="load()">Refresh</button>
        </div>
      </app-page-header>

      @if (auth.isManagerOrAdmin() && clips.length > 0) {
        <app-bulk-action-bar
          [allSelected]="allSelected"
          [total]="clips.length"
          [selectedCount]="selectedIds.size"
          (toggleAll)="toggleSelectAll($event)">
          <button class="ghost danger" type="button" (click)="deleteSelected()" [disabled]="bulkDeleting || selectedIds.size === 0">Delete selected</button>
          @if (storeId) {
            <button class="ghost danger" type="button" (click)="deleteAllInStore()" [disabled]="bulkDeleting">Delete all in store</button>
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
      } @else if (clips.length === 0) {
        <app-empty-state
          title="No clips uploaded yet"
          detail="Clips appear after the connector detects motion and uploads video." />
      } @else {
        <app-data-table>
          <table desktop class="table">
            <thead>
              <tr>
                @if (auth.isManagerOrAdmin()) { <th class="chk-col"></th> }
                <th>Time</th>
                <th>Camera</th>
                <th>Status</th>
                <th>Duration</th>
                <th>AI events</th>
                <th>Risk</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (c of clips; track c.id) {
                <tr
                  [class.selected-row]="selectedIds.has(c.id)"
                  (click)="openClip(c.id)"
                  tabindex="0"
                  (keydown.enter)="openClip(c.id)">
                  @if (auth.isManagerOrAdmin()) {
                    <td class="chk-col" (click)="$event.stopPropagation()">
                      <input type="checkbox" [checked]="selectedIds.has(c.id)" (change)="toggleSelect(c.id, $event)" aria-label="Select clip" />
                    </td>
                  }
                  <td>{{ c.createdAt | date:'MMM d, h:mm a' }}</td>
                  <td>{{ c.cameraName }}</td>
                  <td><app-status-badge [level]="c.status" [label]="c.status" /></td>
                  <td>{{ c.durationSec }}s</td>
                  <td>{{ c.eventCount }}</td>
                  <td>{{ c.riskScore ?? '—' }}</td>
                  <td (click)="$event.stopPropagation()">
                    <button class="ghost small" type="button" [routerLink]="['/app/clips', c.id]">View</button>
                    @if (c.alertId) {
                      <a class="alert-link" [routerLink]="['/app/alerts', c.alertId]">Alert</a>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>

          <div mobile class="alert-cards">
            @for (c of clips; track c.id) {
              <div class="alert-card-mobile" (click)="openClip(c.id)" tabindex="0" (keydown.enter)="openClip(c.id)">
                <div class="alert-card-mobile-head">
                  <strong>{{ c.cameraName }}</strong>
                  <app-status-badge [level]="c.status" [label]="c.status" />
                </div>
                <div class="alert-card-mobile-meta">
                  <span class="muted">{{ c.createdAt | date:'MMM d, h:mm a' }}</span>
                  <span class="muted">{{ c.durationSec }}s · {{ c.eventCount }} events</span>
                  <span class="muted">Risk {{ c.riskScore ?? '—' }}</span>
                </div>
                <div class="alert-card-mobile-actions" (click)="$event.stopPropagation()">
                  <button class="ghost small" type="button" [routerLink]="['/app/clips', c.id]">View</button>
                  @if (c.alertId) {
                    <a class="alert-link" [routerLink]="['/app/alerts', c.alertId]">Alert</a>
                  }
                </div>
              </div>
            }
          </div>
        </app-data-table>
      }
    </app-page-container>
  `,
  styles: [`
    .chk-col { width: 40px; text-align: center; }
    .alert-link { margin-left: 8px; font-size: 0.78rem; }
    .alert-card-mobile-actions { margin-top: 8px; display: flex; align-items: center; gap: 8px; }
    button.danger { color: var(--danger); border-color: rgba(248, 113, 113, 0.35); }
  `],
})
export class ClipsComponent implements OnInit {
  clips: ClipListItem[] = [];
  stores: Store[] = [];
  storeId = '';
  loading = false;
  error = '';
  bulkDeleting = false;
  selectedIds = new Set<string>();

  constructor(
    private api: ApiService,
    public auth: AuthService,
    private route: ActivatedRoute,
    private router: Router,
    private storeCtx: StoreContextService,
    private confirm: ConfirmDialogService,
  ) {}

  get allSelected(): boolean {
    return this.clips.length > 0 && this.clips.every((c) => this.selectedIds.has(c.id));
  }

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => (this.stores = s));
    this.route.queryParamMap.subscribe((params) => {
      this.storeId = params.get('storeId') ?? this.storeCtx.storeId() ?? '';
      this.load();
    });
  }

  openClip(id: string): void {
    this.router.navigate(['/app/clips', id]);
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.selectedIds.clear();
    this.api.listClips(this.storeId || undefined).subscribe({
      next: (c) => {
        this.clips = c;
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load clips';
      },
    });
  }

  toggleSelect(id: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    if (checked) this.selectedIds.add(id);
    else this.selectedIds.delete(id);
  }

  toggleSelectAll(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.selectedIds.clear();
    if (checked) this.clips.forEach((c) => this.selectedIds.add(c.id));
  }

  async deleteSelected(): Promise<void> {
    const ids = [...this.selectedIds];
    if (!ids.length) return;
    const ok = await this.confirm.open({
      title: 'Delete clips',
      message: `Delete ${ids.length} selected clip(s)?`,
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
      title: 'Delete all clips',
      message: `Delete ALL clips in ${name}?`,
      confirmLabel: 'Delete all',
      danger: true,
    });
    if (!ok) return;
    this.runBulkDelete({ storeId: this.storeId, deleteAllInStore: true });
  }

  private runBulkDelete(body: { storeId?: string; ids?: string[]; deleteAllInStore?: boolean }): void {
    this.bulkDeleting = true;
    this.api.bulkDeleteClips(body).subscribe({
      next: () => {
        this.bulkDeleting = false;
        this.selectedIds.clear();
        this.load();
      },
      error: (e) => {
        this.bulkDeleting = false;
        this.error = e?.error?.error || 'Bulk delete failed';
      },
    });
  }
}
