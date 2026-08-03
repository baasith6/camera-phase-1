import { Injectable, OnDestroy, inject, signal } from '@angular/core';
import { Subject } from 'rxjs';
import { API_BASE } from './api.config';
import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { Alert } from './models';

export interface LiveAlertEvent {
  alert: Alert;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class LiveAlertsService implements OnDestroy {
  readonly connected = signal(false);
  readonly pendingCount = signal(0);
  readonly newAlert$ = new Subject<LiveAlertEvent>();
  readonly toastMessage = signal('');

  private api = inject(ApiService);
  private es?: EventSource;
  private retryTimer?: ReturnType<typeof setTimeout>;
  private toastTimer?: ReturnType<typeof setTimeout>;
  private retryMs = 2000;

  constructor(private auth: AuthService) {}

  connect(): void {
    if (!this.auth.token) return;
    this.disconnect();
    const url = `${API_BASE}/api/alerts/stream?access_token=${encodeURIComponent(this.auth.token)}`;
    this.es = new EventSource(url);

    this.es.addEventListener('connected', () => {
      this.connected.set(true);
      this.retryMs = 2000;
    });

    this.es.addEventListener('alert', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        const alert: Alert = {
          id: data.alertId,
          alertType: data.alertType,
          riskLevel: data.riskLevel,
          riskScore: data.riskScore,
          status: 'PendingReview',
          createdAt: data.createdAt,
          storeId: data.storeId,
          evidenceJson: '[]',
          cameraId: '',
          clipId: '',
          modelVersion: '',
          ruleVersion: '',
        };
        const message = `New ${data.riskLevel} risk alert`;
        this.newAlert$.next({ alert, message });
        this.pendingCount.update((n) => n + 1);
        this.showToast(`${message} — ${data.alertType}`);
      } catch {
        /* ignore malformed events */
      }
    });

    this.es.onerror = () => {
      this.connected.set(false);
      this.es?.close();
      this.retryTimer = setTimeout(() => this.connect(), this.retryMs);
      this.retryMs = Math.min(this.retryMs * 2, 30000);
    };
  }

  disconnect(): void {
    this.es?.close();
    this.es = undefined;
    clearTimeout(this.retryTimer);
    this.connected.set(false);
  }

  showToast(msg: string): void {
    this.toastMessage.set(msg);
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => this.toastMessage.set(''), 5000);
  }

  clearToast(): void {
    this.toastMessage.set('');
    clearTimeout(this.toastTimer);
  }

  refreshPendingCount(storeId?: string): void {
    this.api.listAlerts(storeId || undefined, 'PendingReview').subscribe({
      next: (alerts) => this.pendingCount.set(alerts.length),
      error: () => this.pendingCount.set(0),
    });
  }

  ngOnDestroy(): void {
    this.disconnect();
    clearTimeout(this.toastTimer);
  }
}
