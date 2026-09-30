import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { formatNaira } from '../../lib/format';

const AgentContext = createContext(null);

// Pages listen for this to reload their own figures the moment money lands.
export const WALLET_CHANGED = 'gabstep:wallet-changed';

/**
 * The partner's profile and wallet, shared by every page in the portal so a
 * balance changed on Wallet is the same balance the sidebar and Overview show.
 *
 * The wallet is checked every few seconds on any page. When staff confirm a
 * payment or a visa in the admin, the new balance shows without a reload, the
 * agent is told how much arrived, and every open page refreshes its figures.
 */
export function AgentProvider({ children }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const earned = useRef(null);
  const toast = useToast();

  const reload = useCallback(async () => {
    const { data } = await partners.profile();
    setProfile(data);
    if (data?.wallet) earned.current = Number(data.wallet.total_earned) || 0;
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

  useLiveRefresh(
    async () => {
      try {
        const { data: wallet } = await partners.wallet();
        const total = Number(wallet.total_earned) || 0;
        const before = earned.current;
        earned.current = total;
        setWallet(wallet);
        if (before !== null && total > before) {
          toast.success(`${formatNaira(total - before)} added to your wallet.`);
          window.dispatchEvent(new CustomEvent(WALLET_CHANGED, { detail: wallet }));
        }
      } catch {
        // A missed check is retried on the next tick.
      }
    },
    { intervalMs: 6000, enabled: Boolean(profile) },
  );

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

/** Runs `callback` whenever new money lands in the wallet. */
export function useOnWalletChange(callback) {
  const saved = useRef(callback);
  useEffect(() => {
    saved.current = callback;
  }, [callback]);
  useEffect(() => {
    const handler = () => saved.current?.();
    window.addEventListener(WALLET_CHANGED, handler);
    return () => window.removeEventListener(WALLET_CHANGED, handler);
  }, []);
}
