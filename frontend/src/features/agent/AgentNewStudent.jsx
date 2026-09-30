import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import SearchableSelect from '../../components/ui/SearchableSelect';
import Icon from '../../lib/icons';
import { formatMoney } from '../../lib/format';
import { compressImageFile } from '../../lib/compress';
import { errorMessage } from '../../api/client';
import { applications, catalog, partners, payments } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import { useCatalog, useInstitutions } from '../../hooks/useCatalog';
import { ALL_WORLD_COUNTRIES } from '../../lib/countries';
import ProgramPicker from '../wizard/ProgramPicker';
import FeePayment from './FeePayment';
import { downloadStudentSummary } from './studentSummary';

const STEPS = ['Student details', 'Academic background', 'University and course', 'Documents', 'Review and register'];

const QUALIFICATIONS = ["Bachelor's Degree", "Master's Degree", 'HND', 'OND', 'SSCE / High School'];

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
};

// The three named documents. Anything else goes under Other documents.
const SLOTS = [
  { slot: 'passport', kind: 'passport', name: 'International passport data page', icon: 'passport' },
  { slot: 'academic', kind: 'academic', name: 'Academic documents & transcripts', icon: 'document' },
  { slot: 'cv', kind: 'cv', name: 'Curriculum vitae', icon: 'resume' },
];

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,application/pdf,image/*';
const EMPTY_DOCS = { passport: null, academic: null, cv: null };

/** A form field with its icon, label and an inline asterisk when required. */
function Field({ icon, label, required, htmlFor, labelId, children }) {
  const Tag = htmlFor ? 'label' : 'span';
  return (
    <div className="nf-field">
      <Tag className="nf-label" htmlFor={htmlFor} id={labelId}>
        {icon ? <Icon name={icon} size={16} className="nf-label-icon" /> : null}
        <span>{label}</span>
        {required ? <span className="nf-req" aria-hidden="true">*</span> : null}
      </Tag>
      {children}
    </div>
  );
}

/**
 * Registering a student on their behalf, in five steps, then paying the fee.
 *
 * The form can be saved as a draft at any step and finished later from
 * Students › Drafts; a draft keeps its documents too. Once registered, the fee
 * is paid with Paystack or, for agents in Nigeria, by transfer to a company
 * account.
 */
