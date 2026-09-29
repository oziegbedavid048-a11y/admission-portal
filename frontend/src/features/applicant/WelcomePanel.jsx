import { Link } from 'react-router-dom';
import WeatherBanner from '../../components/ui/WeatherBanner';
import { useAuth } from '../../context/AuthContext';
import Icon from '../../lib/icons';
import { firstNameOf } from '../../lib/format';

/**
 * The overview before there is an application.
 *
 * A new account has nothing to track yet, so this page does one job: point at
 * the course list, and show the four steps from here to a submitted file, with
 * the first one already done.
 */

const STEPS = [
  { title: 'Create your account', text: 'Done. Everything happens from this dashboard.', done: true },
  { title: 'Choose a course', text: 'Compare universities, tuition, duration and start dates.' },
  { title: 'Apply', text: 'Add your education and upload your documents.' },
  { title: 'Pay and track', text: 'Pay the application fee, then follow every stage here.' },
];

export default function WelcomePanel() {
  const { user } = useAuth();

  return (
    <div className="gx-page">
      <WeatherBanner userName={firstNameOf(user?.full_name)} />

      <section className="gx-card gx-welcome">
        <div>
          <h2>Find your course</h2>
          <p className="gx-muted">Browse every programme our partner universities offer, then apply in minutes.</p>
        </div>
        <Link to="/portal/courses" className="gx-btn gx-btn-primary gx-btn-lg">
          Browse courses
          <Icon name="arrowRight" size={17} strokeWidth={2} />
        </Link>
      </section>

      <section className="gx-card" aria-labelledby="next-title">
        <div className="gx-card-head">
          <h2 id="next-title" className="gx-card-title">How it works</h2>
        </div>
        <ol className="gx-steps">
          {STEPS.map((step, index) => (
            <li key={step.title} className={`gx-step ${step.done ? 'is-done' : ''}`.trim()}>
              <span className="gx-step-num" aria-hidden="true">
                {step.done ? <Icon name="check" size={14} strokeWidth={2.4} /> : index + 1}
              </span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
