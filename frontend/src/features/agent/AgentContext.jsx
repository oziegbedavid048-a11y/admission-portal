import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { partners } from '../../api/endpoints';

const AgentContext = createContext(null);

/**
 * The partner's profile and wallet, shared by every page in the portal so a
 * balance changed on Wallet is the same balance the sidebar and Overview show.
 */
export function AgentProvider({ children }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    const { data } = await partners.profile();
    setProfile(data);
    return data;
  }, []);

  useEffect(() => {
    reload()
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [reload]);

  const setWallet = useCallback((wallet) => {
    setProfile((current) => (current ? { ...current, wallet } : current));
  }, []);

  const value = useMemo(
    () => ({ profile, setProfile, wallet: profile?.wallet, setWallet, loading, reload }),
    [profile, setWallet, loading, reload],
  );

  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>;
}

export function useAgent() {
  const context = useContext(AgentContext);
  if (!context) throw new Error('useAgent must be used inside an AgentProvider.');
  return context;
}
