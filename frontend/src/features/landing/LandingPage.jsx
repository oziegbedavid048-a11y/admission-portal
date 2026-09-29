import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
      <SiteHeader onOpenLogin={onOpenLogin} />

      <main>
        <HeroCarousel>
          <div className="hero-copy">
            <h1 className="hero-title">Begin your global education journey</h1>
            <p className="hero-subtitle">
              Create an account, browse courses and tuition across our partner
              universities, and apply when you are ready.
            </p>

            {/* One action carries the page. Signing up comes first now: the
                courses, their tuition and the application itself all live in the
                dashboard an account opens. Signing in is the quiet alternative. */}
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
                    Create free account
                    <Icon name="arrowRight" size={18} strokeWidth={2} />
                  </button>
                  <button
                    type="button"
                    className="btn btn-quiet btn-lg"
                    onClick={() => onOpenLogin?.()}
                  >
                    <Icon name="signIn" size={17} strokeWidth={2} />
                    Sign in
                  </button>
                </>
              )}
            </div>
          </div>
        </HeroCarousel>
      </main>
    </>
  );
}
