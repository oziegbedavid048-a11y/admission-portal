import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import PasswordField, { passwordChecks } from '../../components/ui/PasswordField';
import SearchableSelect from '../../components/ui/SearchableSelect';
import { errorMessage, fieldErrors } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import Icon from '../../lib/icons';
import { ALL_WORLD_COUNTRIES } from '../../lib/countries';
import CheckEmailPanel from './CheckEmailPanel';

/**
 * Registration for a partner agent.
 *
 * One page, four short sections in the order people think about them: who you
 * are, how you will sign in, where commission is paid, and the sales manager
 * who referred you. The payout account is asked for up front because
 * commission is paid into it, and there is no second chance to ask before the
 * first withdrawal.
 */

const BLANK = {
  full_name: '',
  email: '',
  phone: '',
  country: 'Nigeria',
  agency_name: '',
  password: '',
  bank_name: '',
  account_number: '',
  account_name: '',
  agent_code: '',
};

const BENEFITS = [
  { icon: 'wallet', title: 'Commission per student', text: 'Paid when the fee settles, and again when the visa is confirmed.' },
  { icon: 'megaphone', title: 'Ad funding', text: 'Interest-free capital to advertise, repaid from your earnings.' },
  { icon: 'payout', title: 'Withdraw any time', text: 'Straight to your bank account.' },
];

