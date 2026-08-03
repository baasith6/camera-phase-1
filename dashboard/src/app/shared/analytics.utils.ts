import { Alert } from '../core/models';

export interface AlertTrendPoint {
  label: string;
  count: number;
}

export function buildAlertTrends(alerts: Alert[], days = 7): AlertTrendPoint[] {
  const buckets = new Map<string, number>();
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    buckets.set(d.toISOString().slice(0, 10), 0);
  }
  for (const a of alerts) {
    const key = a.createdAt.slice(0, 10);
    if (buckets.has(key)) buckets.set(key, (buckets.get(key) ?? 0) + 1);
  }
  return [...buckets.entries()].map(([label, count]) => ({
    label: label.slice(5),
    count,
  }));
}

export function countByRisk(alerts: Alert[]): Record<string, number> {
  const out: Record<string, number> = { High: 0, Medium: 0, Low: 0, None: 0 };
  for (const a of alerts) {
    const k = a.riskLevel in out ? a.riskLevel : 'None';
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

export function countReviewOutcomes(alerts: Alert[]): Record<string, number> {
  const out: Record<string, number> = {
    Confirmed: 0,
    Dismissed: 0,
    FalsePositive: 0,
    PendingReview: 0,
    NeedsFollowUp: 0,
  };
  for (const a of alerts) {
    if (a.status in out) out[a.status]++;
  }
  return out;
}
