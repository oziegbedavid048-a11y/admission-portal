import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import Icon from '../../lib/icons';

/**
 * The sidebar-and-topbar frame both portals sit in.
 *
 * The applicant portal and the partner portal are styled by two different
 * stylesheets that use the same structure under different prefixes, so the
 * prefix is a prop rather than two near-identical components.
 */
export default function PortalShell({
  prefix = 'portal',
  brandLabel,
  title,
  nav,
  footerSlot,
  topbarRight,
  onSignOut,
  children,
}) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const sidebarClass = prefix === 'agent' ? 'agent-sidebar' : 'portal-sidebar';
  const overlayClass = prefix === 'agent' ? 'agent-sidebar-overlay' : 'portal-sidebar-overlay';
  const shellClass = prefix === 'agent' ? 'agent-portal-shell' : 'portal-shell';
  const mainClass = prefix === 'agent' ? 'agent-main' : 'portal-main';
  const topbarClass = prefix === 'agent' ? 'agent-topbar' : 'portal-topbar';
  const topbarLeftClass = prefix === 'agent' ? 'agent-topbar-left' : 'portal-topbar-left';
  const topbarRightClass = prefix === 'agent' ? 'agent-topbar-right' : 'portal-topbar-right';
  const bodyClass = prefix === 'agent' ? 'agent-page-body' : 'portal-body';

  // Navigating closes the drawer, so a tap on a phone never leaves it hanging
  // open over the page it just opened.
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (title) {
      document.title = title;
    }
  }, [title]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);

  return (
    <section className={prefix === 'agent' ? 'agent-section' : 'dashboard-section'}>
      <div className={shellClass}>
        <aside className={`${sidebarClass} ${open ? 'open' : ''}`.trim()}>
          <div className="sidebar-brand">
            <div className="sidebar-brand-lead">
              <img src="/assets/logo.png" alt="" />
              <div className="sidebar-brand-text">
                Gabstep
                <span>{brandLabel}</span>
              </div>
            </div>
            <button
              type="button"
              className="sidebar-close-btn"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
            >
              <Icon name="close" size={18} />
            </button>
          </div>

          <ul className="sidebar-nav">
            {nav.map((item) => (
              <li className="sidebar-nav-item" key={item.to}>
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

          <div className="sidebar-foot">
            {footerSlot}
            <button
              type="button"
              className="sidebar-foot-link"
              onClick={() => navigate('/')}
            >
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
        />

        <div className={mainClass}>
          <header className={topbarClass}>
            <div className={topbarLeftClass}>
              <div className="portal-topbar-brand-wrap">
                <h1 className="portal-topbar-brand">{title}</h1>
              </div>
            </div>

            <div className={topbarRightClass}>
              {topbarRight}
              <button
                type="button"
                className={`btn-sidebar-toggle ${open ? 'is-active' : ''}`}
                aria-label="Toggle navigation menu"
                aria-expanded={open}
                onClick={() => setOpen((prev) => !prev)}
                title="Toggle navigation"
              >
                <span className="btn-toggle-bars" aria-hidden="true">
                  <span className="toggle-bar bar-top"></span>
                  <span className="toggle-bar bar-mid"></span>
                  <span className="toggle-bar bar-bot"></span>
                </span>
              </button>
            </div>
          </header>

          <div className={bodyClass}>{children}</div>
        </div>
      </div>
    </section>
  );
}
