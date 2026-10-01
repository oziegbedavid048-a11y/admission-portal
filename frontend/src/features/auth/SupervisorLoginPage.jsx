import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PasswordInput from '../../components/ui/PasswordInput';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

/**
 * Sales Managers do not sign themselves up. The admissions desk creates the
 * account and the sign-in details are emailed, so this screen only signs in.
 */
export default function SupervisorLoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');
  const { signIn, user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = 'Sales manager sign in · Gabstep';
  }, []);

  useEffect(() => {
    if (user?.role === 'supervisor') navigate('/sales-manager', { replace: true });
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
      if (signedIn.role !== 'supervisor') {
        toast.warning('That account is not a Sales Manager account.');
        navigate(signedIn.role === 'agent' ? '/agent' : '/portal');
        return;
      }
      toast.success(`Welcome back, ${(signedIn.full_name || '').split(' ')[0]}.`);
      navigate('/sales-manager');
    } catch (error) {
      setFormError(errorMessage(error, 'Invalid email or password.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="agent-section">
      <div className="agent-auth-view">
        <div className="agent-auth-card sv-auth-card">
          <div className="agent-auth-logo">
            <img src="/assets/logo.png" alt="" />
            <div className="auth-brand">
              Gabstep
              <span>Sales managers</span>
            </div>
          </div>

          <h2>Sign in</h2>
          <p className="auth-sub">Welcome back.</p>

          <form onSubmit={submit} noValidate>
            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="sv-login-email">
                Email address
              </label>
              <input
                type="email"
                id="sv-login-email"
                className="agent-form-control"
                autoComplete="email"
                value={email}
                onChange={(event) => { setEmail(event.target.value); setFormError(''); }}
                required
              />
            </div>

            <div className="agent-form-group">
              <div className="sv-label-row">
                <label className="agent-form-label" htmlFor="sv-login-pass">
                  Password
                </label>
                <Link to="/forgot-password" className="gx-link">
                  Forgot password?
                </Link>
              </div>
              <PasswordInput
                id="sv-login-pass"
                className="agent-form-control"
                autoComplete="current-password"
                value={password}
                onChange={(event) => { setPassword(event.target.value); setFormError(''); }}
                required
              />
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
        </div>
      </div>
    </section>
  );
}
