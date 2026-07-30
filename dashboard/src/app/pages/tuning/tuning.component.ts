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

      <div class="tuning-grid">
        <div class="card">
          <h3>Signal weights</h3>
          <div class="kv">
            <div class="k">High-value zone entry</div><input type="number" [(ngModel)]="cfg.weights['HighValueZoneEntry']" />
            <div class="k">Dwell (max)</div><input type="number" [(ngModel)]="cfg.weights['Dwell']" />
            <div class="k">Repeated handling</div><input type="number" [(ngModel)]="cfg.weights['RepeatedHandling']" />
            <div class="k">Bag / open-bag near shelf</div><input type="number" [(ngModel)]="cfg.weights['BagOpen']" />
            <div class="k">Concealment</div><input type="number" [(ngModel)]="cfg.weights['Concealment']" />
            <div class="k">Exit without checkout</div><input type="number" [(ngModel)]="cfg.weights['ExitWithoutCheckout']" />
            <div class="k">Shelf pickup, no checkout</div><input type="number" [(ngModel)]="cfg.weights['ShelfPickupNoCheckout']" />
            <div class="k">Blind-spot movement</div><input type="number" [(ngModel)]="cfg.weights['BlindSpotMovement']" />
            <div class="k">Group distraction</div><input type="number" [(ngModel)]="cfg.weights['GroupDistraction']" />
            <div class="k">High-value zone activity</div><input type="number" [(ngModel)]="cfg.weights['HighValueActivity']" />
            <div class="k">Low-staff removal</div><input type="number" [(ngModel)]="cfg.weights['LowStaffRemoval']" />
          </div>
        </div>

        <div class="card">
          <h3>Thresholds</h3>
          <div class="kv">
            <div class="k">Dwell threshold (s)</div><input type="number" [(ngModel)]="cfg.dwellThresholdSec" />
            <div class="k">Dwell max (s)</div><input type="number" [(ngModel)]="cfg.dwellMaxSec" />
            <div class="k">Repeated handling count</div><input type="number" [(ngModel)]="cfg.repeatedHandlingThreshold" />
            <div class="k">Group size threshold</div><input type="number" [(ngModel)]="cfg.groupSizeThreshold" />
            <div class="k">Low-staff start hour</div><input type="number" [(ngModel)]="cfg.lowStaffStartHour" />
            <div class="k">Low-staff end hour</div><input type="number" [(ngModel)]="cfg.lowStaffEndHour" />
            <div class="k">Low band</div><input type="number" [(ngModel)]="cfg.lowBand" />
            <div class="k">Medium band</div><input type="number" [(ngModel)]="cfg.mediumBand" />
            <div class="k">High band</div><input type="number" [(ngModel)]="cfg.highBand" />
          </div>
        </div>
      </div>

      <button type="button" (click)="save()" [disabled]="saving">Save config</button>
      @if (saved) { <span class="ok"> Saved.</span> }
    </app-page-container>
  `,
  styles: [`
    .tuning-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; margin-bottom: 16px; }
    @media (max-width: 980px) { .tuning-grid { grid-template-columns: 1fr; } }
    .kv { display: grid; grid-template-columns: 1fr 110px; gap: 8px; align-items: center; }
    .k { color: var(--text-muted); font-size: 0.88rem; }
    .ok { color: var(--success); margin-left: 8px; }
  `],
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
