import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { PageContainerComponent, PageHeaderComponent } from '../../shared/ui-components';
import { SetupCamerasStepComponent } from './setup-cameras-step.component';
import { SetupConnectorStepComponent } from './setup-connector-step.component';
import { SetupContextService } from './setup-context.service';
import { SetupVerifyStepComponent } from './setup-verify-step.component';
import { SetupZonesStepComponent } from './setup-zones-step.component';

@Component({
  selector: 'app-setup',
  standalone: true,
  providers: [SetupContextService],
  imports: [
    PageContainerComponent,
    PageHeaderComponent,
    SetupConnectorStepComponent,
    SetupCamerasStepComponent,
    SetupZonesStepComponent,
    SetupVerifyStepComponent,
  ],
  template: `
    <app-page-container>
      <app-page-header
        title="Setup"
        subtitle="Set up cameras step by step — about 15 minutes" />

      <div class="stepper" role="tablist" aria-label="Setup steps">
        @for (s of ctx.steps; track s.id) {
          <button
            type="button"
            class="stepper-btn"
            [class.active]="ctx.step === s.id"
            [class.done]="ctx.step > s.id"
            (click)="ctx.goToStep(s.id)">
            @if (ctx.step > s.id) { ✓ }
            {{ s.label }}
          </button>
        }
      </div>

      @switch (ctx.step) {
        @case (1) { <app-setup-connector-step /> }
        @case (2) { <app-setup-cameras-step /> }
        @case (3) { <app-setup-zones-step /> }
        @case (4) { <app-setup-verify-step /> }
      }
    </app-page-container>
  `,
})
export class SetupComponent implements OnInit, OnDestroy {
  readonly ctx: SetupContextService;
  private pollTimer?: ReturnType<typeof setInterval>;

  constructor(
    ctx: SetupContextService,
    private route: ActivatedRoute,
    private api: ApiService,
  ) {
    this.ctx = ctx;
  }

  ngOnInit(): void {
    this.ctx.loadStores();
    this.ctx.loadInstallerInfo();
    this.route.queryParamMap.subscribe((params) => {
      const fromQuery = params.get('storeId');
      const stepParam = params.get('step');
      if (stepParam) {
        const n = parseInt(stepParam, 10);
        if (n >= 1 && n <= 4) this.ctx.step = n;
      }
      this.api.listStores().subscribe((s) => {
        this.ctx.stores = s;
        const pick = fromQuery || this.ctx.auth.storeId() || '';
        if (pick && s.some((x) => x.id === pick)) this.ctx.selectStore(pick);
      });
    });
    this.pollTimer = setInterval(() => {
      if (this.ctx.storeId) this.ctx.refreshConnectors();
    }, 15_000);
  }

  ngOnDestroy(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
  }
}
