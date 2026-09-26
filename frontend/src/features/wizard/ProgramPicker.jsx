import { useMemo, useRef, useState } from 'react';
import Icon from '../../lib/icons';
import { formatMoney, formatTuition } from '../../lib/format';

/**
 * Step 3: one school, then up to two of its courses.
 *
 * Two plain select fields, one at a time. The school field is the only thing on
 * screen until a school is chosen; it then collapses to a single line and the
 * course field takes its place. Nothing else is shown, because everything else
 * is either a decision the applicant has already made or a detail they can read
 * on the course they picked.
 *
 * Courses are grouped into native optgroups by level rather than made into a
 * separate step, which keeps the ordering without adding a third field.
 *
 * The applicant wizard and the partner portal both use this, which is why the
 * selection lives in the parent rather than here.
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
  selection,
  onChange,
  onNotify,
}) {
  const courseFieldRef = useRef(null);
  // The school field stays open until a school is picked, and reopens only when
  // the applicant asks to change it.
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

  const pickInstitution = (slug) => {
    if (!slug) {
      onChange({ institution: null, level: null, programs: [] });
      return;
    }
    if (slug === selection.institution) {
      setSchoolOpen(false);
      return;
    }
    onChange({ institution: slug, level: null, programs: [] });
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
    onChange({ ...selection, programs: [...chosen, program] });
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

  if (!safeInstitutions.length) {
    return (
      <div className="callout callout-info">
        <Icon name="info" size={20} className="callout-icon" strokeWidth={2} />
        <div className="callout-content">
          No partner institutions are listed for {countryName} yet. Choose another
          destination in step 1.
        </div>
      </div>
    );
  }

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
    </div>
  );
}
