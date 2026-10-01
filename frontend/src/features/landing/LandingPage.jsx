import { useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';
import { useAuth } from '../../context/AuthContext';
import SiteFooter from '../../components/layout/SiteFooter';
import HeroCarousel from './HeroCarousel';
import GoogleReviews from './GoogleReviews';

const ABOUT = [
  {
    icon: 'building',
    title: 'Partner universities',
    text: 'Compare courses, tuition and start dates, country by country.',
  },
  {
    icon: 'passport',
    title: 'Visa support',
    text: 'From offer and admission letters through to your visa.',
  },
  {
    icon: 'badgeCheck',
    title: 'One place to track',
    text: 'Every stage in your dashboard, with an email at each step.',
  },
];

const STEPS = [
  { title: 'Create an account', text: 'Sign up and confirm your email.' },
  { title: 'Pick a course', text: 'Choose a country, a university and a course.' },
  { title: 'Upload and pay', text: 'Add your documents and pay the fee in your own currency.' },
  { title: 'Track to your visa', text: 'Follow each stage and receive your letters.' },
];

const AGENT_POINTS = [
  {
    icon: 'userPlus',
    title: 'Register students',
    text: 'File applications and upload documents in one place.',
  },
  {
    icon: 'wallet',
    title: 'Earn commission',
    text: "Paid when a student's fee is settled, and again when their visa is confirmed.",
  },
  {
    icon: 'megaphone',
    title: 'Ads funding',
    text: 'Interest-free funding to grow your reach, repaid from your earnings.',
  },
  {
    icon: 'payout',
    title: 'Withdraw anytime',
    text: 'Send your balance straight to your bank account.',
  },
];

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

        <div className="marketing">
          <section className="section" aria-labelledby="lp-about-title">
            <div className="container">
              <div className="section-head">
                <span className="section-eyebrow">About Gabstep</span>
                <h2 id="lp-about-title" className="section-title">
                  Your route to studying abroad
                </h2>
                <p className="section-lede">
                  Gabstep connects students with partner universities abroad and
                  guides every application from course choice to visa.
                </p>
              </div>
              <div className="lp-cards">
                {ABOUT.map((item) => (
                  <article key={item.title} className="lp-card">
                    <span className="lp-card-icon">
                      <Icon name={item.icon} size={22} />
                    </span>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                  </article>
                ))}
              </div>
            </div>
          </section>

          <section className="section section-alt" aria-labelledby="lp-apply-title">
            <div className="container">
              <div className="section-head">
                <span className="section-eyebrow">For applicants</span>
                <h2 id="lp-apply-title" className="section-title">Apply in four steps</h2>
              </div>
              <ol className="lp-steps">
                {STEPS.map((step, index) => (
                  <li key={step.title} className="lp-step">
                    <span className="lp-step-num" aria-hidden="true">{index + 1}</span>
                    <h3>{step.title}</h3>
                    <p>{step.text}</p>
                  </li>
                ))}
              </ol>
              {isApplicant ? (
                <Link to="/portal" className="btn btn-primary btn-lg">
                  Go to my dashboard
                  <Icon name="arrowRight" size={18} strokeWidth={2} />
                </Link>
              ) : user ? null : (
                <Link to="/signup" className="btn btn-primary btn-lg">
                  <Icon name="cap" size={18} strokeWidth={2} />
                  Create applicant account
                </Link>
              )}
            </div>
          </section>

          <section className="section" aria-labelledby="lp-agent-title">
            <div className="container">
              <div className="section-head">
                <span className="section-eyebrow">For agents</span>
                <h2 id="lp-agent-title" className="section-title">
                  Earn with every student you place
                </h2>
                <p className="section-lede">
                  Register students, follow their progress and get paid as they move forward.
                </p>
              </div>
              <div className="lp-cards lp-cards-4">
                {AGENT_POINTS.map((item) => (
                  <article key={item.title} className="lp-card">
                    <span className="lp-card-icon">
                      <Icon name={item.icon} size={22} />
                    </span>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                  </article>
                ))}
              </div>
              {isAgent ? (
                <Link to="/agent" className="btn btn-primary btn-lg">
                  Open partner portal
                  <Icon name="arrowRight" size={18} strokeWidth={2} />
                </Link>
              ) : user ? null : (
                <Link to="/agent/register" className="btn btn-primary btn-lg">
                  <Icon name="users" size={18} strokeWidth={2} />
                  Become an agent
                </Link>
              )}
            </div>
          </section>

          <GoogleReviews />
        </div>
      </main>

      <SiteFooter onOpenLogin={user ? undefined : onOpenLogin} />
    </>
  );
}