export default function AgentNewStudent() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(BLANK);
  // Each document is { file } before it is uploaded and { remote } once it
  // sits on a draft.
  const [docs, setDocs] = useState(EMPTY_DOCS);
  const [others, setOthers] = useState([]);
  const [removedRemote, setRemovedRemote] = useState([]);
  const [draftId, setDraftId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [quote, setQuote] = useState(null);
  const [created, setCreated] = useState(null);
  const [done, setDone] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const shellRef = useRef(null);
  const otherCounter = useRef(1);

  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const { originNames } = useCatalog();
  const { institutions, loading: institutionsLoading } = useInstitutions(form.destinationCountry);

  const safeInstitutions = Array.isArray(institutions) ? institutions : [];
  const institution = useMemo(
    () => safeInstitutions.find((item) => item.slug === form.institution) || null,
    [safeInstitutions, form.institution],
  );
  const isCustomCourse = Boolean(form.is_custom_course || (safeInstitutions.length === 0 && !institutionsLoading));

  const update = (patch) => setForm((current) => ({ ...current, ...patch }));

  // Arriving from the course browser with a university already chosen.
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

  // Continuing a draft.
  useEffect(() => {
    const id = location.state?.draftId;
    if (!id) return;
    let cancelled = false;
    partners
      .draft(id)
      .then(({ data }) => {
        if (cancelled) return;
        setDraftId(data.id);
        setForm({ ...BLANK, ...(data.data?.form || {}) });
        setStep(Math.min(Math.max(data.step || 1, 1), 5));
        const nextDocs = { ...EMPTY_DOCS };
        const nextOthers = [];
        (data.files || []).forEach((item) => {
          if (item.slot in nextDocs) nextDocs[item.slot] = { remote: item };
          else nextOthers.push({ slot: item.slot, name: item.name, remote: item });
        });
        const highest = nextOthers.reduce((max, item) => Math.max(max, Number(item.slot.split('-')[1]) || 0), 0);
        otherCounter.current = highest + 1;
        setDocs(nextDocs);
        setOthers(nextOthers);
      })
      .catch(() => {
        if (!cancelled) toast.error('Could not open that draft.');
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state?.draftId]);

  // The fee, in the student's currency, for the review step.
  useEffect(() => {
    if (step !== 5 || !form.originCountry) return undefined;
    let cancelled = false;
    catalog
      .feeQuote(form.originCountry, form.institution)
      .then(({ data }) => {
        if (cancelled) return;
        const waived = isCustomCourse || (institution ? institution.is_fee_free : false);
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
  }, [step, form.originCountry, form.institution, institution, isCustomCourse]);

  const scrollTop = () =>
    window.setTimeout(() => shellRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 20);

  const validate = (which) => {
    if (which === 1) {
      if (!form.fullName.trim()) return toast.warning('Enter the student’s full name.') || false;
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()))
        return toast.warning('Enter a valid student email address.') || false;
      if (!form.phone.trim()) return toast.warning('Enter a phone number.') || false;
    }
    if (which === 2) {
      if (!form.previousSchools.trim()) return toast.warning('List the institutions they attended.') || false;
      const year = Number(form.yearGraduated);
      if (!year || year < 1960 || year > 2035) return toast.warning('Enter a valid graduation year.') || false;
      if (!form.gradeGpa.trim()) return toast.warning('Enter their grade or CGPA.') || false;
    }
    if (which === 3) {
      if (isCustomCourse) {
        if (!form.custom_course?.trim()) return toast.warning('Enter the course the student wants.') || false;
      } else {
        if (!form.institution) return toast.warning('Choose a university.') || false;
        if (!form.programs.length) return toast.warning('Choose at least one course.') || false;
      }
    }
    if (which === 4) {
      const unnamed = others.find((item) => (item.file || item.remote) && !item.name.trim());
      if (unnamed) return toast.warning('Name each of the other documents.') || false;
    }
    return true;
  };

  const goTo = (target) => {
    if (target < 1 || target > STEPS.length) return;
    if (target > step) {
      for (let current = step; current < target; current += 1) {
        if (!validate(current)) return;
      }
    }
    setStep(target);
    scrollTop();
  };

  // ── Documents ──

  const pick = async (event) => {
    const raw = event.target.files?.[0] || null;
    event.target.value = '';
    return raw ? compressImageFile(raw) : null;
  };

  const setSlotFile = (slot, file) => {
    setDocs((current) => {
      const previous = current[slot];
      if (previous?.remote) setRemovedRemote((list) => [...list, previous.remote.id]);
      return { ...current, [slot]: file ? { file } : null };
    });
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

  // ── Drafts ──

  const saveDraft = async () => {
    const payload = { step, data: { form } };
    let id = draftId;
    if (id) {
      await partners.updateDraft(id, payload);
    } else {
      const { data } = await partners.createDraft(payload);
      id = data.id;
      setDraftId(id);
    }

    await Promise.all(removedRemote.map((fileId) => partners.deleteDraftFile(id, fileId).catch(() => null)));
    setRemovedRemote([]);

    const nextDocs = { ...docs };
    for (const meta of SLOTS) {
      const entry = docs[meta.slot];
      if (entry?.file) {
        const { data } = await partners.uploadDraftFile(id, { ...meta, file: entry.file });
        nextDocs[meta.slot] = { remote: data };
      }
    }
    const nextOthers = [];
    for (const item of others) {
      if (item.file) {
        const { data } = await partners.uploadDraftFile(id, {
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
    return id;
  };

  const onSaveDraft = async () => {
    if (!form.fullName.trim()) {
      toast.warning('Enter the student’s name before saving a draft.');
      return;
    }
    setSaving(true);
    try {
      await saveDraft();
      toast.success('Draft saved. Find it under Students › Drafts.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not save the draft.'));
    } finally {
      setSaving(false);
    }
  };

  // ── Submit ──

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
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
        notes: '',
      };

      let student;
      if (draftId) {
        // Every document goes onto the draft first, and the draft's documents
        // move to the new application in the same request.
        const id = await saveDraft();
        ({ data: student } = await partners.createStudent({ ...payload, draft: id }));
      } else {
        ({ data: student } = await partners.createStudent(payload));
        const queue = [
          ...SLOTS.filter((meta) => docs[meta.slot]?.file).map((meta) => ({
            file: docs[meta.slot].file,
            kind: meta.kind,
            name: meta.name,
          })),
          ...others
            .filter((item) => item.file)
            .map((item) => ({ file: item.file, kind: 'other', name: item.name.trim() || 'Other document' })),
        ];
        if (queue.length) {
          const results = await Promise.allSettled(
            queue.map((item) => applications.uploadDocument(student.reference, item)),
          );
          const failed = results.filter((result) => result.status === 'rejected').length;
          if (failed) toast.warning(`${failed} document(s) did not upload. Add them from the student’s file.`);
        }
      }

      setCreated(student);
      if (quote?.waived) {
        // Records the waiver so the file counts as settled and the summary
        // can be downloaded.
        await payments.checkout(student.reference, 'agent').catch(() => null);
        setDone({ kind: 'waived' });
      } else {
        setStep(6);
      }
      scrollTop();
    } catch (error) {
      toast.error(errorMessage(error, 'Could not register that student.'));
    } finally {
      setBusy(false);
    }
  };

  const resetAll = () => {
    setCreated(null);
    setDone(null);
    setDraftId(null);
    setForm(BLANK);
    setDocs(EMPTY_DOCS);
    setOthers([]);
    setRemovedRemote([]);
    setQuote(null);
    setStep(1);
    navigate('/agent/students/new', { replace: true, state: null });
    scrollTop();
  };

  const summary = async () => {
    setDownloading(true);
    try {
      await downloadStudentSummary(created.reference);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not download the summary.'));
    } finally {
      setDownloading(false);
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

  const footer = (back, next) => (
    <div className="nf-footer">
      <div className="nf-footer-start">
        {back ? (
          <button type="button" className="agent-btn agent-btn-secondary" onClick={back}>
            Back
          </button>
        ) : (
          <button type="button" className="agent-btn agent-btn-secondary" onClick={() => navigate('/agent/students')}>
            Cancel
          </button>
        )}
      </div>
      <div className="nf-footer-end">
        <button type="button" className="agent-btn agent-btn-secondary" onClick={onSaveDraft} disabled={saving || busy}>
          {saving ? <span className="spinner-sm" aria-hidden="true" /> : null}
          {saving ? 'Saving' : 'Save draft'}
        </button>
        {next}
      </div>
    </div>
  );

  const continueBtn = (target, label = 'Continue') => (
    <button type="button" className="agent-btn agent-btn-primary" onClick={() => goTo(target)}>
      {label}
    </button>
  );

  // ── Finished ──

  if (done) {
    return (
      <div className="agent-stack" ref={shellRef}>
        <div className="nf-card nf-done">
          <span className={`nf-done-mark${done.kind === 'review' ? ' is-wait' : ''}`} aria-hidden="true">
            <Icon name={done.kind === 'review' ? 'clock' : 'check'} size={26} strokeWidth={2.4} />
          </span>
          <h2>{done.kind === 'review' ? 'Receipt sent' : 'Student registered'}</h2>
          <p className="nf-done-lede">
            {done.kind === 'review'
              ? `We are checking the transfer for ${created.full_name}. You will get an email once it is confirmed.`
              : `${created.full_name} is registered. This university does not charge an application fee.`}
          </p>
          <dl className="nf-done-facts">
            <div>
              <dt>Application reference</dt>
              <dd>{created.reference}</dd>
            </div>
            <div>
              <dt>Payment</dt>
              <dd>{done.kind === 'review' ? 'Awaiting confirmation' : 'No fee'}</dd>
            </div>
          </dl>
          <div className="nf-done-actions">
            {done.kind === 'waived' ? (
              <button type="button" className="agent-btn agent-btn-primary" onClick={summary} disabled={downloading}>
                {downloading ? <span className="spinner-sm" aria-hidden="true" /> : null}
                Download student summary
              </button>
            ) : null}
            <button type="button" className="agent-btn agent-btn-secondary" onClick={() => navigate('/agent/students')}>
              Go to students
            </button>
            <button type="button" className="agent-btn agent-btn-secondary" onClick={resetAll}>
              Register another
            </button>
          </div>
        </div>
      </div>
    );
  }

  const heading = step === 6 ? 'Payment' : STEPS[step - 1];

  return (
    <div className="agent-stack" ref={shellRef}>
      <div className="nf-card">
        <div className="nf-head">
          <span className="nf-step-count">{step === 6 ? 'Final step' : `Step ${step} of ${STEPS.length}`}</span>
          <h2 className="nf-title">{heading}</h2>
          {draftId && step < 6 ? <span className="nf-draft-tag">Draft</span> : null}
          <div className="nf-progress" aria-hidden="true">
            {STEPS.map((label, index) => (
              <span key={label} className={`nf-progress-seg${index < Math.min(step, 5) ? ' is-on' : ''}`} />
            ))}
          </div>
        </div>

        {step === 1 ? (
          <>
            <div className="nf-grid">
              <Field icon="user" label="Full legal name" required htmlFor="st-name">
                <input
                  id="st-name"
                  className="agent-form-control"
                  autoComplete="off"
                  value={form.fullName}
                  onChange={(event) => update({ fullName: event.target.value })}
                />
              </Field>
              <Field icon="mail" label="Student email" required htmlFor="st-email">
                <input
                  id="st-email"
                  type="email"
                  inputMode="email"
                  autoComplete="off"
                  className="agent-form-control"
                  value={form.email}
                  onChange={(event) => update({ email: event.target.value })}
                />
              </Field>
              <Field icon="chat" label="Phone or WhatsApp" required htmlFor="st-phone">
                <input
                  id="st-phone"
                  type="tel"
                  inputMode="tel"
                  className="agent-form-control"
                  value={form.phone}
                  onChange={(event) => update({ phone: event.target.value })}
                />
              </Field>
              <Field icon="pin" label="Country of origin" required labelId="st-origin-label">
                <SearchableSelect
                  options={originNames}
                  value={form.originCountry}
                  onChange={(value) => update({ originCountry: value })}
                  labelledBy="st-origin-label"
                />
              </Field>
            </div>
            <Field icon="globe" label="Destination country" required labelId="st-dest-label">
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
                labelledBy="st-dest-label"
              />
            </Field>
            {footer(null, continueBtn(2))}
          </>
        ) : null}

        {step === 2 ? (
          <>
            <Field icon="building" label="Institutions attended" required htmlFor="st-prev">
              <input
                id="st-prev"
                className="agent-form-control"
                value={form.previousSchools}
                onChange={(event) => update({ previousSchools: event.target.value })}
              />
            </Field>
            <div className="nf-grid nf-grid-3">
              <Field icon="cap" label="Highest qualification" required htmlFor="st-qual">
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
              </Field>
              <Field icon="calendar" label="Graduation year" required htmlFor="st-year">
                <input
                  id="st-year"
                  type="number"
                  inputMode="numeric"
                  min="1960"
                  max="2035"
                  className="agent-form-control"
                  value={form.yearGraduated}
                  onChange={(event) => update({ yearGraduated: event.target.value })}
                />
              </Field>
              <Field icon="medal" label="Grade or CGPA" required htmlFor="st-gpa">
                <input
                  id="st-gpa"
                  className="agent-form-control"
                  value={form.gradeGpa}
                  onChange={(event) => update({ gradeGpa: event.target.value })}
                />
              </Field>
            </div>
            {footer(() => goTo(1), continueBtn(3))}
          </>
        ) : null}

        {step === 3 ? (
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
                onChange={(next) => update(next)}
                onNotify={(message, type) => toast.toast(message, type)}
              />
            </div>
            {footer(() => goTo(2), continueBtn(4))}
          </>
        ) : null}

        {step === 4 ? (
          <>
            <p className="nf-lede">PDF or photo, up to 10MB each. Anything missing can be added later.</p>
            <div className="nf-docs">
              {SLOTS.map((meta) => (
                <div className="nf-doc" key={meta.slot}>
                  <span className="nf-label">
                    <Icon name={meta.icon} size={16} className="nf-label-icon" />
                    <span>{meta.name}</span>
                  </span>
                  {fileRow(
                    `doc-${meta.slot}`,
                    docName(docs[meta.slot]),
                    async (event) => {
                      const file = await pick(event);
                      if (file) setSlotFile(meta.slot, file);
                    },
                    () => setSlotFile(meta.slot, null),
                  )}
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
                <p className="nf-muted">Birth certificate, reference letter, English test result and so on.</p>
              ) : (
                others.map((item, index) => (
                  <div className="nf-doc nf-doc-other" key={item.slot}>
                    <label className="sr-only" htmlFor={`other-name-${item.slot}`}>
                      Name of document {index + 1}
                    </label>
                    <input
                      id={`other-name-${item.slot}`}
                      className="agent-form-control"
                      placeholder="Document name"
                      maxLength={160}
                      value={item.name}
                      onChange={(event) => updateOther(item.slot, { name: event.target.value })}
                    />
                    {fileRow(
                      `other-file-${item.slot}`,
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
            {footer(() => goTo(3), continueBtn(5, 'Review'))}
          </>
        ) : null}

        {step === 5 ? (
          <>
            <dl className="nf-review">
              <div>
                <dt>Student</dt>
                <dd>{form.fullName}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{form.email}</dd>
              </div>
              <div>
                <dt>Phone</dt>
                <dd>{form.phone}</dd>
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
                  {isCustomCourse ? 'To be matched by our team' : institution?.name || 'Not chosen'}
                  <small>
                    {isCustomCourse
                      ? form.custom_course
                      : form.programs.map((program) => program.name).join(' and ')}
                  </small>
                </dd>
              </div>
              <div className="nf-review-wide">
                <dt>Documents</dt>
                <dd>
                  {[
                    ...SLOTS.filter((meta) => docs[meta.slot]).map((meta) => meta.name),
                    ...others.filter((item) => item.file || item.remote).map((item) => item.name || 'Other document'),
                  ].join(', ') || 'None yet'}
                </dd>
              </div>
            </dl>

            <div className="nf-fee">
              <div className="nf-fee-row">
                <span>Application fee</span>
                <span>{quote ? formatMoney(quote.amount, quote.currency) : 'Calculating'}</span>
              </div>
              {quote && !quote.waived && Number(quote.processing_fee) > 0 ? (
                <div className="nf-fee-row">
                  <span>Card processing (Paystack only)</span>
                  <span>{formatMoney(quote.processing_fee, quote.currency)}</span>
                </div>
              ) : null}
              <div className="nf-fee-row nf-fee-total">
                <span>{quote?.waived ? 'No fee for this university' : 'Paid on the next step'}</span>
                <span>{quote ? formatMoney(quote.total, quote.currency) : ''}</span>
              </div>
            </div>

            {footer(
              () => goTo(4),
              <button type="button" className="agent-btn agent-btn-primary" onClick={submit} disabled={busy || !quote}>
                {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
                {busy ? 'Registering' : quote?.waived ? 'Register student' : 'Register and pay'}
              </button>,
            )}
          </>
        ) : null}

        {step === 6 && created ? (
          <>
            <p className="nf-lede">
              <strong>{created.full_name}</strong> is registered as <strong>{created.reference}</strong>. Pay the
              application fee to send the file to the admissions desk.
            </p>
            <FeePayment reference={created.reference} onTransferSent={() => setDone({ kind: 'review' })} />
            <div className="nf-footer nf-footer-single">
              <button type="button" className="nf-link-btn" onClick={() => navigate('/agent/students')}>
                Pay later from Students
              </button>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
