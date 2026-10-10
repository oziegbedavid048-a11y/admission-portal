import { Suspense, lazy, useCallback, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import ProtectedRoute from './components/layout/ProtectedRoute';
import PaymentReturnPage from './features/wizard/PaymentReturnPage';
import Loading from './components/ui/Loading';
import LoginModal from './features/auth/LoginModal';
import LandingPage from './features/landing/LandingPage';
import ErrorBoundary from './components/ui/ErrorBoundary';
import { useAuth } from './context/AuthContext';
import { usePostHogPageView } from './hooks/usePostHogPageView';

// The portals and the wizard are big and most visitors never open them, so
// they are split out of the first download.
const SignupPage = lazy(() => import('./features/auth/SignupPage'));
const ForgotPasswordPage = lazy(() => import('./features/auth/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./features/auth/ResetPasswordPage'));
const VerifyEmailPage = lazy(() => import('./features/auth/VerifyEmailPage'));
const ApplicantPortal = lazy(() => import('./features/applicant/ApplicantPortal'));
const AgentLoginPage = lazy(() => import('./features/auth/AgentLoginPage'));
const AgentRegisterPage = lazy(() => import('./features/auth/AgentRegisterPage'));
const AgentPortal = lazy(() => import('./features/agent/AgentPortal'));
const SupervisorLoginPage = lazy(() => import('./features/auth/SupervisorLoginPage'));
const SupervisorPortal = lazy(() => import('./features/supervisor/SupervisorPortal'));
const NotFoundPage = lazy(() => import('./features/landing/NotFoundPage'));

/**
 * The old "apply" address. Applying starts from an account now, so a visitor is
 * sent to sign up, and a signed-in applicant to the course list in their
 * dashboard, where every Apply button lives.
 */
function ApplyRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return <Navigate to={user ? '/portal/courses' : '/signup'} replace />;
}

export default function App() {
  usePostHogPageView(); // fire $pageview on every route change
  const [loginOpen, setLoginOpen] = useState(false);
  const openLogin = useCallback(() => setLoginOpen(true), []);
  const closeLogin = useCallback(() => setLoginOpen(false), []);

  return (
    <ErrorBoundary>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<LandingPage onOpenLogin={openLogin} />} />
          <Route path="/signup" element={<SignupPage onOpenLogin={openLogin} />} />
          <Route path="/apply" element={<ApplyRedirect />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage onOpenLogin={openLogin} />} />
          <Route path="/reset-password" element={<ResetPasswordPage onOpenLogin={openLogin} />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />

          <Route
            path="/portal/*"
            element={
              <ProtectedRoute role="applicant">
                <ApplicantPortal />
              </ProtectedRoute>
            }
          />

          <Route path="/agent/login" element={<AgentLoginPage />} />
          <Route path="/agent/register" element={<AgentRegisterPage />} />
          <Route
            path="/agent/*"
            element={
              <ProtectedRoute role="agent">
                <AgentPortal />
              </ProtectedRoute>
            }
          />

          <Route path="/sales-manager/login" element={<SupervisorLoginPage />} />
          <Route
            path="/sales-manager/*"
            element={
              <ProtectedRoute role="supervisor">
                <SupervisorPortal />
              </ProtectedRoute>
            }
          />

          {/* Paystack sends the applicant back here. Unprotected so applicants returning from Paystack on any device or tab can confirm payment and auto-sign in. */}
          <Route path="/payment/:reference" element={<PaymentReturnPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>

      <LoginModal open={loginOpen} onClose={closeLogin} />
    </ErrorBoundary>
  );
}
