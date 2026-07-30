import { AfterViewChecked, Component, ElementRef, ViewChild } from '@angular/core';
import { ConfirmDialogService } from './confirm-dialog.service';

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  template: `
    @if (dialog.visible() && dialog.options(); as opts) {
      <div class="backdrop" role="presentation" (click)="dialog.cancel()"></div>
      <div class="modal" role="alertdialog" [attr.aria-labelledby]="'confirm-title'" aria-modal="true">
        <h3 id="confirm-title">{{ opts.title }}</h3>
        <p>{{ opts.message }}</p>
        <div class="actions">
          <button #cancelBtn type="button" class="ghost" (click)="dialog.cancel()">{{ opts.cancelLabel }}</button>
          <button type="button" [class.danger]="opts.danger" (click)="dialog.confirm()">{{ opts.confirmLabel }}</button>
        </div>
      </div>
    }
  `,
  styles: [`
    .backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.4);
      z-index: 200;
    }
    .modal {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      z-index: 201;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      width: min(400px, calc(100vw - 32px));
      box-shadow: var(--shadow-md);
    }
    .modal h3 { margin: 0 0 8px; font-size: 1.05rem; }
    .modal p { margin: 0 0 20px; color: var(--text-muted); line-height: 1.5; }
    .actions { display: flex; justify-content: flex-end; gap: 8px; }
    button.danger { background: var(--danger); color: #fff; border: none; }
    button.danger:hover { filter: brightness(0.95); }
  `],
})
export class ConfirmDialogComponent implements AfterViewChecked {
  @ViewChild('cancelBtn') cancelBtn?: ElementRef<HTMLButtonElement>;
  private focused = false;

  constructor(public dialog: ConfirmDialogService) {}

  ngAfterViewChecked(): void {
    if (this.dialog.visible() && !this.focused) {
      this.cancelBtn?.nativeElement.focus();
      this.focused = true;
    } else if (!this.dialog.visible()) {
      this.focused = false;
    }
  }
}
