import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Icon from '../../lib/icons';

export default function SiteHeader({ onOpenLogin }) {
  const { user, isAgent, isSupervisor } = useAuth();
  const navigate = useNavigate();

  const goToPortal = () => {
    if (!user) {
      onOpenLogin?.();
      return;
    }
    navigate(isSupervisor ? '/sales-manager' : isAgent ? '/agent' : '/portal');
  };

  return (
    <header className="site-header">
      <div className="container nav-container">
        <Link to="/" className="brand-logo" aria-label="Gabstep Application Portal home">
          <span className="brand-icon-wrap">
            <img src="/assets/logo.png" alt="" className="brand-logo-img" />
          </span>
          <span className="brand-name">
            Gabstep
            <span className="sub">Application Portal</span>
          </span>
        </Link>

        <div className="nav-right">
          {user ? (
            <button
              type="button"
              className="nav-user-chip"
              onClick={goToPortal}
              aria-label={
                isSupervisor
                  ? 'Open the Sales Manager portal'
                  : isAgent
                    ? 'Open the partner portal'
                    : 'Open my application'
              }
            >
              <span className="chip-avatar">
                {user.avatar ? (
                  <img
                    src={user.avatar}
                    alt=""
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ) : null}
                <span>{user.initials}</span>
              </span>
              <span className="chip-name">
                {isSupervisor ? 'Sales Manager portal' : isAgent ? 'Partner portal' : 'My application'}
              </span>
            </button>
          ) : (
            <>
              <Link to="/agent/login" className="btn-nav-agent" aria-label="Agent portal sign in">
                <Icon name="users" size={15} strokeWidth={2.2} />
                <span>Agent Portal</span>
              </Link>
              <Link
                to="/sales-manager/login"
                className="btn-nav-agent btn-nav-quiet"
                aria-label="Sales Manager portal sign in"
              >
                <Icon name="shield" size={15} strokeWidth={2.2} />
                <span>Sales Manager</span>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