export default function AgentRegisterPage() {
  const [form, setForm] = useState(BLANK);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState('');
  const { user, isAgent, isSupervisor, registerAgent } = useAuth();
  const toast = useToast();

  useEffect(() => {
    document.title = 'Create agent account · Gabstep';
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

  const validate = () => {
    const found = {};
    if (form.full_name.trim().split(/\s+/).length < 2) found.full_name = 'Enter your first and last name.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) found.email = 'Enter a valid email address.';
    if (form.phone.replace(/\D/g, '').length < 7) found.phone = 'Enter a phone number we can reach you on.';
    if (!form.country) found.country = 'Choose the country you work in.';
    if (!passwordChecks(form.password).every((check) => check.met)) found.password = 'Choose a stronger password.';
    if (!form.bank_name.trim()) found.bank_name = 'Enter your bank.';
    if (!/^\d{10}$/.test(form.account_number)) found.account_number = 'Enter the 10-digit account number.';
    if (!form.account_name.trim()) found.account_name = 'Enter the name on the account.';
    if (form.agent_code.trim() && form.agent_code.trim().length < 4)
      found.agent_code = 'That code looks too short. Check it with your sales manager.';
    setErrors(found);
    return Object.keys(found).length === 0;
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!validate()) {
      toast.warning('Check the highlighted fields.');
      return;
    }
    setBusy(true);
    try {
      const created = await registerAgent({
        ...form,
        full_name: form.full_name.trim(),
        email: form.email.trim().toLowerCase(),
        phone: form.phone.trim(),
        agency_name: form.agency_name.trim(),
        bank_name: form.bank_name.trim(),
        account_name: form.account_name.trim(),
        agent_code: form.agent_code.trim().toUpperCase(),
      });
      setSentTo(created?.email || form.email.trim().toLowerCase());
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) {
      setErrors(fieldErrors(error));
      toast.error(errorMessage(error, 'Your agent account could not be created.'));
    } finally {
      setBusy(false);
    }
  };

  const input = (name, label, props = {}, hint = null) => (
    <div className={`gx-field ${errors[name] ? 'has-error' : ''}`.trim()}>
      <label htmlFor={`ar-${name}`}>{label}</label>
      <input
        id={`ar-${name}`}
        className="gx-input"
        value={form[name]}
        onChange={(event) => update({ [name]: event.target.value })}
        aria-invalid={Boolean(errors[name])}
        aria-describedby={errors[name] ? `ar-${name}-error` : hint ? `ar-${name}-hint` : undefined}
        {...props}
      />
      {hint ? (
        <span className="gx-hint" id={`ar-${name}-hint`}>
          {hint}
        </span>
      ) : null}
      {errors[name] ? (
        <span className="gx-error" id={`ar-${name}-error`}>
          {String(errors[name])}
        </span>
      ) : null}
    </div>
  );

  return (
    <>
      <SiteHeader />
      <main className="gx-register">
        <aside className="gx-register-aside" aria-label="Why partner with Gabstep">
          <span className="gx-eyebrow">Gabstep partner network</span>
          <h1>Place students abroad. Earn on every one.</h1>
          <ul className="gx-benefits">
            {BENEFITS.map((item) => (
              <li key={item.title}>
                <span className="gx-icon-tile" aria-hidden="true">
                  <Icon name={item.icon} size={20} />
                </span>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.text}</span>
                </div>
              </li>
            ))}
          </ul>
        </aside>

        <div className="gx-card gx-register-card">
          {sentTo ? (
            <CheckEmailPanel email={sentTo} onChangeEmail={() => setSentTo('')} />
          ) : (
          <>
          <div className="gx-auth-head">
            <h2 className="gx-register-title">Create your agent account</h2>
            <p className="gx-muted">It takes about two minutes.</p>
          </div>

          <form className="gx-form" onSubmit={submit} noValidate>
            <fieldset className="gx-section">
              <legend>
                <span className="gx-section-num">1</span>
                About you
              </legend>
              <div className="gx-form-row">
                {input('full_name', 'Full legal name', { autoComplete: 'name' })}
                {input('email', 'Email address', { type: 'email', autoComplete: 'email', inputMode: 'email' })}
              </div>
              <div className="gx-form-row">
                {input('phone', 'Phone or WhatsApp', { type: 'tel', autoComplete: 'tel', inputMode: 'tel' })}
                <div className={`gx-field ${errors.country ? 'has-error' : ''}`.trim()}>
                  <span className="gx-label" id="ar-country-label">
                    Country you work in
                  </span>
                  <SearchableSelect
                    options={ALL_WORLD_COUNTRIES}
                    value={form.country}
                    onChange={(value) => update({ country: value })}
                    labelledBy="ar-country-label"
                  />
                  {errors.country ? <span className="gx-error">{String(errors.country)}</span> : null}
                </div>
              </div>
              {input('agency_name', 'Agency name (optional)', { autoComplete: 'organization' })}
            </fieldset>

            <fieldset className="gx-section">
              <legend>
                <span className="gx-section-num">2</span>
                Password
              </legend>
              <PasswordField
                id="ar-password"
                label="Choose a password"
                value={form.password}
                onChange={(value) => update({ password: value })}
                error={errors.password}
              />
            </fieldset>

            <fieldset className="gx-section">
              <legend>
                <span className="gx-section-num">3</span>
                Payout account
              </legend>
              <p className="gx-muted gx-small gx-section-note">Your commission is paid into this account.</p>
              <div className="gx-form-row">
                {input('bank_name', 'Bank name')}
                {input('account_number', 'Account number', { inputMode: 'numeric', maxLength: 10, autoComplete: 'off' }, '10 digits')}
              </div>
              {input('account_name', 'Account name', { autoComplete: 'off' }, 'Exactly as your bank shows it.')}
            </fieldset>

            <fieldset className="gx-section">
              <legend>
                <span className="gx-section-num">4</span>
                Referral code (optional)
              </legend>
              {input(
                'agent_code',
                'Sales manager code',
                { autoCapitalize: 'characters', className: 'gx-input gx-input-code' },
                'If a sales manager invited you, enter their code.',
              )}
            </fieldset>

            <button type="submit" className="gx-btn gx-btn-primary gx-btn-lg gx-btn-block" disabled={busy}>
              {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
              {busy ? 'Creating your account' : 'Create agent account'}
            </button>
          </form>

          <p className="gx-auth-foot">
            Have an account?{' '}
            <Link to="/agent/login" className="gx-link">
              Login here
            </Link>
          </p>
          </>
          )}
        </div>
      </main>
    </>
  );
}
