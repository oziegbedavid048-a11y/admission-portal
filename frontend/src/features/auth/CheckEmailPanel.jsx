import { useEffect, useState } from 'react';
import { auth } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import Icon from '../../lib/icons';

/**
 * "Check your email", shown after signing up and when someone tries to sign in
 * before confirming their address. It offers the one thing that helps: sending
 * the link again, with a short wait between sends.
 */
export default function CheckEmailPanel({ email, title = 'Check your email', onChangeEmail, compact = false }) {
  const toast = useToast();
  const [wait, setWait] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = window.setTimeout(() => setWait((current) => current - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  const resend = async () => {
    setBusy(true);
    try {
      await auth.resendVerification(email);
      toast.success('A new link is on its way.');
      setWait(60);
    } catch {
      toast.error('The email could not be sent. Try again in a minute.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={compact ? 'gx-check-email is-compact' : 'gx-auth-done'} role="status">
      {compact ? null : (
        <span className="gx-icon-tile" aria-hidden="true">
          <Icon name="mail" size={22} />
        </span>
      )}
      {compact ? <strong>{title}</strong> : <h1>{title}</h1>}
      <p className="gx-muted">
        We sent a confirmation link to <strong>{email}</strong>. Open it to activate your account.
        Check your spam folder if you cannot find it.
      </p>
      <div className="gx-auth-actions">
        <button type="button" className="gx-btn gx-btn-secondary" onClick={resend} disabled={busy || wait > 0}>
          {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
          {wait > 0 ? `Resend in ${wait}s` : 'Resend email'}
        </button>
        {onChangeEmail ? (
          <button type="button" className="gx-btn gx-btn-ghost" onClick={onChangeEmail}>
            Use a different email
          </button>
        ) : null}
      </div>
    </div>
  );
}
