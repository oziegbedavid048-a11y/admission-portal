import { useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';
import { useAuth } from '../../context/AuthContext';
import HeroCarousel from './HeroCarousel';

export default function LandingPage({ onOpenLogin }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAgent, isSupervisor } = useAuth();

  // A guard that bounced someone here asks for the sign-in dialog.
  useEffect(() => {
    if (location.state?.signIn) onOpenLogin?.();
  }, [location.state, onOpenLogin]);

  const isApplicant = user && !isAgent && !isSupervisor;

  return (
    <>
      <SiteHeader />

      <main>
        <HeroCarousel>
          <div className="hero-copy">
            <h1 className="hero-title">Begin your global education journey</h1>
            <p className="hero-subtitle">
              Create an account, browse courses and tuition across our partner
              universities, and apply when you are ready.
            </p>

            {/* Two ways in: an applicant account, or a partner agent account.
                Returning visitors sign in from the quiet line underneath. */}
            <div className="hero-cta-group">
              {isApplicant ? (
                <button
                  type="button"
                  className="btn btn-accent btn-lg"
                  onClick={() => navigate('/portal')}
                >
                  Go to my dashboard
                  <Icon name="arrowRight" size={18} strokeWidth={2} />
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="btn btn-accent btn-lg"
                    onClick={() => navigate('/signup')}
                  >
                    <Icon name="cap" size={18} strokeWidth={2} />
                    Create applicant account
                  </button>
                  <button
                    type="button"
                    className="btn btn-quiet btn-lg"
                    onClick={() => navigate('/agent/register')}
                  >
                    <Icon name="users" size={18} strokeWidth={2} />
                    Create agent account
                  </button>
                </>
              )}
            </div>

            {user ? null : (
              <p className="hero-signin">
                Already have an account?{' '}
                <button type="button" className="hero-signin-link" onClick={() => onOpenLogin?.()}>
                  Applicant sign in
                </button>
                <Link to="/agent/login" className="hero-signin-link">
                  Agent sign in
                </Link>
              </p>
            )}
          </div>
        </HeroCarousel>
      </main>
    </>
  );
}
