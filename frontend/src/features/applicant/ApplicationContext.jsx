import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { applications } from '../../api/endpoints';
import useLiveRefresh from '../../hooks/useLiveRefresh';

const ApplicationContext = createContext(null);

/**
 * Holds the signed-in applicant's file for the whole portal, so the five pages
 * share one copy rather than each fetching it and drifting apart.
 */
export function ApplicationProvider({ children }) {
  const [application, setApplication] = useState(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);

  const reload = useCallback(async () => {
    try {
      const { data } = await applications.mine();
      setApplication(data);
      setMissing(false);
      return data;
    } catch (error) {
      if (error?.response?.status === 404) setMissing(true);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  // Stages, documents, letters and payments are all moved by the admissions
  // desk. Polling is what turns those into something the applicant sees
  // without being told to refresh.
  useLiveRefresh(() => {
    reload().catch(() => {});
  }, { intervalMs: 15000 });

  const value = useMemo(
    () => ({ application, setApplication, loading, missing, reload }),
    [application, loading, missing, reload],
  );

  return <ApplicationContext.Provider value={value}>{children}</ApplicationContext.Provider>;
}

export function useApplication() {
  const context = useContext(ApplicationContext);
  if (!context) throw new Error('useApplication must be used inside an ApplicationProvider.');
  return context;
}
