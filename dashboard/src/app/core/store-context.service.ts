import { Injectable, signal } from '@angular/core';
import { Store } from './models';

@Injectable({ providedIn: 'root' })
export class StoreContextService {
  readonly storeId = signal('');
  readonly stores = signal<Store[]>([]);

  setStores(stores: Store[]): void {
    this.stores.set(stores);
  }

  setStoreId(id: string): void {
    this.storeId.set(id);
  }

  activeStoreName(): string {
    const id = this.storeId();
    if (!id) return 'All stores';
    return this.stores().find((s) => s.id === id)?.name ?? 'All stores';
  }
}
