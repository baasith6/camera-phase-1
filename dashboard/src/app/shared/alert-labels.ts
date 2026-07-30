export function alertTypeLabel(type: string): string {
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
      return 'Pending';
    case 'Confirmed':
      return 'Confirmed';
    case 'Dismissed':
      return 'Dismissed';
    case 'FalsePositive':
      return 'False positive';
    case 'NeedsFollowUp':
      return 'Follow-up';
    default:
      return status;
  }
}
