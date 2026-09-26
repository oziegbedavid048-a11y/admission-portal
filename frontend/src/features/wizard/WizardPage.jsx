import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Dropzone from '../../components/ui/Dropzone';
import SearchableSelect from '../../components/ui/SearchableSelect';
import Icon from '../../lib/icons';
import { formatMoney } from '../../lib/format';
import { applications, catalog, payments } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useCatalog, useInstitutions } from '../../hooks/useCatalog';
import { ALL_WORLD_COUNTRIES } from '../../lib/countries';
import PaymentGatewayModal from './PaymentGatewayModal';
import ProgramPicker from './ProgramPicker';
import ProvisioningModal from './ProvisioningModal';

const TOTAL_STEPS = 5;
const DRAFT_KEY = 'gabstep_wizard_draft';

const QUALIFICATIONS = [
  'SSCE / High School',
  'OND',
  'HND',
  "Bachelor's Degree",
  "Master's Degree",
];

const BLANK = {
  fullName: '',
  email: '',
  phone: '',
  originCountry: '',
  destinationCountry: 'Canada',
  previousSchools: '',
  qualification: '',
  yearGraduated: '',
  gradeGpa: '',
  institution: '',
  level: null,
  programs: [],
  is_custom_course: false,
  custom_course: '',
};

/** A password a person can read out over the phone without ambiguity. */
function generatePassword() {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  return `Gabstep${Array.from(bytes, (byte) => alphabet[byte % alphabet.length]).join('')}`;
}

