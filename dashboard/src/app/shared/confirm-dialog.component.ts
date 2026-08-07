import { AfterViewChecked, Component, ElementRef, ViewChild } from '@angular/core';
import { ConfirmDialogService } from './confirm-dialog.service';

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  template: `
    @if (dialog.visible() && dialog.options(); as opts) {
      <div class="fixed inset-0 z-[200] bg-black/40" role="presentation" (click)="dialog.cancel()"></div>
      <div
        class="fixed left-1/2 top-1/2 z-[201] w-[min(400px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-card border border-border bg-surface p-6 shadow-pop"
        role="alertdialog" [attr.aria-labelledby]="'confirm-title'" aria-modal="true">
        <h3 id="confirm-title" class="mb-2 mt-0 text-[1.05rem]">{{ opts.title }}</h3>
        <p class="mb-5 mt-0 leading-normal text-ink-muted">{{ opts.message }}</p>
        <div class="flex justify-end gap-2">
          <button #cancelBtn type="button" class="ghost" (click)="dialog.cancel()">{{ opts.cancelLabel }}</button>
          <button
            type="button"
            [class]="opts.danger ? '!border-none !bg-danger !text-white hover:brightness-95' : ''"
            (click)="dialog.confirm()">{{ opts.confirmLabel }}</button>
        </div>
      </div>
    }
  `,
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
