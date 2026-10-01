import { Link } from 'react-router-dom';

const SUPPORT_EMAIL = 'support@gabstep.com';

/**
 * The public footer: the brand, the two ways in, and how to reach support.
 * `onOpenLogin` opens the applicant sign-in dialog; without it the link is left out.
 */
export default function SiteFooter({ onOpenLogin }) {
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="sf-top">
          <div className="sf-brand">
            <Link to="/" className="sf-logo" aria-label="Gabstep home">
              <img src="/assets/logo.png" alt="" />
              <span>Gabstep</span>
            </Link>
            <p>Study abroad applications, from course to visa.</p>
          </div>

          <nav className="sf-links" aria-label="Footer">
            <div>
              <h3>Applicants</h3>
              <Link to="/signup">Create account</Link>
              {onOpenLogin ? (
                <button type="button" onClick={onOpenLogin}>
                  Sign in
                </button>
              ) : null}
            </div>
            <div>
              <h3>Agents</h3>
              <Link to="/agent/register">Become an agent</Link>
              <Link to="/agent/login">Agent sign in</Link>
            </div>
            <div>
              <h3>Contact</h3>
              <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
            </div>
          </nav>
        </div>

        <div className="sf-bottom">
          <span>&copy; {year} Gabstep. All rights reserved.</span>
        </div>
      </div>
    </footer>
  );
}
