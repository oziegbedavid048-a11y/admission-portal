import { useMemo } from 'react';

const MAX_COURSES = 2;

const LEVEL_LABELS = {
  bachelors: "Bachelor's Degrees",
  masters: 'Masters & MBA',
  phd: 'PhD & Doctoral',
  diplomas: 'Diplomas & Certificates',
  other: 'Other Programs',
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
      onChange({
        ...selection,
        institution: null,
        level: null,
        programs: [],
        is_custom_course: false,
      });
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
  };

  const findProgram = (id) => {
    if (!id || !groups.length) return null;
    for (const group of groups) {
      const match = group.programs.find((p) => String(p.id) === String(id));
      if (match) return match;
    }
    return null;
  };

  const addProgram = (program) => {
    if (!program || isChosen(program)) return;
    if (atLimit) {
      onNotify?.(`You can pick at most ${MAX_COURSES} courses per application.`, 'warning');
      return;
    }
    onChange({
      ...selection,
      programs: [...chosen, program],
      is_custom_course: false,
    });
  };

  const removeProgram = (program) => {
    onChange({
      ...selection,
      programs: chosen.filter((item) => item.id !== program.id),
    });
  };

  if (loading) {
    return (
      <div className="empty-block" style={{ padding: '24px 0', textAlign: 'center' }}>
        <span className="spinner" aria-hidden="true" />
      </div>
    );
  }

  // ── Manual / Type Course Mode ──
  if (isCustomMode) {
    return (
      <div className="custom-course-clean">
        <div className="form-group">
          <label className="form-label" htmlFor="custom-course-input">
            Course / Programme <span className="req">*</span>
          </label>
          <input
            id="custom-course-input"
            type="text"
            className="form-control"
            placeholder="e.g. Master of Business Administration, Computer Science"
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
        </div>

        {safeInstitutions.length > 0 ? (
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              onClick={() =>
                onChange({
                  ...selection,
                  is_custom_course: false,
                  custom_course: '',
                })
              }
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--brand-600, #2563eb)',
                fontSize: '0.875rem',
                textDecoration: 'underline',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              &larr; Select from partner institutions in {countryName}
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  // ── Standard Dropdown Mode ──
  return (
    <div className="picker-dropdown-mode">
      {/* 1. School Dropdown */}
      <div className="form-group">
        <label className="form-label" htmlFor="picker_school">
          Institution / School <span className="req">*</span>
        </label>
        <select
          id="picker_school"
          className="form-control"
          value={selection.institution || ''}
          onChange={(e) => pickInstitution(e.target.value)}
        >
          <option value="">Select a school</option>
          {safeInstitutions.map((item) => (
            <option key={item.slug} value={item.slug}>
              {item.name} {item.location ? `— ${item.location}` : ''}
            </option>
          ))}
        </select>
      </div>

      {/* 2. Course Dropdown */}
      <div className="form-group">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <label className="form-label" htmlFor="picker_course" style={{ margin: 0 }}>
            Course / Programme <span className="req">*</span>
          </label>
          {chosen.length > 0 && (
            <span style={{ fontSize: '0.8125rem', color: 'var(--g-ink-2, #64748b)' }}>
              {chosen.length} of {MAX_COURSES} selected
            </span>
          )}
        </div>

        <select
          id="picker_course"
          className="form-control"
          value=""
          disabled={!institution || atLimit}
          onChange={(e) => {
            const prog = findProgram(e.target.value);
            if (prog) addProgram(prog);
          }}
        >
          <option value="">
            {!institution
              ? 'Select an institution first'
              : atLimit
                ? `Maximum ${MAX_COURSES} courses selected`
                : 'Select a course'}
          </option>
          {groups.map((group) => (
            <optgroup key={group.key} label={group.label}>
              {group.programs.map((prog) => (
                <option key={prog.id} value={prog.id} disabled={isChosen(prog)}>
                  {prog.name}
                  {prog.duration ? ` (${prog.duration})` : ''}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {/* Selected Courses List */}
      {chosen.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {chosen.map((prog) => (
              <div
                key={prog.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: 'var(--g-surface-2, #f8fafc)',
                  border: '1px solid var(--g-line, #e2e8f0)',
                  borderRadius: 6,
                  fontSize: '0.875rem',
                }}
              >
                <div>
                  <strong>{prog.name}</strong>
                  {prog.duration ? (
                    <span style={{ color: 'var(--g-ink-2, #64748b)', marginLeft: 8 }}>
                      ({prog.duration})
                    </span>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => removeProgram(prog)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#dc2626',
                    fontSize: '0.8125rem',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clean Link: Type Manually */}
      <div style={{ marginTop: 12 }}>
        <button
          type="button"
          onClick={() =>
            onChange({
              institution: '',
              level: null,
              programs: [],
              is_custom_course: true,
              custom_course: selection.custom_course || '',
            })
          }
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--brand-600, #2563eb)',
            fontSize: '0.875rem',
            textDecoration: 'underline',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          Can&apos;t find your institution or course? Type manually
        </button>
      </div>
    </div>
  );
}
