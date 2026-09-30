import { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, matchPath, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Icon from '../../lib/icons';
import UserAvatar from '../ui/UserAvatar';

/**
 * The sidebar-and-topbar frame every portal sits in.
 *
 * The applicant portal and the partner portals are styled by two stylesheets
 * that share one structure under different prefixes, so the prefix is a prop
 * rather than two near-identical components.
 *
 * The top bar carries the site's name, as the header of every page does; the
 * page you are on is highlighted in the sidebar and named in the browser tab.
 * The profile chip reads the signed-in user, so a new photo shows here the
 * moment it is saved on any profile page.
 */
export default function PortalShell({
  prefix = 'portal',
  brandLabel,
  siteName,
  nav,
  profilePath,
  footerSlot,
  onSignOut,
  children,
}) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

  const agent = prefix === 'agent';
  const sidebarClass = agent ? 'agent-sidebar' : 'portal-sidebar';
  const overlayClass = agent ? 'agent-sidebar-overlay' : 'portal-sidebar-overlay';
  const shellClass = agent ? 'agent-portal-shell' : 'portal-shell';
  const mainClass = agent ? 'agent-main' : 'portal-main';
  const topbarClass = agent ? 'agent-topbar' : 'portal-topbar';
  const topbarLeftClass = agent ? 'agent-topbar-left' : 'portal-topbar-left';
  const topbarRightClass = agent ? 'agent-topbar-right' : 'portal-topbar-right';
  const bodyClass = agent ? 'agent-page-body' : 'portal-body';

  // The page title is the nav item that owns the current address; the most
  // specific match wins, so /portal/courses is "Courses", not "Overview".
  const current = useMemo(() => {
    const items = nav.filter((item) =>
      matchPath({ path: item.end ? item.to : `${item.to}/*`, end: Boolean(item.end) }, location.pathname),
    );
    return items.sort((a, b) => b.to.length - a.to.length)[0] || null;
  }, [nav, location.pathname]);
  const pageTitle = current?.title || current?.label || brandLabel;

  // Navigating closes the drawer, so a tap on a phone never leaves it hanging
  // open over the page it just opened.
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.title = `${pageTitle} · Gabstep`;
  }, [pageTitle]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);

  return (
    <section className={agent ? 'agent-section' : 'dashboard-section'}>
      <div className={shellClass}>
        <aside
          className={`${sidebarClass} ${open ? 'open' : ''}`.trim()}
          aria-label={`${brandLabel} navigation`}
        >
          <div className="sidebar-brand">
            <Link to="/" className="sidebar-brand-lead" aria-label="Gabstep home">
              <img src="/assets/logo.png" alt="" />
              <div className="sidebar-brand-text">
                Gabstep
                <span>{brandLabel}</span>
              </div>
            </Link>
            <button
              type="button"
              className="sidebar-close-btn"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
            >
              <Icon name="close" size={18} />
            </button>
          </div>

          <nav>
            <ul className="sidebar-nav">
              {nav
                .filter((item) => !item.hidden)
                .map((item) => (
                  <li className="sidebar-nav-item" key={item.to}>
                    {item.divider ? <div className="sidebar-nav-divider" aria-hidden="true" /> : null}
                    <NavLink
                      end={item.end}
                      to={item.to}
                      className={({ isActive }) =>
                        `sidebar-nav-link ${isActive ? 'active' : ''}`.trim()
                      }
                    >
                      <Icon name={item.icon} size={20} />
                      <span>{item.label}</span>
                    </NavLink>
                  </li>
                ))}
            </ul>
          </nav>

          <div className="sidebar-foot">
            {footerSlot}
            <button type="button" className="sidebar-foot-link" onClick={() => navigate('/')}>
              <Icon name="home" size={20} />
              <span>Main site</span>
            </button>
            <button type="button" className="sidebar-foot-link" onClick={onSignOut}>
              <Icon name="signOut" size={20} />
              <span>Sign out</span>
            </button>
          </div>
        </aside>

        <div
          className={`${overlayClass} ${open ? 'active' : ''}`.trim()}
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />

        <div className={mainClass}>
          <header className={topbarClass}>
            <div className={topbarLeftClass}>
              <div className="portal-topbar-brand-wrap">
                <h1 className="portal-topbar-brand">{siteName || pageTitle}</h1>
              </div>
            </div>

            <div className={topbarRightClass}>
              {profilePath ? (
                <Link className="agent-topbar-profile-btn" to={profilePath} title="Your profile">
                  <UserAvatar
                    className="agent-topbar-avatar"
                    src={user?.avatar}
                    initials={user?.initials}
                  />
                  <span className="agent-topbar-name" title={user?.full_name || user?.email}>
                    {(user?.full_name || user?.email || '').split(' ')[0]}
                  </span>
                  <Icon name="chevronDown" size={15} strokeWidth={2.2} className="agent-topbar-chevron" />
                </Link>
              ) : null}
              <button
                type="button"
                className={`btn-sidebar-toggle ${open ? 'is-active' : ''}`}
                aria-label={open ? 'Close navigation' : 'Open navigation'}
                aria-expanded={open}
                onClick={() => setOpen((prev) => !prev)}
              >
                <span className="btn-toggle-bars" aria-hidden="true">
                  <span className="toggle-bar bar-top"></span>
                  <span className="toggle-bar bar-mid"></span>
                  <span className="toggle-bar bar-bot"></span>
                </span>
              </button>
            </div>
          </header>

          <main className={bodyClass}>{children}</main>
        </div>
      </div>
    </section>
  );
}
