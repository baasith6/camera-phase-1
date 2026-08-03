const ALERT_TYPE_LABELS: Record<string, string> = {
  HighValueZoneEntry: 'High-value area entry',
  Dwell: 'Loitering detected',
  RepeatedHandling: 'Repeated handling',
  BagOpen: 'Bag opened near shelf',
  Concealment: 'Possible concealment',
  ExitWithoutCheckout: 'Exit without checkout',
  ShelfPickupNoCheckout: 'Shelf pickup, no checkout',
  BlindSpotMovement: 'Blind spot movement',
  GroupDistraction: 'Group distraction',
  HighValueActivity: 'High-value area activity',
  LowStaffRemoval: 'Low-staff hours removal',
};

export function alertTypeLabel(type: string): string {
  if (ALERT_TYPE_LABELS[type]) return ALERT_TYPE_LABELS[type];
  return type
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .trim();
}

export function pillClass(status: string): string {
  switch (status) {
    case 'PendingReview':
      return 'pending';
    case 'Confirmed':
      return 'confirmed';
    case 'Dismissed':
      return 'dismissed';
    case 'FalsePositive':
      return 'falsepos';
    case 'NeedsFollowUp':
      return 'followup';
    default:
      return 'dismissed';
  }
}

export function pillLabel(status: string): string {
  switch (status) {
    case 'PendingReview':
      return 'Needs review';
    case 'Confirmed':
      return 'Confirmed';
    case 'Dismissed':
      return 'Not suspicious';
    case 'FalsePositive':
      return 'False alarm';
    case 'NeedsFollowUp':
      return 'Follow-up';
    default:
      return status;
  }
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days > 1 ? 's' : ''} ago`;
}
