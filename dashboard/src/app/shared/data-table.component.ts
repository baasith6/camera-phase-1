import { Component } from '@angular/core';

@Component({
  selector: 'app-data-table',
  standalone: true,
  template: `
    <div class="data-table-wrap data-table-desktop">
      <ng-content select="[desktop]"></ng-content>
    </div>
    <div class="data-table-mobile">
      <ng-content select="[mobile]"></ng-content>
    </div>
  `,
  styles: [`
    .data-table-mobile { display: none; }
    @media (max-width: 768px) {
      .data-table-desktop { display: none; }
      .data-table-mobile { display: block; }
    }
  `],
})
export class DataTableComponent {}
