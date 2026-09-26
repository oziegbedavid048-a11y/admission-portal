import { Suspense, lazy, useCallback, useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import ProtectedRoute from './components/layout/ProtectedRoute';
import PaymentReturnPage from './features/wizard/PaymentReturnPage';
import Loading from './components/ui/Loading';
import LoginModal from './features/auth/LoginModal';
import LandingPage from './features/landing/LandingPage';
import ErrorBoundary from './components/ui/ErrorBoundary';

// The portals and the wizard are big and most visitors never open them, so
// they are split out of the first download.
const WizardPage = lazy(() => import('./features/wizard/WizardPage'));
const ApplicantPortal = lazy(() => import('./features/applicant/ApplicantPortal'));
const AgentLoginPage = lazy(() => import('./features/auth/AgentLoginPage'));
const AgentRegisterPage = lazy(() => import('./features/auth/AgentRegisterPage'));
const AgentPortal = lazy(() => import('./features/agent/AgentPortal'));
const SupervisorLoginPage = lazy(() => import('./features/auth/SupervisorLoginPage'));
const SupervisorPortal = lazy(() => import('./features/supervisor/SupervisorPortal'));
const NotFoundPage = lazy(() => import('./features/landing/NotFoundPage'));

export default function App() {
  const [loginOpen, setLoginOpen] = useState(false);
  const openLogin = useCallback(() => setLoginOpen(true), []);
  const closeLogin = useCallback(() => setLoginOpen(false), []);

  return (
    <ErrorBoundary>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<LandingPage onOpenLogin={openLogin} />} />
          <Route path="/apply" element={<WizardPage onOpenLogin={openLogin} />} />

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

          {/* Paystack sends the applicant back here. Behind the applicant guard,
              because confirming a payment means reading that application. */}
          <Route
            path="/payment/:reference"
            element={
              <ProtectedRoute role="applicant">
                <PaymentReturnPage />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>

      <LoginModal open={loginOpen} onClose={closeLogin} />
    </ErrorBoundary>
  );
}
