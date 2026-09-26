import { useEffect, useState } from 'react';
import { catalog } from '../api/endpoints';

/**
 * Origin and destination lists.
 *
 * These are edited in the admin, so the cache has a lifetime rather than
 * lasting the whole session: long enough that moving between pages does not
 * refetch, short enough that a destination added by staff turns up on its own.
 */
const CACHE_MS = 60000;
let cache = null;
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
        cache = { origins: origins.data, destinations: destinations.data };
        cachedAt = Date.now();
        if (!cancelled) setData(cache);
      })
      .catch(() => {
        if (!cancelled) setData({ origins: [], destinations: [] });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    origins: data?.origins || [],
    destinations: data?.destinations || [],
    originNames: (data?.origins || []).map((item) => item.name),
    loading,
  };
}

/** Partner institutions for one destination, refetched when it changes. */
export function useInstitutions(country) {
  const [institutions, setInstitutions] = useState([]);
  const [loading, setLoading] = useState(Boolean(country));

  useEffect(() => {
    if (!country) {
      setInstitutions([]);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    catalog
      .institutions(country)
      .then(({ data }) => {
        if (!cancelled) setInstitutions(data);
      })
      .catch(() => {
        if (!cancelled) setInstitutions([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [country]);

  return { institutions, loading };
}
