import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Loading from '../../components/ui/Loading';
import { auth } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';
import Icon from '../../lib/icons';
import CheckEmailPanel from './CheckEmailPanel';

/**
 * Where the link in the verification email lands.
 *
 * Opening it confirms the address, signs the person in and sends the welcome
 * email; from here they go straight to their dashboard. A link that has
 * expired offers a new one.
 */

const HOME = { agent: '/agent', supervisor: '/sales-manager' };

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const { verifyEmail } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState(token ? 'checking' : 'invalid');
  const [role, setRole] = useState('applicant');
  const [email, setEmail] = useState('');
  const [asking, setAsking] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    document.title = 'Confirm your email · Gabstep';
  }, []);

  useEffect(() => {
    // Strict mode runs effects twice in development; the link is only opened once.
    if (!token || started.current) return;
    started.current = true;
    verifyEmail(token)
      .then((user) => {
        setRole(user?.role || 'applicant');
        setState(user?.already ? 'already' : 'done');
      })
      .catch(() => setState('invalid'));
  }, [token, verifyEmail]);

  const home = HOME[role] || '/portal';

  return (
    <>
      <SiteHeader />
      <main className="gx-auth">
        <div className="gx-card gx-auth-card">
          {state === 'checking' ? <Loading label="Confirming your email" /> : null}

          {state === 'done' ? (
            <div className="gx-auth-done" role="status">
              <span className="gx-icon-tile" aria-hidden="true">
                <Icon name="checkCircle" size={22} />
              </span>
              <h1>Email confirmed</h1>
              <p className="gx-muted">Your account is active. We have sent you a welcome email with everything you can do.</p>
              <div className="gx-auth-actions">
                <button type="button" className="gx-btn gx-btn-primary" onClick={() => navigate(home, { replace: true })}>
                  {role === 'agent' ? 'Open partner portal' : 'Go to my dashboard'}
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </button>
              </div>
            </div>
          ) : null}

          {state === 'already' ? (
            <div className="gx-auth-done" role="status">
              <span className="gx-icon-tile" aria-hidden="true">
                <Icon name="checkCircle" size={22} />
              </span>
              <h1>Email already confirmed</h1>
              <p className="gx-muted">Sign in to continue.</p>
              <div className="gx-auth-actions">
                <button
                  type="button"
                  className="gx-btn gx-btn-primary"
                  onClick={() =>
                    role === 'agent'
                      ? navigate('/agent/login', { replace: true })
                      : navigate('/', { replace: true, state: { signIn: true } })
                  }
                >
                  Sign in
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </button>
              </div>
            </div>
          ) : null}

          {state === 'invalid' && !asking ? (
            <div className="gx-auth-done">
              <span className="gx-icon-tile gx-icon-tile-warn" aria-hidden="true">
                <Icon name="alert" size={22} />
              </span>
              <h1>This link has expired</h1>
              <p className="gx-muted">Confirmation links work for 48 hours. Enter your email and we will send a new one.</p>
              <form
                className="gx-form gx-inline-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return;
                  await auth.resendVerification(email.trim()).catch(() => {});
                  setAsking(true);
                }}
              >
                <div className="gx-field">
                  <label htmlFor="ve-email">Email address</label>
                  <input
                    id="ve-email"
                    type="email"
                    className="gx-input"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </div>
                <button type="submit" className="gx-btn gx-btn-primary">
                  Continue
                </button>
              </form>
              <p className="gx-muted gx-small">
                Already confirmed? <Link to="/" state={{ signIn: true }} className="gx-link">Sign in</Link>
              </p>
            </div>
          ) : null}

          {state === 'invalid' && asking ? (
            <CheckEmailPanel email={email.trim()} onChangeEmail={() => setAsking(false)} />
          ) : null}
        </div>
      </main>
    </>
  );
}
