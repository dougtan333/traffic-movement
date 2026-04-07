/**
 * Custom hook for fetching calendar events (holidays, school terms, events).
 * Used by chart components to add annotations. Victoria only.
 *
 * @param {string} dateFrom - ISO date string
 * @param {string} dateTo - ISO date string
 * @returns {{ events: object|null, loading: boolean }}
 */
import { useTrafficData } from './useTrafficData';

function defaultRange() {
  const now = new Date();
  const from = new Date(now);
  from.setFullYear(from.getFullYear() - 1);
  const to = new Date(now);
  to.setMonth(to.getMonth() + 6);
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

export function useCalendarEvents(dateFrom, dateTo) {
  const d = defaultRange();
  const { data, loading } = useTrafficData('/api/traffic/calendar-events', {
    date_from: dateFrom || d.from, date_to: dateTo || d.to,
  });
  return { events: data, loading };
}
