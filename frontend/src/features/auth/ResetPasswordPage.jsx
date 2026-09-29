import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Loading from '../../components/ui/Loading';
import PasswordField, { passwordChecks } from '../../components/ui/PasswordField';
import { auth } from '../../api/endpoints';
import { errorMessage, fieldErrors } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import Icon from '../../lib/icons';

/**
 * Choose a new password from the link in the reset email.
 *
 * The link is checked before the form is shown, so nobody types a new password
 * into a link that has already expired. Once the password is set, every device
 * that was signed in is signed out, this one included, and the person signs in
 * with the new password from the right portal's sign-in page.
 */

const SIGN_IN = {
  agent: '/agent/login',
  supervisor: '/sales-manager/login',
};

export default function ResetPasswordPage({ onOpenLogin }) {
  const [params] = useSearchParams();
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';
  const navigate = useNavigate();
  const toast = useToast();
  const { user, signOut } = useAuth();

  const [state, setState] = useState(uid && token ? 'checking' : 'invalid');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [role, setRole] = useState('applicant');

  useEffect(() => {
    document.title = 'Choose a new password · Gabstep';
  }, []);

  useEffect(() => {
    if (!uid || !token) return;
    let cancelled = false;
    auth
      .validateReset(uid, token)
      .then(() => !cancelled && setState('ready'))
      .catch(() => !cancelled && setState('invalid'));
    return () => {
      cancelled = true;
    };
  }, [uid, token]);

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!passwordChecks(password).every((check) => check.met)) found.password = 'Choose a stronger password.';
    if (confirm !== password) found.confirm = 'The two passwords do not match.';
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      const { data } = await auth.resetPassword(uid, token, password);
      setRole(data?.role || 'applicant');
      // Any session in this browser belonged to the old password.
      if (user) signOut();
      setState('done');
    } catch (error) {
      const fields = fieldErrors(error);
      if (fields.token) {
        setState('invalid');
      } else if (fields.new_password) {
        setErrors({ password: fields.new_password });
      } else {
        toast.error(errorMessage(error, 'Your password could not be changed. Try again.'));
      }
    } finally {
      setBusy(false);
    }
  };

  const goSignIn = () => {
    const path = SIGN_IN[role];
    if (path) navigate(path);
    else {
      navigate('/');
      onOpenLogin?.();
    }
  };

  return (
    <>
      <SiteHeader />
      <main className="gx-auth">
        <div className="gx-card gx-auth-card">
          {state === 'checking' ? <Loading label="Checking your link" /> : null}

          {state === 'invalid' ? (
            <div className="gx-auth-done">
              <span className="gx-icon-tile gx-icon-tile-warn" aria-hidden="true">
                <Icon name="alert" size={22} />
              </span>
              <h1>This link has expired</h1>
              <p className="gx-muted">
                Reset links work once and only for one hour. Ask for a new one and use the newest email.
              </p>
              <div className="gx-auth-actions">
                <Link to="/forgot-password" className="gx-btn gx-btn-primary">
                  Get a new link
                </Link>
              </div>
            </div>
          ) : null}

          {state === 'ready' ? (
            <>
              <div className="gx-auth-head">
                <h1>Choose a new password</h1>
                <p className="gx-muted">You will be signed out everywhere, then sign in with the new one.</p>
              </div>
              <form className="gx-form" onSubmit={submit} noValidate>
                <PasswordField
                  id="rp-password"
                  label="New password"
                  value={password}
                  onChange={(value) => {
                    setPassword(value);
                    setErrors((current) => ({ ...current, password: undefined }));
                  }}
                  error={errors.password}
                />
                <PasswordField
                  id="rp-confirm"
                  label="Confirm new password"
                  value={confirm}
                  onChange={(value) => {
                    setConfirm(value);
                    setErrors((current) => ({ ...current, confirm: undefined }));
                  }}
                  error={errors.confirm}
                  showChecks={false}
                />
                <button type="submit" className="gx-btn gx-btn-primary gx-btn-lg gx-btn-block" disabled={busy}>
                  {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
                  {busy ? 'Saving' : 'Save new password'}
                </button>
              </form>
            </>
          ) : null}

          {state === 'done' ? (
            <div className="gx-auth-done" role="status">
              <span className="gx-icon-tile" aria-hidden="true">
                <Icon name="checkCircle" size={22} />
              </span>
              <h1>Password changed</h1>
              <p className="gx-muted">Sign in with your new password.</p>
              <div className="gx-auth-actions">
                <button type="button" className="gx-btn gx-btn-primary" onClick={goSignIn}>
                  Sign in
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </main>
    </>
  );
}
