import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Icon from '../../lib/icons';
import UserAvatar from '../ui/UserAvatar';

/**
 * The public header.
 *
 * Signed out, it offers two things: "Create account", the one action the site
 * is for, and "Sign in", a menu that holds every portal. The partner and sales
 * manager portals used to sit in the header as two loose buttons of equal
 * weight to everything else; they are in the menu now, under a heading that
 * says who they are for. Signed in, the header is a single chip back to your
 * own portal.
 */

const PORTALS = [
  {
    key: 'applicant',
    icon: 'cap',
    title: 'Applicant',
    detail: 'Track your application',
  },
  {
    key: 'agent',
    icon: 'users',
    title: 'Partner agent',
    detail: 'Register and follow students',
    to: '/agent/login',
  },
  {
    key: 'manager',
    icon: 'shield',
    title: 'Sales manager',
    detail: 'Your agents and earnings',
    to: '/sales-manager/login',
  },
];

export default function SiteHeader({ onOpenLogin }) {
  const { user, isAgent, isSupervisor } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);

  const portalPath = isSupervisor ? '/sales-manager' : isAgent ? '/agent' : '/portal';
  const portalName = isSupervisor ? 'Sales manager portal' : isAgent ? 'Partner portal' : 'My dashboard';

  // Close on outside click and on Escape, returning focus to the button.
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onPointer = (event) => {
      if (!wrapRef.current?.contains(event.target)) setMenuOpen(false);
    };
    const onKey = (event) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        buttonRef.current?.focus();
      }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const items = [...(menuRef.current?.querySelectorAll('.nav-menu-item') || [])];
        if (!items.length) return;
        event.preventDefault();
        const index = items.indexOf(document.activeElement);
        const next = event.key === 'ArrowDown' ? index + 1 : index - 1;
        items[(next + items.length) % items.length].focus();
      }
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    menuRef.current?.querySelector('.nav-menu-item')?.focus();
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const choose = (portal) => {
    setMenuOpen(false);
    if (portal.to) navigate(portal.to);
    else onOpenLogin?.();
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

        <nav className="nav-actions" aria-label="Account">
          {user ? (
            <Link to={portalPath} className="nav-user-chip" aria-label={`Open ${portalName}`}>
              <UserAvatar className="chip-avatar" src={user.avatar} initials={user.initials} />
              <span className="chip-name">{portalName}</span>
            </Link>
          ) : (
            <>
              <div className="nav-menu-wrap" ref={wrapRef}>
                <button
                  type="button"
                  ref={buttonRef}
                  className="nav-link-quiet"
                  aria-haspopup="true"
                  aria-expanded={menuOpen}
                  aria-controls="signin-menu"
                  onClick={() => setMenuOpen((open) => !open)}
                >
                  <span className="nav-link-label">Sign in</span>
                  <Icon name="chevronDown" size={16} strokeWidth={2} />
                </button>

                {menuOpen ? (
                  <div className="nav-menu" id="signin-menu" ref={menuRef} role="menu">
                    <div className="nav-menu-label" aria-hidden="true">
                      Sign in as
                    </div>
                    {PORTALS.map((portal, index) => (
                      <div key={portal.key}>
                        {index === 1 ? <div className="nav-menu-divider" role="separator" /> : null}
                        <button
                          type="button"
                          role="menuitem"
                          className="nav-menu-item"
                          onClick={() => choose(portal)}
                        >
                          <span className="nav-menu-icon" aria-hidden="true">
                            <Icon name={portal.icon} size={18} />
                          </span>
                          <span className="nav-menu-text">
                            <strong>{portal.title}</strong>
                            <span>{portal.detail}</span>
                          </span>
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              <Link to="/signup" className="gx-btn gx-btn-primary nav-cta">
                Create account
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
