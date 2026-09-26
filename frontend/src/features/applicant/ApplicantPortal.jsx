import { useEffect, useState } from 'react';
import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import PortalShell from '../../components/layout/PortalShell';
import Loading from '../../components/ui/Loading';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { ApplicationProvider, useApplication } from './ApplicationContext';
import AdmissionCelebrationModal from './AdmissionCelebrationModal';
import DetailsPanel from './DetailsPanel';
import LettersPanel from './LettersPanel';
import OverviewPanel from './OverviewPanel';
import ProfilePanel from './ProfilePanel';

const NAV = [
  { to: '/portal', end: true, label: 'Overview', icon: 'dashboard' },
  { to: '/portal/details', label: 'Applicant Details', icon: 'fileText' },
  { to: '/portal/letters', label: 'Letters', icon: 'mail' },
  { to: '/portal/profile', label: 'Profile', icon: 'user' },
];

function PortalRoutes() {
  const { loading, missing, application } = useApplication();
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const toast = useToast();
  const [celebrationLetter, setCelebrationLetter] = useState(null);

  const letters = application?.letters || [];
  const newestLetter = letters[0];

  // Auto trigger when an admission letter has arrived and hasn't been acknowledged
  useEffect(() => {
    if (newestLetter) {
      try {
        const seen = localStorage.getItem(`gabstep_admission_celebration_seen_${newestLetter.id}`);
        if (!seen) {
          setCelebrationLetter(newestLetter);
        }
      } catch {
        setCelebrationLetter(newestLetter);
      }
    }
  }, [newestLetter?.id]);

  // Listen for explicit celebration requests (e.g. from OverviewPanel or LettersPanel)
  useEffect(() => {
    const handler = (e) => {
      const letterToCelebrate = e.detail || newestLetter;
      if (letterToCelebrate) {
        setCelebrationLetter(letterToCelebrate);
      }
    };
    window.addEventListener('gabstep:celebrate-letter', handler);
    return () => window.removeEventListener('gabstep:celebrate-letter', handler);
  }, [newestLetter]);

  const initials = (user?.full_name || application?.full_name || 'A')
    .split(' ')
    .filter(Boolean)
    .map((s) => s[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
  const displayName = user?.full_name || application?.full_name || 'Applicant';

  if (loading) return <Loading label="Opening your application" />;

  if (missing || !application) {
    return (
      <section className="dashboard-section">
        <div className="container" style={{ padding: 'var(--space-16) 0' }}>
          <div className="card">
            <div className="card-head">
              <h2>No application yet</h2>
            </div>
            <p className="card-body-text">
              Your account is ready, but there is no application on it. Start one and this
              portal will fill in as it moves through the pipeline.
            </p>
            <button
              type="button"
              className="g-btn g-btn-primary"
              style={{ marginTop: 20 }}
              onClick={() => navigate('/apply')}
            >
              Start an application
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <PortalShell
      prefix="portal"
      brandLabel="Applicant portal"
      title="Gabstep Applicant Portal"
      nav={NAV}
      topbarRight={
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Link className="agent-topbar-profile-btn" to="/portal/profile" title="Your profile">
            <span className="agent-topbar-avatar">
              {user?.avatar ? <img src={user.avatar} alt="" /> : <span>{initials}</span>}
            </span>
            <span className="agent-topbar-name">{displayName}</span>
          </Link>
        </div>
      }
      onSignOut={() => {
        signOut();
        toast.info('Signed out.');
        navigate('/');
      }}
    >
      {/* ── Admission Letter Celebration Modal with Continuous Flowing Confetti & Backdrop Blur ── */}
      <AdmissionCelebrationModal
        isOpen={Boolean(celebrationLetter)}
        onClose={() => setCelebrationLetter(null)}
        letter={celebrationLetter}
        application={application}
      />

      <Routes>
        <Route index element={<OverviewPanel />} />
        <Route path="details" element={<DetailsPanel />} />
        <Route path="programme" element={<Navigate to="/portal/details" replace />} />
        <Route path="letters" element={<LettersPanel />} />
        <Route path="correction" element={<Navigate to="/portal/details" replace />} />
        <Route path="profile" element={<ProfilePanel />} />
        <Route path="*" element={<Navigate to="/portal" replace />} />
      </Routes>
    </PortalShell>
  );
}

export default function ApplicantPortal() {
  return (
    <ApplicationProvider>
      <PortalRoutes />
    </ApplicationProvider>
  );
}
