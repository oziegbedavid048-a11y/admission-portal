import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { applications } from '../../api/endpoints';
import useLiveRefresh from '../../hooks/useLiveRefresh';

const ApplicationContext = createContext(null);

// The application the applicant last looked at, so a refresh or a return from
// the payment page opens the same one.
const SELECTED_KEY = 'gabstep_selected_application';

export function rememberSelectedApplication(reference) {
  try {
    if (reference) localStorage.setItem(SELECTED_KEY, reference);
    else localStorage.removeItem(SELECTED_KEY);
  } catch {
    // Storage can be unavailable (private mode). The newest file is shown then.
  }
}

function storedSelection() {
  try {
    return localStorage.getItem(SELECTED_KEY) || '';
  } catch {
    return '';
  }
}

/**
 * Holds the signed-in applicant's files for the whole portal, so every page
 * shares one copy rather than each fetching it and drifting apart.
 *
 * An applicant can apply to more than one school; each school is its own
 * application with its own fee. `applicationsList` is every file in brief, and
 * `application` is the one being viewed, which every page reads.
 */
export function ApplicationProvider({ children }) {
  const [applicationsList, setApplicationsList] = useState([]);
  const [application, setApplication] = useState(null);
  const [selected, setSelected] = useState(storedSelection);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const reload = useCallback(async (reference) => {
    const wanted = reference ?? selectedRef.current;
    try {
      const [{ data: list }, { data }] = await Promise.all([
        applications.mineAll(),
        applications.mine(wanted || undefined),
      ]);
      setApplicationsList(Array.isArray(list) ? list : []);
      setApplication(data);
      setMissing(false);
      return data;
    } catch (error) {
      if (error?.response?.status === 404) {
        setApplicationsList([]);
        setApplication(null);
        setMissing(true);
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const selectApplication = useCallback(
    (reference) => {
      rememberSelectedApplication(reference);
      setSelected(reference);
      selectedRef.current = reference;
      return reload(reference);
    },
    [reload],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  // Stages, documents, letters and payments are all moved by the admissions
  // desk. Polling is what turns those into something the applicant sees
  // without being told to refresh.
  useLiveRefresh(() => {
    reload().catch(() => {});
  }, { intervalMs: 8000 });

  const value = useMemo(
    () => ({
      application,
      applicationsList,
      setApplication,
      selectApplication,
      loading,
      missing,
      reload,
    }),
    [application, applicationsList, selectApplication, loading, missing, reload],
  );

  return <ApplicationContext.Provider value={value}>{children}</ApplicationContext.Provider>;
}

export function useApplication() {
  const context = useContext(ApplicationContext);
  if (!context) throw new Error('useApplication must be used inside an ApplicationProvider.');
  return context;
}
