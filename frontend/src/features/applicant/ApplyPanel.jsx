import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import Dropzone from '../../components/ui/Dropzone';
import SearchableSelect from '../../components/ui/SearchableSelect';
import { applications, catalog, payments } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useCatalog, useInstitutions } from '../../hooks/useCatalog';
import Icon from '../../lib/icons';
import { formatMoney, formatTuition } from '../../lib/format';
import ProgramPicker from '../wizard/ProgramPicker';
import { useApplication } from './ApplicationContext';

/**
 * The application, filled in from inside the dashboard.
 *
 * The applicant already has an account, so there is nothing to create and no
 * password to hand out: the personal step is prefilled from the account, and
 * the course arrives already chosen from the course list. Four short steps are
 * left, then the fee.
 *
 * The fee shown is the quote from the server for this school in the
 * applicant's currency. Nothing on this page invents a figure: until the quote
 * arrives it says so, and if it cannot be fetched it offers to try again.
 */

const STEPS = ['Your details', 'Education', 'Course', 'Documents', 'Review'];
const DRAFT_KEY = 'gabstep_portal_apply_draft';

const QUALIFICATIONS = ['SSCE / High School', 'OND', 'HND', "Bachelor's Degree", "Master's Degree"];

export default function ApplyPanel() {
  const { user } = useAuth();
  const { application, reload } = useApplication();
  const { originNames, destinations } = useCatalog();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const topRef = useRef(null);

  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState({});
  const [files, setFiles] = useState({ passport: null, academic: null, cv: null });
  const [quote, setQuote] = useState(null);
  const [quoteState, setQuoteState] = useState('idle');
  const [submitting, setSubmitting] = useState(false);
  // What the submit is doing right now, shown full-screen so nothing else on
  // the page can take over while documents upload and Paystack loads.
  const [phase, setPhase] = useState('');
  const leaving = useRef(false);
  const [submitted, setSubmitted] = useState(null);
  const [form, setForm] = useState(() => ({
    fullName: user?.full_name || '',
    phone: user?.phone || '',
    originCountry: user?.country || '',
    destinationCountry: params.get('destination') || '',
    previousSchools: '',
    qualification: '',
    yearGraduated: '',
    gradeGpa: '',
    institution: params.get('institution') || '',
    level: null,
    programs: [],
    is_custom_course: false,
    custom_course: '',
  }));

  const { institutions, loading: institutionsLoading } = useInstitutions(form.destinationCountry);
  const institution = useMemo(
    () => (institutions || []).find((item) => item.slug === form.institution) || null,
    [institutions, form.institution],
  );
  const isCustomCourse = Boolean(form.is_custom_course);
  const feeFree = isCustomCourse || Boolean(institution?.is_fee_free);

  const update = useCallback((patch) => {
    setForm((current) => ({ ...current, ...patch }));
    setErrors((current) => {
      const next = { ...current };
      Object.keys(patch).forEach((key) => delete next[key]);
      return next;
    });
  }, []);

  // The course chosen on the course list arrives as ?program=, and is selected
  // once the school's programmes have loaded.
  const wantedProgram = params.get('program');
  const preselected = useRef(false);
  useEffect(() => {
    if (preselected.current || !wantedProgram || !institution?.programs) return;
    const program = institution.programs.find((item) => String(item.id) === String(wantedProgram));
    if (program) {
      preselected.current = true;
      update({ programs: [program], level: program.level || null });
    }
  }, [institution, wantedProgram, update]);

  // Restore typed answers from an earlier visit. Files are never kept.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null');
      if (saved?.previousSchools !== undefined) {
        setForm((current) => ({
          ...current,
          previousSchools: saved.previousSchools || '',
          qualification: saved.qualification || '',
          yearGraduated: saved.yearGraduated || '',
          gradeGpa: saved.gradeGpa || '',
        }));
      }
    } catch {
      /* a damaged draft is simply ignored */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          previousSchools: form.previousSchools,
          qualification: form.qualification,
          yearGraduated: form.yearGraduated,
          gradeGpa: form.gradeGpa,
        }),
      );
    } catch {
      /* storage can be unavailable in private windows */
    }
  }, [form.previousSchools, form.qualification, form.yearGraduated, form.gradeGpa]);

  const loadQuote = useCallback(() => {
    if (feeFree || !form.institution) {
      setQuote(null);
      setQuoteState('free');
      return;
    }
    setQuoteState('loading');
    catalog
      .feeQuote(form.originCountry || user?.country || 'Nigeria', form.institution)
      .then(({ data }) => {
        setQuote(data);
        setQuoteState('ready');
      })
      .catch(() => setQuoteState('failed'));
  }, [feeFree, form.institution, form.originCountry, user?.country]);

  useEffect(() => {
    if (step === 4) loadQuote();
  }, [step, loadQuote]);

  // Someone who already has an application goes to it; but not while this page
  // is the one creating it, or the dashboard flashed up before Paystack opened.
  if (application && !submitted && !submitting && !leaving.current) return <Navigate to="/portal" replace />;

  const validate = (index) => {
    const found = {};
    if (index === 0) {
      if (form.fullName.trim().split(/\s+/).length < 2) found.fullName = 'Enter your full legal name.';
      if (form.phone.replace(/\D/g, '').length < 7) found.phone = 'Enter a phone number we can reach you on.';
      if (!form.originCountry) found.originCountry = 'Choose your country of origin.';
      if (!form.destinationCountry) found.destinationCountry = 'Choose where you want to study.';
    }
    if (index === 1) {
      if (!form.previousSchools.trim()) found.previousSchools = 'List the schools you attended.';
      if (!form.qualification) found.qualification = 'Choose your highest qualification.';
      const year = Number(form.yearGraduated);
      if (!year || year < 1960 || year > new Date().getFullYear() + 1) found.yearGraduated = 'Enter the year you graduated.';
      if (!form.gradeGpa.trim()) found.gradeGpa = 'Enter your grade or GPA.';
    }
    if (index === 2) {
      if (isCustomCourse && !form.custom_course.trim()) found.course = 'Enter the course you want to study.';
      if (!isCustomCourse && !form.institution) found.course = 'Choose a university.';
      else if (!isCustomCourse && !form.programs.length) found.course = 'Choose at least one course.';
    }
    if (index === 3) {
      if (!files.passport) found.passport = 'Add your passport data page.';
      if (!files.academic) found.academic = 'Add your academic documents.';
      if (!files.cv) found.cv = 'Add your CV.';
    }
    setErrors(found);
    if (Object.keys(found).length) {
      toast.warning(Object.values(found)[0]);
      return false;
    }
    return true;
  };

  const go = (target) => {
    if (target > step) {
      for (let index = step; index < target; index += 1) if (!validate(index)) return;
    }
    setStep(target);
    window.setTimeout(() => topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 20);
  };

  const upload = async (reference) => {
    const queue = [
      { file: files.passport, kind: 'passport', name: 'International passport data page' },
      { file: files.academic, kind: 'academic', name: 'Academic documents & transcripts' },
      { file: files.cv, kind: 'cv', name: 'Curriculum vitae' },
    ].filter((item) => item.file);
    const results = await Promise.allSettled(
      queue.map((item) => applications.uploadDocument(reference, item)),
    );
    const failed = results.filter((result) => result.status === 'rejected').length;
    if (failed) {
      toast.warning(`${failed} document${failed === 1 ? '' : 's'} did not upload. Add them again from Application.`);
    }
  };

  const submit = async () => {
    for (let index = 0; index < 4; index += 1) {
      if (!validate(index)) {
        setStep(index);
        return;
      }
    }
    setSubmitting(true);
    setPhase('saving');
    try {
      const { data: created } = await applications.create({
        full_name: form.fullName.trim(),
        email: user.email,
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

      setPhase('uploading');
      const [settlement] = await Promise.all([
        payments.checkout(created.reference).then((response) => response.data).catch(() => null),
        upload(created.reference),
      ]);
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch {
        /* nothing to clear */
      }

      if (!isCustomCourse && settlement?.authorization_url) {
        // Stay on this screen until the browser has left for Paystack.
        leaving.current = true;
        setPhase('payment');
        window.location.assign(settlement.authorization_url);
        return;
      }

      setSubmitted({
        reference: created.reference,
        transferAccount: settlement?.transfer_account || null,
        feeOutstanding: !feeFree && !settlement?.waived,
      });
      reload();
    } catch (error) {
      toast.error(errorMessage(error, 'Your application could not be submitted.'));
    } finally {
      if (!leaving.current) {
        setSubmitting(false);
        setPhase('');
      }
    }
  };

  const field = (name) => `gx-field ${errors[name] ? 'has-error' : ''}`.trim();
  const errorFor = (name) => (errors[name] ? <span className="gx-error">{String(errors[name])}</span> : null);

  if (submitted) {
    return (
      <div className="gx-page">
        <section className="gx-card gx-empty">
          <span className="gx-icon-tile" aria-hidden="true">
            <Icon name="checkCircle" size={24} />
          </span>
          <h3>Application submitted</h3>
          <p className="gx-muted">
            Reference <strong>{submitted.reference}</strong>. We will email you as it moves forward.
          </p>
          {submitted.feeOutstanding && submitted.transferAccount ? (
            <div className="gx-card" style={{ marginTop: 12, textAlign: 'left', width: '100%', maxWidth: 420 }}>
              <h4 className="gx-card-title" style={{ fontSize: 15, marginBottom: 8 }}>Pay by bank transfer</h4>
              <p className="gx-muted gx-small">
                {submitted.transferAccount.bank} · {submitted.transferAccount.account_number}
                <br />
                {submitted.transferAccount.beneficiary}
                <br />
                Use {submitted.reference} as the payment reference.
              </p>
            </div>
          ) : null}
          <button type="button" className="gx-btn gx-btn-primary" style={{ marginTop: 12 }} onClick={() => navigate('/portal')}>
            Go to overview
          </button>
        </section>
      </div>
    );
  }

  if (phase) {
    const label = {
      saving: 'Submitting your application',
      uploading: 'Uploading your documents',
      payment: 'Opening secure payment',
    }[phase];
    return (
      <div className="gx-page">
        <section className="gx-card gx-processing" role="status" aria-live="polite">
          <span className="gx-processing-spinner" aria-hidden="true" />
          <h2>{label}</h2>
          <p className="gx-muted">Please keep this page open. This takes a few seconds.</p>
          <ol className="gx-processing-steps">
            <li className={phase === 'saving' ? 'is-current' : 'is-done'}>Application</li>
            <li className={phase === 'uploading' ? 'is-current' : phase === 'payment' ? 'is-done' : ''}>Documents</li>
            <li className={phase === 'payment' ? 'is-current' : ''}>Payment</li>
          </ol>
        </section>
      </div>
    );
  }

  return (
    <div className="gx-page" ref={topRef}>
      <section className="gx-card">
        <ol className="gx-progress" aria-label="Application steps">
          {STEPS.map((label, index) => (
            <li
              key={label}
              className={index < step ? 'is-done' : index === step ? 'is-current' : ''}
              aria-current={index === step ? 'step' : undefined}
            >
              <span>
                {index + 1}. {label}
              </span>
            </li>
          ))}
        </ol>

        {step === 0 ? (
          <div className="gx-form">
            <div className="gx-card-head" style={{ marginBottom: 0 }}>
              <h2 className="gx-card-title">Your details</h2>
            </div>
            <div className="gx-form-row">
              <div className={field('fullName')}>
                <label htmlFor="ap-name">Full legal name</label>
                <input id="ap-name" className="gx-input" autoComplete="name" value={form.fullName} onChange={(event) => update({ fullName: event.target.value })} />
                <span className="gx-hint">Exactly as your passport prints it.</span>
                {errorFor('fullName')}
              </div>
              <div className="gx-field">
                <label htmlFor="ap-email">Email address</label>
                <input id="ap-email" className="gx-input" value={user?.email || ''} readOnly />
              </div>
            </div>
            <div className="gx-form-row">
              <div className={field('phone')}>
                <label htmlFor="ap-phone">Phone number</label>
                <input id="ap-phone" type="tel" className="gx-input" autoComplete="tel" value={form.phone} onChange={(event) => update({ phone: event.target.value })} />
                {errorFor('phone')}
              </div>
              <div className={field('originCountry')}>
                <span className="gx-label" id="ap-origin-label">Country of origin</span>
                <SearchableSelect options={originNames} value={form.originCountry} onChange={(value) => update({ originCountry: value })} labelledBy="ap-origin-label" />
                {errorFor('originCountry')}
              </div>
            </div>
            <div className={field('destinationCountry')}>
              <span className="gx-label" id="ap-dest-label">Where you want to study</span>
              <SearchableSelect
                options={destinations.map((item) => item.name)}
                value={form.destinationCountry}
                onChange={(value) => update({ destinationCountry: value, institution: '', programs: [], level: null, is_custom_course: false, custom_course: '' })}
                labelledBy="ap-dest-label"
              />
              {errorFor('destinationCountry')}
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="gx-form">
            <div className="gx-card-head" style={{ marginBottom: 0 }}>
              <h2 className="gx-card-title">Education</h2>
            </div>
            <div className={field('previousSchools')}>
              <label htmlFor="ap-schools">Schools attended</label>
              <input id="ap-schools" className="gx-input" value={form.previousSchools} onChange={(event) => update({ previousSchools: event.target.value })} />
              {errorFor('previousSchools')}
            </div>
            <div className="gx-form-row">
              <div className={field('qualification')}>
                <label htmlFor="ap-qual">Highest qualification</label>
                <select id="ap-qual" className="gx-input" value={form.qualification} onChange={(event) => update({ qualification: event.target.value })}>
                  <option value="" />
                  {QUALIFICATIONS.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
                {errorFor('qualification')}
              </div>
              <div className={field('yearGraduated')}>
                <label htmlFor="ap-year">Year of graduation</label>
                <input id="ap-year" type="number" inputMode="numeric" className="gx-input" value={form.yearGraduated} onChange={(event) => update({ yearGraduated: event.target.value })} />
                {errorFor('yearGraduated')}
              </div>
            </div>
            <div className={field('gradeGpa')}>
              <label htmlFor="ap-grade">Grade or GPA</label>
              <input id="ap-grade" className="gx-input" value={form.gradeGpa} onChange={(event) => update({ gradeGpa: event.target.value })} />
              {errorFor('gradeGpa')}
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="gx-form">
            <div className="gx-card-head" style={{ marginBottom: 0 }}>
              <h2 className="gx-card-title">Course</h2>
              <Link to="/portal/courses" className="gx-btn gx-btn-ghost gx-btn-sm">Browse all courses</Link>
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
                onChange={(next) => update({ ...next, course: undefined })}
                onNotify={(message, type) => toast.toast(message, type)}
              />
            </div>
            {errorFor('course')}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="gx-form">
            <div className="gx-card-head" style={{ marginBottom: 0 }}>
              <h2 className="gx-card-title">Documents</h2>
              <span className="gx-muted gx-small">Clear, full-page scans. Photos are compressed for you.</span>
            </div>
            {destinations.find((item) => item.name === form.destinationCountry)?.is_european ? (
              <p className="gx-muted gx-small">
                European universities prefer a{' '}
                <a className="gx-link" href="https://europa.eu/europass/en/create-europass-cv" target="_blank" rel="noreferrer">
                  Europass CV
                </a>
                .
              </p>
            ) : null}
            <div className="dropzone-container">
              <Dropzone icon="passport" title="Passport data page" hint="PDF or photo · up to 10MB" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif" maxMb={10} file={files.passport} onSelect={(file) => setFiles((current) => ({ ...current, passport: file }))} onReject={(message) => toast.warning(message)} />
              <Dropzone icon="document" title="Academic documents" hint="Transcripts and certificates · PDF or photo · up to 10MB" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif" maxMb={10} file={files.academic} onSelect={(file) => setFiles((current) => ({ ...current, academic: file }))} onReject={(message) => toast.warning(message)} />
              <Dropzone icon="resume" title="CV" hint="PDF · up to 10MB" accept=".pdf" maxMb={10} file={files.cv} onSelect={(file) => setFiles((current) => ({ ...current, cv: file }))} onReject={(message) => toast.warning(message)} />
            </div>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="gx-form">
            <div className="gx-card-head" style={{ marginBottom: 0 }}>
              <h2 className="gx-card-title">Review</h2>
            </div>
            <ul className="gx-list">
              <li className="gx-list-row">
                <span className="gx-muted">Applicant</span>
                <span className="gx-list-title">{form.fullName}</span>
              </li>
              <li className="gx-list-row">
                <span className="gx-muted">University</span>
                <span className="gx-list-title">{isCustomCourse ? 'To be matched by our team' : institution?.name}</span>
              </li>
              <li className="gx-list-row">
                <span className="gx-muted">Course</span>
                <span className="gx-list-title" style={{ textAlign: 'right' }}>
                  {isCustomCourse ? form.custom_course : form.programs.map((program) => program.name).join(', ')}
                </span>
              </li>
              {!isCustomCourse && form.programs[0]?.tuition ? (
                <li className="gx-list-row">
                  <span className="gx-muted">Tuition</span>
                  <span className="gx-list-title">{formatTuition(form.programs[0].tuition, institution?.currency)}</span>
                </li>
              ) : null}
              <li className="gx-list-row">
                <span className="gx-muted">Application fee</span>
                <span className="gx-list-title">
                  {feeFree
                    ? 'No fee'
                    : quoteState === 'ready' && quote
                      ? formatMoney(quote.amount + (quote.processing_fee || 0), quote.currency)
                      : quoteState === 'failed'
                        ? (
                          <button type="button" className="gx-link" onClick={loadQuote}>
                            Could not load. Try again
                          </button>
                        )
                        : 'Calculating'}
                </span>
              </li>
            </ul>
            {!feeFree && quoteState === 'ready' && quote?.processing_fee ? (
              <p className="gx-muted gx-small">
                Includes {formatMoney(quote.processing_fee, quote.currency)} card processing. You pay on the next screen.
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="gx-form-actions" style={{ justifyContent: 'space-between', marginTop: 24 }}>
          {step === 0 ? (
            <Link to="/portal/courses" className="gx-btn gx-btn-secondary">
              <Icon name="arrowLeft" size={16} strokeWidth={2} />
              Courses
            </Link>
          ) : (
            <button type="button" className="gx-btn gx-btn-secondary" onClick={() => go(step - 1)} disabled={submitting}>
              <Icon name="arrowLeft" size={16} strokeWidth={2} />
              Back
            </button>
          )}
          {step < 4 ? (
            <button type="button" className="gx-btn gx-btn-primary" onClick={() => go(step + 1)}>
              Continue
              <Icon name="arrowRight" size={16} strokeWidth={2} />
            </button>
          ) : (
            <button
              type="button"
              className="gx-btn gx-btn-primary gx-btn-lg"
              onClick={submit}
              disabled={submitting || (!feeFree && quoteState !== 'ready')}
            >
              {submitting ? <span className="spinner-sm" aria-hidden="true" /> : null}
              {submitting ? 'Submitting' : feeFree ? 'Submit application' : 'Submit and pay'}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
