export function formatDuration(minutes: number): string {
  const total = Math.round(minutes);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h ? `${h} h ${m.toString().padStart(2, '0')} min` : `${m} min`;
}

export function formatMiles(mi: number, digits = 0): string {
  return `${mi.toLocaleString(undefined, { maximumFractionDigits: digits })} mi`;
}

/** Absolute time, optionally in a location's IANA timezone (e.g. a checkpoint's). */
export function formatDateTime(iso: string, timeZone?: string | null): string {
  const opts: Intl.DateTimeFormatOptions = {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  };
  try {
    return new Intl.DateTimeFormat(undefined, { ...opts, timeZone: timeZone ?? undefined }).format(
      new Date(iso),
    );
  } catch {
    return new Intl.DateTimeFormat(undefined, opts).format(new Date(iso));
  }
}

export function formatHourLabel(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    hour: 'numeric',
    timeZoneName: 'short',
  }).format(new Date(iso));
}

export function formatNumber(v: number | null | undefined, digits: number, unit = ''): string {
  if (v == null) return '-';
  return `${v.toFixed(digits)}${unit}`;
}

/** Value for <input type="datetime-local"> in the browser's local time. */
export function toLocalInputValue(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Next quarter hour at least `aheadMinutes` from now. */
export function defaultDeparture(aheadMinutes = 30): Date {
  const d = new Date(Date.now() + aheadMinutes * 60_000);
  d.setSeconds(0, 0);
  d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15);
  return d;
}

export const MAX_DEPARTURE_AHEAD_MS = 48 * 3600_000;
export const PAST_GRACE_MS = 15 * 60_000;

/** Same window as the backend: now (minus 15 min grace) .. now + 48 h. */
export function departureError(value: string, now = Date.now()): string | null {
  if (!value) return 'Choose a departure date and time.';
  const t = new Date(value).getTime();
  if (Number.isNaN(t)) return 'Invalid date/time.';
  if (t < now - PAST_GRACE_MS) return 'Departure time is in the past. Pick a time from now on.';
  if (t > now + MAX_DEPARTURE_AHEAD_MS)
    return 'Departure must be within the next 48 hours (forecast range).';
  return null;
}
