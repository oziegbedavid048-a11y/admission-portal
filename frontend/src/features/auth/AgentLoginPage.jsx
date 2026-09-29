import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import CheckEmailPanel from './CheckEmailPanel';

export default function AgentLoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [unverified, setUnverified] = useState('');
  const { signIn, user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    if (user?.role === 'agent') navigate('/agent', { replace: true });
  }, [user, navigate]);

  const submit = async (event) => {
    event.preventDefault();
    if (!email.trim() || !password) {
      toast.warning('Enter your email and password.');
      return;
    }

    setBusy(true);
    try {
      const signedIn = await signIn(email.trim(), password);
      if (signedIn.role !== 'agent') {
        toast.warning('That account is an applicant account. Opening your application.');
        navigate('/portal');
        return;
      }
      toast.success(`Welcome back, ${(signedIn.full_name || '').split(' ')[0]}.`);
      navigate('/agent');
    } catch (error) {
      if (error?.response?.data?.code === 'email_not_verified') {
        setUnverified(email.trim());
        return;
      }
      toast.error(errorMessage(error, 'Those details do not match a partner account.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="agent-section">
      <div className="agent-auth-view">
        <div className="agent-auth-card">
          <div className="agent-auth-logo">
            <img src="/assets/logo.png" alt="" />
            <div className="auth-brand">
              Gabstep Agents
              <span>Partner network</span>
            </div>
          </div>

          <h2>Partner sign in</h2>
          <p className="auth-sub">
            Use the email address and password you registered with.
          </p>

          {unverified ? (
            <CheckEmailPanel
              compact
              email={unverified}
              title="Confirm your email first"
              onChangeEmail={() => setUnverified('')}
            />
          ) : (
          <form onSubmit={submit}>
            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="ag-login-id">
                Email address *
              </label>
              <input
                type="email"
                id="ag-login-id"
                className="agent-form-control"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="ag-login-pass">
                Password *
              </label>
              <input
                type="password"
                id="ag-login-pass"
                className="agent-form-control"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            <div className="gx-forgot-row">
              <Link to="/forgot-password" className="gx-link">
                Forgot password?
              </Link>
            </div>

            <button
              type="submit"
              className="agent-btn agent-btn-primary agent-btn-block"
              disabled={busy}
            >
              {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
              {busy ? 'Signing in' : 'Sign in'}
            </button>
          </form>
          )}

          <div className="auth-switch-link">
            New partner?{' '}
            <Link className="link-btn" to="/agent/register">
              Register your agency
            </Link>
          </div>

          <div className="auth-switch-link">
            Are you a Sales Manager?{' '}
            <Link className="link-btn" to="/sales-manager/login">
              Sign in here
            </Link>
          </div>

          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <Link
              to="/"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.8125rem',
                color: 'var(--slate-500)',
                textDecoration: 'none',
              }}
            >
              <Icon name="arrowLeft" size={15} strokeWidth={2} />
              Back to the student site
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
