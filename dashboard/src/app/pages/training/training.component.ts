import { Component, HostListener, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { TrainingSampleDetail, TrainingSampleItem, TrainingStats } from '../../core/models';
import { alertTypeLabel } from '../../shared/alert-labels';
import {
  PageContainerComponent,
  PageHeaderComponent,
  DataTableComponent,
  EmptyStateComponent,
  ErrorBannerComponent,
  SkeletonListComponent,
} from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-training',
  standalone: true,
  imports: [
    FormsModule,
    DatePipe,
    PageContainerComponent,
    PageHeaderComponent,
    DataTableComponent,
    EmptyStateComponent,
    ErrorBannerComponent,
    SkeletonListComponent,
    StatusBadgeComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header title="Training dataset">
        <div actions>
          <button class="ghost" type="button" (click)="load()">Refresh</button>
          <button class="relative inline-flex items-center gap-2 disabled:opacity-65" type="button" disabled
                  title="Model training will be available in a later release">
            Train Model
            <span class="rounded-full bg-white/25 px-1.5 py-0.5 text-[0.62rem] font-bold uppercase tracking-[0.04em]">Coming Soon</span>
          </button>
        </div>
      </app-page-header>

      @if (error) {
        <app-error-banner [message]="error">
          <button class="ghost small" type="button" (click)="load()">Retry</button>
        </app-error-banner>
      }

      @if (stats) {
        <!-- .stat-tile/.sv are marker classes only (e2e verify-training.spec.ts queries them). -->
        <div class="mb-2 flex flex-wrap gap-3">
          <div class="stat-tile flex flex-1 basis-[120px] flex-col gap-0.5 rounded-ctl border border-border px-3 py-2"><span class="sv text-[1.15rem] font-bold">{{ stats.total }}</span><span class="text-xs text-ink-muted">Total samples</span></div>
          <div class="stat-tile flex flex-1 basis-[120px] flex-col gap-0.5 rounded-ctl border border-border px-3 py-2"><span class="sv text-[1.15rem] font-bold text-success">{{ stats.ready }}</span><span class="text-xs text-ink-muted">Ready</span></div>
          <div class="stat-tile flex flex-1 basis-[120px] flex-col gap-0.5 rounded-ctl border border-border px-3 py-2"><span class="sv text-[1.15rem] font-bold text-warning">{{ stats.pending }}</span><span class="text-xs text-ink-muted">Pending</span></div>
          <div class="stat-tile flex flex-1 basis-[120px] flex-col gap-0.5 rounded-ctl border border-border px-3 py-2"><span class="sv text-[1.15rem] font-bold text-ink-muted">{{ stats.excluded }}</span><span class="text-xs text-ink-muted">Excluded</span></div>
          <div class="stat-tile flex flex-1 basis-[120px] flex-col gap-0.5 rounded-ctl border border-border px-3 py-2"><span class="sv text-[1.15rem] font-bold text-danger">{{ stats.clipIssues }}</span><span class="text-xs text-ink-muted">Clip issues</span></div>
        </div>

        @if (patternRows.length) {
          <button type="button" class="mb-2 cursor-pointer border-none !bg-transparent !p-0 text-[0.85rem] !text-accent font-normal" (click)="showPatternStats = !showPatternStats">
            {{ showPatternStats ? 'Hide label counts by pattern' : 'Show label counts by pattern' }}
          </button>
          @if (showPatternStats) {
            <div class="mb-3 flex flex-wrap gap-2">
              @for (row of patternRows; track row.pattern) {
                <div class="inline-flex items-center gap-2 rounded-full border border-border px-2.5 py-1 text-[0.8rem]">
                  <span class="text-ink-muted">{{ label(row.pattern) }}</span>
                  <span class="font-semibold text-success" title="Positive labels">+{{ row.positive }}</span>
                  <span class="font-semibold text-danger" title="Hard-negative labels">−{{ row.hardNegative }}</span>
                </div>
              }
            </div>
          }
        }
      }

      @if (loading) {
        <app-skeleton-list />
      } @else if (samples.length === 0) {
        <app-empty-state
          title="No training samples yet"
          detail="Review alerts and confirm the patterns you see — every review becomes a dataset entry here." />
      } @else {
        <app-data-table>
          <table desktop class="table">
            <thead>
              <tr>
                <th>Updated</th>
                <th>Alert type</th>
                <th>Confirmed</th>
                <th>Labels</th>
                <th>Status</th>
                <th>Reviewer</th>
              </tr>
            </thead>
            <tbody>
              @for (s of samples; track s.id) {
                <tr
                  [class.selected-row]="detail?.id === s.id"
                  (click)="openDetail(s.id)"
                  tabindex="0"
                  (keydown.enter)="openDetail(s.id)">
                  <td>{{ s.updatedAt | date:'MMM d, h:mm a' }}</td>
                  <td>{{ label(s.alertType) }}</td>
                  <td class="max-w-[200px]">
                    @for (p of s.humanConfirmedPatterns; track p) {
                      <span class="mini-chip !border-accent !bg-accent !text-white">{{ label(p) }}</span>
                    } @empty { <span class="muted">—</span> }
                  </td>
                  <td class="whitespace-nowrap">
                    <span class="font-semibold text-success">{{ s.positiveCount }} pos</span> ·
                    <span class="font-semibold text-danger">{{ s.hardNegativeCount }} neg</span>
                  </td>
                  <td><app-status-badge [level]="statusLevel(s.datasetStatus)" [label]="s.datasetStatus" /></td>
                  <td class="max-w-[140px] overflow-hidden text-ellipsis whitespace-nowrap">{{ s.reviewerEmail || '—' }}</td>
                </tr>
              }
            </tbody>
          </table>

          <div mobile class="flex flex-col gap-2.5">
            @for (s of samples; track s.id) {
              <div class="alert-card-mobile" (click)="openDetail(s.id)" tabindex="0" (keydown.enter)="openDetail(s.id)">
                <div class="mb-2 flex items-start justify-between gap-2">
                  <strong>{{ label(s.alertType) }}</strong>
                  <app-status-badge [level]="statusLevel(s.datasetStatus)" [label]="s.datasetStatus" />
                </div>
                <div class="flex flex-wrap gap-2 text-[0.82rem]">
                  <span class="muted">{{ s.updatedAt | date:'MMM d, h:mm a' }}</span>
                  <span class="muted">{{ s.positiveCount }} pos · {{ s.hardNegativeCount }} neg · {{ s.reviewOutcome }}</span>
                </div>
              </div>
            }
          </div>
        </app-data-table>
      }

      @if (detail || detailLoading || detailError) {
        <div class="fixed inset-0 z-[200] bg-black/40" (click)="detail = undefined; detailError = ''; detailLoading = false;"></div>
        <!-- .detail-panel/.label-row are marker classes only (e2e verify-training.spec.ts queries them). -->
        <div class="detail-panel card fixed bottom-0 right-0 top-0 z-[201] !m-0 w-[min(760px,100vw)] overflow-y-auto !rounded-none border-l border-border !p-4 shadow-pop">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="m-0 text-base">Sample detail</h3>
            <button class="ghost small" type="button" (click)="detail = undefined; detailError = ''; detailLoading = false;">Close</button>
          </div>

          @if (detailLoading) {
            <p class="muted">Loading...</p>
          } @else if (detailError) {
            <app-error-banner [message]="detailError" />
          } @else if (detail) {
          <div class="flex flex-col gap-4">
            <div>
              @if (detail.clipUrl) {
                <video [src]="detail.clipUrl" controls width="100%"></video>
              } @else {
                <p class="muted">Clip not available — the dataset copy could not be found.</p>
              }
            </div>

            <div>
              <h4 class="m-0 mb-2 text-[0.9rem]">Per-pattern labels</h4>
              @if (!editing) {
                <div class="flex flex-col gap-1.5">
                  @for (l of detail.labels; track l.pattern) {
                    <div class="label-row flex items-center justify-between gap-2 text-[0.85rem]">
                      <span>{{ label(l.pattern) }}</span>
                      <span class="inline-flex gap-1">
                        @if (l.aiDetected) { <span class="mini-chip !border-accent !text-accent">AI</span> }
                        <span class="mini-chip"
                              [class.!border-success]="l.labelStatus === 'Positive'" [class.!text-success]="l.labelStatus === 'Positive'"
                              [class.!border-danger]="l.labelStatus === 'HardNegative'" [class.!text-danger]="l.labelStatus === 'HardNegative'">
                          {{ l.labelStatus }}
                        </span>
                      </span>
                    </div>
                  } @empty { <p class="muted">No labels.</p> }
                </div>
                <div class="mt-2.5 flex gap-2">
                  <button class="ghost small" type="button" (click)="startEdit()">Edit labels</button>
                  <button class="ghost small" type="button" (click)="toggleInclude()" [disabled]="savingDetail">
                    {{ detail.includeInTraining ? 'Exclude from training' : 'Include in training' }}
                  </button>
                </div>
              } @else {
                <div class="flex flex-wrap gap-2">
                  @for (p of allPatterns; track p) {
                    <label class="chip inline-flex min-w-0 max-w-full cursor-pointer select-none items-center gap-1.5" [class.active]="editSelected.has(p)">
                      <input class="pointer-events-none absolute opacity-0" type="checkbox" [checked]="editSelected.has(p)" (change)="toggleEdit(p)" />
                      <span class="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{{ label(p) }}</span>
                    </label>
                  }
                </div>
                <div class="mt-2.5 flex gap-2">
                  <button class="small" type="button" (click)="saveLabels()" [disabled]="savingDetail">Save labels</button>
                  <button class="ghost small" type="button" (click)="editing = false">Cancel</button>
                </div>
              }
              @if (detailError) { <app-error-banner [message]="detailError" /> }

              <h4 class="m-0 mb-2 mt-4 text-[0.9rem]">Audit</h4>
              <div class="muted small flex flex-col gap-1">
                <div>Reviewer: {{ detail.reviewerEmail || '—' }}</div>
                <div>Outcome: {{ detail.reviewOutcome }}</div>
                <div>Store: {{ detail.storeName }} · {{ detail.cameraName }}</div>
                <div>Model: {{ detail.modelVersion }} · Rules: {{ detail.ruleVersion }}</div>
                <div>Created: {{ detail.createdAt | date:'medium' }}</div>
                <div>Updated: {{ detail.updatedAt | date:'medium' }}</div>
                <div>In training: {{ detail.includeInTraining ? 'Yes' : 'No' }}</div>
              </div>
            </div>
          </div>
          }
        </div>
      }
    </app-page-container>
  `,
  styles: [`
    .selected-row td { background: var(--accent-soft) !important; }
    .mini-chip {
      display: inline-block; font-size: 0.7rem; padding: 2px 8px; margin: 1px;
      border-radius: 999px; border: 1px solid var(--border-strong);
    }
  `],
})
export class TrainingComponent implements OnInit {
  samples: TrainingSampleItem[] = [];
  stats?: TrainingStats;
  detail?: TrainingSampleDetail;
  allPatterns: string[] = [];
  loading = false;
  error = '';
  detailError = '';
  detailLoading = false;
  savingDetail = false;
  editing = false;
  editSelected = new Set<string>();
  showPatternStats = false;

  constructor(private api: ApiService, public auth: AuthService) {}

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.detail) this.detail = undefined;
  }

  ngOnInit(): void {
    this.api.getPatterns().subscribe({
      next: (p) => (this.allPatterns = p),
      error: () => (this.allPatterns = []),
    });
    this.load();
  }

  get patternRows(): { pattern: string; positive: number; hardNegative: number }[] {
    if (!this.stats) return [];
    const patterns = new Set([
      ...Object.keys(this.stats.positiveByPattern),
      ...Object.keys(this.stats.hardNegativeByPattern),
    ]);
    return [...patterns].sort().map((pattern) => ({
      pattern,
      positive: this.stats!.positiveByPattern[pattern] ?? 0,
      hardNegative: this.stats!.hardNegativeByPattern[pattern] ?? 0,
    }));
  }

  label(pattern: string): string {
    return alertTypeLabel(pattern);
  }

  statusLevel(status: string): string {
    switch (status) {
      case 'Ready': return 'Low';
      case 'PendingReview': return 'Medium';
      case 'ClipUnavailable':
      case 'CopyFailed': return 'High';
      default: return 'None';
    }
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.detail = undefined;
    this.api.listTrainingSamples().subscribe({
      next: (s) => {
        this.samples = s;
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load training samples';
      },
    });
    this.api.getTrainingStats().subscribe({
      next: (st) => (this.stats = st),
      error: () => (this.stats = undefined),
    });
  }

  openDetail(id: string): void {
    this.editing = false;
    this.detailError = '';
    this.detailLoading = true;
    this.api.getTrainingSample(id).subscribe({
      next: (d) => {
        this.detail = d;
        this.detailLoading = false;
      },
      error: (e) => {
        this.detailError = e?.error?.error || 'Failed to load sample';
        this.detailLoading = false;
      },
    });
  }

  startEdit(): void {
    if (!this.detail) return;
    this.editSelected = new Set(
      this.detail.labels.filter((l) => l.humanConfirmed).map((l) => l.pattern),
    );
    this.editing = true;
  }

  toggleEdit(pattern: string): void {
    if (this.editSelected.has(pattern)) this.editSelected.delete(pattern);
    else this.editSelected.add(pattern);
  }

  saveLabels(): void {
    if (!this.detail) return;
    this.savingDetail = true;
    this.detailError = '';
    this.api.updateTrainingLabels(this.detail.id, [...this.editSelected], this.detail.version).subscribe({
      next: (d) => {
        this.detail = d;
        this.savingDetail = false;
        this.editing = false;
        this.refreshRow(d);
      },
      error: (e) => {
        this.savingDetail = false;
        this.detailError = e?.error?.error || 'Failed to save labels';
      },
    });
  }

  toggleInclude(): void {
    if (!this.detail) return;
    this.savingDetail = true;
    this.detailError = '';
    this.api.setTrainingInclude(this.detail.id, !this.detail.includeInTraining).subscribe({
      next: (d) => {
        this.detail = d;
        this.savingDetail = false;
        this.refreshRow(d);
      },
      error: (e) => {
        this.savingDetail = false;
        this.detailError = e?.error?.error || 'Failed to update sample';
      },
    });
  }

  /** Keep the table row in sync with an updated detail without a full reload. */
  private refreshRow(d: TrainingSampleDetail): void {
    const row = this.samples.find((s) => s.id === d.id);
    if (row) {
      row.humanConfirmedPatterns = d.labels.filter((l) => l.humanConfirmed).map((l) => l.pattern);
      row.aiDetectedPatterns = d.labels.filter((l) => l.aiDetected).map((l) => l.pattern);
      row.positiveCount = d.labels.filter((l) => l.labelStatus === 'Positive').length;
      row.hardNegativeCount = d.labels.filter((l) => l.labelStatus === 'HardNegative').length;
      row.datasetStatus = d.datasetStatus;
      row.includeInTraining = d.includeInTraining;
      row.updatedAt = d.updatedAt;
    }
    this.api.getTrainingStats().subscribe({ next: (st) => (this.stats = st) });
  }
}
