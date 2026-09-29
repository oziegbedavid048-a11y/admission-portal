import { useEffect, useMemo, useState } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import PortalShell from '../../components/layout/PortalShell';
import Loading from '../../components/ui/Loading';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import SupportPage from '../support/SupportPage';
import { ApplicationProvider, useApplication } from './ApplicationContext';
import AdmissionCelebrationModal from './AdmissionCelebrationModal';
import ApplyPanel from './ApplyPanel';
import CoursesPanel from './CoursesPanel';
import DetailsPanel from './DetailsPanel';
import LettersPanel from './LettersPanel';
import OverviewPanel from './OverviewPanel';
import ProfilePanel from './ProfilePanel';
import WelcomePanel from './WelcomePanel';

/**
 * The applicant's dashboard.
 *
 * It opens as soon as someone signs up, before there is any application: the
 * overview then points at the course list, and Apply lives on each course. Once
 * an application exists, Application and Letters join the sidebar and the
 * overview becomes the tracker.
 */
function PortalRoutes() {
  const { loading, application } = useApplication();
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const toast = useToast();
  const [celebrationLetter, setCelebrationLetter] = useState(null);

  const letters = application?.letters || [];
  const newestLetter = letters[0];

  // Celebrate an admission letter the first time it is seen.
  useEffect(() => {
    if (!newestLetter) return;
    try {
      const seen = localStorage.getItem(`gabstep_admission_celebration_seen_${newestLetter.id}`);
      if (!seen) setCelebrationLetter(newestLetter);
    } catch {
      setCelebrationLetter(newestLetter);
    }
  }, [newestLetter?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const handler = (event) => {
      const letter = event.detail || newestLetter;
      if (letter) setCelebrationLetter(letter);
    };
    window.addEventListener('gabstep:celebrate-letter', handler);
    return () => window.removeEventListener('gabstep:celebrate-letter', handler);
  }, [newestLetter]);

  const nav = useMemo(
    () => [
      { to: '/portal', end: true, label: 'Overview', icon: 'dashboard' },
      { to: '/portal/courses', label: 'Courses', icon: 'cap' },
      { to: '/portal/apply', label: 'Apply', title: 'Apply', icon: 'fileText', hidden: true },
      { to: '/portal/details', label: 'Application', icon: 'fileText', hidden: !application },
      { to: '/portal/letters', label: 'Letters', icon: 'mail', hidden: !application },
      { to: '/portal/support', label: 'Support', icon: 'headset', divider: true },
      { to: '/portal/profile', label: 'Profile', icon: 'user' },
    ],
    [application],
  );

  if (loading) return <Loading label="Opening your dashboard" />;

  return (
    <PortalShell
      prefix="portal"
      brandLabel="Application Portal"
      nav={nav}
      profilePath="/portal/profile"
      onSignOut={() => {
        signOut();
        toast.info('Signed out.');
        navigate('/');
      }}
    >
      {application ? (
        <AdmissionCelebrationModal
          isOpen={Boolean(celebrationLetter)}
          onClose={() => setCelebrationLetter(null)}
          letter={celebrationLetter}
          application={application}
        />
      ) : null}

      <Routes>
        <Route index element={application ? <OverviewPanel /> : <WelcomePanel />} />
        <Route path="courses" element={<CoursesPanel />} />
        <Route path="apply" element={<ApplyPanel />} />
        <Route path="details" element={application ? <DetailsPanel /> : <Navigate to="/portal" replace />} />
        <Route path="letters" element={application ? <LettersPanel /> : <Navigate to="/portal" replace />} />
        <Route path="support" element={<SupportPage />} />
        <Route path="profile" element={<ProfilePanel />} />
        <Route path="programme" element={<Navigate to="/portal/details" replace />} />
        <Route path="correction" element={<Navigate to="/portal/details" replace />} />
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
