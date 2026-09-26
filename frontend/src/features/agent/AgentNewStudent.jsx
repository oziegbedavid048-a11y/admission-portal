import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Modal from '../../components/ui/Modal';
import SearchableSelect from '../../components/ui/SearchableSelect';
import Icon from '../../lib/icons';
import { formatMoney, formatNaira } from '../../lib/format';
import { errorMessage } from '../../api/client';
import { applications, catalog, partners, payments } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import { useCatalog, useInstitutions } from '../../hooks/useCatalog';
import { ALL_WORLD_COUNTRIES } from '../../lib/countries';
import ProgramPicker from '../wizard/ProgramPicker';
import { useAgent } from './AgentContext';

const TOTAL_STEPS = 5;

const QUALIFICATIONS = [
  "Bachelor's Degree",
  "Master's Degree",
  'HND',
  'OND',
  'SSCE / High School',
];

const BLANK = {
  fullName: '',
  email: '',
  phone: '',
  originCountry: 'Nigeria',
  destinationCountry: 'Canada',
  previousSchools: '',
  qualification: "Bachelor's Degree",
  yearGraduated: '',
  gradeGpa: '',
  institution: '',
  level: null,
  programs: [],
  is_custom_course: false,
  custom_course: '',
  notes: '',
};

/**
 * The same five-step application the student would fill in, filed by the agent
 * on their behalf. On submit the student also gets their own portal account,
 * and the one-time password is handed back so the agent can pass it on.
 */
