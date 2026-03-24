export function formatDateTime(value?: string | null): string {
  if (!value) {
    return 'Not available';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatMonths(value?: number | null): string {
  if (value == null || value <= 0) {
    return 'Not specified';
  }

  const years = Math.floor(value / 12);
  const months = value % 12;
  const parts: string[] = [];

  if (years > 0) {
    parts.push(`${years}y`);
  }
  if (months > 0) {
    parts.push(`${months}m`);
  }

  return parts.join(' ') || `${value}m`;
}

export function formatListPreview(values?: string[] | null, limit = 4): string {
  if (!values || values.length === 0) {
    return 'Not specified';
  }

  const shown = values.slice(0, limit);
  const remainder = values.length - shown.length;
  return remainder > 0 ? `${shown.join(', ')} +${remainder}` : shown.join(', ');
}
