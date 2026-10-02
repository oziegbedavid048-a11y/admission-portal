import { useEffect, useState } from 'react';
import Avatar from '../../components/ui/Avatar';
import Modal from '../../components/ui/Modal';
import PasswordInput from '../../components/ui/PasswordInput';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { auth, supervisors } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import AgentCodeCard from './AgentCodeCard';
import { useSupervisor } from './SupervisorContext';

export default function SupervisorProfile() {
  const { profile, setProfile, reload } = useSupervisor();
  const { refreshUser, changePassword } = useAuth();
  const toast = useToast();

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    region: '',
    bank_name: '',
    account_number: '',
    account_name: '',
  });
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' });
  // Changing where payouts go is confirmed with the account password.
  const [payoutPassword, setPayoutPassword] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [busy, setBusy] = useState(null);

  // The form is filled from the profile once, when it first arrives. The
  // dashboard refreshes the profile every few seconds, and refilling the form
  // on each refresh wiped out whatever was being typed, so a change could be
  // saved as the old value without anyone noticing.
  useEffect(() => {
    if (!profile) return;
    setForm({
      full_name: profile.full_name || '',
      email: profile.email || '',
      phone: profile.phone || '',
      region: profile.region || '',
      bank_name: profile.bank_name || '',
      account_number: profile.account_number || '',
      account_name: profile.account_name || '',
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id]);

  const save = async (which, payload, message) => {
    setBusy(which);
    try {
      const { data } = await supervisors.updateProfile(payload);
      setProfile(data);
      await refreshUser();
      toast.success(message);
      return true;
    } catch (error) {
      toast.error(errorMessage(error, 'Could not save those details.'));
      return false;
    } finally {
      setBusy(null);
    }
  };

  const savePersonal = (event) => {
    event.preventDefault();
    if (!form.full_name.trim()) {
      toast.warning('Your name is required.');
      return;
    }
    save(
      'personal',
      { full_name: form.full_name, phone: form.phone, region: form.region },
      'Your details are saved.',
    );
  };

  const payoutChanged =
    Boolean(profile) &&
    (form.bank_name.trim() !== (profile.bank_name || '') ||
      form.account_number !== (profile.account_number || '') ||
      form.account_name.trim() !== (profile.account_name || ''));

  // Update checks the details, then asks for the password before anything
  // is saved.
  const savePayout = (event) => {
    event.preventDefault();
    if (form.account_number && !/^\d{10}$/.test(form.account_number)) {
      toast.warning('Account number should be 10 digits.');
      return;
    }
    if (!payoutChanged) {
      toast.info('Nothing has changed.');
      return;
    }
    setPayoutPassword('');
    setPasswordError('');
    setConfirmOpen(true);
  };

  const closeConfirm = () => {
    if (busy === 'payout') return;
    setConfirmOpen(false);
    setPayoutPassword('');
    setPasswordError('');
  };

  const confirmPayout = async (event) => {
    event?.preventDefault();
    if (!payoutPassword) {
      setPasswordError('Enter your password.');
      return;
    }
    setBusy('payout');
    setPasswordError('');
    try {
      const { data } = await supervisors.updateProfile({
        bank_name: form.bank_name.trim(),
        account_number: form.account_number,
        account_name: form.account_name.trim(),
        current_password: payoutPassword,
      });
      setProfile(data);
      await refreshUser();
      setConfirmOpen(false);
      setPayoutPassword('');
      toast.success('Payment account updated.');
    } catch (error) {
      const fieldError = error?.response?.data?.current_password;
      if (fieldError) {
        setPasswordError(Array.isArray(fieldError) ? fieldError[0] : String(fieldError));
      } else {
        setConfirmOpen(false);
        setPayoutPassword('');
        toast.error(errorMessage(error, 'Could not update your payment account.'));
      }
    } finally {
      setBusy(null);
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    if (passwords.next.length < 8) {
      toast.warning('Use at least 8 characters.');
      return;
    }
    if (passwords.next !== passwords.confirm) {
      toast.warning('The new passwords do not match.');
      return;
    }

    setBusy('password');
    try {
      await changePassword(passwords.current, passwords.next);
      setPasswords({ current: '', next: '', confirm: '' });
      toast.success('Password changed.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not change your password.'));
    } finally {
      setBusy(null);
    }
  };

  const uploadAvatar = async (file) => {
    if (!file.type.startsWith('image/')) {
      toast.warning('Choose an image file.');
      throw new Error('Not an image');
    }
    if (file.size > 4 * 1024 * 1024) {
      toast.warning('Keep the photo under 4MB.');
      throw new Error('Too large');
    }

    try {
      await auth.updateAvatar(file);
      await Promise.all([refreshUser(), reload()]);
      toast.success('Photo updated.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not upload that photo.'));
      throw error;
    }
  };

  if (!profile) return null;

  const input = (name, label, props = {}) => (
    <div className="agent-form-group">
      <label className="agent-form-label" htmlFor={`sv-${name}`}>
        {label}
      </label>
      <input
        id={`sv-${name}`}
        className="agent-form-control"
        value={form[name]}
        onChange={(event) => setForm({ ...form, [name]: event.target.value })}
        {...props}
      />
    </div>
  );

  return (
    <div className="agent-stack">
      <section className="profile-hero">
        <div className="profile-hero-cover" />
        <div className="profile-hero-body">
          <Avatar
            id="sv-avatar-input"
            src={profile?.avatar}
            initials={profile?.initials}
            onSelect={uploadAvatar}
          />
          <div className="profile-hero-text">
            <h2>{profile.full_name}</h2>
            <p>Sales Manager · {profile.agent_count} agents</p>
          </div>
        </div>
      </section>

      <AgentCodeCard code={profile.agent_code} agentCount={profile.agent_count} />

      <form onSubmit={savePersonal}>
        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">
              <span className="agent-icon accent" aria-hidden="true">
                <Icon name="user" size={18} />
              </span>
              Your details
            </h2>
          </div>
          <div className="agent-2col-grid">
            {input('full_name', 'Full name *', { required: true })}
            {input('email', 'Email address', {
              type: 'email',
              readOnly: true,
              style: {
                background: 'var(--g-surface-2)',
                color: 'var(--g-ink-2)',
                cursor: 'not-allowed',
              },
            })}
            {input('phone', 'Phone / WhatsApp', { type: 'tel' })}
            {input('region', 'Region or team', { })}
          </div>
          <button
            type="submit"
            className="agent-btn agent-btn-primary"
            style={{ marginTop: 20 }}
            disabled={busy === 'personal'}
          >
            Save details
          </button>
        </section>
      </form>

      <form onSubmit={savePayout}>
        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">
              <span className="agent-icon accent" aria-hidden="true">
                <Icon name="wallet" size={18} />
              </span>
              Payment account
            </h2>
            <span className="agent-card-note">Where your bonus is sent</span>
          </div>
          <div className="agent-2col-grid">
            {input('bank_name', 'Bank name', { })}
            {input('account_number', 'Account number (10 digits)', {
              inputMode: 'numeric',
              maxLength: 10,
            })}
            {input('account_name', 'Account name')}
          </div>
          <button
            type="submit"
            className="agent-btn agent-btn-primary"
            style={{ marginTop: 20 }}
            disabled={busy === 'payout'}
          >
            Update payment account
          </button>
        </section>
      </form>

      <form onSubmit={savePassword}>
        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">
              <span className="agent-icon accent" aria-hidden="true">
                <Icon name="lock" size={18} />
              </span>
              Security
            </h2>
          </div>
          <div className="agent-2col-grid">
            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="sv-pass-current">
                Current password
              </label>
              <input
                id="sv-pass-current"
                type="password"
                className="agent-form-control"
                autoComplete="current-password"
                value={passwords.current}
                onChange={(event) => setPasswords({ ...passwords, current: event.target.value })}
              />
            </div>
            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="sv-pass-new">
                New password
              </label>
              <input
                id="sv-pass-new"
                type="password"
                className="agent-form-control"
                autoComplete="new-password"
                value={passwords.next}
                onChange={(event) => setPasswords({ ...passwords, next: event.target.value })}
              />
            </div>
            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="sv-pass-confirm">
                Confirm new password
              </label>
              <input
                id="sv-pass-confirm"
                type="password"
                className="agent-form-control"
                autoComplete="new-password"
                value={passwords.confirm}
                onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })}
              />
            </div>
          </div>
          <button
            type="submit"
            className="agent-btn agent-btn-secondary"
            style={{ marginTop: 20 }}
            disabled={busy === 'password'}
          >
            Change password
          </button>
        </section>
      </form>

      <Modal
        open={confirmOpen}
        onClose={closeConfirm}
        dismissable={busy !== 'payout'}
        variant="agent"
        title="Confirm with your password"
        labelledBy="sv-payout-confirm-title"
        footer={
          <>
            <button
              type="button"
              className="agent-btn agent-btn-secondary"
              onClick={closeConfirm}
              disabled={busy === 'payout'}
            >
              Cancel
            </button>
            <button
              type="submit"
              form="sv-payout-confirm-form"
              className="agent-btn agent-btn-primary"
              disabled={busy === 'payout' || !payoutPassword}
            >
              {busy === 'payout' ? <span className="spinner-sm" aria-hidden="true" /> : null}
              {busy === 'payout' ? 'Updating' : 'Update'}
            </button>
          </>
        }
      >
        <form id="sv-payout-confirm-form" onSubmit={confirmPayout} noValidate>
          <dl className="payout-confirm-summary">
            <div>
              <dt>Bank</dt>
              <dd>{form.bank_name.trim()}</dd>
            </div>
            <div>
              <dt>Account number</dt>
              <dd>{form.account_number}</dd>
            </div>
            <div>
              <dt>Account name</dt>
              <dd>{form.account_name.trim()}</dd>
            </div>
          </dl>
          <div className="agent-form-group">
            <label className="agent-form-label" htmlFor="sv-payout-confirm-password">
              Password
            </label>
            <PasswordInput
              id="sv-payout-confirm-password"
              className="agent-form-control"
              autoComplete="current-password"
              autoFocus
              value={payoutPassword}
              onChange={(event) => {
                setPayoutPassword(event.target.value);
                if (passwordError) setPasswordError('');
              }}
              aria-invalid={Boolean(passwordError)}
              aria-describedby={passwordError ? 'sv-payout-confirm-error' : undefined}
            />
            {passwordError ? (
              <span className="field-error" id="sv-payout-confirm-error" role="alert">
                {passwordError}
              </span>
            ) : null}
          </div>
        </form>
      </Modal>
    </div>
  );
}
