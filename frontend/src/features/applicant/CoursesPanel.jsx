import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Loading from '../../components/ui/Loading';
import { catalog } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import Icon from '../../lib/icons';
import { formatMoney, formatTuition } from '../../lib/format';
import { useApplication } from './ApplicationContext';

/**
 * Courses, found the way people actually choose: a country, then a university,
 * then a course.
 *
 * Listing every programme at once buried the one someone wanted under a hundred
 * they did not. Each step here narrows the next, and the choice lives in the
 * address (?country=&school=), so the browser's Back button steps back out.
 *
 * Tuition stays in the school's own currency. The application fee is quoted in
 * the applicant's currency by the same endpoint the checkout uses, so the figure
 * shown is the figure they will pay.
 */

const LEVELS = [
  { value: 'all', label: 'All levels' },
  { value: 'bachelors', label: "Bachelor's" },
  { value: 'masters', label: 'Masters & MBA' },
  { value: 'phd', label: 'PhD' },
  { value: 'diplomas', label: 'Diplomas' },
  { value: 'other', label: 'Other' },
];

const LEVEL_NAMES = {
  bachelors: "Bachelor's degree",
  masters: 'Masters & MBA',
  phd: 'PhD',
  diplomas: 'Diploma',
  other: 'Programme',
};

function feeText(quote, school) {
  if (school?.is_fee_free) return 'No application fee';
  if (quote === undefined) return 'Application fee: checking';
  if (!quote) return `Application fee: ${formatMoney(school.application_fee, school.application_fee_currency)}`;
  return `Application fee: ${formatMoney(quote.amount, quote.currency)}`;
}

