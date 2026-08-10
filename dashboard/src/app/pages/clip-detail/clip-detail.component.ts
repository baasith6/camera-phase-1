import { Component, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { ClipDetail } from '../../core/models';
import { ConfirmDialogService } from '../../shared/confirm-dialog.service';
import { PageContainerComponent, PageHeaderComponent, ErrorBannerComponent, SkeletonListComponent } from '../../shared/ui-components';
import { StatusBadgeComponent } from '../../shared/status-badge.component';

@Component({
  selector: 'app-clip-detail',
  standalone: true,
  imports: [DatePipe, DecimalPipe, RouterLink, PageContainerComponent, PageHeaderComponent, ErrorBannerComponent, SkeletonListComponent, StatusBadgeComponent],
  template: `
    <app-page-container>
      @if (loading) {
        <app-skeleton-list [count]="4" />
      } @else if (clip) {
        <app-page-header [title]="clip.cameraName">
          <div actions class="flex items-center gap-2">
            <app-status-badge [level]="clip.status" [label]="clip.status" />
            @if (auth.isManagerOrAdmin()) {
              <button class="ghost !text-danger !border-danger/35" type="button" (click)="deleteClip()" [disabled]="deleting">Delete</button>
            }
          </div>
          <div below>
            <a class="text-[0.82rem] text-accent no-underline" routerLink="/app/clips">Back to Clips</a>
          </div>
        </app-page-header>

        <div class="grid items-start gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div class="flex min-w-0 flex-col gap-4">
            <div class="card !mb-0">
              <h3>Video</h3>
              @if (clip.clipUrl) {
                <video class="rounded-[6px] border border-border-strong" [src]="clip.clipUrl" controls width="100%"></video>
              } @else {
                <div class="px-4 py-6 text-center">
                  <p class="muted">Clip not available yet — it may still be uploading or processing.</p>
                </div>
              }
            </div>

            <div class="card !mb-0">
              <h3>AI events ({{ clip.eventCount }})</h3>
              @if (clip.aiEvents.length === 0) {
                <p class="muted">No AI events recorded for this clip.</p>
              } @else {
                <table class="table compact">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Zone</th>
                      <th>Confidence</th>
                      <th>Value</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (e of clip.aiEvents; track $index) {
                      <tr>
                        <td>{{ e.eventType }}</td>
                        <td>{{ e.zoneName || '—' }}</td>
                        <td>{{ e.confidence | number:'1.0-2' }}</td>
                        <td>{{ e.value | number:'1.0-1' }}</td>
                        <td>{{ e.startTs | date:'h:mm:ss a' }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              }
            </div>
          </div>

          <div class="flex min-w-0 flex-col gap-4">
            <div class="card !mb-0">
              <h3>Analysis</h3>
              <div class="flex flex-col">
                <div class="detail-item"><span class="dk">Store</span><span>{{ clip.storeName }}</span></div>
                <div class="detail-item"><span class="dk">Trigger</span><span>{{ clip.triggerReason }}</span></div>
                <div class="detail-item"><span class="dk">Duration</span><span>{{ clip.durationSec | number:'1.0-1' }}s</span></div>
                <div class="detail-item"><span class="dk">Uploaded</span><span>{{ clip.createdAt | date:'medium' }}</span></div>
                @if (clip.analyzedAt) {
                  <div class="detail-item"><span class="dk">Analyzed</span><span>{{ clip.analyzedAt | date:'medium' }}</span></div>
                }
                @if (clip.modelVersion) {
                  <div class="detail-item"><span class="dk">Model</span><span class="mono">{{ clip.modelVersion }}</span></div>
                }
                <div class="detail-item">
                  <span class="dk">Risk score</span>
                  <span class="font-semibold" [class.text-warning]="(clip.riskScore ?? 0) >= 40">
                    {{ clip.riskScore ?? '—' }}
                  </span>
                </div>
              </div>
            </div>

            @if (clip.analysisNote) {
              <div class="card !mb-0 !border-warning-soft">
                <p class="muted small">{{ clip.analysisNote }}</p>
              </div>
            }

            @if (clip.alertId) {
              <div class="card !mb-0">
                <p>An alert was created from this clip.</p>
                <a
                  class="mt-2 inline-block rounded-[6px] border border-border-strong px-2.5 py-1.5 text-[0.85rem] text-accent no-underline"
                  [routerLink]="['/app/alerts', clip.alertId]">View alert</a>
              </div>
            } @else if (clip.status === 'Analyzed' && (clip.riskScore ?? 0) < 40) {
              <div class="card !mb-0 !border-warning-soft">
                <h3>No alert yet</h3>
                <p class="muted small">
                  Alerts are created when the risk score reaches 40 or higher.
                  This clip scored {{ clip.riskScore ?? 0 }} — review the video and AI events above.
                </p>
              </div>
            }
          </div>
        </div>
      } @else if (error) {
        <app-error-banner [message]="error" />
      }
    </app-page-container>
  `,
  styles: [`
    .detail-item {
      display: flex; align-items: center; justify-content: space-between; gap: 1rem;
      padding: 0.5rem 0; border-bottom: 1px solid var(--border); font-size: 0.88rem;
    }
    .detail-item:last-child { border-bottom: none; }
    .dk { color: var(--text-muted); font-size: 0.8rem; }
    .table.compact th, .table.compact td { font-size: 0.82rem; padding: 0.35rem 0.5rem; }
  `],
})
export class ClipDetailComponent implements OnInit {
  clip?: ClipDetail;
  error = '';
  deleting = false;
  loading = true;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService,
    public auth: AuthService,
    private confirm: ConfirmDialogService,
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getClip(id).subscribe({
      next: (c) => {
        this.clip = c;
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.error || 'Failed to load clip';
      },
    });
  }

  async deleteClip(): Promise<void> {
    if (!this.clip) return;
    const ok = await this.confirm.open({
      title: 'Delete clip',
      message: 'Delete this clip from cloud storage and remove all analysis?',
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;
    this.deleting = true;
    this.api.deleteClip(this.clip.id).subscribe({
      next: () => this.router.navigate(['/app/clips']),
      error: (e) => {
        this.deleting = false;
        this.error = e?.error?.error || 'Delete failed';
      },
    });
  }
}
