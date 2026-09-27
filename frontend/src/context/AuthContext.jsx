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

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // The access token lives in memory, so on every load there is no session yet
  // and the refresh cookie has to be asked. That check is what `loading` covers.
  const [loading, setLoading] = useState(true);

  const signOut = useCallback(() => {
    tokenStore.clear();
    setUser(null);
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
    return payload.user;
  }, []);

  const signIn = useCallback(
    async (email, password) => {
      const { data } = await auth.login(email, password);
      return adopt(data);
    },
    [adopt],
  );

  /**
   * Create an applicant account without signing anybody in.
   *
   * The wizard needs an account to hang the application and its documents on, and
   * it needs a token to make those calls. It does not need a session: an
   * application is not paid for yet, and being silently logged in while the
   * payment page loads is how somebody ends up inside a dashboard for a file they
   * have not paid for. So the token is stored for the submit and the user is not,
   * which leaves the header signed out. `endSubmitSession` drops the token again.
   */
  const registerApplicantForSubmit = useCallback(async (payload) => {
    const { data } = await auth.registerApplicant(payload);
    tokenStore.save(data);
    return data.user;
  }, []);

  const endSubmitSession = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const registerApplicant = useCallback(
    async (payload) => {
      const { data } = await auth.registerApplicant(payload);
      return adopt(data);
    },
    [adopt],
  );

  const registerAgent = useCallback(
    async (payload) => {
      const { data } = await auth.registerAgent(payload);
      return adopt(data);
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
      registerApplicantForSubmit,
      endSubmitSession,
      registerAgent,
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
      registerApplicantForSubmit,
      endSubmitSession,
      registerAgent,
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
