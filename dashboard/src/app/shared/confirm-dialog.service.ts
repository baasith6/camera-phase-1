import { Injectable, signal } from '@angular/core';

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ConfirmDialogService {
  readonly visible = signal(false);
  readonly options = signal<ConfirmOptions | null>(null);

  private resolver?: (confirmed: boolean) => void;

  open(opts: ConfirmOptions): Promise<boolean> {
    this.options.set({
      confirmLabel: 'Confirm',
      cancelLabel: 'Cancel',
      ...opts,
    });
    this.visible.set(true);
    return new Promise((resolve) => {
      this.resolver = resolve;
    });
  }

  confirm(): void {
    this.visible.set(false);
    this.resolver?.(true);
    this.resolver = undefined;
  }

  cancel(): void {
    this.visible.set(false);
    this.resolver?.(false);
    this.resolver = undefined;
  }
}
