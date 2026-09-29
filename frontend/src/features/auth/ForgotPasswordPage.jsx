import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import { auth } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import Icon from '../../lib/icons';

/**
 * Ask for a password reset link. One page for every kind of account.
 *
 * The confirmation reads the same whether or not the address has an account,
 * because the server answers the same either way: nobody can use this page to
 * find out who is registered.
 */
export default function ForgotPasswordPage({ onOpenLogin }) {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState('');
  const toast = useToast();

  useEffect(() => {
    document.title = 'Reset password · Gabstep';
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    const value = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setError('Enter the email address you signed up with.');
      return;
    }
    setBusy(true);
    try {
      await auth.forgotPassword(value);
      setSentTo(value);
    } catch (err) {
      toast.error(errorMessage(err, 'The request could not be sent. Try again.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <SiteHeader />
      <main className="gx-auth">
        <div className="gx-card gx-auth-card">
          {sentTo ? (
            <div className="gx-auth-done" role="status">
              <span className="gx-icon-tile" aria-hidden="true">
                <Icon name="mail" size={22} />
              </span>
              <h1>Check your email</h1>
              <p className="gx-muted">
                If an account uses <strong>{sentTo}</strong>, a link to reset the password is on its way.
                It expires in one hour. Check your spam folder if it has not arrived in a few minutes.
              </p>
              <div className="gx-auth-actions">
                <button type="button" className="gx-btn gx-btn-secondary" onClick={() => setSentTo('')}>
                  Use another email
                </button>
                <Link to="/" className="gx-btn gx-btn-primary">
                  Back to home
                </Link>
              </div>
            </div>
          ) : (
            <>
              <div className="gx-auth-head">
                <h1>Reset your password</h1>
                <p className="gx-muted">Enter the email you signed up with and we will send you a link.</p>
              </div>
              <form className="gx-form" onSubmit={submit} noValidate>
                <div className={`gx-field ${error ? 'has-error' : ''}`.trim()}>
                  <label htmlFor="fp-email">Email address</label>
                  <input
                    id="fp-email"
                    type="email"
                    className="gx-input"
                    autoComplete="email"
                    inputMode="email"
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value);
                      setError('');
                    }}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'fp-email-error' : undefined}
                  />
                  {error ? (
                    <span className="gx-error" id="fp-email-error">
                      {error}
                    </span>
                  ) : null}
                </div>
                <button type="submit" className="gx-btn gx-btn-primary gx-btn-lg gx-btn-block" disabled={busy}>
                  {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
                  {busy ? 'Sending' : 'Send reset link'}
                </button>
              </form>
              <p className="gx-auth-foot">
                Remembered it?{' '}
                <button type="button" className="gx-link" onClick={() => onOpenLogin?.()}>
                  Sign in
                </button>
              </p>
            </>
          )}
        </div>
      </main>
    </>
  );
}
