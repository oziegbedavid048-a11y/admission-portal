import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { restoreSession, tokenStore } from '../api/client';
import { auth } from '../api/endpoints';
import posthog from '../lib/posthog';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // The access token lives in memory, so on every load there is no session yet
  // and the refresh cookie has to be asked. That check is what `loading` covers.
  const [loading, setLoading] = useState(true);

  const signOut = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    // Reset PostHog so the next visitor gets a fresh anonymous identity.
    posthog.reset();
    // The cookie is httpOnly, so only the server can remove it.
    auth.logout().catch(() => {});
  }, []);

  // A refresh token that no longer works signs the session out from anywhere
  // in the app, including a background request the user never saw.
  useEffect(() => {
    const handler = () => setUser(null);
    window.addEventListener('gabstep:signed-out', handler);
    return () => window.removeEventListener('gabstep:signed-out', handler);
  }, []);

  // Restore the session from the refresh cookie once, on boot. No cookie means
  // nobody is signed in, which is not an error and must not clear anything.
  useEffect(() => {
    let cancelled = false;
    restoreSession()
      .then((restored) => {
        if (!cancelled && restored) setUser(restored);
      })
      .catch(() => {
        if (!cancelled) {
          tokenStore.clear();
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const adopt = useCallback((payload) => {
    tokenStore.save(payload);
    setUser(payload.user);
    // Identify the user in PostHog so all subsequent events are linked.
    const u = payload.user;
    if (u?.id) {
      posthog.identify(String(u.id), {
        email:    u.email,
        role:     u.role,
        name:     u.full_name ?? u.name ?? undefined,
      });
    }
    return payload.user;
  }, []);

  const signIn = useCallback(
    async (email, password) => {
      const { data } = await auth.login(email, password);
      return adopt(data);
    },
    [adopt],
  );

  // Signing up does not sign anyone in: the account waits for its email to be
  // confirmed. Both return the server's answer, which names the address the
  // confirmation link went to.
  // When the confirmation email cannot be sent, the server opens the account
  // and returns a session instead; that is adopted and reported as signedIn.
  const registerApplicant = useCallback(
    async (payload) => {
      const { data } = await auth.registerApplicant(payload);
      if (data?.access) adopt(data);
      return { ...data, signedIn: Boolean(data?.access) };
    },
    [adopt],
  );

  const registerAgent = useCallback(
    async (payload) => {
      const { data } = await auth.registerAgent(payload);
      if (data?.access) adopt(data);
      return { ...data, signedIn: Boolean(data?.access) };
    },
    [adopt],
  );

  /** Open a verification link: the server confirms it and starts a session. */
  const verifyEmail = useCallback(
    async (token) => {
      const { data } = await auth.verifyEmail(token);
      // A link opened before is no longer a way in: it only confirms.
      if (!data?.access) return { role: data?.role, already: true };
      return adopt(data);
    },
    [adopt],
  );

  /**
   * Change the password while signed in. The server signs out every other
   * device and hands this one a fresh session, which is adopted here so the
   * person making the change stays signed in.
   */
  const changePassword = useCallback(
    async (currentPassword, newPassword) => {
      const { data } = await auth.changePassword(currentPassword, newPassword);
      if (data?.access) adopt(data);
      return data;
    },
    [adopt],
  );

  const refreshUser = useCallback(async () => {
    const { data } = await auth.me();
    setUser(data);
    return data;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      isAgent: user?.role === 'agent',
      isSupervisor: user?.role === 'supervisor',
      isApplicant: user?.role === 'applicant',
      signIn,
      signOut,
      registerApplicant,
      registerAgent,
      verifyEmail,
      changePassword,
      refreshUser,
      setUser,
      adopt,
    }),
    [
      user,
      loading,
      signIn,
      signOut,
      registerApplicant,
      registerAgent,
      verifyEmail,
      changePassword,
      refreshUser,
      adopt,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider.');
  return context;
}
