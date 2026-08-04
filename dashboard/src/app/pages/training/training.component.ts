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
          <button class="primary train-btn" type="button" disabled
                  title="Model training will be available in a later release">
            Train Model
            <span class="soon-badge">Coming Soon</span>
          </button>
        </div>
      </app-page-header>

      @if (error) {
        <app-error-banner [message]="error">
          <button class="ghost small" type="button" (click)="load()">Retry</button>
        </app-error-banner>
      }

      @if (stats) {
        <div class="stat-row">
          <div class="stat-tile"><span class="sv">{{ stats.total }}</span><span class="sl">Total samples</span></div>
          <div class="stat-tile"><span class="sv ok">{{ stats.ready }}</span><span class="sl">Ready</span></div>
          <div class="stat-tile"><span class="sv warn">{{ stats.pending }}</span><span class="sl">Pending</span></div>
          <div class="stat-tile"><span class="sv muted-v">{{ stats.excluded }}</span><span class="sl">Excluded</span></div>
          <div class="stat-tile"><span class="sv danger-v">{{ stats.clipIssues }}</span><span class="sl">Clip issues</span></div>
        </div>

        @if (patternRows.length) {
          <button type="button" class="link-toggle" (click)="showPatternStats = !showPatternStats">
            {{ showPatternStats ? 'Hide label counts by pattern' : 'Show label counts by pattern' }}
          </button>
          @if (showPatternStats) {
            <div class="pattern-stats">
              @for (row of patternRows; track row.pattern) {
                <div class="pattern-stat">
                  <span class="pn">{{ label(row.pattern) }}</span>
                  <span class="pos" title="Positive labels">+{{ row.positive }}</span>
                  <span class="neg" title="Hard-negative labels">−{{ row.hardNegative }}</span>
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
                  <td class="chips-cell">
                    @for (p of s.humanConfirmedPatterns; track p) {
                      <span class="mini-chip on">{{ label(p) }}</span>
                    } @empty { <span class="muted">—</span> }
                  </td>
                  <td class="nowrap">
                    <span class="pos">{{ s.positiveCount }} pos</span> ·
                    <span class="neg">{{ s.hardNegativeCount }} neg</span>
                  </td>
                  <td><app-status-badge [level]="statusLevel(s.datasetStatus)" [label]="s.datasetStatus" /></td>
                  <td class="ellipsis">{{ s.reviewerEmail || '—' }}</td>
                </tr>
              }
            </tbody>
          </table>

          <div mobile class="alert-cards">
            @for (s of samples; track s.id) {
              <div class="alert-card-mobile" (click)="openDetail(s.id)" tabindex="0" (keydown.enter)="openDetail(s.id)">
                <div class="alert-card-mobile-head">
                  <strong>{{ label(s.alertType) }}</strong>
                  <app-status-badge [level]="statusLevel(s.datasetStatus)" [label]="s.datasetStatus" />
                </div>
                <div class="alert-card-mobile-meta">
                  <span class="muted">{{ s.updatedAt | date:'MMM d, h:mm a' }}</span>
                  <span class="muted">{{ s.positiveCount }} pos · {{ s.hardNegativeCount }} neg · {{ s.reviewOutcome }}</span>
                </div>
              </div>
            }
          </div>
        </app-data-table>
      }

      @if (detail) {
        <div class="drawer-backdrop" (click)="detail = undefined"></div>
        <div class="card detail-panel">
          <div class="detail-head">
            <h3>Sample detail</h3>
            <button class="ghost small" type="button" (click)="detail = undefined">Close</button>
          </div>

          <div class="detail-grid">
            <div class="detail-main">
              @if (detail.clipUrl) {
                <video class="clip" [src]="detail.clipUrl" controls width="100%"></video>
              } @else {
                <p class="muted">Clip not available — the dataset copy could not be found.</p>
              }
            </div>

            <div class="detail-side">
              <h4>Per-pattern labels</h4>
              @if (!editing) {
                <div class="label-list">
                  @for (l of detail.labels; track l.pattern) {
                    <div class="label-row">
                      <span class="ln">{{ label(l.pattern) }}</span>
                      <span class="badges">
                        @if (l.aiDetected) { <span class="mini-chip ai">AI</span> }
                        <span class="mini-chip" [class.pos-chip]="l.labelStatus === 'Positive'"
                              [class.neg-chip]="l.labelStatus === 'HardNegative'">
                          {{ l.labelStatus }}
                        </span>
                      </span>
                    </div>
                  } @empty { <p class="muted">No labels.</p> }
                </div>
                <div class="detail-actions">
                  <button class="ghost small" type="button" (click)="startEdit()">Edit labels</button>
                  <button class="ghost small" type="button" (click)="toggleInclude()" [disabled]="savingDetail">
                    {{ detail.includeInTraining ? 'Exclude from training' : 'Include in training' }}
                  </button>
                </div>
              } @else {
                <div class="chip-grid">
                  @for (p of allPatterns; track p) {
                    <label class="chip" [class.on]="editSelected.has(p)">
                      <input type="checkbox" [checked]="editSelected.has(p)" (change)="toggleEdit(p)" />
                      <span>{{ label(p) }}</span>
                    </label>
                  }
                </div>
                <div class="detail-actions">
                  <button class="primary small" type="button" (click)="saveLabels()" [disabled]="savingDetail">Save labels</button>
                  <button class="ghost small" type="button" (click)="editing = false">Cancel</button>
                </div>
              }
              @if (detailError) { <app-error-banner [message]="detailError" /> }

              <h4>Audit</h4>
              <div class="audit-list muted small">
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
        </div>
      }
    </app-page-container>
  `,
  styles: [`
    .train-btn { position: relative; display: inline-flex; align-items: center; gap: 8px; }
    .train-btn:disabled { opacity: 0.65; cursor: not-allowed; }
    .soon-badge {
      font-size: 0.62rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
      padding: 2px 6px; border-radius: 999px; background: rgba(255, 255, 255, 0.25);
    }
    .stat-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
    .stat-tile {
      flex: 1 1 120px; display: flex; flex-direction: column; gap: 2px;
      padding: 8px 12px; border: 1px solid var(--border, rgba(128,128,128,0.25));
      border-radius: var(--radius-sm); background: var(--card, transparent);
    }
    .sv { font-size: 1.15rem; font-weight: 700; }
    .sv.ok { color: var(--success); }
    .sv.warn { color: var(--warning, #f59e0b); }
    .sv.muted-v { color: var(--text-muted); }
    .sv.danger-v { color: var(--danger); }
    .sl { font-size: 0.75rem; color: var(--text-muted); }
    .link-toggle {
      background: none; border: none; color: var(--accent); padding: 0;
      font-size: 0.85rem; cursor: pointer; margin-bottom: 8px;
    }
    .pattern-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .pattern-stat {
      display: inline-flex; align-items: center; gap: 8px; font-size: 0.8rem;
      padding: 4px 10px; border: 1px solid var(--border, rgba(128,128,128,0.25));
      border-radius: 999px;
    }
    .pn { color: var(--text-muted); }
    .pos { color: var(--success); font-weight: 600; }
    .neg { color: var(--danger); font-weight: 600; }
    .chips-cell { max-width: 200px; }
    .mini-chip {
      display: inline-block; font-size: 0.7rem; padding: 2px 8px; margin: 1px;
      border-radius: 999px; border: 1px solid var(--border, rgba(128,128,128,0.35));
    }
    .mini-chip.ai { border-color: var(--accent); color: var(--accent); }
    .mini-chip.on { background: var(--accent); border-color: var(--accent); color: white; }
    .mini-chip.pos-chip { border-color: var(--success); color: var(--success); }
    .mini-chip.neg-chip { border-color: var(--danger); color: var(--danger); }
    .nowrap { white-space: nowrap; }
    .ellipsis { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .drawer-backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); z-index: 200; }
    .detail-panel {
      position: fixed; top: 0; right: 0; bottom: 0; width: min(760px, 100vw);
      z-index: 201; overflow-y: auto; margin: 0; padding: 16px;
      border-radius: 0; border-left: 1px solid var(--border, rgba(128,128,128,0.25));
      box-shadow: var(--shadow-md, 0 8px 24px rgba(0,0,0,0.25));
    }
    .detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .detail-head h3 { margin: 0; font-size: 1rem; }
    .detail-grid { display: flex; flex-direction: column; gap: 16px; }
    .detail-side h4 { margin: 0 0 8px; font-size: 0.9rem; }
    .detail-side h4:not(:first-child) { margin-top: 16px; }
    .label-list { display: flex; flex-direction: column; gap: 6px; }
    .label-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 0.85rem; }
    .badges { display: inline-flex; gap: 4px; }
    .detail-actions { display: flex; gap: 8px; margin-top: 10px; }
    .audit-list { display: flex; flex-direction: column; gap: 4px; }
    .chip-grid { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 12px; border-radius: 999px; cursor: pointer;
      border: 1px solid var(--border, rgba(128,128,128,0.35));
      font-size: 0.85rem; user-select: none;
      max-width: 100%; min-width: 0;
    }
    .chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
    .chip input { position: absolute; opacity: 0; pointer-events: none; }
    .chip.on { background: var(--accent); border-color: var(--accent); color: white; }
    button.primary { background: var(--accent); color: white; border: none; border-radius: var(--radius-sm); padding: 0.5rem 1rem; font-weight: 600; cursor: pointer; }
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
    this.api.getTrainingSample(id).subscribe({
      next: (d) => (this.detail = d),
      error: (e) => (this.detailError = e?.error?.error || 'Failed to load sample'),
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
    this.api.updateTrainingLabels(this.detail.id, [...this.editSelected]).subscribe({
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
