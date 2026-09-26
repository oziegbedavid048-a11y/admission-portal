import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Icon from '../../lib/icons';
import { errorMessage, fieldErrors } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

const BLANK = {
  full_name: '',
  email: '',
  phone: '',
  password: '',
  agency_name: '',
  country: 'Nigeria',
  agent_code: '',
  bank_name: '',
  account_number: '',
  account_name: '',
};

/**
 * Registration for a partner agency. The payout account is collected up front
 * because commission is paid to it, and there is no second chance to ask before
 * the first withdrawal.
 */
export default function AgentRegisterPage() {
  const [form, setForm] = useState(BLANK);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const { registerAgent } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const set = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const validate = () => {
    const found = {};
    if (!form.full_name.trim()) found.full_name = 'Enter your full name.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) found.email = 'Enter a valid email address.';
    if (!form.phone.trim()) found.phone = 'Enter a phone number.';
    if (form.password.length < 8) found.password = 'Use at least 8 characters.';
    if (!form.bank_name.trim()) found.bank_name = 'Enter your bank.';
    if (!/^\d{10}$/.test(form.account_number)) found.account_number = 'Account number should be 10 digits.';
    if (!form.account_name.trim()) found.account_name = 'Enter the name on the account.';
    if (form.agent_code.trim() && form.agent_code.trim().length < 4)
      found.agent_code = 'That code looks too short. Check it with your Sales Manager.';
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
      await registerAgent({
        ...form,
        agent_code: form.agent_code.trim().toUpperCase(),
      });
      toast.success('Your partner account is ready.');
      navigate('/agent');
    } catch (error) {
      setErrors(fieldErrors(error));
      toast.error(errorMessage(error, 'Could not create your partner account.'));
    } finally {
      setBusy(false);
    }
  };

  const field = (name, label, props = {}, hint = null, className = '') => (
    <div className={`agent-form-group ${className}`.trim()}>
      <label className="agent-form-label" htmlFor={`ag-reg-${name}`}>
        {label}
      </label>
      <input
        id={`ag-reg-${name}`}
        className="agent-form-control"
        value={form[name]}
        onChange={set(name)}
        {...props}
      />
      {hint ? <span className="agent-form-hint">{hint}</span> : null}
      {errors[name] ? <span className="field-error">{errors[name]}</span> : null}
    </div>
  );

  return (
    <section className="agent-section">
      <div className="agent-auth-view">
        <div className="agent-auth-card" style={{ maxWidth: 680 }}>
          <div className="agent-auth-logo">
            <img src="/assets/logo.png" alt="" />
            <div className="auth-brand">
              Gabstep Agents
              <span>Partner network</span>
            </div>
          </div>

          <h2>Become a partner</h2>

          <form onSubmit={submit}>
            <div className="signup-section-header">
              <span className="signup-section-title">Agency & Personal Details</span>
            </div>
            <div className="agent-2col-grid">
              {field('full_name', 'Full legal name *', { autoComplete: 'name', placeholder: 'e.g. Adaeze Nwosu' })}
              {field('email', 'Email address *', {
                type: 'email',
                autoComplete: 'email',
                placeholder: 'you@agency.com',
              })}
              {field('phone', 'Phone / WhatsApp *', {
                type: 'tel',
                autoComplete: 'tel',
                placeholder: '+234 803 100 2200',
              })}
              {field('password', 'Password *', {
                type: 'password',
                autoComplete: 'new-password',
                placeholder: 'At least 8 characters',
              })}
              {field('agency_name', 'Agency name', { placeholder: 'e.g. Global Education Consult' })}
              {field('country', 'Operating country *', { placeholder: 'Nigeria' })}
            </div>

            <div className="signup-section-header">
              <span className="signup-section-title">Sales Manager Referral</span>
            </div>
            <div className="agent-2col-grid">
              {field(
                'agent_code',
                'Referral code',
                {
                  placeholder: 'GSA-XXXXXX',
                  autoCapitalize: 'characters',
                  style: { textTransform: 'uppercase', letterSpacing: '0.06em' },
                },
                null,
                'agent-col-span-2'
              )}
            </div>

            <div className="signup-section-header">
              <span className="signup-section-title">Payout Account</span>
            </div>
            <div className="agent-2col-grid">
              {field('bank_name', 'Bank name *', { placeholder: 'e.g. Access Bank, GTBank' })}
              {field('account_number', 'Account number (10 digits) *', {
                inputMode: 'numeric',
                maxLength: 10,
                placeholder: '0123456789',
              })}
              {field(
                'account_name',
                'Account name *',
                { placeholder: 'Full legal account name as registered with your bank' },
                null,
                'agent-col-span-2'
              )}
            </div>

            <button
              type="submit"
              className="agent-btn agent-btn-primary agent-btn-block"
              style={{ marginTop: 24 }}
              disabled={busy}
            >
              {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
              {busy ? 'Creating your account...' : 'Create partner account'}
            </button>
          </form>

          <div className="auth-switch-link">
            Already registered?{' '}
            <Link className="link-btn" to="/agent/login">
              Sign in
            </Link>
          </div>

          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <Link
              to="/"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.8125rem',
                color: 'var(--slate-500)',
                textDecoration: 'none',
              }}
            >
              <Icon name="arrowLeft" size={15} strokeWidth={2} />
              Back to the student site
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
