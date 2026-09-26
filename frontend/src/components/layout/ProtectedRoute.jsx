import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Loading from '../ui/Loading';

/**
 * Gate a route on being signed in, and optionally on holding a role.
 * Someone signed in with the wrong role is sent to their own portal rather
 * than to a sign-in screen they do not need.
 */
export default function ProtectedRoute({ role, children }) {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  if (loading) return <Loading label="Checking your session" />;

  if (!isAuthenticated) {
    const to =
      role === 'agent' ? '/agent/login' : role === 'supervisor' ? '/sales-manager/login' : '/';
    return <Navigate to={to} state={{ from: location.pathname, signIn: true }} replace />;
  }

  if (role && user.role !== role) {
    const home =
      user.role === 'agent'
        ? '/agent'
        : user.role === 'supervisor'
          ? '/sales-manager'
          : '/portal';
    return <Navigate to={home} replace />;
  }

  return children;
}
