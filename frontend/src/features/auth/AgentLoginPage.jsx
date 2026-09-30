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
  const [formError, setFormError] = useState('');
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
      setFormError('Enter your email and password.');
      return;
    }
    setFormError('');

    setBusy(true);
    try {
      const signedIn = await signIn(email.trim(), password);
      if (signedIn.role !== 'agent') {
        const supervisor = signedIn.role === 'supervisor';
        toast.info(supervisor ? 'Opening your sales manager portal.' : 'Opening your application dashboard.');
        navigate(supervisor ? '/sales-manager' : '/portal');
        return;
      }
      toast.success(`Welcome back, ${(signedIn.full_name || '').split(' ')[0]}.`);
      navigate('/agent');
    } catch (error) {
      if (error?.response?.data?.code === 'email_not_verified') {
        setUnverified(email.trim());
        return;
      }
      setFormError(errorMessage(error, 'Invalid email or password.'));
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
                onChange={(event) => { setEmail(event.target.value); setFormError(''); }}
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
                onChange={(event) => { setPassword(event.target.value); setFormError(''); }}
                required
              />
            </div>

            <div className="gx-forgot-row">
              <Link to="/forgot-password" className="gx-link">
                Forgot password?
              </Link>
            </div>

            {formError ? (
              <div className="gx-form-alert" role="alert">
                <Icon name="alert" size={18} strokeWidth={2} />
                <span>{formError}</span>
              </div>
            ) : null}

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
