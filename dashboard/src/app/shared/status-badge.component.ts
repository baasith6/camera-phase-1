import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  template: `<span class="badge" [class]="level.toLowerCase()">{{ label || level }}</span>`,
})
export class StatusBadgeComponent {
  @Input({ required: true }) level = '';
  @Input() label = '';
}
