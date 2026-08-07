import { Component } from '@angular/core';

@Component({
  selector: 'app-data-table',
  standalone: true,
  template: `
    <!-- .data-table-desktop is a marker class only (e2e smoke.spec.ts queries it). -->
    <div class="data-table-desktop data-table-wrap hidden md:block">
      <ng-content select="[desktop]"></ng-content>
    </div>
    <div class="md:hidden">
      <ng-content select="[mobile]"></ng-content>
    </div>
  `,
})
export class DataTableComponent {}
