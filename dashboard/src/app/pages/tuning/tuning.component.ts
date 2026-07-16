import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { RiskConfig, Store } from '../../core/models';

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
  imports: [FormsModule],
  template: `
    <div class="header-row">
      <h2>Risk Tuning</h2>
      <select [(ngModel)]="storeId" (change)="load()">
        <option value="">Global default</option>
        @for (s of stores; track s.id) { <option [value]="s.id">{{ s.name }}</option> }
      </select>
    </div>

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
        <div class="k">Low-staff start hour (0-23)</div><input type="number" [(ngModel)]="cfg.lowStaffStartHour" />
        <div class="k">Low-staff end hour (0-23)</div><input type="number" [(ngModel)]="cfg.lowStaffEndHour" />
        <div class="k">Low band (analytics ≥)</div><input type="number" [(ngModel)]="cfg.lowBand" />
        <div class="k">Medium band (alert ≥)</div><input type="number" [(ngModel)]="cfg.mediumBand" />
        <div class="k">High band (priority ≥)</div><input type="number" [(ngModel)]="cfg.highBand" />
      </div>
    </div>

    <button (click)="save()" [disabled]="saving">Save config</button>
    @if (saved) { <span class="ok"> Saved.</span> }
  `,
  styles: [`
    .header-row { display:flex; justify-content:space-between; align-items:center; }
    .kv { display:grid; grid-template-columns:220px 120px; gap:.4rem; align-items:center; }
    .k { color:#8ab4f8; }
    .ok { color:#7bd88f; }
  `],
})
export class TuningComponent implements OnInit {
  stores: Store[] = [];
  storeId = '';
  cfg: RiskConfig = structuredClone(DEFAULT_CONFIG);
  saving = false;
  saved = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.listStores().subscribe((s) => (this.stores = s));
    this.load();
  }

  load(): void {
    this.saved = false;
    this.api.getRuleConfigs(this.storeId || undefined).subscribe((configs) => {
      // Prefer the most specific (store) config, else global.
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
    this.saving = true; this.saved = false;
    this.api.upsertRuleConfig(this.cfg, this.storeId || undefined).subscribe({
      next: () => { this.saving = false; this.saved = true; },
      error: () => { this.saving = false; },
    });
  }
}
