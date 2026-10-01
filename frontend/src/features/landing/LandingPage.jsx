import { useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import SiteFooter from '../../components/layout/SiteFooter';
import Icon from '../../lib/icons';
import { useAuth } from '../../context/AuthContext';
import useReveal from '../../hooks/useReveal';
import HeroCarousel from './HeroCarousel';
import GoogleReviews, { HAS_REVIEWS } from './GoogleReviews';

// Figures and services as Gabstep publishes them on gabstep.com.
const STATS = [
  { value: '15', label: 'Years of experience' },
  { value: '500+', label: 'Visas approved' },
  { value: '120+', label: 'Partner universities' },
];

const SERVICES = [
  { icon: 'passport', title: 'Study visas', text: 'Canada, the United Kingdom and Malta.' },
  { icon: 'cap', title: 'University placement', text: 'The right course at the right school.' },
  { icon: 'book', title: 'Test preparation', text: 'Ready for the exams your school asks for.' },
  { icon: 'document', title: 'SOP and LOR', text: 'Statements and references that stand out.' },
  { icon: 'wallet', title: 'Student loans', text: 'Guidance on funding your studies.' },
  { icon: 'chat', title: 'Career counselling', text: 'A path that fits your goals.' },
];

const STEPS = [
  { title: 'Create an account', text: 'Sign up and confirm your email.' },
  { title: 'Pick a course', text: 'Choose a country, a university and a course.' },
  { title: 'Upload and pay', text: 'Add your documents and pay the fee in your own currency.' },
  { title: 'Track to your visa', text: 'Follow every stage and receive your letters.' },
];

const AGENT_POINTS = [
  { icon: 'userPlus', title: 'Register students', text: 'File applications and documents in one place.' },
  { icon: 'wallet', title: 'Earn commission', text: "When a student's fee is settled, and again at visa." },
  { icon: 'megaphone', title: 'Ads funding', text: 'Interest-free funding to grow your reach.' },
  { icon: 'payout', title: 'Withdraw anytime', text: 'Straight to your bank account.' },
];

const SECTIONS = [
  { id: 'about', label: 'About' },
  ...(HAS_REVIEWS ? [{ id: 'reviews', label: 'Reviews' }] : []),
  { id: 'apply', label: 'How to apply' },
  { id: 'agents', label: 'Agents' },
];

export default function LandingPage({ onOpenLogin }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAgent, isSupervisor } = useAuth();
  useReveal();

  // A guard that bounced someone here asks for the sign-in dialog.
  useEffect(() => {
    if (location.state?.signIn) onOpenLogin?.();
  }, [location.state, onOpenLogin]);

  const isApplicant = user && !isAgent && !isSupervisor;

  return (
    <>
      <SiteHeader sections={SECTIONS} onOpenLogin={onOpenLogin} />

      <main className="landing">
        <HeroCarousel>
          <div className="hero-copy">
            <h1 className="hero-title">Begin your global education journey</h1>
            <p className="hero-subtitle">
              Create an account, browse courses and tuition across our partner
              universities, and apply when you are ready.
            </p>

            <div className="hero-cta-group">
              {isApplicant ? (
                <button type="button" className="btn btn-accent btn-lg" onClick={() => navigate('/portal')}>
                  Go to my dashboard
                  <Icon name="arrowRight" size={18} strokeWidth={2} />
                </button>
              ) : user ? null : (
                <>
                  <button type="button" className="btn btn-accent btn-lg" onClick={() => navigate('/signup')}>
                    Start your application
                    <Icon name="arrowRight" size={18} strokeWidth={2} />
                  </button>
                  <a href="#about" className="btn btn-quiet btn-lg">
                    Learn more
                  </a>
                </>
              )}
            </div>
          </div>
        </HeroCarousel>

        <section id="about" className="lp-section" aria-labelledby="lp-about-title">
          <div className="container">
            <header className="lp-head reveal">
              <p className="lp-eyebrow">About Apply Gabstep</p>
              <h2 id="lp-about-title" className="lp-title">
                Fifteen years of opening doors abroad.
              </h2>
              <p className="lp-lede">
                Apply Gabstep is a global study abroad and career consultancy. We guide
                students from choosing a course to landing a visa, all from our platform.
              </p>
            </header>

            <dl className="lp-stats reveal">
              {STATS.map((stat) => (
                <div key={stat.label}>
                  <dt>{stat.label}</dt>
                  <dd>{stat.value}</dd>
                </div>
              ))}
            </dl>

            <ul className="lp-services">
              {SERVICES.map((service) => (
                <li key={service.title} className="lp-service reveal">
                  <Icon name={service.icon} size={26} strokeWidth={1.6} interactive={false} />
                  <h3>{service.title}</h3>
                  <p>{service.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <GoogleReviews />

        <section id="apply" className="lp-section" aria-labelledby="lp-apply-title">
          <div className="container">
            <header className="lp-head reveal">
              <p className="lp-eyebrow">For applicants</p>
              <h2 id="lp-apply-title" className="lp-title">Apply in four simple steps.</h2>
              <p className="lp-lede">Everything happens in one dashboard, from your first course to your visa.</p>
            </header>

            <ol className="lp-steps">
              {STEPS.map((step, index) => (
                <li key={step.title} className="lp-step reveal">
                  <span className="lp-step-num" aria-hidden="true">{index + 1}</span>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </li>
              ))}
            </ol>

            <div className="lp-cta reveal">
              {isApplicant ? (
                <Link to="/portal" className="lp-btn">
                  Go to my dashboard
                  <Icon name="arrowRight" size={18} strokeWidth={2} interactive={false} />
                </Link>
              ) : user ? null : (
                <Link to="/signup" className="lp-btn">
                  Create applicant account
                  <Icon name="arrowRight" size={18} strokeWidth={2} interactive={false} />
                </Link>
              )}
            </div>
          </div>
        </section>

        <section id="agents" className="lp-section" aria-labelledby="lp-agent-title">
          <div className="container lp-split">
            <header className="lp-head lp-head-left reveal">
              <p className="lp-eyebrow">For agents</p>
              <h2 id="lp-agent-title" className="lp-title">Earn with every student you place.</h2>
              <p className="lp-lede">
                Register students, follow their progress and get paid as they move forward.
              </p>
              {isAgent ? (
                <Link to="/agent" className="lp-btn">
                  Open partner portal
                  <Icon name="arrowRight" size={18} strokeWidth={2} interactive={false} />
                </Link>
              ) : user ? null : (
                <Link to="/agent/register" className="lp-btn">
                  Become an agent
                  <Icon name="arrowRight" size={18} strokeWidth={2} interactive={false} />
                </Link>
              )}
            </header>

            <ul className="lp-points">
              {AGENT_POINTS.map((point) => (
                <li key={point.title} className="reveal">
                  <span className="lp-point-icon">
                    <Icon name={point.icon} size={22} strokeWidth={1.7} interactive={false} />
                  </span>
                  <div>
                    <h3>{point.title}</h3>
                    <p>{point.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <SiteFooter sections={SECTIONS} onOpenLogin={user ? undefined : onOpenLogin} />
    </>
  );
}
