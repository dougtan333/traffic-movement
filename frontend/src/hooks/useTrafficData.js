/**
 * Custom hook for fetching data from the AMIP API.
 * Handles loading state, errors, and automatic refetch on param change.
 *
 * @param {string} endpoint - API path (e.g. '/api/traffic/weekly-trend')
 * @param {object} params - Query parameters as key-value pairs
 * @returns {{ data: any, loading: boolean, error: string|null }}
 */
import { useState, useEffect } from 'react';
import { API_URL } from '../constants';

export function useTrafficData(endpoint, params = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const paramString = new URLSearchParams(params).toString();
  const url = `${API_URL}${endpoint}${paramString ? '?' + paramString : ''}`;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
      })
      .then(json => { if (!cancelled) setData(json); })
      .catch(err => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [url]);

  return { data, loading, error };
}
