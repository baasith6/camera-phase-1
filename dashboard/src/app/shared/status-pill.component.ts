import { Component, Input } from '@angular/core';
import { pillClass, pillLabel } from './alert-labels';

@Component({
  selector: 'app-status-pill',
  standalone: true,
  template: `<span class="pill" [class]="cls">{{ text }}</span>`,
})
export class StatusPillComponent {
  @Input({ required: true }) status = '';

  get cls(): string {
    return pillClass(this.status);
  }

  get text(): string {
    return pillLabel(this.status);
  }
}
