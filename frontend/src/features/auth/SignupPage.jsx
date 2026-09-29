import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import SearchableSelect from '../../components/ui/SearchableSelect';
import { errorMessage, fieldErrors } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useCatalog } from '../../hooks/useCatalog';
import Icon from '../../lib/icons';
import CheckEmailPanel from './CheckEmailPanel';

/**
 * Create an applicant account.
 *
 * This is the front door now. An applicant signs up first, lands in their
 * dashboard, browses courses with their tuition and duration, and applies from
 * there. The application no longer has to be filled in before anyone can see
 * what is on offer.
 *
 * The person chooses their own password here, so it is never emailed back to
 * them: the welcome email only confirms the account exists.
 */

const BLANK = { fullName: '', email: '', phone: '', country: '', password: '' };

export default function SignupPage({ onOpenLogin }) {
  const [form, setForm] = useState(BLANK);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [sentTo, setSentTo] = useState('');
  const { user, isAgent, isSupervisor, registerApplicant } = useAuth();
  const { originNames } = useCatalog();
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = 'Create account · Gabstep';
  }, []);

  if (user) {
    return <Navigate to={isSupervisor ? '/sales-manager' : isAgent ? '/agent' : '/portal'} replace />;
  }

  const update = (patch) => {
    setForm((current) => ({ ...current, ...patch }));
    setErrors((current) => {
      const next = { ...current };
      Object.keys(patch).forEach((key) => delete next[key]);
      return next;
    });
  };

  const checks = [
    { label: '8 or more characters', met: form.password.length >= 8 },
    { label: 'Not only numbers', met: form.password.length > 0 && !/^\d+$/.test(form.password) },
  ];

  const validate = () => {
    const found = {};
    if (form.fullName.trim().split(/\s+/).length < 2) found.fullName = 'Enter your first and last name.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) found.email = 'Enter a valid email address.';
    if (form.phone.replace(/\D/g, '').length < 7) found.phone = 'Enter a phone number we can reach you on.';
    if (!form.country) found.country = 'Choose your country.';
    if (!checks.every((check) => check.met)) found.password = 'Choose a stronger password.';
    setErrors(found);
    return Object.keys(found).length === 0;
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!validate()) return;

    setBusy(true);
    try {
      const created = await registerApplicant({
        full_name: form.fullName.trim(),
        email: form.email.trim().toLowerCase(),
        phone: form.phone.trim(),
        country: form.country,
        password: form.password,
      });
      if (created?.signedIn) {
        navigate('/portal', { replace: true });
        return;
      }
      setSentTo(created?.email || form.email.trim().toLowerCase());
    } catch (error) {
      const fields = fieldErrors(error);
      const mapped = {
        fullName: fields.full_name,
        email: fields.email,
        phone: fields.phone,
        country: fields.country,
        password: fields.password,
      };
      setErrors(Object.fromEntries(Object.entries(mapped).filter(([, value]) => value)));
      toast.error(errorMessage(error, 'Your account could not be created.'));
    } finally {
      setBusy(false);
    }
  };

  const field = (name) => `gx-field ${errors[name] ? 'has-error' : ''}`.trim();
  const errorFor = (name) =>
    errors[name] ? (
      <span className="gx-error" id={`${name}-error`}>
        {String(errors[name])}
      </span>
    ) : null;
  const aria = (name) => ({
    'aria-invalid': Boolean(errors[name]),
    'aria-describedby': errors[name] ? `${name}-error` : undefined,
  });

  return (
    <>
      <SiteHeader />

      <main className="gx-auth">
        <div className="gx-card gx-auth-card">
          {sentTo ? (
            <CheckEmailPanel email={sentTo} onChangeEmail={() => setSentTo('')} />
          ) : (
          <>
          <div className="gx-auth-head">
            <h1>Create your account</h1>
            <p className="gx-muted">Browse courses and tuition, then apply from your dashboard.</p>
          </div>

          <form className="gx-form" onSubmit={submit} noValidate>
            <div className={field('fullName')}>
              <label htmlFor="su-name">Full name</label>
              <input
                id="su-name"
                className="gx-input"
                autoComplete="name"
                value={form.fullName}
                onChange={(event) => update({ fullName: event.target.value })}
                {...aria('fullName')}
              />
              <span className="gx-hint">As it appears on your passport.</span>
              {errorFor('fullName')}
            </div>

            <div className={field('email')}>
              <label htmlFor="su-email">Email address</label>
              <input
                id="su-email"
                type="email"
                className="gx-input"
                autoComplete="email"
                inputMode="email"
                value={form.email}
                onChange={(event) => update({ email: event.target.value })}
                {...aria('email')}
              />
              {errorFor('email')}
            </div>

            <div className="gx-form-row">
              <div className={field('phone')}>
                <label htmlFor="su-phone">Phone number</label>
                <input
                  id="su-phone"
                  type="tel"
                  className="gx-input"
                  autoComplete="tel"
                  inputMode="tel"
                  value={form.phone}
                  onChange={(event) => update({ phone: event.target.value })}
                  {...aria('phone')}
                />
                {errorFor('phone')}
              </div>

              <div className={field('country')}>
                <span className="gx-label" id="su-country-label">
                  Country
                </span>
                <SearchableSelect
                  options={originNames}
                  value={form.country}
                  onChange={(value) => update({ country: value })}
                  labelledBy="su-country-label"
                />
                {errorFor('country')}
              </div>
            </div>

            <div className={field('password')}>
              <label htmlFor="su-password">Password</label>
              <div className="gx-password-wrap">
                <input
                  id="su-password"
                  type={showPassword ? 'text' : 'password'}
                  className="gx-input"
                  autoComplete="new-password"
                  value={form.password}
                  onChange={(event) => update({ password: event.target.value })}
                  {...aria('password')}
                />
                <button
                  type="button"
                  className="gx-btn gx-btn-ghost gx-btn-sm gx-password-toggle"
                  onClick={() => setShowPassword((shown) => !shown)}
                  aria-pressed={showPassword}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              <ul className="gx-checks" aria-label="Password requirements">
                {checks.map((check) => (
                  <li key={check.label} className={check.met ? 'is-met' : ''}>
                    <Icon name={check.met ? 'checkCircle' : 'clock'} size={14} strokeWidth={2} />
                    {check.label}
                  </li>
                ))}
              </ul>
              {errorFor('password')}
            </div>

            <button type="submit" className="gx-btn gx-btn-primary gx-btn-lg gx-btn-block" disabled={busy}>
              {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
              {busy ? 'Creating account' : 'Create account'}
            </button>
          </form>

          <p className="gx-auth-foot">
            Already have an account?{' '}
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