export default function AgentNewStudent() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(BLANK);
  const [files, setFiles] = useState({ passport: null, academic: null, cv: null });
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null);
  const [quote, setQuote] = useState(null);
  const [gateway, setGateway] = useState('Paystack');
  const shellRef = useRef(null);

  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const { profile, setWallet } = useAgent();
  const { originNames, destinations } = useCatalog();
  const { institutions, loading: institutionsLoading } = useInstitutions(form.destinationCountry);

  const safeInstitutions = Array.isArray(institutions) ? institutions : [];
  const institution = useMemo(
    () => safeInstitutions.find((item) => item.slug === form.institution) || null,
    [safeInstitutions, form.institution],
  );
  const isCustomCourse = Boolean(
    form.is_custom_course || (safeInstitutions.length === 0 && !institutionsLoading)
  );

  const update = (patch) => setForm((current) => ({ ...current, ...patch }));

  useEffect(() => {
    const picked = location.state;
    if (!picked?.destination) return;
    setForm((current) => ({
      ...current,
      destinationCountry: picked.destination,
      institution: picked.institution || '',
      level: null,
      programs: [],
    }));
  }, [location.state]);

  // The fee is quoted in the student's own currency, so it can be shown on the
  // review step before anything is created.
  useEffect(() => {
    if (step !== 5 || !form.originCountry) return;
    let cancelled = false;
    catalog
      .feeQuote(form.originCountry)
      .then(({ data }) => {
        if (cancelled) return;
        const waived = institution ? institution.is_fee_free : false;
        const amount = waived ? 0 : data.amount;
        const processing = waived ? 0 : data.processing_fee;
        setQuote({ ...data, amount, processing_fee: processing, total: amount + processing, waived });
      })
      .catch(() => {
        if (!cancelled) setQuote(null);
      });
    return () => {
      cancelled = true;
    };
  }, [step, form.originCountry, institution]);

  const validate = (which) => {
    if (which === 1) {
      if (!form.fullName.trim()) return toast.warning('Enter the student’s full name.') || false;
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
        return toast.warning('Enter a valid student email address.') || false;
      if (!form.phone.trim()) return toast.warning('Enter a phone number.') || false;
    }
    if (which === 2) {
      if (!form.previousSchools.trim())
        return toast.warning('List the institutions they attended.') || false;
      const year = Number(form.yearGraduated);
      if (!year || year < 1960 || year > 2035)
        return toast.warning('Enter a valid graduation year.') || false;
      if (!form.gradeGpa.trim()) return toast.warning('Enter their grade or GPA.') || false;
    }
    if (which === 3) {
      if (isCustomCourse) {
        if (!form.custom_course?.trim()) {
          return toast.warning('Enter the student’s desired course or programme.') || false;
        }
      } else {
        if (!form.institution) return toast.warning('Choose a partner institution or type course manually.') || false;
        if (!form.programs.length) return toast.warning('Choose at least one course.') || false;
      }
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

  const submit = async () => {
    setBusy(true);
    try {
      const { data } = await partners.createStudent({
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
        notes: form.notes.trim(),
      });

      const queue = [
        files.passport && {
          file: files.passport,
          kind: 'passport',
          name: 'International passport data page',
        },
        files.academic && {
          file: files.academic,
          kind: 'academic',
          name: 'Academic documents & transcripts',
        },
        files.cv && { file: files.cv, kind: 'cv', name: 'Curriculum vitae' },
      ].filter(Boolean);

      if (queue.length) {
        const results = await Promise.allSettled(
          queue.map((item) => applications.uploadDocument(data.reference, item)),
        );
        const failed = results.filter((result) => result.status === 'rejected').length;
        if (failed) toast.warning(`${failed} document(s) did not upload.`);
      }

      // Registering does not earn anything on its own. Paying the application
      // fee does, so the fee is settled here and the commission lands with it.
      let commission = 0;
      let feePaid = false;
      if (!isCustomCourse) {
        try {
          const { data: checkout } = await payments.checkout(data.reference, gateway);
          commission = Number(checkout.commission_paid) || 0;
          feePaid = true;
          if (checkout.wallet) setWallet(checkout.wallet);
        } catch (error) {
          toast.warning(
            errorMessage(
              error,
              'The student is registered but the fee did not go through. Pay it from Students to earn your commission.',
            ),
          );
        }
      }

      setCreated({ ...data, commission, feePaid });
    } catch (error) {
      toast.error(errorMessage(error, 'Could not register that student.'));
    } finally {
      setBusy(false);
    }
  };

  const filePicker = (key, label, accept, icon) => (
    <div className={`dropzone-card ${files[key] ? 'has-file' : ''}`.trim()}>
      <input
        type="file"
        className="dropzone-file-input"
        accept={accept}
        onChange={(event) =>
          setFiles((current) => ({ ...current, [key]: event.target.files?.[0] || null }))
        }
      />
      <Icon name={icon} size={34} className="dropzone-icon" strokeWidth={1.6} />
      <div className="dropzone-title">{label}</div>
      <div className="dropzone-hint">Optional. The student can add it later</div>
      <button type="button" className="btn btn-sm btn-secondary">
        {files[key] ? 'Replace file' : 'Browse or drop a file'}
      </button>
      <div className={`uploaded-file-tag ${files[key] ? 'visible' : ''}`.trim()}>
        <div className="uploaded-file-info">
          <Icon name="check" size={16} className="file-status-icon" strokeWidth={2.4} />
          <div>
            <span className="file-name-display">{files[key]?.name || ''}</span>
          </div>
        </div>
        <span className="badge badge-success">Ready</span>
      </div>
    </div>
  );

  return (
    <div className="agent-stack" ref={shellRef}>
      <section className="agent-banner">
        <span className="agent-icon" aria-hidden="true">
          <Icon name="userPlus" size={22} animate />
        </span>
        <div className="agent-banner-text">
          <h2>Register a student</h2>
          <p>The full application, filed on their behalf.</p>
        </div>
      </section>

      <div className="agent-wizard-shell">

        {step === 1 ? (
          <div className="ag-wizard-card">
            <div className="ag-wizard-card-header">
              <h3>Student details</h3>
              <p>As printed on their international passport.</p>
            </div>

            <div className="agent-2col-grid">
              <div className="agent-form-group">
                <label className="agent-form-label" htmlFor="st-name">
                  Full legal name *
                </label>
                <input
                  id="st-name"
                  className="agent-form-control"
                  placeholder="Chukwudi Emmanuel Okafor"
                  value={form.fullName}
                  onChange={(event) => update({ fullName: event.target.value })}
                />
              </div>

              <div className="agent-form-group">
                <label className="agent-form-label" htmlFor="st-email">
                  Student email *
                </label>
                <input
                  id="st-email"
                  type="email"
                  className="agent-form-control"
                  placeholder="student@example.com"
                  value={form.email}
                  onChange={(event) => update({ email: event.target.value })}
                />
              </div>
            </div>

            <div className="agent-2col-grid">
              <div className="agent-form-group">
                <label className="agent-form-label" htmlFor="st-phone">
                  Phone / WhatsApp *
                </label>
                <input
                  id="st-phone"
                  type="tel"
                  className="agent-form-control"
                  placeholder="+234 802 345 6789"
                  value={form.phone}
                  onChange={(event) => update({ phone: event.target.value })}
                />
              </div>

              <div className="agent-form-group">
                <label className="agent-form-label" id="st-origin-label">
                  Country of origin *
                </label>
                <SearchableSelect
                  options={originNames}
                  value={form.originCountry}
                  onChange={(value) => update({ originCountry: value })}
                  labelledBy="st-origin-label"
                />
              </div>
            </div>

            <div className="agent-form-group">
              <label className="agent-form-label" id="st-dest-label">
                Destination country *
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
                placeholder="Search any destination country..."
                labelledBy="st-dest-label"
              />
            </div>

            <div className="ag-wizard-footer">
              <button
                type="button"
                className="agent-btn agent-btn-secondary"
                onClick={() => navigate('/agent/students')}
              >
                Cancel
              </button>
              <button type="button" className="agent-btn agent-btn-primary" onClick={() => goTo(2)}>
                Continue
                <Icon name="arrowRight" size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="ag-wizard-card">
            <div className="ag-wizard-card-header">
              <h3>Academic background</h3>
              <p>Their highest completed qualification and grades.</p>
            </div>

            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="st-prev">
                Institutions attended *
              </label>
              <input
                id="st-prev"
                className="agent-form-control"
                placeholder="University of Ibadan"
                value={form.previousSchools}
                onChange={(event) => update({ previousSchools: event.target.value })}
              />
            </div>

            <div className="agent-2col-grid">
              <div className="agent-form-group">
                <label className="agent-form-label" htmlFor="st-qual">
                  Highest qualification *
                </label>
                <select
                  id="st-qual"
                  className="agent-form-select"
                  value={form.qualification}
                  onChange={(event) => update({ qualification: event.target.value })}
                >
                  {QUALIFICATIONS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              <div className="agent-form-group">
                <label className="agent-form-label" htmlFor="st-year">
                  Graduation year *
                </label>
                <input
                  id="st-year"
                  type="number"
                  min="1960"
                  max="2035"
                  className="agent-form-control"
                  placeholder="2023"
                  value={form.yearGraduated}
                  onChange={(event) => update({ yearGraduated: event.target.value })}
                />
              </div>
            </div>

            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="st-gpa">
                Grade or CGPA *
              </label>
              <input
                id="st-gpa"
                className="agent-form-control"
                placeholder="Second Class Upper, or 4.25 / 5.0"
                value={form.gradeGpa}
                onChange={(event) => update({ gradeGpa: event.target.value })}
              />
            </div>

            <div className="ag-wizard-footer">
              <button type="button" className="agent-btn agent-btn-secondary" onClick={() => goTo(1)}>
                <Icon name="arrowLeft" size={16} strokeWidth={2} />
                Back
              </button>
              <button type="button" className="agent-btn agent-btn-primary" onClick={() => goTo(3)}>
                Continue
                <Icon name="arrowRight" size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="ag-wizard-card">
            <div className="ag-wizard-card-header">
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

            <div className="ag-wizard-footer">
              <button type="button" className="agent-btn agent-btn-secondary" onClick={() => goTo(2)}>
                <Icon name="arrowLeft" size={16} strokeWidth={2} />
                Back
              </button>
              <button type="button" className="agent-btn agent-btn-primary" onClick={() => goTo(4)}>
                Continue
                <Icon name="arrowRight" size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="ag-wizard-card">
            <div className="ag-wizard-card-header">
              <h3>Documents</h3>
              <p>Attach what you have. The student can add the rest from their portal.</p>
            </div>

            <div className="dropzone-container">
              {filePicker('passport', 'International passport data page', '.pdf,.jpg,.jpeg,.png', 'passport')}
              {filePicker('academic', 'Academic documents', '.pdf', 'document')}
              {filePicker('cv', 'Curriculum vitae', '.pdf', 'resume')}
            </div>

            <div className="agent-form-group">
              <label className="agent-form-label" htmlFor="st-notes">
                Counselling notes
              </label>
              <textarea
                id="st-notes"
                className="agent-form-control"
                rows={3}
                placeholder="Anything the admissions desk should know"
                value={form.notes}
                onChange={(event) => update({ notes: event.target.value })}
              />
            </div>

            <div className="ag-wizard-footer">
              <button type="button" className="agent-btn agent-btn-secondary" onClick={() => goTo(3)}>
                <Icon name="arrowLeft" size={16} strokeWidth={2} />
                Back
              </button>
              <button type="button" className="agent-btn agent-btn-primary" onClick={() => goTo(5)}>
                Review
                <Icon name="arrowRight" size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        ) : null}

        {step === 5 ? (
          <div className="ag-wizard-card">
            <div className="ag-wizard-card-header">
              <h3>Review and submit</h3>
              <p>Check the file before it joins the admissions queue.</p>
            </div>

            <div className="dossier-grid">
              <div className="dossier-item">
                <span className="d-label">Student</span>
                <span className="d-val">{form.fullName || 'Not entered'}</span>
              </div>
              <div className="dossier-item">
                <span className="d-label">Email</span>
                <span className="d-val">{form.email || 'Not entered'}</span>
              </div>
              <div className="dossier-item">
                <span className="d-label">Phone</span>
                <span className="d-val">{form.phone || 'Not entered'}</span>
              </div>
              <div className="dossier-item">
                <span className="d-label">Route</span>
                <span className="d-val">
                  {form.originCountry} to {form.destinationCountry}
                </span>
              </div>
              <div className="dossier-item">
                <span className="d-label">Previous institution</span>
                <span className="d-val">{form.previousSchools || 'Not entered'}</span>
              </div>
              <div className="dossier-item">
                <span className="d-label">Qualification</span>
                <span className="d-val">
                  {form.qualification} ({form.yearGraduated || 'year not entered'})
                </span>
              </div>
              <div className="dossier-item dossier-item-wide">
                <span className="d-label">Institution</span>
                <span className="d-val d-val-accent">
                  {institution?.name || 'Not chosen'}
                </span>
                <span className="d-val d-val-sm">
                  {form.programs.map((program) => program.name).join(' and ') || 'Not chosen'}
                </span>
              </div>
            </div>

            <div className="summary-invoice">
              <div className="invoice-header">Application fee</div>
              <div className="invoice-row">
                <span>Application fee</span>
                <span className="invoice-amount">
                  {quote ? formatMoney(quote.amount, quote.currency) : 'Calculating'}
                </span>
              </div>
              <div className="invoice-row">
                <span>Gateway processing</span>
                <span className="invoice-amount">
                  {quote ? formatMoney(quote.processing_fee, quote.currency) : 'Calculating'}
                </span>
              </div>
              <div className="invoice-row total">
                <span>You pay now</span>
                <span className="invoice-amount-total">
                  {quote ? formatMoney(quote.total, quote.currency) : 'Calculating'}
                </span>
              </div>
            </div>

            {quote && !quote.waived ? (
              <div className="agent-form-group">
                <label className="agent-form-label" htmlFor="ag-gateway">
                  Pay with
                </label>
                <select
                  id="ag-gateway"
                  className="agent-form-select"
                  value={gateway}
                  onChange={(event) => setGateway(event.target.value)}
                >
                  <option value="Paystack">Paystack</option>
                  <option value="Flutterwave">Flutterwave</option>
                </select>
              </div>
            ) : null}

            {quote?.waived ? (
              <div className="callout callout-warning">
                <Icon name="alert" size={20} className="callout-icon" strokeWidth={2} />
                <div className="callout-content">
                  <strong>{institution?.name} waives the application fee.</strong> With no
                  fee to settle there is no registration commission on this student. You
                  still earn {formatNaira(30000)} when their visa is verified.
                </div>
              </div>
            ) : (
              <div className="callout callout-success">
                <Icon name="checkCircle" size={20} className="callout-icon" strokeWidth={2} />
                <div className="callout-content">
                  <strong>{formatNaira(30000)} lands in your wallet the moment this fee
                  clears</strong>, and {formatNaira(30000)} more once the admissions desk
                  verifies their visa. Filed by {profile?.full_name} ({profile?.partner_code}).
                </div>
              </div>
            )}

            <div className="ag-wizard-footer">
              <button type="button" className="agent-btn agent-btn-secondary" onClick={() => goTo(4)}>
                <Icon name="arrowLeft" size={16} strokeWidth={2} />
                Back
              </button>
              <button
                type="button"
                className="agent-btn agent-btn-primary agent-btn-lg"
                onClick={submit}
                disabled={busy}
              >
                {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
                {busy
                  ? 'Submitting'
                  : quote?.waived
                    ? 'Register student'
                    : `Register and pay ${quote ? formatMoney(quote.total, quote.currency) : ''}`}
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <Modal
        open={Boolean(created)}
        dismissable={false}
        variant="agent"
        title="Student registered"
        labelledBy="student-created-title"
        footer={
          <>
            <button
              type="button"
              className="agent-btn agent-btn-secondary"
              onClick={() => {
                setCreated(null);
                setForm(BLANK);
                setFiles({ passport: null, academic: null, cv: null });
                setStep(1);
              }}
            >
              Register another
            </button>
            <button
              type="button"
              className="agent-btn agent-btn-primary"
              onClick={() => navigate('/agent/students')}
            >
              Go to students
            </button>
          </>
        }
      >
        <p className="sheet-lede">
          {created?.full_name} is in the admissions queue as{' '}
          <strong>{created?.reference}</strong>.
        </p>

        {created?.commission ? (
          <div className="commission-flash">
            <Icon name="trend" size={22} />
            <span>
              <strong>{formatNaira(created.commission)} added to your balance.</strong>
              <small>
                Another {formatNaira(30000)} follows once their visa is verified.
              </small>
            </span>
          </div>
        ) : (
          <div className="callout callout-warning">
            <Icon name="alert" size={20} className="callout-icon" strokeWidth={2} />
            <div className="callout-content">
              {created?.feePaid
                ? 'No fee was charged on this file, so no registration commission was earned.'
                : 'The application fee is still outstanding. Pay it from Students and your commission is credited straight away.'}
            </div>
          </div>
        )}

        <div className="callout callout-info">
          <Icon name="info" size={20} className="callout-icon" strokeWidth={2} />
          <div className="callout-content">
            {created?.account_created
              ? 'This file is yours to run. The student is not contacted at all, so every status change and every letter comes to you by email.'
              : 'This student already had an account. Every status change and every letter on this file still comes to you by email.'}
          </div>
        </div>

      </Modal>
    </div>
  );
}
