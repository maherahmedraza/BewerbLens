/**
 * Normalizes raw Python enum repr strings (e.g. "Status.APPLIED")
 * to their human-readable display values (e.g. "Applied").
 *
 * This handles a Python 3.11+ behavior where str(SomeStrEnum.MEMBER)
 * returns "ClassName.MEMBER" instead of the enum's .value.
 */

const ENUM_TO_DISPLAY: Record<string, string> = {
  'Status.APPLIED': 'Applied',
  'Status.REJECTED': 'Rejected',
  'Status.POSITIVE_RESPONSE': 'Positive Response',
  'Status.INTERVIEW': 'Interview',
  'Status.OFFER': 'Offer',
  'Classification.APPLICATION_CONFIRMATION': 'Applied',
  'Classification.REJECTION': 'Rejected',
  'Classification.POSITIVE_RESPONSE': 'Positive Response',
};

export function normalizeStatus(raw: string): string {
  if (!raw) return 'Unknown';
  return ENUM_TO_DISPLAY[raw] || raw;
}

export const STATUS_COLORS: Record<string, string> = {
  'Applied': '#3b82f6',
  'Rejected': '#ef4444',
  'Positive Response': '#10b981',
  'Interview': '#f59e0b',
  'Offer': '#8b5cf6',
};

export const STATUS_MAP: Record<string, { label: string; color: string }> = {
  'Applied': { label: 'Pending', color: 'var(--accent-blue)' },
  'Rejected': { label: 'Rejected', color: 'var(--accent-red)' },
  'Positive Response': { label: 'Positive', color: 'var(--accent-green)' },
  'Interview': { label: 'Interview', color: 'var(--accent-orange)' },
  'Offer': { label: 'Offer', color: 'var(--accent-purple)' },
};