export function CourseBrowser({ onApply, applyLabel = 'Apply', canApply = true, banner = null, feeOrigin }) {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const country = params.get('country') || '';
  const schoolSlug = params.get('school') || '';

  const [countries, setCountries] = useState(null);
  const [schools, setSchools] = useState(null);
  const [quotes, setQuotes] = useState({});
  const [level, setLevel] = useState('all');
  const [search, setSearch] = useState('');

  const loadCountries = useCallback(() => {
    catalog
      .destinations()
      .then(({ data }) => setCountries(Array.isArray(data) ? data : []))
      .catch(() => setCountries((current) => current || []));
  }, []);

  const loadSchools = useCallback(() => {
    if (!country) return;
    catalog
      .institutions(country)
      .then(({ data }) => setSchools(Array.isArray(data) ? data : []))
      .catch(() => setSchools((current) => current || []));
  }, [country]);

  useEffect(() => {
    loadCountries();
  }, [loadCountries]);

  useEffect(() => {
    setSchools(null);
    loadSchools();
  }, [loadSchools]);

  useEffect(() => {
    setLevel('all');
    setSearch('');
  }, [schoolSlug]);

  // Staff add courses in the admin; keep what is on screen current.
  useLiveRefresh(() => {
    loadCountries();
    loadSchools();
  }, { intervalMs: 30000 });

  // One fee quote per school in the chosen country.
  useEffect(() => {
    (schools || []).forEach((school) => {
      if (school.slug in quotes || school.is_fee_free) return;
      setQuotes((current) => ({ ...current, [school.slug]: undefined }));
      catalog
        .feeQuote(feeOrigin || user?.country || 'Nigeria', school.slug)
        .then(({ data }) => setQuotes((current) => ({ ...current, [school.slug]: data })))
        .catch(() => setQuotes((current) => ({ ...current, [school.slug]: null })));
    });
  }, [schools]); // eslint-disable-line react-hooks/exhaustive-deps

  const school = useMemo(
    () => (schools || []).find((item) => item.slug === schoolSlug) || null,
    [schools, schoolSlug],
  );

  const courses = useMemo(() => {
    if (!school) return [];
    const term = search.trim().toLowerCase();
    return (school.programs || []).filter(
      (course) =>
        (level === 'all' || course.level === level) &&
        (!term || course.name.toLowerCase().includes(term)),
    );
  }, [school, level, search]);

  const levelsHere = useMemo(() => {
    const present = new Set((school?.programs || []).map((course) => course.level));
    return LEVELS.filter((item) => item.value === 'all' || present.has(item.value));
  }, [school]);

  const go = (next) => {
    const query = new URLSearchParams();
    if (next.country) query.set('country', next.country);
    if (next.school) query.set('school', next.school);
    setParams(query);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const apply = (course) => onApply?.({ course, school, country });

  const available = (countries || []).filter((item) => item.institution_count !== 0);

  return (
    <div className="gx-page">
      {banner}

      <nav className="gx-crumbs" aria-label="Course browser">
        <ol>
          <li>
            {country ? (
              <button type="button" className="gx-link" onClick={() => go({})}>
                Countries
              </button>
            ) : (
              <span aria-current="page">Countries</span>
            )}
          </li>
          {country ? (
            <li>
              <Icon name="chevronRight" size={14} strokeWidth={2} />
              {schoolSlug ? (
                <button type="button" className="gx-link" onClick={() => go({ country })}>
                  {country}
                </button>
              ) : (
                <span aria-current="page">{country}</span>
              )}
            </li>
          ) : null}
          {school ? (
            <li>
              <Icon name="chevronRight" size={14} strokeWidth={2} />
              <span aria-current="page">{school.name}</span>
            </li>
          ) : null}
        </ol>
      </nav>

      {/* ── 1. Country ── */}
      {!country ? (
        <section className="gx-card" aria-labelledby="country-title">
          <div className="gx-card-head">
            <h2 id="country-title" className="gx-card-title">Where do you want to study?</h2>
          </div>
          {countries === null ? (
            <Loading label="Loading destinations" />
          ) : available.length === 0 ? (
            <div className="gx-empty">
              <h3>No destinations yet</h3>
              <p className="gx-muted">New universities are added regularly. Check back soon.</p>
            </div>
          ) : (
            <div className="gx-pick-grid">
              {available.map((item) => (
                <button key={item.id} type="button" className="gx-pick" onClick={() => go({ country: item.name })}>
                  <span className="gx-pick-badge" aria-hidden="true">{item.code || item.name.slice(0, 2).toUpperCase()}</span>
                  <span className="gx-pick-text">
                    <strong>{item.name}</strong>
                    <span>
                      {item.institution_count} universit{item.institution_count === 1 ? 'y' : 'ies'} · {item.program_count} courses
                    </span>
                  </span>
                  <Icon name="chevronRight" size={18} strokeWidth={2} className="gx-pick-chevron" />
                </button>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {/* ── 2. University ── */}
      {country && !schoolSlug ? (
        <section className="gx-card" aria-labelledby="school-title">
          <div className="gx-card-head">
            <h2 id="school-title" className="gx-card-title">Choose a university in {country}</h2>
          </div>
          {schools === null ? (
            <Loading label="Loading universities" />
          ) : schools.length === 0 ? (
            <div className="gx-empty">
              <h3>No universities here yet</h3>
              <button type="button" className="gx-btn gx-btn-secondary" onClick={() => go({})}>
                Choose another country
              </button>
            </div>
          ) : (
            <div className="gx-pick-grid gx-pick-grid-wide">
              {schools.map((item) => (
                <button key={item.slug} type="button" className="gx-pick gx-pick-school" onClick={() => go({ country, school: item.slug })}>
                  <span className="gx-pick-badge" aria-hidden="true">
                    <Icon name="building" size={20} />
                  </span>
                  <span className="gx-pick-text">
                    <strong>{item.name}</strong>
                    <span>{item.location || country}</span>
                    <span className="gx-facts">
                      <span className="gx-fact">{(item.programs || []).length} courses</span>
                      {item.tuition_summary ? <span className="gx-fact">{item.tuition_summary}</span> : null}
                      <span className="gx-fact">{feeText(quotes[item.slug], item)}</span>
                    </span>
                  </span>
                  <Icon name="chevronRight" size={18} strokeWidth={2} className="gx-pick-chevron" />
                </button>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {/* ── 3. Courses ── */}
      {country && schoolSlug ? (
        schools === null ? (
          <Loading label="Loading courses" />
        ) : !school ? (
          <section className="gx-card gx-empty">
            <h3>That university is not listed</h3>
            <button type="button" className="gx-btn gx-btn-secondary" onClick={() => go({ country })}>
              See universities in {country}
            </button>
          </section>
        ) : (
          <>
            <section className="gx-card gx-school-head">
              <span className="gx-icon-tile" aria-hidden="true">
                <Icon name="building" size={22} />
              </span>
              <div>
                <h2 className="gx-card-title">{school.name}</h2>
                <p className="gx-muted">{school.location || country}</p>
                <div className="gx-facts">
                  <span className="gx-fact">{feeText(quotes[school.slug], school)}</span>
                  {school.deposit_note ? <span className="gx-fact">{school.deposit_note}</span> : null}
                </div>
              </div>
            </section>

            <section className="gx-card" aria-labelledby="course-list-title">
              <div className="gx-card-head">
                <h2 id="course-list-title" className="gx-card-title">
                  Courses <span className="gx-muted gx-count">{courses.length}</span>
                </h2>
                <div className="gx-search gx-search-inline">
                  <Icon name="search" size={18} />
                  <label className="sr-only" htmlFor="course-search">Search courses</label>
                  <input
                    id="course-search"
                    type="search"
                    className="gx-input"
                    placeholder="Search this university"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </div>
              </div>

              {levelsHere.length > 2 ? (
                <div className="gx-segments" role="group" aria-label="Level">
                  {levelsHere.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      className={`gx-segment ${level === item.value ? 'is-active' : ''}`.trim()}
                      aria-pressed={level === item.value}
                      onClick={() => setLevel(item.value)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ) : null}

              {courses.length === 0 ? (
                <div className="gx-empty">
                  <h3>No courses match</h3>
                  <p className="gx-muted">Try another level, or clear the search.</p>
                </div>
              ) : (
                <div className="gx-courses">
                  {courses.map((course) => (
                    <article className="gx-course" key={course.id}>
                      <div>
                        <h3 className="gx-course-name">{course.name}</h3>
                        <div className="gx-facts">
                          <span className="gx-fact">{LEVEL_NAMES[course.level] || 'Programme'}</span>
                          {course.duration ? (
                            <span className="gx-fact">
                              <Icon name="clock" size={13} strokeWidth={2} />
                              {course.duration}
                            </span>
                          ) : null}
                          {course.intake ? (
                            <span className="gx-fact">
                              <Icon name="calendar" size={13} strokeWidth={2} />
                              Starts {course.intake}
                            </span>
                          ) : null}
                        </div>
                        {course.scholarship ? <p className="gx-muted gx-small gx-course-note">{course.scholarship}</p> : null}
                      </div>

                      <div className="gx-course-side">
                        <div className="gx-tuition">
                          {course.tuition ? formatTuition(course.tuition, school.currency) : 'Tuition on request'}
                          <small>Tuition</small>
                        </div>
                        {canApply ? (
                          <button type="button" className="gx-btn gx-btn-primary gx-btn-sm" onClick={() => apply(course)}>
                            {applyLabel}
                            <Icon name="arrowRight" size={15} strokeWidth={2} />
                          </button>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )
      ) : null}
    </div>
  );
}

/** The applicant's Courses page: the browser, with Apply opening the application. */
export default function CoursesPanel() {
  const { application } = useApplication();
  const navigate = useNavigate();

  return (
    <CourseBrowser
      canApply={!application}
      onApply={({ course, school, country }) => {
        const query = new URLSearchParams({
          destination: country,
          institution: school.slug,
          program: String(course.id),
        });
        navigate(`/portal/apply?${query.toString()}`);
      }}
      banner={
        application ? (
          <section className="gx-card gx-welcome">
            <div>
              <h2>Your application is in progress</h2>
              <p className="gx-muted">
                {application.institution?.name || 'Your chosen course'} · {application.reference}
              </p>
            </div>
            <Link to="/portal/details" className="gx-btn gx-btn-secondary">
              View application
            </Link>
          </section>
        ) : null
      }
    />
  );
}
