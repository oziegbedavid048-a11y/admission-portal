import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import UserAvatar from '../ui/UserAvatar';

/**
 * The public header: the brand, and for someone signed in, a way back to their
 * own portal. Signing up and signing in live on the landing page's hero and on
 * each sign-up page, so the header carries no buttons of its own. The sales
 * manager portal is reached by its address, /sales-manager/login.
 */
export default function SiteHeader() {
  const { user, isAgent, isSupervisor } = useAuth();

  const portalPath = isSupervisor ? '/sales-manager' : isAgent ? '/agent' : '/portal';
  const portalName = isSupervisor ? 'Sales manager portal' : isAgent ? 'Partner portal' : 'My dashboard';

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

        {user ? (
          <nav className="nav-actions" aria-label="Account">
            <Link to={portalPath} className="nav-user-chip" aria-label={`Open ${portalName}`}>
              <UserAvatar className="chip-avatar" src={user.avatar} initials={user.initials} />
              <span className="chip-name">{portalName}</span>
            </Link>
          </nav>
        ) : null}
      </div>
    </header>
  );
}
