import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { RiskConfig, Store } from '../../core/models';
import { PageContainerComponent, PageHeaderComponent, ErrorBannerComponent } from '../../shared/ui-components';

const DEFAULT_CONFIG: RiskConfig = {
  weights: {
    HighValueZoneEntry: 15,
    Dwell: 20,
    RepeatedHandling: 15,
    BagOpen: 20,
    Concealment: 20,
    ExitWithoutCheckout: 20,
    ShelfPickupNoCheckout: 25,
    BlindSpotMovement: 15,
    GroupDistraction: 10,
    HighValueActivity: 15,
    LowStaffRemoval: 10,
  },
  dwellThresholdSec: 30,
  dwellMaxSec: 90,
  repeatedHandlingThreshold: 3,
  groupSizeThreshold: 3,
  lowStaffStartHour: 22,
  lowStaffEndHour: 6,
  lowBand: 40,
  mediumBand: 70,
  highBand: 90,
};

@Component({
  selector: 'app-tuning',
  standalone: true,
  imports: [FormsModule, PageContainerComponent, PageHeaderComponent, ErrorBannerComponent],
  template: `
    <app-page-container>
      <app-page-header title="Risk tuning" subtitle="Adjust signal weights and alert thresholds.">
        <div actions>
          <select [(ngModel)]="storeId" (change)="load()" aria-label="Store scope">
            <option value="">Global default</option>
            @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
          </select>
        </div>
      </app-page-header>

      @if (error) {
        <app-error-banner [message]="error" />
      }

      <div class="mb-4 grid grid-cols-1 items-start gap-4 min-[980px]:grid-cols-2">
        <div class="card !mb-0">
          <h3>Signal weights</h3>
          <div class="grid grid-cols-[1fr_110px] items-center gap-2">
            <div class="text-[0.88rem] text-ink-muted">High-value zone entry</div><input type="number" [(ngModel)]="cfg.weights['HighValueZoneEntry']" />
            <div class="text-[0.88rem] text-ink-muted">Dwell (max)</div><input type="number" [(ngModel)]="cfg.weights['Dwell']" />
            <div class="text-[0.88rem] text-ink-muted">Repeated handling</div><input type="number" [(ngModel)]="cfg.weights['RepeatedHandling']" />
            <div class="text-[0.88rem] text-ink-muted">Bag / open-bag near shelf</div><input type="number" [(ngModel)]="cfg.weights['BagOpen']" />
            <div class="text-[0.88rem] text-ink-muted">Concealment</div><input type="number" [(ngModel)]="cfg.weights['Concealment']" />
            <div class="text-[0.88rem] text-ink-muted">Exit without checkout</div><input type="number" [(ngModel)]="cfg.weights['ExitWithoutCheckout']" />
            <div class="text-[0.88rem] text-ink-muted">Shelf pickup, no checkout</div><input type="number" [(ngModel)]="cfg.weights['ShelfPickupNoCheckout']" />
            <div class="text-[0.88rem] text-ink-muted">Blind-spot movement</div><input type="number" [(ngModel)]="cfg.weights['BlindSpotMovement']" />
            <div class="text-[0.88rem] text-ink-muted">Group distraction</div><input type="number" [(ngModel)]="cfg.weights['GroupDistraction']" />
            <div class="text-[0.88rem] text-ink-muted">High-value zone activity</div><input type="number" [(ngModel)]="cfg.weights['HighValueActivity']" />
            <div class="text-[0.88rem] text-ink-muted">Low-staff removal</div><input type="number" [(ngModel)]="cfg.weights['LowStaffRemoval']" />
          </div>
        </div>

        <div class="card !mb-0">
          <h3>Thresholds</h3>
          <div class="grid grid-cols-[1fr_110px] items-center gap-2">
            <div class="text-[0.88rem] text-ink-muted">Dwell threshold (s)</div><input type="number" [(ngModel)]="cfg.dwellThresholdSec" />
            <div class="text-[0.88rem] text-ink-muted">Dwell max (s)</div><input type="number" [(ngModel)]="cfg.dwellMaxSec" />
            <div class="text-[0.88rem] text-ink-muted">Repeated handling count</div><input type="number" [(ngModel)]="cfg.repeatedHandlingThreshold" />
            <div class="text-[0.88rem] text-ink-muted">Group size threshold</div><input type="number" [(ngModel)]="cfg.groupSizeThreshold" />
            <div class="text-[0.88rem] text-ink-muted">Low-staff start hour</div><input type="number" [(ngModel)]="cfg.lowStaffStartHour" />
            <div class="text-[0.88rem] text-ink-muted">Low-staff end hour</div><input type="number" [(ngModel)]="cfg.lowStaffEndHour" />
            <div class="text-[0.88rem] text-ink-muted">Low band</div><input type="number" [(ngModel)]="cfg.lowBand" />
            <div class="text-[0.88rem] text-ink-muted">Medium band</div><input type="number" [(ngModel)]="cfg.mediumBand" />
            <div class="text-[0.88rem] text-ink-muted">High band</div><input type="number" [(ngModel)]="cfg.highBand" />
          </div>
        </div>
      </div>

      <button type="button" (click)="save()" [disabled]="saving">Save config</button>
      @if (saved) { <span class="ml-2 text-success"> Saved.</span> }
    </app-page-container>
  `,
})
export class TuningComponent implements OnInit {
  stores: Store[] = [];
  storeId = '';
  cfg: RiskConfig = structuredClone(DEFAULT_CONFIG);
  saving = false;
  saved = false;
  error = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => (this.stores = s));
    this.load();
  }

  load(): void {
    this.saved = false;
    this.api.getRuleConfigs(this.storeId || undefined).subscribe((configs) => {
      const match = configs.find((c) => (this.storeId ? c.storeId === this.storeId : !c.storeId)) || configs[0];
      if (match?.configJson) {
        try { this.cfg = { ...DEFAULT_CONFIG, ...JSON.parse(match.configJson) }; }
        catch { this.cfg = structuredClone(DEFAULT_CONFIG); }
      } else {
        this.cfg = structuredClone(DEFAULT_CONFIG);
      }
    });
  }

  save(): void {
    this.saving = true;
    this.saved = false;
    this.error = '';
    this.api.upsertRuleConfig(this.cfg, this.storeId || undefined).subscribe({
      next: () => { this.saving = false; this.saved = true; },
      error: (e) => {
        this.saving = false;
        this.error = e?.error?.error || 'Failed to save config';
      },
    });
  }
}
