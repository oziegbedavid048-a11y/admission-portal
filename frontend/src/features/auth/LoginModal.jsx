import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

export default function LoginModal({ open, onClose }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const { signIn } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const submit = async (event) => {
    event.preventDefault();
    if (!email.trim() || !password) {
      toast.warning('Enter your email and password.');
      return;
    }

    setBusy(true);
    try {
      const user = await signIn(email.trim(), password);
      onClose?.();
      setPassword('');
      toast.success(`Welcome back, ${(user.full_name || '').split(' ')[0] || 'there'}.`);
      navigate(user.role === 'agent' ? '/agent' : '/portal');
    } catch (error) {
      toast.error(errorMessage(error, 'Those details do not match an account.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Applicant sign in"
      labelledBy="login-modal-title"
    >
      <form onSubmit={submit}>
        <div className="form-group">
          <label className="form-label" htmlFor="login_email">
            Email address <span className="req">*</span>
          </label>
          <input
            type="email"
            id="login_email"
            className="form-control"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="login_password">
            Password <span className="req">*</span>
          </label>
          <input
            type="password"
            id="login_password"
            className="form-control"
            autoComplete="current-password"
            placeholder="Your password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
          {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
          {busy ? 'Signing in' : 'Sign in'}
        </button>
      </form>

      <div className="callout callout-info" style={{ marginTop: 24, marginBottom: 0 }}>
        <Icon name="info" size={20} className="callout-icon" strokeWidth={2} />
        <div className="callout-content" style={{ fontSize: '0.8125rem' }}>
          <strong>First time here?</strong> Your password is emailed to you when your
          application is submitted. Check your inbox for it.
        </div>
      </div>
    </Modal>
  );
}
