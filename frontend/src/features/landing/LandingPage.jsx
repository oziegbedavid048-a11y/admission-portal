import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';
import { useAuth } from '../../context/AuthContext';
import HeroCarousel from './HeroCarousel';

export default function LandingPage({ onOpenLogin }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAgent } = useAuth();

  // A guard that bounced someone here asks for the sign-in dialog.
  useEffect(() => {
    if (location.state?.signIn) onOpenLogin?.();
  }, [location.state, onOpenLogin]);

  const startApplication = () => {
    navigate('/apply');
  };

  return (
    <>
      <SiteHeader onOpenLogin={onOpenLogin} />

      <main>
        <HeroCarousel>
          <h1 className="hero-title">Begin your global education journey</h1>
          <p className="hero-subtitle">
            Choose a partner institution, upload your credentials, and follow your
            admission and visa from one place.
          </p>

          {/* One action carries the weight of the page: starting an application is
              what the hero is for. Signing in is the quiet alternative beside it,
              and the partner and sales manager portals are not repeated here at
              all -- they are already in the header, and four buttons of equal
              weight left a visitor with nothing to look at first. */}
          <div className="hero-cta-group">
            <button
              type="button"
              className="btn btn-accent btn-lg"
              onClick={startApplication}
            >
              Start application
              <Icon name="arrowRight" size={18} strokeWidth={2} />
            </button>

            <button
              type="button"
              className="btn btn-quiet btn-lg"
              onClick={() => (user && !isAgent ? navigate('/portal') : onOpenLogin?.())}
            >
              <Icon name="signIn" size={17} strokeWidth={2} />
              {user && !isAgent ? 'My application' : 'Applicant login'}
            </button>
          </div>
        </HeroCarousel>
      </main>
    </>
  );
}
