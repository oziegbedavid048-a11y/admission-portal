import { useMemo, useRef, useState } from 'react';
import Icon from '../../lib/icons';
import { formatMoney, formatTuition } from '../../lib/format';

/**
 * Step 3: Institution and Course Selection.
 *
 * Provides instant course search, school filtering, clear course cards,
 * and seamless fallback for custom course input when no school is listed or
 * when an applicant wants a course not in the partner list.
 */

const MAX_COURSES = 2;

const LEVEL_LABELS = {
  bachelors: "Bachelor's Degrees",
  masters: 'Masters & MBA',
  phd: 'PhD & Doctoral',
  diplomas: 'Diplomas & Certificates',
  other: 'Other Academic Programs',
};

export default function ProgramPicker({
  institutions,
  loading,
  countryName,
  selection = {},
  onChange,
  onNotify,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSchoolFilter, setSelectedSchoolFilter] = useState('all');
  const courseFieldRef = useRef(null);

  const safeInstitutions = Array.isArray(institutions) ? institutions : [];

  // Flatten all courses across all institutions for this country
  const allCoursesWithSchool = useMemo(() => {
    const list = [];
    safeInstitutions.forEach((inst) => {
      if (Array.isArray(inst.programs)) {
        inst.programs.forEach((prog) => {
          list.push({
            ...prog,
            institutionSlug: inst.slug,
            institutionName: inst.name,
            institutionLocation: inst.location,
            currency: inst.currency,
            applicationFee: inst.application_fee,
            isFeeFree: inst.is_fee_free,
          });
        });
      }
    });
    return list;
  }, [safeInstitutions]);

  const chosen = selection.programs || [];
  const isChosen = (program) => chosen.some((item) => item.id === program.id);
  const atLimit = chosen.length >= MAX_COURSES;
  const isCustomMode = !safeInstitutions.length || Boolean(selection?.is_custom_course);

  // Filtered courses based on school tab and search query
  const filteredCourses = useMemo(() => {
    let result = allCoursesWithSchool;
    if (selectedSchoolFilter !== 'all') {
      result = result.filter((c) => c.institutionSlug === selectedSchoolFilter);
    }
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.institutionName && c.institutionName.toLowerCase().includes(q)) ||
          (c.qualification_level && c.qualification_level.toLowerCase().includes(q)) ||
          (c.intake && c.intake.toLowerCase().includes(q)),
      );
    }
    return result;
  }, [allCoursesWithSchool, selectedSchoolFilter, searchQuery]);

  const addProgram = (program) => {
    if (!program || isChosen(program)) return;
    if (atLimit) {
      onNotify?.(`You can pick at most ${MAX_COURSES} courses per application.`, 'warning');
      return;
    }

    // Set institution from the chosen course if not already set or matching
    onChange({
      ...selection,
      institution: program.institutionSlug || selection.institution,
      programs: [...chosen, program],
      is_custom_course: false,
    });
  };

  const removeProgram = (program) => {
    const remaining = chosen.filter((item) => item.id !== program.id);
    onChange({
      ...selection,
      programs: remaining,
      institution: remaining.length > 0 ? (remaining[0].institutionSlug || selection.institution) : '',
    });
  };

  if (loading) {
    return (
      <div className="empty-block" style={{ padding: '40px 0', textAlign: 'center' }}>
        <span className="spinner" aria-hidden="true" />
        <p style={{ marginTop: 12, color: 'var(--g-ink-2, #64748b)', fontSize: '0.875rem' }}>
          Loading universities and courses for {countryName}...
        </p>
      </div>
    );
  }

  // ── Manual / Custom Course Mode ──
  if (isCustomMode) {
    return (
      <div className="picker">
        {safeInstitutions.length > 0 ? (
          <div style={{ marginBottom: 16 }}>
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
                color: 'var(--brand-600, #2563eb)',
                fontWeight: 600,
                padding: '6px 12px',
                cursor: 'pointer',
              }}
            >
              <Icon name="arrowLeft" size={14} strokeWidth={2} />
              Switch back to {countryName} catalogued universities ({safeInstitutions.length} schools, {allCoursesWithSchool.length} courses)
            </button>
          </div>
        ) : null}

        <div
          style={{
            background: 'var(--g-surface-2, #f8fafc)',
            border: '1.5px solid var(--g-line, #e2e8f0)',
            borderRadius: '12px',
            padding: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '18px' }}>
            <div
              style={{
                background: 'rgba(37, 99, 235, 0.1)',
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
              <h4 style={{ margin: '0 0 4px', fontSize: '1.05rem', color: '#0f172a', fontWeight: 700 }}>
                Specify your desired course in {countryName}
              </h4>
              <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b', lineHeight: 1.5 }}>
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
              placeholder="e.g. MSc Artificial Intelligence, BSc Nursing, MBA, LLB Law, Medicine..."
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
                color: '#15803d',
                fontWeight: 600,
              }}
            >
              <Icon name="checkCircle" size={16} strokeWidth={2.2} />
              <span>
                Zero application fee: No payment is required for custom course submissions. You will receive your student portal login immediately upon completing registration.
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Standard Catalog Mode (With Search & Visual Course Selection) ──
  return (
    <div className="picker" ref={courseFieldRef}>
      {/* ── Top Bar: Chosen Courses Badges ── */}
      {chosen.length > 0 ? (
        <div
          style={{
            background: '#eff6ff',
            border: '1.5px solid #bfdbfe',
            borderRadius: '10px',
            padding: '14px 18px',
            marginBottom: '20px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#1e40af' }}>
              Selected Courses ({chosen.length} of {MAX_COURSES})
            </span>
            <span style={{ fontSize: '0.75rem', color: '#3b82f6', fontWeight: 600 }}>
              {atLimit ? 'Maximum reached' : 'You can select 1 more'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {chosen.map((prog) => (
              <div
                key={prog.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: '#ffffff',
                  border: '1px solid #dbeafe',
                  padding: '8px 14px',
                  borderRadius: '6px',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#0f172a' }}>
                    {prog.name}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                    {prog.institutionName || 'Partner School'}
                    {prog.duration ? ` · ${prog.duration}` : ''}
                    {prog.tuition ? ` · ${formatTuition(prog.tuition, prog.currency || 'EUR')}` : ''}
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => removeProgram(prog)}
                  style={{ color: '#dc2626', fontSize: '0.8rem', fontWeight: 600, padding: '4px 8px' }}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* ── Partner Universities Chips / Tabs ── */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Filter by Partner University in {countryName}:
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <button
            type="button"
            className={`btn btn-sm ${selectedSchoolFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setSelectedSchoolFilter('all')}
            style={{ borderRadius: '20px', fontSize: '0.8125rem', padding: '5px 14px' }}
          >
            All Universities ({safeInstitutions.length})
          </button>
          {safeInstitutions.map((inst) => (
            <button
              key={inst.slug}
              type="button"
              className={`btn btn-sm ${selectedSchoolFilter === inst.slug ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setSelectedSchoolFilter(inst.slug)}
              style={{ borderRadius: '20px', fontSize: '0.8125rem', padding: '5px 14px' }}
            >
              {inst.name} ({inst.programs?.length || 0})
            </button>
          ))}
        </div>
      </div>

      {/* ── Search Input ── */}
      <div style={{ position: 'relative', marginBottom: 18 }}>
        <div style={{ position: 'absolute', left: 14, top: 12, color: '#94a3b8' }}>
          <Icon name="search" size={17} strokeWidth={2.2} />
        </div>
        <input
          type="text"
          className="form-control"
          placeholder={`Search ${allCoursesWithSchool.length} courses in ${countryName} (e.g. MBA, Artificial Intelligence, Business, Healthcare)...`}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ paddingLeft: 40, height: 42, fontSize: '0.9rem' }}
        />
        {searchQuery ? (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            style={{
              position: 'absolute',
              right: 12,
              top: 10,
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '1rem',
            }}
          >
            ✕
          </button>
        ) : null}
      </div>

      {/* ── Courses Count ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#475569' }}>
          Showing {filteredCourses.length} available course{filteredCourses.length === 1 ? '' : 's'}
        </span>
        {searchQuery ? (
          <span style={{ fontSize: '0.8125rem', color: '#64748b' }}>
            Filtered by &ldquo;{searchQuery}&rdquo;
          </span>
        ) : null}
      </div>

      {/* ── Courses Grid / List ── */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          maxHeight: '440px',
          overflowY: 'auto',
          paddingRight: '4px',
          marginBottom: '20px',
        }}
      >
        {filteredCourses.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: '32px 16px',
              background: '#f8fafc',
              borderRadius: '10px',
              border: '1px dashed #cbd5e1',
            }}
          >
            <p style={{ margin: '0 0 10px', color: '#64748b', fontSize: '0.9rem' }}>
              No course matched &ldquo;{searchQuery}&rdquo; in {countryName}.
            </p>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() =>
                onChange({
                  ...selection,
                  institution: '',
                  level: null,
                  programs: [],
                  is_custom_course: true,
                  custom_course: searchQuery,
                })
              }
              style={{ fontWeight: 600 }}
            >
              Type &ldquo;{searchQuery}&rdquo; as a custom course
            </button>
          </div>
        ) : (
          filteredCourses.map((prog) => {
            const chosenThis = isChosen(prog);
            const levelLabel = LEVEL_LABELS[prog.level] || prog.level;
            return (
              <div
                key={prog.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '14px',
                  padding: '14px 18px',
                  borderRadius: '10px',
                  border: chosenThis ? '2px solid #2563eb' : '1px solid #e2e8f0',
                  background: chosenThis ? '#f0f7ff' : '#ffffff',
                  boxShadow: chosenThis ? '0 2px 8px rgba(37,99,235,0.1)' : '0 1px 3px rgba(0,0,0,0.02)',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: 4 }}>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: '#e0e7ff',
                        color: '#3730a3',
                        textTransform: 'uppercase',
                        letterSpacing: '0.03em',
                      }}
                    >
                      {levelLabel}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 500 }}>
                      {prog.institutionName} · {prog.institutionLocation}
                    </span>
                  </div>

                  <h5 style={{ margin: '0 0 4px', fontSize: '0.98rem', color: '#0f172a', fontWeight: 600 }}>
                    {prog.name}
                  </h5>

                  <div style={{ display: 'flex', gap: '14px', fontSize: '0.8rem', color: '#64748b', flexWrap: 'wrap' }}>
                    {prog.duration ? <span>Duration: <strong>{prog.duration}</strong></span> : null}
                    {prog.qualification_level ? <span>Cert: <strong>{prog.qualification_level}</strong></span> : null}
                    {prog.tuition ? (
                      <span style={{ color: '#0369a1', fontWeight: 600 }}>
                        Tuition: {formatTuition(prog.tuition, prog.currency || 'EUR')}
                      </span>
                    ) : null}
                    {prog.intake ? <span>Intake: <strong>{prog.intake}</strong></span> : null}
                  </div>
                </div>

                <div style={{ flexShrink: 0 }}>
                  {chosenThis ? (
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => removeProgram(prog)}
                      style={{
                        background: '#2563eb',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        fontWeight: 600,
                        fontSize: '0.82rem',
                        padding: '6px 14px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      <Icon name="checkCircle" size={14} strokeWidth={2.5} />
                      Selected
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => addProgram(prog)}
                      disabled={atLimit}
                      style={{
                        borderRadius: '6px',
                        fontWeight: 600,
                        fontSize: '0.82rem',
                        padding: '6px 14px',
                        cursor: atLimit ? 'not-allowed' : 'pointer',
                        opacity: atLimit ? 0.6 : 1,
                      }}
                    >
                      {atLimit ? 'Limit reached' : '+ Select'}
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Bottom Section: Custom Course Fallback ── */}
      <div
        style={{
          padding: '16px',
          background: '#f8fafc',
          border: '1px dashed #cbd5e1',
          borderRadius: '10px',
          textAlign: 'center',
        }}
      >
        <span style={{ fontSize: '0.875rem', color: '#475569' }}>
          Can&apos;t find your desired institution or course above?{' '}
        </span>
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
            color: '#2563eb',
            fontWeight: 700,
            fontSize: '0.875rem',
            textDecoration: 'underline',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          Type your course manually (Free application & review)
        </button>
      </div>
    </div>
  );
}
