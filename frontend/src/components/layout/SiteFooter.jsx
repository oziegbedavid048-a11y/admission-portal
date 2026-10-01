import { Link } from 'react-router-dom';

const SUPPORT_EMAIL = 'support@gabstep.com';

/**
 * The public footer, on a dark ground: the brand, the page's sections, the
 * ways in, and the support address.
 *
 * `sections` is the same { id, label } list the header uses. `onOpenLogin`
 * opens the applicant sign-in dialog; without it that link is left out.
 */
export default function SiteFooter({ sections = [], onOpenLogin }) {
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="sf-top">
          <div className="sf-brand">
            <Link to="/" className="sf-logo" aria-label="Apply Gabstep home">
              <img src="/assets/logo.png" alt="" />
              <span>Apply Gabstep</span>
            </Link>
            <p>Study abroad and career consultancy, from your first course to your visa.</p>
            <a className="sf-email" href={`mailto:${SUPPORT_EMAIL}`}>
              {SUPPORT_EMAIL}
            </a>
          </div>

          <nav className="sf-links" aria-label="Footer">
            {sections.length ? (
              <div>
                <h3>Explore</h3>
                {sections.map((section) => (
                  <a key={section.id} href={`#${section.id}`}>
                    {section.label}
                  </a>
                ))}
              </div>
            ) : null}
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
          </nav>
        </div>

        <div className="sf-bottom">
          <span>&copy; {year} Apply Gabstep. All rights reserved.</span>
          <a href="https://gabstep.com" target="_blank" rel="noopener noreferrer">
            gabstep.com
          </a>
        </div>
      </div>
    </footer>
  );
}
