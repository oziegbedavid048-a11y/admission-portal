import { Link } from 'react-router-dom';

const SUPPORT_EMAIL = 'support@gabstep.com';
const PHONE = '+2349013111121';
const PHONE_DISPLAY = '+234 901 311 1121';

// Gabstep's offices, as listed on gabstep.com.
const OFFICES = [
  { city: 'Lagos', address: 'Suite 103, Philez Plaza, 2 Airport Road, Ajao Estate' },
  { city: 'Ibadan', address: '1 Kings Plaza, Alafia Avenue' },
  { city: 'Ile-Ife', address: 'Opposite Phase 1 OAUTH' },
];

/**
 * The public footer, on a dark ground: the brand and its offices, the page's
 * sections, the ways in, and how to reach the team.
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
            <Link to="/" className="sf-logo" aria-label="Gabstep home">
              <img src="/assets/logo.png" alt="" />
              <span>Gabstep</span>
            </Link>
            <p>Study abroad and career consultancy, from your first course to your visa.</p>
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
            <div>
              <h3>Contact</h3>
              <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
              <a href={`tel:${PHONE}`}>{PHONE_DISPLAY}</a>
              <a href={`https://wa.me/${PHONE.slice(1)}`} target="_blank" rel="noopener noreferrer">
                WhatsApp
              </a>
            </div>
          </nav>
        </div>

        <ul className="sf-offices" aria-label="Offices">
          {OFFICES.map((office) => (
            <li key={office.city}>
              <strong>{office.city}</strong>
              <span>{office.address}</span>
            </li>
          ))}
        </ul>

        <div className="sf-bottom">
          <span>&copy; {year} Gabstep. All rights reserved.</span>
          <a href="https://gabstep.com" target="_blank" rel="noopener noreferrer">
            gabstep.com
          </a>
        </div>
      </div>
    </footer>
  );
}
