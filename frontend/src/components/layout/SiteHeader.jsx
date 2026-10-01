import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Icon from '../../lib/icons';
import UserAvatar from '../ui/UserAvatar';

/**
 * The public header: the brand, and on the home page the section links and
 * the ways in.
 *
 * Nothing floats over the page. Choosing "Sign in" or "Create account" grows
 * the header itself downward to show the options as plain text links, and the
 * phone menu works the same way, so the header is the only surface there is.
 * It folds back up on Escape, on a press outside it, or when a link is chosen.
 * Someone signed in sees a way back to their own portal instead.
 *
 * `sections` is a list of { id, label } for in-page links. `onOpenLogin` opens
 * the applicant sign-in dialog; when it is not passed, the account options are
 * left out (the sign-up pages carry their own).
 */
export default function SiteHeader({ sections = [], onOpenLogin }) {
  const { user, isAgent, isSupervisor } = useAuth();
  // null, 'signin', 'create', or 'menu' (the phone menu).
  const [panel, setPanel] = useState(null);
  const [scrolled, setScrolled] = useState(false);
  const root = useRef(null);
  // What the tray shows. It keeps the last panel while folding shut, so the
  // links stay in place as it closes instead of vanishing first.
  const lastPanel = useRef(null);
  if (panel) lastPanel.current = panel;
  const view = panel || lastPanel.current;

  const portalPath = isSupervisor ? '/sales-manager' : isAgent ? '/agent' : '/portal';
  const portalName = isSupervisor ? 'Sales manager portal' : isAgent ? 'Partner portal' : 'My dashboard';
  const showAccount = !user && Boolean(onOpenLogin);
  const hasMenu = sections.length > 0 || showAccount;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!panel) return undefined;
    const onPointer = (event) => {
      if (!root.current?.contains(event.target)) setPanel(null);
    };
    const onKey = (event) => {
      if (event.key === 'Escape') setPanel(null);
    };
    // Crossing into the other layout leaves nothing sensible open.
    const wide = window.matchMedia('(min-width: 1100px)');
    const onResize = () => setPanel(null);
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    wide.addEventListener('change', onResize);

    // The phone menu holds the page still underneath it.
    const previous = document.body.style.overflow;
    if (panel === 'menu') document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
      wide.removeEventListener('change', onResize);
      document.body.style.overflow = previous;
    };
  }, [panel]);

  const toggle = (name) => setPanel((current) => (current === name ? null : name));
  const close = () => setPanel(null);
  const openLogin = () => {
    close();
    onOpenLogin();
  };

  const signInLinks = (
    <>
      <button type="button" onClick={openLogin}>Applicant sign in</button>
      <Link to="/agent/login" onClick={close}>Agent sign in</Link>
    </>
  );
  const createLinks = (
    <>
      <Link to="/signup" onClick={close}>Applicant account</Link>
      <Link to="/agent/register" onClick={close}>Agent account</Link>
    </>
  );

  return (
    <header
      ref={root}
      className={`site-header ${scrolled ? 'is-scrolled' : ''} ${panel ? 'is-open' : ''}`.trim()}
    >
      <div className="container nav-container">
        <Link to="/" className="brand-logo" aria-label="Gabstep Application Portal home" onClick={close}>
          <span className="brand-icon-wrap">
            <img src="/assets/logo.png" alt="" className="brand-logo-img" />
          </span>
          <span className="brand-name">
            Gabstep
            <span className="sub">Application Portal</span>
          </span>
        </Link>

        {sections.length ? (
          <nav className="sh-links" aria-label="Sections">
            {sections.map((section) => (
              <a key={section.id} href={`#${section.id}`} onClick={close}>
                {section.label}
              </a>
            ))}
          </nav>
        ) : null}

        <div className="sh-actions">
          {user ? (
            <Link to={portalPath} className="nav-user-chip" aria-label={`Open ${portalName}`}>
              <UserAvatar className="chip-avatar" src={user.avatar} initials={user.initials} />
              <span className="chip-name">{portalName}</span>
            </Link>
          ) : null}

          {showAccount ? (
            <div className="sh-account">
              <button
                type="button"
                className="sh-btn sh-btn-ghost"
                aria-expanded={panel === 'signin'}
                aria-controls="sh-tray"
                onClick={() => toggle('signin')}
              >
                Sign in
                <Icon name="chevronDown" size={14} strokeWidth={2.2} interactive={false} />
              </button>
              <button
                type="button"
                className="sh-btn sh-btn-primary"
                aria-expanded={panel === 'create'}
                aria-controls="sh-tray"
                onClick={() => toggle('create')}
              >
                Create account
                <Icon name="chevronDown" size={14} strokeWidth={2.2} interactive={false} />
              </button>
            </div>
          ) : null}

          {hasMenu ? (
            <button
              type="button"
              className="sh-burger"
              aria-label={panel === 'menu' ? 'Close menu' : 'Open menu'}
              aria-expanded={panel === 'menu'}
              aria-controls="sh-tray"
              onClick={() => toggle('menu')}
            >
              <span />
              <span />
            </button>
          ) : null}
        </div>
      </div>

      {hasMenu ? (
        <div id="sh-tray" className={`sh-tray ${panel ? 'is-open' : ''}`.trim()} aria-hidden={!panel}>
          <div className="sh-tray-inner">
            <div className="container">
              {view === 'signin' ? (
                <div className="sh-tray-row">
                  <p>Sign in</p>
                  {signInLinks}
                </div>
              ) : null}

              {view === 'create' ? (
                <div className="sh-tray-row">
                  <p>Create account</p>
                  {createLinks}
                </div>
              ) : null}

              {view === 'menu' ? (
                <div className="sh-tray-menu">
                  {sections.length ? (
                    <nav className="sh-tray-sections" aria-label="Sections">
                      {sections.map((section) => (
                        <a key={section.id} href={`#${section.id}`} onClick={close}>
                          {section.label}
                        </a>
                      ))}
                    </nav>
                  ) : null}
                  {showAccount ? (
                    <div className="sh-tray-groups">
                      <div className="sh-tray-group">
                        <p>Create account</p>
                        {createLinks}
                      </div>
                      <div className="sh-tray-group">
                        <p>Sign in</p>
                        {signInLinks}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </header>
  );
}
