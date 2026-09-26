import { useEffect, useState } from 'react';
import Avatar from '../../components/ui/Avatar';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { auth, supervisors } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import AgentCodeCard from './AgentCodeCard';
import { useSupervisor } from './SupervisorContext';

export default function SupervisorProfile() {
  const { profile, setProfile, reload } = useSupervisor();
  const { refreshUser } = useAuth();
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
  const [busy, setBusy] = useState(null);

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
  }, [profile]);

  const save = async (which, payload, message) => {
    setBusy(which);
    try {
      const { data } = await supervisors.updateProfile(payload);
      setProfile(data);
      await refreshUser();
      toast.success(message);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not save those details.'));
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

  const savePayout = (event) => {
    event.preventDefault();
    if (form.account_number && !/^\d{10}$/.test(form.account_number)) {
      toast.warning('Account number should be 10 digits.');
      return;
    }
    save(
      'payout',
      {
        bank_name: form.bank_name,
        account_number: form.account_number,
        account_name: form.account_name,
      },
      'Payout account updated.',
    );
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
      await auth.changePassword(passwords.current, passwords.next);
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
            {input('region', 'Region or team', { placeholder: 'South West' })}
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
              Payout account
            </h2>
            <span className="agent-card-note">Where your bonus is sent</span>
          </div>
          <div className="agent-2col-grid">
            {input('bank_name', 'Bank name', { placeholder: 'Access Bank' })}
            {input('account_number', 'Account number (10 digits)', {
              inputMode: 'numeric',
              maxLength: 10,
              placeholder: '0123456789',
            })}
            {input('account_name', 'Account name')}
          </div>
          <button
            type="submit"
            className="agent-btn agent-btn-primary"
            style={{ marginTop: 20 }}
            disabled={busy === 'payout'}
          >
            Update payout account
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
    </div>
  );
}
