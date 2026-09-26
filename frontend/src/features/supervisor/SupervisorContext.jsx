import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { supervisors } from '../../api/endpoints';

const SupervisorContext = createContext(null);

/** The Sales Manager's own profile, shared by every page in their portal. */
export function SupervisorProvider({ children }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    const { data } = await supervisors.profile();
    setProfile(data);
    return data;
  }, []);

  useEffect(() => {
    reload()
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [reload]);

  const value = useMemo(
    () => ({ profile, setProfile, loading, reload }),
    [profile, loading, reload],
  );

  return <SupervisorContext.Provider value={value}>{children}</SupervisorContext.Provider>;
}

export function useSupervisor() {
  const context = useContext(SupervisorContext);
  if (!context) throw new Error('useSupervisor must be used inside a SupervisorProvider.');
  return context;
}
