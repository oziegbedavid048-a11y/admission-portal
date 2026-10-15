import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import PortalShell from '../../components/layout/PortalShell';
import Loading from '../../components/ui/Loading';
import { useAuth } from '../../context/AuthContext';
import SupportLauncher from '../../components/ui/SupportLauncher';
import { useLiveChat } from '../../lib/liveChat';
import { useToast } from '../../context/ToastContext';
import SupportPage from '../support/SupportPage';
import AgentCertificate from './AgentCertificate';
import AgentContract from './contract/AgentContract';
import AgentCourses from './AgentCourses';
import AgentLetters from './AgentLetters';
import AgentLoans from './AgentLoans';
import AgentOverview from './AgentOverview';
import AgentProfile from './AgentProfile';
import AgentStudents from './AgentStudents';
import AgentNewStudent from './AgentNewStudent';
import AgentPaymentReturn from './AgentPaymentReturn';
import AgentWallet from './AgentWallet';
import { AgentProvider, useAgent } from './AgentContext';

const NAV = [
  { to: '/agent', end: true, label: 'Overview', icon: 'dashboard' },
  { to: '/agent/students', label: 'Students', icon: 'users' },
  { to: '/agent/students/new', label: 'Register a student', icon: 'userPlus', hidden: true },
  { to: '/agent/letters', label: 'Letters', icon: 'fileText' },
  { to: '/agent/courses', label: 'Courses', icon: 'cap' },
  { to: '/agent/wallet', label: 'Wallet', icon: 'wallet' },
  { to: '/agent/loans', label: 'Ads funding', icon: 'adsFunding' },
  // Shown only once the certificate is ready. See PortalRoutes.
  { to: '/agent/certificate', label: 'Certificate', icon: 'medal', certificate: true },
  // Shown once there is a contract on file, or while it waits to be signed.
  { to: '/agent/contract', label: 'Contract', icon: 'fileText', contract: true },
  { to: '/agent/support', label: 'Support', icon: 'headset', divider: true },
];

function PortalRoutes() {
  const { profile, loading } = useAgent();
  const { user, signOut } = useAuth();
  // Live chat loads in the background; the Support button opens it.
  useLiveChat({ name: user?.full_name, email: user?.email });
  const toast = useToast();
  const navigate = useNavigate();

  if (loading) return <Loading label="Opening your partner portal" />;
  if (!profile) return <Navigate to="/agent/login" replace />;

  // The certificate page appears six hours after sign-up. Until then there is
  // no link to it and nothing mentions it.
  const certificateReady = Boolean(profile.certificate_ready);
  // A new agent signs the partnership contract before anything else: until
  // then the portal is the Contract page and Support, nothing more.
  const contractStatus = profile.contract_status || 'none';
  const mustSign = contractStatus === 'pending';
  const nav = mustSign
    ? NAV.filter((item) => item.contract || item.to === '/agent/support')
    : NAV.filter(
        (item) => (!item.certificate || certificateReady) && (!item.contract || contractStatus === 'signed'),
      );

  return (
    <PortalShell
      prefix="agent"
      brandLabel="Agent portal"
      siteName="Gabstep Agent Portal"
      nav={nav}
      profilePath="/agent/profile"
      onSignOut={() => {
        signOut();
        toast.info('Signed out.');
        navigate('/agent/login');
      }}
    >
      <Routes>
        {mustSign ? (
          <>
            <Route path="contract" element={<AgentContract />} />
            <Route path="support" element={<SupportPage />} />
            <Route path="*" element={<Navigate to="/agent/contract" replace />} />
          </>
        ) : (
          <>
            <Route index element={<AgentOverview />} />
            <Route path="students" element={<AgentStudents />} />
            <Route path="students/new" element={<AgentNewStudent />} />
            <Route path="payment/:reference" element={<AgentPaymentReturn />} />
            <Route path="letters" element={<AgentLetters />} />
            <Route path="wallet" element={<AgentWallet />} />
            <Route path="courses" element={<AgentCourses />} />
            <Route path="loans" element={<AgentLoans />} />
            {certificateReady ? <Route path="certificate" element={<AgentCertificate />} /> : null}
            {contractStatus === 'signed' ? <Route path="contract" element={<AgentContract />} /> : null}
            <Route path="support" element={<SupportPage />} />
            <Route path="profile" element={<AgentProfile />} />
            <Route path="*" element={<Navigate to="/agent" replace />} />
          </>
        )}
      </Routes>
      <SupportLauncher visitor={{ name: user?.full_name, email: user?.email }} />
    </PortalShell>
  );
}

export default function AgentPortal() {
  return (
    <AgentProvider>
      <PortalRoutes />
    </AgentProvider>
  );
}
