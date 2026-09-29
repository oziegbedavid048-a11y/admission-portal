import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../../components/ui/Modal';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import CheckEmailPanel from './CheckEmailPanel';

export default function LoginModal({ open, onClose }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [unverified, setUnverified] = useState('');
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
      navigate(
        user.role === 'agent' ? '/agent' : user.role === 'supervisor' ? '/sales-manager' : '/portal',
      );
    } catch (error) {
      if (error?.response?.data?.code === 'email_not_verified') {
        setUnverified(email.trim());
        return;
      }
      toast.error(errorMessage(error, 'Those details do not match an account.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Sign in"
      labelledBy="login-modal-title"
    >
      {unverified ? (
        <CheckEmailPanel
          compact
          email={unverified}
          title="Confirm your email first"
          onChangeEmail={() => setUnverified('')}
        />
      ) : (
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
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        <div className="gx-forgot-row">
          <button
            type="button"
            className="gx-link"
            onClick={() => {
              onClose?.();
              navigate('/forgot-password');
            }}
          >
            Forgot password?
          </button>
        </div>

        <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
          {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
          {busy ? 'Signing in' : 'Sign in'}
        </button>
      </form>
      )}

      <p className="gx-auth-foot">
        New to Gabstep?{' '}
        <button
          type="button"
          className="gx-link"
          onClick={() => {
            onClose?.();
            navigate('/signup');
          }}
        >
          Create an account
        </button>
      </p>
    </Modal>
  );
}