export default function WizardPage({ onOpenLogin }) {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(BLANK);
  const [files, setFiles] = useState({ passport: null, academic: null, cv: null });
  const [errors, setErrors] = useState({});
  const [quote, setQuote] = useState(null);
  const [gatewayOpen, setGatewayOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [provisioned, setProvisioned] = useState(null);
  const shellRef = useRef(null);

  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const { user, isAuthenticated, registerApplicant } = useAuth();
  const { originNames, destinations } = useCatalog();
  const { institutions, loading: institutionsLoading } = useInstitutions(
    form.destinationCountry,
  );

  const update = useCallback((patch) => {
    setForm((current) => ({ ...current, ...patch }));
    setErrors((current) => {
      const next = { ...current };
      Object.keys(patch).forEach((key) => delete next[key]);
      return next;
    });
  }, []);

  // A destination chosen on the landing page arrives as route state.
  useEffect(() => {
    if (location.state?.destination) {
      update({ destinationCountry: location.state.destination, institution: '', programs: [] });
    }
  }, [location.state, update]);

  // Prefill from the signed-in account, so nobody retypes what we know.
  useEffect(() => {
    if (!user) return;
    setForm((current) => ({
      ...current,
      fullName: current.fullName || user.full_name || '',
      email: current.email || user.email || '',
      phone: current.phone || user.phone || '',
      originCountry: current.originCountry || user.country || '',
    }));
  }, [user]);

  // Restore a saved draft. It lives in this browser rather than on the server
  // because the wizard can be filled in before there is an account to hang it
  // on; the files themselves are never part of it.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (!draft?.form) return;
      setForm((current) => ({ ...current, ...draft.form }));
      setStep(Math.min(TOTAL_STEPS, Math.max(1, draft.step || 1)));
      toast.info('Draft restored from your last visit.');
    } catch {
      localStorage.removeItem(DRAFT_KEY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const safeInstitutions = Array.isArray(institutions) ? institutions : [];
  const institution = useMemo(
    () => safeInstitutions.find((item) => item.slug === form.institution) || null,
    [safeInstitutions, form.institution],
  );

  const isCustomCourse = Boolean(
    form.is_custom_course || (safeInstitutions.length === 0 && !institutionsLoading)
  );

  const feeWaived = isCustomCourse || (institution ? institution.is_fee_free : false);

  // Refresh the fee whenever the applicant's currency could have changed.
  useEffect(() => {
    if (step !== 5 || !form.originCountry) return;
    let cancelled = false;
    catalog
      .feeQuote(form.originCountry)
      .then(({ data }) => {
        if (cancelled) return;
        const amount = feeWaived ? 0 : data.amount;
        const processing = feeWaived ? 0 : data.processing_fee;
        setQuote({
          ...data,
          amount,
          processing_fee: processing,
          total: amount + processing,
          total_charged_ngn: feeWaived
            ? 0
            : Number(data.amount_ngn) + Number(data.processing_fee_ngn || 0),
          waived: feeWaived,
        });
      })
      .catch(() => {
        if (!cancelled) setQuote(null);
      });
    return () => {
      cancelled = true;
    };
  }, [step, form.originCountry, feeWaived]);

  const validate = (which) => {
    const found = {};

    if (which === 1) {
      if (!form.fullName.trim()) found.fullName = 'Enter your full legal name.';
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
        found.email = 'Enter a valid email address.';
      if (!form.phone.trim()) found.phone = 'Enter a phone number we can reach you on.';
      if (!form.originCountry) found.originCountry = 'Choose your country of origin.';
      if (!form.destinationCountry) found.destinationCountry = 'Choose a destination.';
    }

    if (which === 2) {
      if (!form.previousSchools.trim())
        found.previousSchools = 'List the institutions you attended.';
      if (!form.qualification) found.qualification = 'Choose your highest qualification.';
      const year = Number(form.yearGraduated);
      if (!year || year < 1960 || year > 2035)
        found.yearGraduated = 'Enter the year you graduated.';
      if (!form.gradeGpa.trim()) found.gradeGpa = 'Enter your grade or GPA.';
    }

    if (which === 3) {
      if (isCustomCourse) {
        if (!form.custom_course?.trim()) {
          toast.warning('Please enter the course or degree programme you wish to study.');
          return false;
        }
      } else {
        if (!form.institution) {
          toast.warning('Choose one partner institution, or enter your course manually.');
          return false;
        }
        if (!form.programs.length) {
          toast.warning('Choose at least one course.');
          return false;
        }
      }
    }

    if (which === 4) {
      const missing = [
        !files.passport && 'your passport data page',
        !files.academic && 'your academic documents',
        !files.cv && 'your CV',
      ].filter(Boolean);
      if (missing.length) {
        toast.warning(`Still to upload: ${missing.join(', ')}.`);
        return false;
      }
    }

    setErrors(found);
    if (Object.keys(found).length) {
      toast.warning('Check the highlighted fields.');
      return false;
    }
    return true;
  };

  const goTo = (target) => {
    if (target < 1 || target > TOTAL_STEPS) return;
    if (target > step) {
      for (let current = step; current < target; current += 1) {
        if (!validate(current)) return;
      }
    }
    setStep(target);
    window.setTimeout(
      () => shellRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      20,
    );
  };

  const uploadDocuments = async (reference) => {
    const queue = [
      files.passport && { file: files.passport, kind: 'passport', name: 'International passport data page' },
      files.academic && { file: files.academic, kind: 'academic', name: 'Academic documents & transcripts' },
      files.cv && { file: files.cv, kind: 'cv', name: 'Curriculum vitae' },
    ].filter(Boolean);

    // Uploads are not fatal to the submission: the file is on record either
    // way, and a failed upload is something the applicant can redo from
    // Details rather than a reason to lose the application.
    const results = await Promise.allSettled(
      queue.map((item) => applications.uploadDocument(reference, item)),
    );
    const failed = results.filter((result) => result.status === 'rejected').length;
    if (failed) {
      toast.warning(
        `${failed} document${failed === 1 ? '' : 's'} did not upload. Add them again from Details.`,
      );
    }
  };

  const submit = async () => {
    setSubmitting(true);
    let generatedPassword = null;

    try {
      // Anonymous applicants get an account built from what they just typed.
      if (!isAuthenticated) {
        generatedPassword = generatePassword();
        try {
          await registerApplicant({
            email: form.email.trim(),
            full_name: form.fullName.trim(),
            phone: form.phone.trim(),
            country: form.originCountry,
            password: generatedPassword,
          });
        } catch (error) {
          const message = errorMessage(error, 'Could not create your account.');
          toast.error(
            message.includes('already exists')
              ? 'You already have an account with this email. Sign in and your application will continue there.'
              : message,
          );
          if (message.includes('already exists')) onOpenLogin?.();
          setGatewayOpen(false);
          return;
        }
      }

      const { data: application } = await applications.create({
        full_name: form.fullName.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        origin_country: form.originCountry,
        destination_country: form.destinationCountry,
        previous_schools: form.previousSchools.trim(),
        qualification: form.qualification,
        year_graduated: Number(form.yearGraduated),
        grade_gpa: form.gradeGpa.trim(),
        institution: isCustomCourse ? '' : form.institution,
        program_ids: isCustomCourse ? [] : form.programs.map((program) => program.id),
        is_custom_course: isCustomCourse,
        custom_course_name: isCustomCourse ? form.custom_course.trim() : '',
      });

      await uploadDocuments(application.reference);
      const { data: settlement } = await payments.checkout(application.reference);

      localStorage.removeItem(DRAFT_KEY);
      setGatewayOpen(false);

      // A configured provider hands back somewhere to go and pay. Leaving for it
      // is the last step, so the draft is already cleared and the account made.
      if (!isCustomCourse && settlement?.authorization_url) {
        window.location.assign(settlement.authorization_url);
        return;
      }

      setProvisioned({
        reference: application.reference,
        email: application.email,
        fullName: application.full_name,
        accountCreated: Boolean(generatedPassword),
        feeOutstanding: !isCustomCourse && !settlement?.waived,
        transferAccount: settlement?.transfer_account || null,
        isCustomCourse: isCustomCourse,
        customCourseName: isCustomCourse ? form.custom_course.trim() : '',
        destinationCountry: form.destinationCountry,
        generatedPassword: generatedPassword,
      });
    } catch (error) {
      toast.error(errorMessage(error, 'Could not submit your application.'));
      setGatewayOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  const onSubmitClick = () => {
    if (!validate(4)) return;
    if (isCustomCourse || feeWaived) {
      submit();
      return;
    }
    setGatewayOpen(true);
  };

  const fieldProps = (name) => ({
    id: name,
    value: form[name],
    onChange: (event) => update({ [name]: event.target.value }),
    className: 'form-control',
  });

  const groupClass = (name) => `form-group ${errors[name] ? 'has-error' : ''}`.trim();

  const errorNode = (name) =>
    errors[name] ? (
      <span className="form-error" style={{ display: 'block' }}>
        {errors[name]}
      </span>
    ) : null;

  return (
    <>
      <SiteHeader onOpenLogin={onOpenLogin} />

      <section className="wizard-section">
        <div className="container wizard-shell" ref={shellRef}>
          {/* ── Step 1 ── */}
          {step === 1 ? (
            <div className="wizard-card">
              <div className="step-header">
                <h3>Personal details</h3>
                <p>Exactly as your international passport prints them.</p>
              </div>

              <div className="form-grid-2">
                <div className={groupClass('fullName')}>
                  <label className="form-label" htmlFor="fullName">
                    Full legal name <span className="req">*</span>
                  </label>
                  <input type="text" autoComplete="name" placeholder="Chioma Stephanie Adebayo" {...fieldProps('fullName')} />
                  {errorNode('fullName')}
                </div>

                <div className={groupClass('email')}>
                  <label className="form-label" htmlFor="email">
                    Email address <span className="req">*</span>
                  </label>
                  <input type="email" autoComplete="email" placeholder="you@example.com" {...fieldProps('email')} />
                  {errorNode('email')}
                </div>
              </div>

              <div className="form-grid-2">
                <div className={groupClass('phone')}>
                  <label className="form-label" htmlFor="phone">
                    Phone number <span className="req">*</span>
                  </label>
                  <input type="tel" autoComplete="tel" placeholder="+234 801 234 5678" {...fieldProps('phone')} />
                  {errorNode('phone')}
                </div>

                <div className={groupClass('originCountry')}>
                  <label className="form-label" id="origin-label">
                    Country of origin <span className="req">*</span>
                  </label>
                  <SearchableSelect
                    options={originNames}
                    value={form.originCountry}
                    onChange={(value) => update({ originCountry: value })}
                    placeholder="Select your country"
                    labelledBy="origin-label"
                  />
                  {errorNode('originCountry')}
                </div>
              </div>

              <div className={groupClass('destinationCountry')} style={{ marginTop: 12 }}>
                <label className="form-label" id="destination-label">
                  Destination country <span className="req">*</span>
                </label>
                <SearchableSelect
                  options={ALL_WORLD_COUNTRIES}
                  value={form.destinationCountry}
                  onChange={(value) =>
                    update({
                      destinationCountry: value,
                      institution: '',
                      level: null,
                      programs: [],
                      is_custom_course: false,
                      custom_course: '',
                    })
                  }
                  placeholder="Search destination country in the world..."
                  labelledBy="destination-label"
                />
                {errorNode('destinationCountry')}
              </div>

              <div className="wizard-footer">
                <button type="button" className="btn btn-ghost" onClick={() => navigate('/')}>
                  <Icon name="arrowLeft" size={16} strokeWidth={2} />
                  Back to the site
                </button>
                <button type="button" className="btn btn-primary" onClick={() => goTo(2)}>
                  Continue
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </button>
              </div>
            </div>
          ) : null}

          {/* ── Step 2 ── */}
          {step === 2 ? (
            <div className="wizard-card">
              <div className="step-header">
                <h3>Academic background</h3>
                <p>Where you studied and what you achieved.</p>
              </div>

              <div className={groupClass('previousSchools')}>
                <label className="form-label" htmlFor="previousSchools">
                  Institutions attended <span className="req">*</span>
                </label>
                <input type="text" placeholder="University of Lagos" {...fieldProps('previousSchools')} />
                {errorNode('previousSchools')}
              </div>

              <div className="form-grid-2">
                <div className={groupClass('qualification')}>
                  <label className="form-label" htmlFor="qualification">
                    Highest qualification <span className="req">*</span>
                  </label>
                  <select {...fieldProps('qualification')}>
                    <option value="">Select a qualification</option>
                    {QUALIFICATIONS.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  {errorNode('qualification')}
                </div>

                <div className={groupClass('yearGraduated')}>
                  <label className="form-label" htmlFor="yearGraduated">
                    Year of graduation <span className="req">*</span>
                  </label>
                  <input type="number" min="1960" max="2035" placeholder="2023" {...fieldProps('yearGraduated')} />
                  {errorNode('yearGraduated')}
                </div>
              </div>

              <div className={groupClass('gradeGpa')}>
                <label className="form-label" htmlFor="gradeGpa">
                  Grade or GPA <span className="req">*</span>
                </label>
                <input type="text" placeholder="Second Class Upper, or 3.8/4.0" {...fieldProps('gradeGpa')} />
                {errorNode('gradeGpa')}
              </div>

              <div className="wizard-footer">
                <button type="button" className="btn btn-secondary" onClick={() => goTo(1)}>
                  <Icon name="arrowLeft" size={16} strokeWidth={2} />
                  Back
                </button>
                <button type="button" className="btn btn-primary" onClick={() => goTo(3)}>
                  Continue
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </button>
              </div>
            </div>
          ) : null}

          {/* ── Step 3 ── */}
          {step === 3 ? (
            <div className="wizard-card">
              <div className="step-header">
                <h3>Institution and courses</h3>
                <p>One institution, up to two courses.</p>
              </div>

              <div className="schools-container">
                <ProgramPicker
                  institutions={institutions}
                  loading={institutionsLoading}
                  countryName={form.destinationCountry}
                  selection={{
                    institution: form.institution,
                    level: form.level,
                    programs: form.programs,
                    is_custom_course: form.is_custom_course,
                    custom_course: form.custom_course,
                  }}
                  onChange={(next) => update(next)}
                  onNotify={(message, type) => toast.toast(message, type)}
                />
              </div>

              <div className="wizard-footer">
                <button type="button" className="btn btn-secondary" onClick={() => goTo(2)}>
                  <Icon name="arrowLeft" size={16} strokeWidth={2} />
                  Back
                </button>
                <button type="button" className="btn btn-primary" onClick={() => goTo(4)}>
                  Continue
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </button>
              </div>
            </div>
          ) : null}

          {/* ── Step 4 ── */}
          {step === 4 ? (
            <div className="wizard-card">
              <div className="step-header">
                <h3>Your documents</h3>
                <p>Clear, full-page scans. PDF or photo.</p>
              </div>

              {destinations.find((item) => item.name === form.destinationCountry)?.is_european ? (
                <div className="callout callout-warning">
                  <Icon name="alert" size={20} className="callout-icon" strokeWidth={2} />
                  <div className="callout-content">
                    <strong>European institutions prefer a Europass CV.</strong>{' '}
                    <a
                      href="https://europa.eu/europass/en/create-europass-cv"
                      target="_blank"
                      rel="noreferrer"
                      style={{ fontWeight: 700, textDecoration: 'underline' }}
                    >
                      Create one
                    </a>
                  </div>
                </div>
              ) : null}

              <div className="dropzone-container">
                <Dropzone
                  icon="passport"
                  title="International passport data page"
                  hint="PDF, JPG or PNG · up to 5MB"
                  accept=".pdf,.jpg,.jpeg,.png"
                  maxMb={5}
                  file={files.passport}
                  onSelect={(file) => setFiles((current) => ({ ...current, passport: file }))}
                  onReject={(message) => toast.warning(message)}
                />
                <Dropzone
                  icon="document"
                  title="Academic documents"
                  hint="Transcripts and certificates · PDF up to 10MB"
                  accept=".pdf"
                  maxMb={10}
                  file={files.academic}
                  onSelect={(file) => setFiles((current) => ({ ...current, academic: file }))}
                  onReject={(message) => toast.warning(message)}
                />
                <Dropzone
                  icon="resume"
                  title="Curriculum vitae"
                  hint="PDF up to 5MB"
                  accept=".pdf"
                  maxMb={5}
                  file={files.cv}
                  onSelect={(file) => setFiles((current) => ({ ...current, cv: file }))}
                  onReject={(message) => toast.warning(message)}
                />
              </div>

              <div className="wizard-footer">
                <button type="button" className="btn btn-secondary" onClick={() => goTo(3)}>
                  <Icon name="arrowLeft" size={16} strokeWidth={2} />
                  Back
                </button>
                <button type="button" className="btn btn-primary" onClick={() => goTo(5)}>
                  Continue
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </button>
              </div>
            </div>
          ) : null}

          {/* ── Step 5 ── */}
          {step === 5 ? (
            <div className="wizard-card">
              <div className="step-header">
                <h3>{isCustomCourse ? 'Review your application' : 'Review and pay'}</h3>
                <p>
                  {isCustomCourse
                    ? 'No upfront fee required. Complete your registration to receive your student portal login.'
                    : 'Nothing is submitted until this is settled.'}
                </p>
              </div>

              {isCustomCourse ? (
                <>
                  <div className="summary-invoice" style={{ borderLeft: '4px solid var(--brand-600, #2563eb)' }}>
                    <div className="invoice-header">
                      Custom Course Application · {form.destinationCountry}
                    </div>
                    <div className="invoice-row">
                      <span>Destination country</span>
                      <span style={{ fontWeight: 600 }}>{form.destinationCountry}</span>
                    </div>
                    <div className="invoice-row">
                      <span>Desired course / programme</span>
                      <span style={{ fontWeight: 700, color: 'var(--brand-700, #1d4ed8)' }}>
                        {form.custom_course || 'Custom Course'}
                      </span>
                    </div>
                    <div className="invoice-row">
                      <span>Applicant</span>
                      <span style={{ fontWeight: 600 }}>{form.fullName}</span>
                    </div>
                    <div className="invoice-row total">
                      <span>Application fee</span>
                      <span style={{ color: '#16a34a', fontWeight: 800 }}>
                        FREE (Direct Admissions Review)
                      </span>
                    </div>
                  </div>

                  <div className="callout callout-success">
                    <Icon name="checkCircle" size={20} className="callout-icon" strokeWidth={2} />
                    <div className="callout-content">
                      <strong>Zero application fee required today!</strong> Because you specified your own course, no payment is required. Once you submit, our global admissions desk will review your details and contact you directly to match you with universities.
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="summary-invoice">
                    <div className="invoice-header">
                      {institution ? institution.name : 'Your institution'}
                    </div>
                    <div className="invoice-row">
                      <span>Application fee</span>
                      <span style={{ fontWeight: 600 }}>
                        {quote ? formatMoney(quote.amount, quote.currency) : 'Calculating'}
                      </span>
                    </div>
                    <div className="invoice-row">
                      <span>Gateway processing</span>
                      <span style={{ fontWeight: 600 }}>
                        {quote ? formatMoney(quote.processing_fee, quote.currency) : 'Calculating'}
                      </span>
                    </div>
                    <div className="invoice-row total">
                      <span>Total</span>
                      <span style={{ color: 'var(--brand-700)' }}>
                        {quote ? formatMoney(quote.total, quote.currency) : 'Calculating'}
                      </span>
                    </div>
                    {quote && !quote.waived && quote.currency !== 'NGN' ? (
                      <p className="quote-fx-note">
                        Debited as ₦
                        {Number(
                          quote.total_charged_ngn ??
                            Number(quote.amount_ngn) + Number(quote.processing_fee_ngn || 0),
                        ).toLocaleString('en-NG')}{' '}
                        at an indicative rate of {quote.rate} per {quote.currency}.
                      </p>
                    ) : null}
                  </div>

                  {feeWaived ? (
                    <div className="callout callout-success">
                      <Icon name="checkCircle" size={20} className="callout-icon" strokeWidth={2} />
                      <div className="callout-content">
                        <strong>Fee waived.</strong> {institution?.name} is a fee-free partner,
                        so your file goes straight through.
                      </div>
                    </div>
                  ) : (
                    <div className="callout callout-info">
                      <Icon name="lock" size={20} className="callout-icon" strokeWidth={2} />
                      <div className="callout-content">
                        Your file is submitted first. How the fee is collected is shown
                        on the next screen, and your card details never reach us.
                      </div>
                    </div>
                  )}
                </>
              )}

              <div className="wizard-footer">
                <button type="button" className="btn btn-secondary" onClick={() => goTo(4)}>
                  <Icon name="arrowLeft" size={16} strokeWidth={2} />
                  Back
                </button>
                <button
                  type="button"
                  className="btn btn-accent btn-lg"
                  onClick={onSubmitClick}
                  disabled={submitting}
                >
                  {submitting ? <span className="spinner-sm" aria-hidden="true" /> : null}
                  {isCustomCourse
                    ? 'Complete registration & receive login'
                    : feeWaived
                      ? 'Submit application'
                      : `Submit and pay ${quote ? formatMoney(quote.total, quote.currency) : ''}`}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <PaymentGatewayModal
        open={gatewayOpen}
        onClose={() => setGatewayOpen(false)}
        onConfirm={submit}
        email={form.email}
        quote={quote}
        busy={submitting}
      />

      <ProvisioningModal
        open={Boolean(provisioned)}
        details={provisioned}
        onContinue={() => {
          setProvisioned(null);
          navigate('/portal');
        }}
      />
    </>
  );
}
