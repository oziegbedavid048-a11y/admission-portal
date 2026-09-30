import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import PortalShell from '../../components/layout/PortalShell';
import Loading from '../../components/ui/Loading';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import SupportPage from '../support/SupportPage';
import AgentCourses from './AgentCourses';
import AgentLoans from './AgentLoans';
import AgentOverview from './AgentOverview';
import AgentProfile from './AgentProfile';
import AgentStudents from './AgentStudents';
import AgentNewStudent from './AgentNewStudent';
import AgentWallet from './AgentWallet';
import { AgentProvider, useAgent } from './AgentContext';

const NAV = [
  { to: '/agent', end: true, label: 'Overview', icon: 'dashboard' },
  { to: '/agent/students', label: 'Students', icon: 'users' },
  { to: '/agent/students/new', label: 'Register a student', icon: 'userPlus', hidden: true },
  { to: '/agent/courses', label: 'Courses', icon: 'cap' },
  { to: '/agent/wallet', label: 'Wallet', icon: 'wallet' },
  { to: '/agent/loans', label: 'Ad funding', icon: 'adsLoan' },
  { to: '/agent/support', label: 'Support', icon: 'headset', divider: true },
  { to: '/agent/profile', label: 'Profile', icon: 'user' },
];

function PortalRoutes() {
  const { profile, loading } = useAgent();
  const { signOut } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  if (loading) return <Loading label="Opening your partner portal" />;
  if (!profile) return <Navigate to="/agent/login" replace />;

  return (
    <PortalShell
      prefix="agent"
      brandLabel="Agent portal"
      siteName="Gabstep Agent Portal"
      nav={NAV}
      profilePath="/agent/profile"
      onSignOut={() => {
        signOut();
        toast.info('Signed out.');
        navigate('/agent/login');
      }}
    >
      <Routes>
        <Route index element={<AgentOverview />} />
        <Route path="students" element={<AgentStudents />} />
        <Route path="students/new" element={<AgentNewStudent />} />
        <Route path="wallet" element={<AgentWallet />} />
        <Route path="courses" element={<AgentCourses />} />
        <Route path="loans" element={<AgentLoans />} />
        <Route path="support" element={<SupportPage />} />
        <Route path="profile" element={<AgentProfile />} />
        <Route path="*" element={<Navigate to="/agent" replace />} />
      </Routes>
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
