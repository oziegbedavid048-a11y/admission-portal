import { useEffect, useMemo, useState } from 'react';
import { catalog } from '../api/endpoints';
import { getLocalInstitutions } from '../lib/catalogData';

/**
 * Built-in fallback catalog data to ensure the application wizard works
 * seamlessly even during cold boots, offline use, or before backend deployment.
 */
export const FALLBACK_DESTINATIONS = [
  { id: 1, name: 'Canada', slug: 'canada' },
  { id: 2, name: 'United Kingdom', slug: 'united-kingdom' },
  { id: 3, name: 'United States', slug: 'united-states' },
  { id: 4, name: 'Australia', slug: 'australia' },
  { id: 5, name: 'Germany', slug: 'germany' },
  { id: 6, name: 'France', slug: 'france' },
  { id: 7, name: 'Ireland', slug: 'ireland' },
  { id: 8, name: 'Spain', slug: 'spain' },
];

export const FALLBACK_ORIGINS = [
  { id: 1, name: 'Nigeria', currency: 'NGN', symbol: '₦', ngnPerUnit: 1 },
  { id: 2, name: 'Ghana', currency: 'GHS', symbol: 'GH₵', ngnPerUnit: 95 },
  { id: 3, name: 'Kenya', currency: 'KES', symbol: 'KSh', ngnPerUnit: 12 },
  { id: 4, name: 'South Africa', currency: 'ZAR', symbol: 'R', ngnPerUnit: 85 },
  { id: 5, name: 'Cameroon', currency: 'XAF', symbol: 'FCFA', ngnPerUnit: 2.55 },
  { id: 6, name: 'Rwanda', currency: 'RWF', symbol: 'FRw', ngnPerUnit: 1.15 },
  { id: 7, name: 'Uganda', currency: 'UGX', symbol: 'USh', ngnPerUnit: 0.42 },
  { id: 8, name: 'Tanzania', currency: 'TZS', symbol: 'TSh', ngnPerUnit: 0.6 },
  { id: 9, name: 'Egypt', currency: 'EGP', symbol: 'E£', ngnPerUnit: 32 },
  { id: 10, name: 'India', currency: 'INR', symbol: '₹', ngnPerUnit: 18.5 },
  { id: 11, name: 'Pakistan', currency: 'PKR', symbol: '₨', ngnPerUnit: 5.5 },
  { id: 12, name: 'Bangladesh', currency: 'BDT', symbol: '৳', ngnPerUnit: 13 },
  { id: 13, name: 'Philippines', currency: 'PHP', symbol: '₱', ngnPerUnit: 27 },
  { id: 14, name: 'United Kingdom', currency: 'GBP', symbol: '£', ngnPerUnit: 1960 },
  { id: 15, name: 'United States', currency: 'USD', symbol: '$', ngnPerUnit: 1550 },
  { id: 16, name: 'Canada', currency: 'CAD', symbol: 'CA$', ngnPerUnit: 1150 },
];

const CACHE_MS = 60000;
let cache = { origins: FALLBACK_ORIGINS, destinations: FALLBACK_DESTINATIONS };
let cachedAt = 0;

function fresh() {
  return cache && Date.now() - cachedAt < CACHE_MS;
}

/** Drop the cache, for when something is known to have changed. */
export function invalidateCatalog() {
  cache = null;
  cachedAt = 0;
}

export function useCatalog() {
  const [data, setData] = useState(cache);
  const [loading, setLoading] = useState(!fresh());

  useEffect(() => {
    if (fresh()) {
      setData(cache);
      setLoading(false);
      return undefined;
    }
    let cancelled = false;

    Promise.all([catalog.originCountries(), catalog.destinations()])
      .then(([origins, destinations]) => {
        const rawOrigins = origins?.data;
        const rawDests = destinations?.data;

        const validOrigins = Array.isArray(rawOrigins) && rawOrigins.length > 0 ? rawOrigins : FALLBACK_ORIGINS;
        const validDests = Array.isArray(rawDests) && rawDests.length > 0 ? rawDests : FALLBACK_DESTINATIONS;

        cache = { origins: validOrigins, destinations: validDests };
        cachedAt = Date.now();
        if (!cancelled) setData(cache);
      })
      .catch(() => {
        if (!cancelled) {
          cache = { origins: FALLBACK_ORIGINS, destinations: FALLBACK_DESTINATIONS };
          setData(cache);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const safeOrigins = Array.isArray(data?.origins) && data.origins.length > 0
    ? data.origins
    : FALLBACK_ORIGINS;

  const safeDestinations = Array.isArray(data?.destinations) && data.destinations.length > 0
    ? data.destinations
    : FALLBACK_DESTINATIONS;

  const originNames = safeOrigins
    .map((item) => (typeof item === 'string' ? item : item?.name || ''))
    .filter(Boolean);

  return {
    origins: safeOrigins,
    destinations: safeDestinations,
    originNames,
    loading,
  };
}

/** Partner institutions for one destination, refetched when it changes. */
export function useInstitutions(country) {
  const localFallback = useMemo(() => getLocalInstitutions(country), [country]);
  const [institutions, setInstitutions] = useState(localFallback);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!country) {
      setInstitutions([]);
      return undefined;
    }

    const fallback = getLocalInstitutions(country);
    // Initialize immediately with local fallback so user NEVER waits or sees blank
    if (fallback.length > 0) {
      setInstitutions(fallback);
    }

    let cancelled = false;
    catalog
      .institutions(country)
      .then(({ data }) => {
        if (!cancelled && Array.isArray(data) && data.length > 0) {
          setInstitutions(data);
        }
      })
      .catch(() => {
        // Keep fallback on network error/timeout - never wipe out the courses
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [country]);

  const resolved = Array.isArray(institutions) && institutions.length > 0
    ? institutions
    : localFallback;

  return {
    institutions: resolved,
    loading: loading && resolved.length === 0,
  };
}
