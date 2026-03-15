/**
 * API base URL — reads from environment or defaults to local dev.
 * Change via .env: VITE_API_URL=http://localhost:8000
 */
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** City colour scheme — matches AMIP prompt spec */
export const CITY_COLORS = {
  sydney: '#1B3A5C',
  melbourne: '#2A9D8F',
};

/** Year overlay colours for historical comparison charts */
export const YEAR_COLORS = {
  2019: '#185FA5',
  2020: '#E24B4A',
  2021: '#BA7517',
  2024: '#73726c',
  2025: '#1D9E75',
  2026: '#7F77DD',
};

/** Fuel crisis onset date */
export const CRISIS_DATE = '2026-03-03';

/** Day name mapping (ISO day-of-week) */
export const DAY_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
