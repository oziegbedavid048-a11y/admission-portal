import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../../components/ui/Modal';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import CheckEmailPanel from './CheckEmailPanel';
import PasswordField from '../../components/ui/PasswordField';
import Icon from '../../lib/icons';

export default function LoginModal({ open, onClose }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [unverified, setUnverified] = useState('');
  const [formError, setFormError] = useState('');
  const { signIn } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const submit = async (event) => {
    event.preventDefault();
    if (!email.trim() || !password) {
      setFormError('Enter your email and password.');
      return;
    }
    setFormError('');

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
      // Shown in the form, where the person is looking, not only as a toast.
      setFormError(errorMessage(error, 'Invalid email or password.'));
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
      <form className="gx-form" onSubmit={submit} noValidate>
        {formError ? (
          <div className="gx-form-alert" role="alert">
            <Icon name="alert" size={18} strokeWidth={2} />
            <span>{formError}</span>
          </div>
        ) : null}

        <div className="gx-field">
          <label htmlFor="login_email">Email address</label>
          <input
            type="email"
            id="login_email"
            className="gx-input"
            autoComplete="email"
            inputMode="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setFormError('');
            }}
            aria-invalid={Boolean(formError)}
          />
        </div>

        <PasswordField
          id="login_password"
          label="Password"
          value={password}
          onChange={(value) => {
            setPassword(value);
            setFormError('');
          }}
          autoComplete="current-password"
          showChecks={false}
        />

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

        <button type="submit" className="gx-btn gx-btn-primary gx-btn-lg gx-btn-block" disabled={busy}>
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
