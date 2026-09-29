import { useEffect, useState } from 'react';
import Avatar from '../../components/ui/Avatar';
import { errorMessage } from '../../api/client';
import { auth } from '../../api/endpoints';
import { compressImageFile } from '../../lib/compress';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useCatalog } from '../../hooks/useCatalog';

export default function ProfilePanel() {
  const { user, setUser, refreshUser, changePassword } = useAuth();
  const { originNames } = useCatalog();
  const toast = useToast();

  const [profile, setProfile] = useState({
    full_name: '',
    email: '',
    phone: '',
    country: '',
  });
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' });
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    if (!user) return;
    setProfile({
      full_name: user.full_name || '',
      email: user.email || '',
      phone: user.phone || '',
      country: user.country || '',
    });
  }, [user]);

  const saveProfile = async (event) => {
    event.preventDefault();
    if (!profile.full_name.trim()) {
      toast.warning('Enter your name.');
      return;
    }

    setSavingProfile(true);
    try {
      const { email: _email, ...editable } = profile;
      const { data } = await auth.updateMe(editable);
      setUser(data);
      toast.success('Your profile is saved.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not save your profile.'));
    } finally {
      setSavingProfile(false);
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    if (passwords.next.length < 8) {
      toast.warning('Use at least 8 characters.');
      return;
    }
    if (passwords.next !== passwords.confirm) {
      toast.warning('The two passwords do not match.');
      return;
    }

    setSavingPassword(true);
    try {
      await changePassword(passwords.current, passwords.next);
      setPasswords({ current: '', next: '', confirm: '' });
      toast.success('Password changed.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not change your password.'));
    } finally {
      setSavingPassword(false);
    }
  };

  const uploadAvatar = async (rawFile) => {
    if (!rawFile.type.startsWith('image/')) {
      toast.warning('Choose an image file.');
      throw new Error('Not an image');
    }
    const file = await compressImageFile(rawFile, { maxWidth: 800, maxHeight: 800, quality: 0.85 });
    if (file.size > 2 * 1024 * 1024) {
      toast.warning('Keep the photo under 2MB.');
      throw new Error('Too large');
    }

    try {
      const { data } = await auth.updateAvatar(file);
      if (data) setUser(data);
      await refreshUser();
      toast.success('Photo updated.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not upload that photo.'));
      throw error;
    }
  };

  return (
    <div className="portal-stack">
      <section className="profile-hero">
        <div className="profile-hero-cover" />
        <div className="profile-hero-body">
          <Avatar
            id="pf-avatar-input"
            src={user?.avatar}
            initials={user?.initials}
            onSelect={uploadAvatar}
          />
          <div className="profile-hero-text">
            <h2>{user?.full_name || 'Your profile'}</h2>
            <p>{[user?.email, user?.country].filter(Boolean).join('  ·  ')}</p>
          </div>
        </div>
      </section>

      <form onSubmit={saveProfile}>
        <section className="card">
          <div className="card-head">
            <h2>Personal information</h2>
          </div>
          <div className="field-grid">
            <div className="field">
              <label htmlFor="pf-name">Full name</label>
              <input
                type="text"
                id="pf-name"
                value={profile.full_name}
                onChange={(event) => setProfile({ ...profile, full_name: event.target.value })}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="pf-email">Email</label>
              <input
                type="email"
                id="pf-email"
                value={profile.email}
                readOnly
                aria-describedby="pf-email-hint"
              />
              <span id="pf-email-hint" className="gx-hint">
                To change your email, contact Support.
              </span>
            </div>
            <div className="field">
              <label htmlFor="pf-phone">Phone</label>
              <input
                type="tel"
                id="pf-phone"
                value={profile.phone}
                onChange={(event) => setProfile({ ...profile, phone: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="pf-country">Country</label>
              <select
                id="pf-country"
                value={profile.country}
                onChange={(event) => setProfile({ ...profile, country: event.target.value })}
              >
                <option value="">Select a country</option>
                {originNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button
            type="submit"
            className="g-btn g-btn-primary"
            style={{ marginTop: 20 }}
            disabled={savingProfile}
          >
            {savingProfile ? 'Saving' : 'Save changes'}
          </button>
        </section>
      </form>

      <form onSubmit={savePassword}>
        <section className="card">
          <div className="card-head">
            <h2>Security</h2>
          </div>
          <p className="card-body-text">Choose a password of at least 8 characters.</p>
          <div className="field-grid" style={{ marginTop: 20 }}>
            <div className="field">
              <label htmlFor="pf-pass-current">Current password</label>
              <input
                type="password"
                id="pf-pass-current"
                autoComplete="current-password"
                value={passwords.current}
                onChange={(event) => setPasswords({ ...passwords, current: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="pf-pass-new">New password</label>
              <input
                type="password"
                id="pf-pass-new"
                autoComplete="new-password"
                value={passwords.next}
                onChange={(event) => setPasswords({ ...passwords, next: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="pf-pass-confirm">Confirm new password</label>
              <input
                type="password"
                id="pf-pass-confirm"
                autoComplete="new-password"
                value={passwords.confirm}
                onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })}
              />
            </div>
          </div>
          <button
            type="submit"
            className="g-btn g-btn-quiet"
            style={{ marginTop: 20 }}
            disabled={savingPassword}
          >
            {savingPassword ? 'Changing' : 'Change password'}
          </button>
        </section>
      </form>
    </div>
  );
}
