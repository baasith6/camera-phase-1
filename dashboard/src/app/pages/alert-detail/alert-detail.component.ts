import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { Alert } from '../../core/models';
import { AlertReviewPaneComponent } from '../../shared/alert-review-pane.component';
import {
  ErrorBannerComponent,
  PageContainerComponent,
  PageHeaderComponent,
} from '../../shared/ui-components';

@Component({
  selector: 'app-alert-detail',
  standalone: true,
  imports: [
    RouterLink,
    PageContainerComponent,
    PageHeaderComponent,
    ErrorBannerComponent,
    AlertReviewPaneComponent,
  ],
  template: `
    <app-page-container>
      @if (loadError) {
        <app-error-banner [message]="loadError">
          <a class="ghost small" routerLink="/app/alerts" [queryParams]="backQuery">Back to Review</a>
        </app-error-banner>
      } @else {
        <app-page-header title="Review alert">
          <div actions class="queue-nav">
            <button class="ghost" type="button" (click)="goPrev()" [disabled]="!prevId">Previous</button>
            <button class="ghost" type="button" (click)="goNext()" [disabled]="!nextId">Next</button>
          </div>
          <div below>
            <a class="back-link" routerLink="/app/alerts" [queryParams]="backQuery">Back to Review</a>
          </div>
        </app-page-header>

        <app-alert-review-pane
          [alertId]="alertId"
          (reviewed)="onReviewed()" />
      }
    </app-page-container>
  `,
  styles: [`
    .queue-nav { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .queue-nav button { min-height: 44px; }
    .back-link { font-size: 0.82rem; color: var(--accent); text-decoration: none; }
  `],
})
export class AlertDetailComponent implements OnInit {
  alertId = '';
  queue: Alert[] = [];
  prevId = '';
  nextId = '';
  loadError = '';
  backQuery: Record<string, string | null> = {};

  constructor(private route: ActivatedRoute, private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.alertId = this.route.snapshot.paramMap.get('id')!;
    const storeId = this.route.snapshot.queryParamMap.get('storeId') ?? undefined;
    const status = this.route.snapshot.queryParamMap.get('status') ?? undefined;
    this.backQuery = { storeId: storeId ?? null, status: status ?? null };

    this.api.listAlerts(storeId, status).subscribe({
      next: (list) => {
        this.queue = list;
        const idx = list.findIndex((a) => a.id === this.alertId);
        this.prevId = idx > 0 ? list[idx - 1].id : '';
        this.nextId = idx >= 0 && idx < list.length - 1 ? list[idx + 1].id : '';
        if (idx < 0) this.loadError = 'Alert not found';
      },
      error: (e) => {
        this.loadError = e?.error?.error || 'Failed to load alerts';
      },
    });
  }

  goPrev(): void {
    if (this.prevId) this.router.navigate(['/app/alerts', this.prevId], { queryParams: this.backQuery });
  }

  goNext(): void {
    if (this.nextId) this.router.navigate(['/app/alerts', this.nextId], { queryParams: this.backQuery });
  }

  onReviewed(): void {
    if (this.nextId) setTimeout(() => this.goNext(), 600);
  }
}
