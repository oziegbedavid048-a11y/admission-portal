import { useEffect, useRef, useState } from 'react';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { auth, partners } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useAgent } from './AgentContext';


export default function AgentProfile() {
  const { profile, setProfile, reload } = useAgent();
  const { refreshUser, changePassword } = useAuth();
  const toast = useToast();
  const avatarRef = useRef(null);

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    country: '',
    bank_name: '',
    account_number: '',
    account_name: '',
  });
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' });
  const [busy, setBusy] = useState(null);
  const [preview, setPreview] = useState(null);
  const [avatarVersion, setAvatarVersion] = useState(0);

  useEffect(() => {
    if (!profile) return;
    setForm({
      full_name: profile.full_name || '',
      email: profile.email || '',
      phone: profile.phone || '',
      country: profile.country || '',
      bank_name: profile.bank_name || '',
      account_number: profile.account_number || '',
      account_name: profile.account_name || '',
    });
  }, [profile]);

  const save = async (which, payload, message) => {
    setBusy(which);
    try {
      const { data } = await partners.updateProfile(payload);
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
    if (!form.full_name.trim() || !form.email.trim()) {
      toast.warning('Name and email are required.');
      return;
    }
    save(
      'personal',
      { full_name: form.full_name, phone: form.phone, country: form.country },
      'Personal details saved.',
    );
  };

  const savePayout = (event) => {
    event.preventDefault();
    if (!form.bank_name.trim() || !form.account_name.trim()) {
      toast.warning('Fill in every payout field.');
      return;
    }
    if (!/^\d{10}$/.test(form.account_number)) {
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
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.warning('Choose an image file.');
      return;
    }
    if (file.size > 4 * 1024 * 1024) {
      toast.warning('Keep the image under 4MB.');
      return;
    }

    // Show the chosen file straight away. Waiting on the round trip is what
    // made a new photo look as though it had not saved.
    const objectUrl = URL.createObjectURL(file);
    setPreview((current) => {
      if (current) URL.revokeObjectURL(current);
      return objectUrl;
    });

    try {
      await auth.updateAvatar(file);
      await Promise.all([refreshUser(), reload()]);
      // The stored URL can repeat, so a version defeats the browser cache.
      setAvatarVersion((current) => current + 1);
      setPreview(null);
      URL.revokeObjectURL(objectUrl);
      toast.success('Profile picture updated.');
    } catch (error) {
      setPreview(null);
      URL.revokeObjectURL(objectUrl);
      toast.error(errorMessage(error, 'Could not upload that photo.'));
    } finally {
      if (avatarRef.current) avatarRef.current.value = '';
    }
  };

  if (!profile) return null;

  // An object URL must be used exactly as it is; a saved URL gets the version.
  const avatarSrc =
    preview ||
    (profile.avatar
      ? `${profile.avatar}${profile.avatar.includes('?') ? '&' : '?'}v=${avatarVersion}`
      : null);

  const hasMinLength = passwords.next.length >= 8;
  const hasMatch = Boolean(passwords.next && passwords.next === passwords.confirm);


  return (
    <div className="agent-stack">
      {/* ── Executive Identity Hero ── */}
      <section className="ap-hero">
        <div className="ap-hero-cover" />
        <div className="ap-hero-body">
          <div className="ap-hero-left">
            <div className="ap-avatar-wrap">
              <span className="ap-avatar">
                {avatarSrc ? (
                  <img src={avatarSrc} alt={profile.full_name} />
                ) : (
                  <span>{profile.initials}</span>
                )}
              </span>
              <label
                className="ap-avatar-edit-btn"
                htmlFor="agent-avatar-input"
                title="Change photo (PNG or JPG under 4MB)"
              >
                <Icon name="camera" size={15} />
                <span className="sr-only">Upload a profile photo</span>
              </label>
              <input
                type="file"
                id="agent-avatar-input"
                ref={avatarRef}
                accept="image/*"
                className="sr-only"
                onChange={(event) => uploadAvatar(event.target.files?.[0])}
              />
            </div>

            <div className="ap-identity">
              <h1 className="ap-name">{profile.full_name}</h1>
            </div>
          </div>
        </div>
      </section>

      {/* ── 1. Personal Information ── */}
      <form onSubmit={savePersonal}>
          <section className="ap-card">
            <header className="ap-card-head">
              <div className="ap-card-head-left">
                <div className="ap-card-icon-box">
                  <Icon name="user" size={20} />
                </div>
                <div>
                  <h2 className="ap-card-title">Personal information</h2>
                  <p className="ap-card-desc">
                    Your legal identity and primary contact channels.
                  </p>
                </div>
              </div>
              <span className="ap-card-badge">Primary contact</span>
            </header>

            <div className="ap-grid-2col">
              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-name">
                  <span>Full Legal Name *</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="user" size={17} />
                  </span>
                  <input
                    id="ap-name"
                    className="ap-input"
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-email">
                  <span>Email address</span>
                  <span className="ap-label-tag">Verified login</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="lock" size={17} />
                  </span>
                  <input
                    id="ap-email"
                    type="email"
                    className="ap-input"
                    value={form.email}
                    readOnly
                    title="Account email is managed by your administrator"
                  />
                </div>
                <span className="ap-field-hint">Primary email used for portal authentication.</span>
              </div>

              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-phone">
                  <span>Phone / WhatsApp</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="pin" size={17} />
                  </span>
                  <input
                    id="ap-phone"
                    type="tel"
                    className="ap-input"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                </div>
              </div>

              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-country">
                  <span>Operating country</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="globe" size={17} />
                  </span>
                  <input
                    id="ap-country"
                    className="ap-input"
                    value={form.country}
                    onChange={(e) => setForm({ ...form, country: e.target.value })}
                  />
                </div>
              </div>
            </div>

            <footer className="ap-card-footer">
              <span className="ap-footer-note">
                <Icon name="shield" size={16} />
                Details are securely stored and encrypted.
              </span>
              <button
                type="submit"
                className="ap-btn-primary"
                disabled={busy === 'personal'}
              >
                {busy === 'personal' ? <span className="spinner-sm" aria-hidden="true" /> : null}
                <Icon name="save" size={17} strokeWidth={2.2} />
                Save Personal Details
              </button>
            </footer>
          </section>
      </form>

      {/* ── 2. Payout Account ── */}
      <form onSubmit={savePayout}>
          <section className="ap-card">
            <header className="ap-card-head">
              <div className="ap-card-head-left">
                <div className="ap-card-icon-box">
                  <Icon name="wallet" size={20} />
                </div>
                <div>
                  <h2 className="ap-card-title">Payout & settlement account</h2>
                  <p className="ap-card-desc">
                    Commercial bank account where earned commissions and ads loans are wired.
                  </p>
                </div>
              </div>
            </header>

            <div className="ap-grid-2col">
              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-bank">
                  <span>Bank Name *</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="building" size={17} />
                  </span>
                  <input
                    id="ap-bank"
                    className="ap-input"
                    value={form.bank_name}
                    onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-acc-num">
                  <span>Account Number (10 digits) *</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="card" size={17} />
                  </span>
                  <input
                    id="ap-acc-num"
                    className="ap-input mono"
                    inputMode="numeric"
                    maxLength={10}
                    value={form.account_number}
                    onChange={(e) => setForm({ ...form, account_number: e.target.value })}
                    required
                  />
                </div>
                <span className="ap-field-hint">Must be exactly 10 digits NUBAN.</span>
              </div>

              <div className="ap-form-field" style={{ gridColumn: '1 / -1' }}>
                <label className="ap-label" htmlFor="ap-acc-name">
                  <span>Account Beneficiary Name *</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="user" size={17} />
                  </span>
                  <input
                    id="ap-acc-name"
                    className="ap-input"
                    value={form.account_name}
                    onChange={(e) => setForm({ ...form, account_name: e.target.value })}
                    required
                  />
                </div>
                <span className="ap-field-hint">Must exactly match the name registered with your bank.</span>
              </div>
            </div>

            <footer className="ap-card-footer">
              <span className="ap-footer-note">
                <Icon name="lock" size={16} />
                Banking details are encrypted and securely verified.
              </span>
              <button
                type="submit"
                className="ap-btn-primary"
                disabled={busy === 'payout'}
              >
                {busy === 'payout' ? <span className="spinner-sm" aria-hidden="true" /> : null}
                <Icon name="save" size={17} strokeWidth={2.2} />
                Update Payout Account
              </button>
            </footer>
          </section>
      </form>

      {/* ── 3. Security & Access ── */}
      <form onSubmit={savePassword}>
          <section className="ap-card">
            <header className="ap-card-head">
              <div className="ap-card-head-left">
                <div className="ap-card-icon-box">
                  <Icon name="lock" size={20} />
                </div>
                <div>
                  <h2 className="ap-card-title">Security & access</h2>
                  <p className="ap-card-desc">
                    Update your password to keep your partner account and commission wallet secure.
                  </p>
                </div>
              </div>
            </header>

            <div className="ap-grid-2col">
              <div className="ap-form-field" style={{ gridColumn: '1 / -1' }}>
                <label className="ap-label" htmlFor="ap-pass-curr">
                  <span>Current Password *</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="lock" size={17} />
                  </span>
                  <input
                    id="ap-pass-curr"
                    type="password"
                    className="ap-input"
                    autoComplete="current-password"
                    value={passwords.current}
                    onChange={(e) => setPasswords({ ...passwords, current: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-pass-new">
                  <span>New Password *</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="lock" size={17} />
                  </span>
                  <input
                    id="ap-pass-new"
                    type="password"
                    className="ap-input"
                    autoComplete="new-password"
                    value={passwords.next}
                    onChange={(e) => setPasswords({ ...passwords, next: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="ap-form-field">
                <label className="ap-label" htmlFor="ap-pass-conf">
                  <span>Confirm New Password *</span>
                </label>
                <div className="ap-input-wrap">
                  <span className="ap-input-icon">
                    <Icon name="lock" size={17} />
                  </span>
                  <input
                    id="ap-pass-conf"
                    type="password"
                    className="ap-input"
                    autoComplete="new-password"
                    value={passwords.confirm}
                    onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })}
                    required
                  />
                </div>
              </div>
            </div>

            {passwords.next ? (
              <div className="ap-pwd-checks">
                <span className={`ap-pwd-rule ${hasMinLength ? 'valid' : ''}`.trim()}>
                  <Icon name={hasMinLength ? 'checkCircle' : 'alert'} size={15} />
                  At least 8 characters
                </span>
                <span className={`ap-pwd-rule ${hasMatch ? 'valid' : ''}`.trim()}>
                  <Icon name={hasMatch ? 'checkCircle' : 'alert'} size={15} />
                  Passwords match
                </span>
              </div>
            ) : null}

            <footer className="ap-card-footer">
              <span className="ap-footer-note">
                <Icon name="shield" size={16} />
                Requires current password authentication.
              </span>
              <button
                type="submit"
                className="ap-btn-primary"
                disabled={busy === 'password'}
              >
                {busy === 'password' ? <span className="spinner-sm" aria-hidden="true" /> : null}
                <Icon name="lock" size={17} strokeWidth={2.2} />
                Change Password
              </button>
            </footer>
          </section>
      </form>
    </div>
  );
}
