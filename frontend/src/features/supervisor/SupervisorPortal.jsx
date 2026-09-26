import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import PortalShell from '../../components/layout/PortalShell';
import Loading from '../../components/ui/Loading';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { SupervisorProvider, useSupervisor } from './SupervisorContext';
import SupervisorAgents from './SupervisorAgents';
import SupervisorEarnings from './SupervisorEarnings';
import SupervisorOverview from './SupervisorOverview';
import SupervisorProfile from './SupervisorProfile';
import SupervisorStudents from './SupervisorStudents';

const NAV = [
  { to: '/sales-manager', end: true, label: 'Overview', icon: 'dashboard' },
  { to: '/sales-manager/agents', label: 'Agents', icon: 'users' },
  { to: '/sales-manager/students', label: 'Students', icon: 'cap' },
  { to: '/sales-manager/earnings', label: 'Earnings', icon: 'trend' },
  { to: '/sales-manager/profile', label: 'Profile', icon: 'user' },
];

function PortalRoutes() {
  const { profile, loading } = useSupervisor();
  const { signOut } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  if (loading) return <Loading label="Opening your Sales Manager portal" />;
  if (!profile) return <Navigate to="/sales-manager/login" replace />;

  return (
    <PortalShell
      prefix="agent"
      brandLabel="Manager portal"
      title="Gabstep Manager Portal"
      nav={NAV}
      topbarRight={
        <Link
          className="agent-topbar-profile-btn"
          to="/sales-manager/profile"
          title={profile.full_name || 'Your profile'}
        >
          <span className="agent-topbar-avatar">
            {profile.avatar ? <img src={profile.avatar} alt="" /> : <span>{profile.initials}</span>}
          </span>
          <span className="agent-topbar-name">{profile.full_name}</span>
        </Link>
      }
      onSignOut={() => {
        signOut();
        toast.info('Signed out.');
        navigate('/sales-manager/login');
      }}
    >
      <Routes>
        <Route index element={<SupervisorOverview />} />
        <Route path="agents" element={<SupervisorAgents />} />
        <Route path="students" element={<SupervisorStudents />} />
        <Route path="earnings" element={<SupervisorEarnings />} />
        <Route path="profile" element={<SupervisorProfile />} />
        <Route path="*" element={<Navigate to="/sales-manager" replace />} />
      </Routes>
    </PortalShell>
  );
}

export default function SupervisorPortal() {
  return (
    <SupervisorProvider>
      <PortalRoutes />
    </SupervisorProvider>
  );
}
