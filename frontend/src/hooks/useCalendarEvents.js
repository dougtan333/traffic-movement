/**
 * Custom hook for fetching calendar events (holidays, school terms, events).
 * Used by chart components to add annotations. Victoria only.
 *
 * @param {string} dateFrom - ISO date string
 * @param {string} dateTo - ISO date string
 * @returns {{ events: object|null, loading: boolean }}
 */
import { useTrafficData } from './useTrafficData';

export function useCalendarEvents(dateFrom = '2025-01-01', dateTo = '2026-12-31') {
  const { data, loading } = useTrafficData('/api/traffic/calendar-events', {
    date_from: dateFrom, date_to: dateTo,
  });
  return { events: data, loading };
}
