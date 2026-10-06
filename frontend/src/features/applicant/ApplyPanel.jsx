import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import SearchableSelect from '../../components/ui/SearchableSelect';
import StepField from '../../components/form/StepField';
import { applications, catalog, payments } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useCatalog, useInstitutions } from '../../hooks/useCatalog';
import Icon from '../../lib/icons';
import { compressImageFile } from '../../lib/compress';
import { formatMoney, formatTuition } from '../../lib/format';
import EuropeanCvTip from '../../components/ui/EuropeanCvTip';
import ProgramPicker from '../wizard/ProgramPicker';
import { rememberSelectedApplication, useApplication } from './ApplicationContext';

/**
 * The application, filled in from inside the dashboard, one step at a time.
 *
 * It looks and works like the agent's Register a student: an icon beside each
 * label, the asterisk inline, Back on the left and Save draft and Continue on
 * the right. Save draft keeps what was typed and every document on the server,
 * so the applicant can come back before paying and carry on from the Overview.
 *
 * The fee shown is the server's quote for this school in the applicant's
 * currency. Nothing here invents a figure.
 */

const STEPS = ['Your details', 'Education', 'University and course', 'Documents', 'Review and pay'];
const QUALIFICATIONS = ['SSCE / High School', 'OND', 'HND', "Bachelor's Degree", "Master's Degree"];
const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,application/pdf,image/*';
const SLOTS = [
  { slot: 'passport', kind: 'passport', name: 'International passport data page', label: 'Passport data page', icon: 'passport' },
  { slot: 'academic', kind: 'academic', name: 'Academic documents & transcripts', label: 'Academic documents', icon: 'document' },
  { slot: 'cv', kind: 'cv', name: 'Curriculum vitae', label: 'CV', icon: 'resume' },
];
const EMPTY_DOCS = { passport: null, academic: null, cv: null };

export default function ApplyPanel() {
  const { user } = useAuth();
  const { applicationsList, selectApplication } = useApplication();
  const { originNames, destinations } = useCatalog();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const topRef = useRef(null);

  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState({});
  // Each document is { file } before it is saved and { remote } once it sits
  // on the draft.
  const [docs, setDocs] = useState(EMPTY_DOCS);
  const [others, setOthers] = useState([]);
  const [removedRemote, setRemovedRemote] = useState([]);
  const [hasDraft, setHasDraft] = useState(false);
  const [saving, setSaving] = useState(false);
  const [quote, setQuote] = useState(null);
  const [quoteState, setQuoteState] = useState('idle');
  const [submitting, setSubmitting] = useState(false);
  const [phase, setPhase] = useState('');
  const leaving = useRef(false);
  const otherCounter = useRef(1);
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

  // The course chosen on the course list arrives as ?program=.
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

  // Reopen a saved draft. A course picked just now on the course list wins
  // over the one in the draft.
  useEffect(() => {
    let cancelled = false;
    applications
      .getDraft()
      .then(({ data }) => {
        if (cancelled || !data) return;
        setHasDraft(true);
        const saved = data.data?.form || {};
        const pickedNow = params.get('institution');
        setForm((current) => ({
          ...current,
          ...saved,
          ...(pickedNow
            ? {
                destinationCountry: current.destinationCountry,
                institution: current.institution,
                level: current.level,
                programs: current.programs,
                is_custom_course: false,
                custom_course: '',
              }
            : {}),
        }));
        if (!pickedNow) setStep(Math.min(Math.max((data.current_step || 1) - 1, 0), 4));
        const nextDocs = { ...EMPTY_DOCS };
        const nextOthers = [];
        (data.files || []).forEach((item) => {
          if (item.slot in nextDocs) nextDocs[item.slot] = { remote: item };
          else nextOthers.push({ slot: item.slot, name: item.name, remote: item });
        });
        otherCounter.current =
          nextOthers.reduce((max, item) => Math.max(max, Number(item.slot.split('-')[1]) || 0), 0) + 1;
        setDocs(nextDocs);
        setOthers(nextOthers);
      })
      .catch(() => null);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // A school with a live application takes no second one.
  const appliedAt = (slug) =>
    applicationsList.find((item) => item.institution_slug === slug && item.status !== 'rejected') || null;

  const hasDoc = (slot) => Boolean(docs[slot]?.file || docs[slot]?.remote);

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
      else if (!isCustomCourse && appliedAt(form.institution)) {
        found.course = `You have already applied to ${appliedAt(form.institution).institution}. Choose a different school.`;
      }
    }
    if (index === 3) {
      if (!hasDoc('passport')) found.passport = 'Add your passport data page.';
      if (!hasDoc('academic')) found.academic = 'Add your academic documents.';
      if (!hasDoc('cv')) found.cv = 'Add your CV.';
      if (others.some((item) => (item.file || item.remote) && !item.name.trim())) found.others = 'Name each of the other documents.';
    }
    setErrors(found);
    if (Object.keys(found).length) {
      toast.warning(Object.values(found)[0]);
      return false;
    }
    return true;
  };

  const scrollTop = () =>
    window.setTimeout(() => topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 20);

  const go = (target) => {
    if (target > step) {
      for (let index = step; index < target; index += 1) if (!validate(index)) return;
    }
    setStep(target);
    scrollTop();
  };

  // ── Documents ──

  const pick = async (event) => {
    const raw = event.target.files?.[0] || null;
    event.target.value = '';
    if (raw && raw.size > 10 * 1024 * 1024 && !raw.type.startsWith('image/')) {
      toast.warning('That file is larger than 10MB.');
      return null;
    }
    return raw ? compressImageFile(raw) : null;
  };

  const setSlotFile = (slot, file) => {
    setDocs((current) => {
      if (current[slot]?.remote) setRemovedRemote((list) => [...list, current[slot].remote.id]);
      return { ...current, [slot]: file ? { file } : null };
    });
    setErrors((current) => ({ ...current, [slot]: undefined }));
  };

  const addOther = () => {
    const slot = `other-${otherCounter.current}`;
    otherCounter.current += 1;
    setOthers((current) => [...current, { slot, name: '', file: null, remote: null }]);
  };

  const updateOther = (slot, patch) =>
    setOthers((current) =>
      current.map((item) => {
        if (item.slot !== slot) return item;
        if (patch.file && item.remote) setRemovedRemote((list) => [...list, item.remote.id]);
        return { ...item, ...patch, ...(patch.file ? { remote: null } : {}) };
      }),
    );

  const removeOther = (slot) =>
    setOthers((current) =>
      current.filter((item) => {
        if (item.slot === slot && item.remote) setRemovedRemote((list) => [...list, item.remote.id]);
        return item.slot !== slot;
      }),
    );

  // ── Draft ──

  const saveDraft = async () => {
    await applications.saveDraft({ current_step: step + 1, data: { form } });
    setHasDraft(true);
    await Promise.all(removedRemote.map((id) => applications.deleteDraftFile(id).catch(() => null)));
    setRemovedRemote([]);

    const nextDocs = { ...docs };
    for (const meta of SLOTS) {
      const entry = docs[meta.slot];
      if (entry?.file) {
        const { data } = await applications.uploadDraftFile({ ...meta, file: entry.file });
        nextDocs[meta.slot] = { remote: data };
      }
    }
    const nextOthers = [];
    for (const item of others) {
      if (item.file) {
        const { data } = await applications.uploadDraftFile({
          slot: item.slot,
          kind: 'other',
          name: item.name.trim() || 'Other document',
          file: item.file,
        });
        nextOthers.push({ ...item, file: null, remote: data });
      } else if (item.remote || item.name) {
        nextOthers.push(item);
      }
    }
    setDocs(nextDocs);
    setOthers(nextOthers);
  };

  const onSaveDraft = async () => {
    setSaving(true);
    try {
      await saveDraft();
      toast.success('Draft saved. Continue any time from your Overview.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not save your draft.'));
    } finally {
      setSaving(false);
    }
  };

  // ── Submit ──

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
      // With a draft, every document goes onto it first and moves to the new
      // application in the same request that creates it.
      if (hasDraft) await saveDraft();

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
      const queue = hasDraft
        ? []
        : [
            ...SLOTS.filter((meta) => docs[meta.slot]?.file).map((meta) => ({
              file: docs[meta.slot].file,
              kind: meta.kind,
              name: meta.name,
            })),
            ...others
              .filter((item) => item.file)
              .map((item) => ({ file: item.file, kind: 'other', name: item.name.trim() || 'Other document' })),
          ];
      const [settlement, results] = await Promise.all([
        payments.checkout(created.reference).then((response) => response.data).catch(() => null),
        Promise.allSettled(queue.map((item) => applications.uploadDocument(created.reference, item))),
      ]);
      const failed = results.filter((result) => result.status === 'rejected').length;
      if (failed) toast.warning(`${failed} document${failed === 1 ? '' : 's'} did not upload. Add them again from Application.`);

      // The new application is the one the dashboard opens on, including on
      // the way back from the payment page.
      rememberSelectedApplication(created.reference);

      if (!isCustomCourse && settlement?.authorization_url) {
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
      selectApplication(created.reference);
    } catch (error) {
      toast.error(errorMessage(error, 'Your application could not be submitted.'));
    } finally {
      if (!leaving.current) {
        setSubmitting(false);
        setPhase('');
      }
    }
  };

  // ── Pieces ──

  const docName = (entry) => entry?.file?.name || entry?.remote?.original_filename || '';

  const fileRow = (id, value, onPick, onClear) => (
    <div className="nf-file">
      <span className={`nf-file-name${value ? '' : ' is-empty'}`} title={value}>
        {value || 'No file chosen'}
      </span>
      <div className="nf-file-actions">
        {value ? (
          <button type="button" className="nf-link-btn" onClick={onClear}>
            Remove
          </button>
        ) : null}
        <label className="agent-btn agent-btn-secondary agent-btn-sm nf-file-btn" htmlFor={id}>
          {value ? 'Replace' : 'Choose file'}
        </label>
        <input id={id} type="file" accept={ACCEPT} className="sr-only" onChange={onPick} />
      </div>
    </div>
  );

  if (submitted) {
    return (
      <div className="agent-stack" ref={topRef}>
        <div className="nf-card nf-done">
          <span className="nf-done-mark" aria-hidden="true">
            <Icon name="check" size={26} strokeWidth={2.4} />
          </span>
          <h2>Application submitted</h2>
          <p className="nf-done-lede">We will email you as it moves forward.</p>
          <dl className="nf-done-facts">
            <div>
              <dt>Application reference</dt>
              <dd>{submitted.reference}</dd>
            </div>
            <div>
              <dt>Application fee</dt>
              <dd>{submitted.feeOutstanding ? 'Due' : 'No fee'}</dd>
            </div>
          </dl>
          {submitted.feeOutstanding && submitted.transferAccount ? (
            <dl className="pay-account nf-done-account">
              <div>
                <dt>Bank</dt>
                <dd>{submitted.transferAccount.bank}</dd>
              </div>
              <div>
                <dt>Account number</dt>
                <dd>{submitted.transferAccount.account_number}</dd>
              </div>
              <div>
                <dt>Account name</dt>
                <dd>{submitted.transferAccount.beneficiary}</dd>
              </div>
              <div>
                <dt>Payment reference</dt>
                <dd>{submitted.reference}</dd>
              </div>
            </dl>
          ) : null}
          <div className="nf-done-actions">
            <button type="button" className="agent-btn agent-btn-primary" onClick={() => navigate('/portal')}>
              Go to overview
            </button>
          </div>
        </div>
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

  const footer = (primary) => (
    <div className="nf-footer">
      <div className="nf-footer-start">
        {step === 0 ? (
          <Link to="/portal/courses" className="agent-btn agent-btn-secondary">
            Courses
          </Link>
        ) : (
          <button type="button" className="agent-btn agent-btn-secondary" onClick={() => go(step - 1)} disabled={submitting}>
            Back
          </button>
        )}
      </div>
      <div className="nf-footer-end">
        <button type="button" className="agent-btn agent-btn-secondary" onClick={onSaveDraft} disabled={saving || submitting}>
          {saving ? <span className="spinner-sm" aria-hidden="true" /> : null}
          {saving ? 'Saving' : 'Save draft'}
        </button>
        {primary}
      </div>
    </div>
  );

  const continueBtn = (
    <button type="button" className="agent-btn agent-btn-primary" onClick={() => go(step + 1)}>
      {step === 3 ? 'Review' : 'Continue'}
    </button>
  );

  return (
    <div className="agent-stack" ref={topRef}>
      <div className="nf-card">
        <div className="nf-head">
          <span className="nf-step-count">
            Step {step + 1} of {STEPS.length}
          </span>
          <h2 className="nf-title">{STEPS[step]}</h2>
          {hasDraft ? <span className="nf-draft-tag">Draft</span> : null}
          <div className="nf-progress" aria-hidden="true">
            {STEPS.map((label, index) => (
              <span key={label} className={`nf-progress-seg${index <= step ? ' is-on' : ''}`} />
            ))}
          </div>
        </div>

        {step === 0 ? (
          <>
            <div className="nf-grid">
              <StepField icon="user" label="Full legal name" required htmlFor="ap-name" error={errors.fullName} hint="Exactly as your passport prints it.">
                <input id="ap-name" className="agent-form-control" autoComplete="name" value={form.fullName} onChange={(event) => update({ fullName: event.target.value })} />
              </StepField>
              <StepField icon="mail" label="Email address" htmlFor="ap-email">
                <input id="ap-email" className="agent-form-control" value={user?.email || ''} readOnly />
              </StepField>
              <StepField icon="chat" label="Phone number" required htmlFor="ap-phone" error={errors.phone}>
                <input id="ap-phone" type="tel" inputMode="tel" className="agent-form-control" autoComplete="tel" value={form.phone} onChange={(event) => update({ phone: event.target.value })} />
              </StepField>
              <StepField icon="pin" label="Country of origin" required labelId="ap-origin-label" error={errors.originCountry}>
                <SearchableSelect options={originNames} value={form.originCountry} onChange={(value) => update({ originCountry: value })} labelledBy="ap-origin-label" />
              </StepField>
            </div>
            <StepField icon="globe" label="Where you want to study" required labelId="ap-dest-label" error={errors.destinationCountry}>
              <SearchableSelect
                options={destinations.map((item) => item.name)}
                value={form.destinationCountry}
                onChange={(value) => update({ destinationCountry: value, institution: '', programs: [], level: null, is_custom_course: false, custom_course: '' })}
                labelledBy="ap-dest-label"
              />
            </StepField>
            {footer(continueBtn)}
          </>
        ) : null}

        {step === 1 ? (
          <>
            <StepField icon="building" label="Schools attended" required htmlFor="ap-schools" error={errors.previousSchools}>
              <input id="ap-schools" className="agent-form-control" value={form.previousSchools} onChange={(event) => update({ previousSchools: event.target.value })} />
            </StepField>
            <div className="nf-grid nf-grid-3">
              <StepField icon="cap" label="Highest qualification" required htmlFor="ap-qual" error={errors.qualification}>
                <select id="ap-qual" className="agent-form-select" value={form.qualification} onChange={(event) => update({ qualification: event.target.value })}>
                  <option value="">Choose</option>
                  {QUALIFICATIONS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </StepField>
              <StepField icon="calendar" label="Year of graduation" required htmlFor="ap-year" error={errors.yearGraduated}>
                <input id="ap-year" type="number" inputMode="numeric" className="agent-form-control" value={form.yearGraduated} onChange={(event) => update({ yearGraduated: event.target.value })} />
              </StepField>
              <StepField icon="medal" label="Grade or GPA" required htmlFor="ap-grade" error={errors.gradeGpa}>
                <input id="ap-grade" className="agent-form-control" value={form.gradeGpa} onChange={(event) => update({ gradeGpa: event.target.value })} />
              </StepField>
            </div>
            {footer(continueBtn)}
          </>
        ) : null}

        {step === 2 ? (
          <>
            <div className="nf-picker">
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
            {errors.course ? <p className="nf-error">{errors.course}</p> : null}
            {footer(continueBtn)}
          </>
        ) : null}

        {step === 3 ? (
          <>
            <p className="nf-lede">Clear, full-page scans. PDF or photo, up to 10MB each. Photos are compressed for you.</p>
            {destinations.find((item) => item.name === form.destinationCountry)?.is_european ? (
              <p className="nf-muted">
                European universities prefer a{' '}
                <a className="gx-link" href="https://europa.eu/europass/en/create-europass-cv" target="_blank" rel="noreferrer">
                  Europass CV
                </a>
                .
              </p>
            ) : null}
            <div className="nf-docs">
              {SLOTS.map((meta) => (
                <div className={`nf-doc${errors[meta.slot] ? ' has-error' : ''}`} key={meta.slot}>
                  <span className="nf-label">
                    <Icon name={meta.icon} size={16} className="nf-label-icon" />
                    <span>{meta.label}</span>
                    <span className="nf-req" aria-hidden="true">*</span>
                  </span>
                  {fileRow(
                    `ap-doc-${meta.slot}`,
                    docName(docs[meta.slot]),
                    async (event) => {
                      const file = await pick(event);
                      if (file) setSlotFile(meta.slot, file);
                    },
                    () => setSlotFile(meta.slot, null),
                  )}
                  {errors[meta.slot] ? <span className="nf-error">{errors[meta.slot]}</span> : null}
                  {meta.slot === 'cv' ? <EuropeanCvTip /> : null}
                </div>
              ))}
            </div>

            <div className="nf-others">
              <div className="nf-others-head">
                <span className="nf-label">
                  <Icon name="paperclip" size={16} className="nf-label-icon" />
                  <span>Other documents</span>
                </span>
                <button type="button" className="agent-btn agent-btn-secondary agent-btn-sm" onClick={addOther}>
                  Add a document
                </button>
              </div>
              {others.length === 0 ? (
                <p className="nf-muted">Optional: English test result, reference letter, birth certificate and so on.</p>
              ) : (
                others.map((item, index) => (
                  <div className="nf-doc nf-doc-other" key={item.slot}>
                    <label className="sr-only" htmlFor={`ap-other-${item.slot}`}>
                      Name of document {index + 1}
                    </label>
                    <input
                      id={`ap-other-${item.slot}`}
                      className="agent-form-control"
                      placeholder="Document name"
                      maxLength={160}
                      value={item.name}
                      onChange={(event) => updateOther(item.slot, { name: event.target.value })}
                    />
                    {fileRow(
                      `ap-other-file-${item.slot}`,
                      docName(item),
                      async (event) => {
                        const file = await pick(event);
                        if (file) updateOther(item.slot, { file });
                      },
                      () => removeOther(item.slot),
                    )}
                  </div>
                ))
              )}
            </div>
            {footer(continueBtn)}
          </>
        ) : null}

        {step === 4 ? (
          <>
            <dl className="nf-review">
              <div>
                <dt>Applicant</dt>
                <dd>{form.fullName}</dd>
              </div>
              <div>
                <dt>From and to</dt>
                <dd>
                  {form.originCountry} to {form.destinationCountry}
                </dd>
              </div>
              <div>
                <dt>Education</dt>
                <dd>
                  {form.qualification}, {form.yearGraduated} · {form.gradeGpa}
                  <small>{form.previousSchools}</small>
                </dd>
              </div>
              <div>
                <dt>University</dt>
                <dd>
                  {isCustomCourse ? 'To be matched by our team' : institution?.name}
                  <small>{isCustomCourse ? form.custom_course : form.programs.map((program) => program.name).join(', ')}</small>
                </dd>
              </div>
              {!isCustomCourse && form.programs[0]?.tuition ? (
                <div>
                  <dt>Tuition</dt>
                  <dd>{formatTuition(form.programs[0].tuition, institution?.currency)}</dd>
                </div>
              ) : null}
              <div className={!isCustomCourse && form.programs[0]?.tuition ? '' : 'nf-review-wide'}>
                <dt>Documents</dt>
                <dd>
                  {[
                    ...SLOTS.filter((meta) => hasDoc(meta.slot)).map((meta) => meta.label),
                    ...others.filter((item) => item.file || item.remote).map((item) => item.name || 'Other document'),
                  ].join(', ') || 'None'}
                </dd>
              </div>
            </dl>

            <div className="nf-fee">
              <div className="nf-fee-row nf-fee-total">
                <span>Application fee</span>
                <span>
                  {feeFree
                    ? 'No fee'
                    : quoteState === 'ready' && quote
                      ? formatMoney(quote.amount + (quote.processing_fee || 0), quote.currency)
                      : quoteState === 'failed'
                        ? (
                          <button type="button" className="nf-link-btn" onClick={loadQuote}>
                            Could not load. Try again
                          </button>
                        )
                        : 'Calculating'}
                </span>
              </div>
              {!feeFree && quoteState === 'ready' && quote?.processing_fee ? (
                <div className="nf-fee-row">
                  <span>Includes card processing</span>
                  <span>{formatMoney(quote.processing_fee, quote.currency)}</span>
                </div>
              ) : null}
            </div>

            {footer(
              <button
                type="button"
                className="agent-btn agent-btn-primary"
                onClick={submit}
                disabled={submitting || (!feeFree && quoteState !== 'ready')}
              >
                {submitting ? <span className="spinner-sm" aria-hidden="true" /> : null}
                {submitting ? 'Submitting' : feeFree ? 'Submit application' : 'Submit and pay'}
              </button>,
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
