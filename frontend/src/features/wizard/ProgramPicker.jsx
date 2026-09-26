import { useMemo, useRef, useState } from 'react';
import Icon from '../../lib/icons';
import { formatMoney, formatTuition } from '../../lib/format';

/**
 * Step 3: one school, then up to two of its courses, OR manual custom course entry.
 *
 * If a country has no catalog institutions listed, or if the applicant cannot
 * find their intended course in the partner list, they can type their course
 * directly. Custom courses waive application payment at checkout and trigger direct
 * admissions desk follow-up.
 */

const MAX_COURSES = 2;

const LEVEL_LABELS = {
  bachelors: "Bachelor's degrees",
  masters: 'Masters & MBA',
  phd: 'PhD & doctoral',
  diplomas: 'Diplomas & certificates',
  other: 'Other programmes',
};

const LEVEL_ORDER = ['bachelors', 'masters', 'phd', 'diplomas', 'other'];

export default function ProgramPicker({
  institutions,
  loading,
  countryName,
  selection = {},
  onChange,
  onNotify,
}) {
  const courseFieldRef = useRef(null);
  const [schoolOpen, setSchoolOpen] = useState(!selection.institution);

  const safeInstitutions = Array.isArray(institutions) ? institutions : [];
  const institution = useMemo(
    () => safeInstitutions.find((item) => item.slug === selection?.institution) || null,
    [safeInstitutions, selection?.institution],
  );

  const groups = useMemo(() => {
    if (!institution || !Array.isArray(institution.programs)) return [];
    const buckets = new Map();
    institution.programs.forEach((program) => {
      const key = LEVEL_LABELS[program.level] ? program.level : 'other';
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(program);
    });
    return LEVEL_ORDER.filter((key) => buckets.has(key)).map((key) => ({
      key,
      label: LEVEL_LABELS[key],
      programs: buckets.get(key),
    }));
  }, [institution]);

  const chosen = selection.programs || [];
  const isChosen = (program) => chosen.some((item) => item.id === program.id);
  const atLimit = chosen.length >= MAX_COURSES;
  const isCustomMode = !safeInstitutions.length || Boolean(selection?.is_custom_course);

  const pickInstitution = (slug) => {
    if (!slug) {
      onChange({ ...selection, institution: null, level: null, programs: [], is_custom_course: false });
      return;
    }
    if (slug === selection.institution) {
      setSchoolOpen(false);
      return;
    }
    onChange({
      ...selection,
      institution: slug,
      level: null,
      programs: [],
      is_custom_course: false,
      custom_course: '',
    });
    setSchoolOpen(false);
    window.setTimeout(
      () => courseFieldRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }),
      260,
    );
  };

  const addProgram = (program) => {
    if (!program || isChosen(program)) return;
    if (atLimit) {
      onNotify?.(`You can pick at most ${MAX_COURSES} courses per institution.`, 'warning');
      return;
    }
    onChange({ ...selection, programs: [...chosen, program], is_custom_course: false });
  };

  const removeProgram = (program) => {
    onChange({ ...selection, programs: chosen.filter((item) => item.id !== program.id) });
  };

  const findProgram = (id) => {
    for (const group of groups) {
      const match = group.programs.find((program) => String(program.id) === id);
      if (match) return match;
    }
    return null;
  };

  if (loading) {
    return (
      <div className="empty-block">
        <span className="spinner" aria-hidden="true" />
      </div>
    );
  }

  // ── Manual / Custom Course Mode ──
  if (isCustomMode) {
    return (
      <div className="picker">
        {safeInstitutions.length > 0 ? (
          <div style={{ marginBottom: 14 }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() =>
                onChange({
                  ...selection,
                  is_custom_course: false,
                  custom_course: '',
                })
              }
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.85rem',
                color: 'var(--brand-700)',
                fontWeight: 600,
                padding: '6px 12px',
              }}
            >
              <Icon name="arrowLeft" size={14} strokeWidth={2} />
              Switch back to {countryName} partner universities ({safeInstitutions.length})
            </button>
          </div>
        ) : null}

        <div
          style={{
            background: 'var(--slate-50, #f8fafc)',
            border: '1.5px solid var(--slate-200, #e2e8f0)',
            borderRadius: '12px',
            padding: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '18px' }}>
            <div
              style={{
                background: '#eff6ff',
                color: '#2563eb',
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Icon name="cap" size={22} strokeWidth={2} />
            </div>
            <div>
              <h4 style={{ margin: '0 0 4px', fontSize: '1.05rem', color: 'var(--slate-900)', fontWeight: 700 }}>
                Specify your desired course in {countryName}
              </h4>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--slate-600)', lineHeight: 1.5 }}>
                {safeInstitutions.length === 0
                  ? `There are no pre-cataloged partner universities for ${countryName} yet. Type your desired course or degree programme below to continue. Our admissions desk will review your submission and contact you directly.`
                  : 'Cannot find your desired university or course in the catalog? Enter the course you want to study below and our team will assist you.'}
              </p>
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="custom-course-input" style={{ fontWeight: 600 }}>
              Course / Degree Programme <span className="req">*</span>
            </label>
            <input
              id="custom-course-input"
              type="text"
              className="form-control"
              placeholder="e.g. MSc Artificial Intelligence, BSc Nursing, MBA, LLB Law..."
              value={selection.custom_course || ''}
              onChange={(e) =>
                onChange({
                  ...selection,
                  institution: '',
                  level: null,
                  programs: [],
                  is_custom_course: true,
                  custom_course: e.target.value,
                })
              }
              autoFocus
            />
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginTop: '12px',
                padding: '10px 14px',
                background: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: '8px',
                fontSize: '0.8125rem',
                color: '#166534',
                fontWeight: 600,
              }}
            >
              <Icon name="checkCircle" size={16} strokeWidth={2.2} />
              <span>
                Zero application fee: No payment is required for custom course submissions. You will receive your login details immediately upon completing registration.
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Standard Catalog Mode ──
  return (
    <div className="picker">
      {schoolOpen || !institution ? (
        <div className="picker-field">
          <label className="picker-label" htmlFor="picker-school">
            School
          </label>
          <div className="picker-select-wrap">
            <select
              id="picker-school"
              className="picker-select"
              value={selection.institution || ''}
              onChange={(event) => pickInstitution(event.target.value)}
            >
              <option value="">Select a school</option>
              {safeInstitutions.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name} &mdash; {item.location}
                </option>
              ))}
            </select>
            <Icon name="chevronDown" size={18} strokeWidth={2.2} className="picker-chevron" />
          </div>
        </div>
      ) : (
        <div className="picker-chosen">
          <div className="picker-chosen-text">
            <span className="picker-chosen-label">School</span>
            <span className="picker-chosen-value">{institution.name}</span>
            <span className="picker-chosen-meta">
              {institution.location}
              {institution.is_fee_free
                ? ' · Free application'
                : ` · Application fee ${formatMoney(
                    institution.application_fee,
                    institution.currency,
                  )}`}
            </span>
          </div>
          <button type="button" className="picker-change" onClick={() => setSchoolOpen(true)}>
            Change
          </button>
        </div>
      )}

      {/* Kept visible while the school field is reopened, so changing your mind
          about changing school is not a dead end. */}
      {institution ? (
        <div className="picker-field picker-reveal" ref={courseFieldRef}>
          <label className="picker-label" htmlFor="picker-course">
            Course
            <span className="picker-count">
              {chosen.length} of {MAX_COURSES}
            </span>
          </label>
          <div className="picker-select-wrap">
            <select
              id="picker-course"
              className="picker-select"
              value=""
              disabled={atLimit}
              onChange={(event) => addProgram(findProgram(event.target.value))}
            >
              <option value="">
                {atLimit ? `Maximum ${MAX_COURSES} courses selected` : 'Select a course'}
              </option>
              {groups.map((group) => (
                <optgroup key={group.key} label={group.label}>
                  {group.programs.map((program) => (
                    <option key={program.id} value={program.id} disabled={isChosen(program)}>
                      {program.name}
                      {program.duration ? ` (${program.duration})` : ''}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <Icon name="chevronDown" size={18} strokeWidth={2.2} className="picker-chevron" />
          </div>

          {chosen.length ? (
            <ul className="picker-chosen-list">
              {chosen.map((program) => {
                const meta = [
                  program.duration,
                  program.qualification_level,
                  formatTuition(program.tuition, institution.currency),
                  program.intake ? `Intake ${program.intake}` : null,
                ].filter(Boolean);

                return (
                  <li className="picker-chosen-item" key={program.id}>
                    <div className="picker-chosen-text">
                      <span className="picker-chosen-value">{program.name}</span>
                      {meta.length ? (
                        <span className="picker-chosen-meta">{meta.join(' · ')}</span>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      className="picker-change"
                      onClick={() => removeProgram(program)}
                      aria-label={`Remove ${program.name}`}
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      ) : null}

      <div
        style={{
          marginTop: 20,
          paddingTop: 16,
          borderTop: '1px dashed var(--slate-200, #e2e8f0)',
          textAlign: 'center',
        }}
      >
        <span style={{ fontSize: '0.875rem', color: 'var(--slate-500)' }}>
          Can't find your desired institution or course?{' '}
        </span>
        <button
          type="button"
          className="btn btn-link"
          style={{
            fontSize: '0.875rem',
            fontWeight: 700,
            color: 'var(--brand-700)',
            padding: 0,
            textDecoration: 'underline',
            cursor: 'pointer',
          }}
          onClick={() =>
            onChange({
              institution: '',
              level: null,
              programs: [],
              is_custom_course: true,
              custom_course: selection.custom_course || '',
            })
          }
        >
          Type your course manually
        </button>
      </div>
    </div>
  );
}
