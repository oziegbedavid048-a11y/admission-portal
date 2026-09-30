import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Loading from '../../components/ui/Loading';
import SearchableSelect from '../../components/ui/SearchableSelect';
import { catalog } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import Icon from '../../lib/icons';
import { ALL_WORLD_COUNTRIES } from '../../lib/countries';
import { formatMoney, formatTuition, resolveMediaUrl } from '../../lib/format';
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

  const available = useMemo(
    () => (countries || []).filter((item) => item.institution_count !== 0),
    [countries],
  );
  const schoolNames = useMemo(() => (schools || []).map((item) => item.name), [schools]);

  const countryOptions = useMemo(() => {
    const first = available.map((item) => item.name);
    return [...first, ...ALL_WORLD_COUNTRIES.filter((name) => !first.includes(name))];
  }, [available]);

  return (
    <div className="gx-page">
      {banner}

      {/* ── 1 and 2. Country, then university: two searchable dropdowns. The
          country list is every country, those with partner universities first;
          the university list is the partners in the chosen country. ── */}
      <section className="gx-card" aria-labelledby="country-title">
        <div className="gx-card-head">
          <h2 id="country-title" className="gx-card-title">Find a course</h2>
        </div>
        <div className="gx-picker-row">
          <div className="gx-field">
            <span className="gx-label" id="course-country-label">
              Country
            </span>
            <SearchableSelect
              options={countryOptions}
              value={country}
              onChange={(value) => go({ country: value })}
              labelledBy="course-country-label"
            />
          </div>
          <div className="gx-field">
            <span className="gx-label" id="course-school-label">
              University
            </span>
            {country && schools === null ? (
              <div className="gx-input gx-input-loading" aria-busy="true">
                <span className="spinner-sm" aria-hidden="true" />
              </div>
            ) : (
              <SearchableSelect
                options={schoolNames}
                value={school?.name || ''}
                onChange={(name) => {
                  const picked = (schools || []).find((item) => item.name === name);
                  if (picked) go({ country, school: picked.slug });
                }}
                labelledBy="course-school-label"
              />
            )}
          </div>
        </div>

        {!country && countries !== null ? (
          <p className="gx-muted gx-small gx-picker-hint">
            {available.length
              ? `Partner universities in ${available.map((item) => item.name).join(', ')}.`
              : 'New universities are added regularly.'}
          </p>
        ) : null}

        {country && schools !== null && schools.length === 0 ? (
          <div className="gx-empty">
            <span className="gx-icon-tile" aria-hidden="true">
              <Icon name="globe" size={22} />
            </span>
            <h3>No partner universities in {country} yet</h3>
            <p className="gx-muted">
              {available.length
                ? `Try ${available.map((item) => item.name).join(' or ')}.`
                : 'New universities are added regularly.'}
            </p>
          </div>
        ) : null}

        {country && schools?.length && !schoolSlug ? (
          <p className="gx-muted gx-small gx-picker-hint">
            {schools.length} universit{schools.length === 1 ? 'y' : 'ies'} in {country}. Choose one to see its courses.
          </p>
        ) : null}
      </section>

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
            {/* The school over a darkened photo of its campus: name, where it
                is, and what it costs. */}
            <section
              className="gx-school-hero"
              style={{ backgroundImage: `url("${resolveMediaUrl(school.cover_image) || '/assets/hero/campus-1.jpg'}")` }}
              aria-labelledby="school-hero-title"
            >
              <div className="gx-school-hero-inner">
                <span className="gx-school-hero-eyebrow">{country}</span>
                <h2 id="school-hero-title">{school.name}</h2>
                <p className="gx-school-hero-location">
                  <Icon name="pin" size={16} strokeWidth={2} />
                  {!school.location
                    ? country
                    : school.location.toLowerCase().includes(country.toLowerCase())
                      ? school.location
                      : `${school.location}, ${country}`}
                </p>
                <dl className="gx-school-hero-facts">
                  <div>
                    <dt>Tuition</dt>
                    <dd>{school.tuition_summary || 'Varies by course'}</dd>
                  </div>
                  <div>
                    <dt>Application fee</dt>
                    <dd>{feeText(quotes[school.slug], school).replace('Application fee: ', '')}</dd>
                  </div>
                  <div>
                    <dt>Courses</dt>
                    <dd>{(school.programs || []).length}</dd>
                  </div>
                </dl>
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
                <div className="gx-table-scroll" role="region" aria-label="Courses" tabIndex={0}>
                  <table className="gx-table">
                    <thead>
                      <tr>
                        <th scope="col">Course</th>
                        <th scope="col">Level</th>
                        <th scope="col">Duration</th>
                        <th scope="col">Starts</th>
                        <th scope="col" className="t-num">Tuition / year</th>
                        {canApply ? <th scope="col"><span className="sr-only">Action</span></th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {courses.map((course) => (
                        <tr key={course.id}>
                          <th scope="row" className="gx-table-course">
                            <span className="gx-table-name">{course.name}</span>
                            {course.scholarship ? <span className="gx-table-sub">{course.scholarship}</span> : null}
                          </th>
                          <td>{LEVEL_NAMES[course.level] || 'Programme'}</td>
                          <td>{course.duration || '—'}</td>
                          <td>{course.intake || '—'}</td>
                          <td className="t-num gx-table-money">
                            {course.tuition ? formatTuition(course.tuition, school.currency).replace(' / year', '') : 'On request'}
                          </td>
                          {canApply ? (
                            <td className="gx-table-action">
                              <button type="button" className="gx-btn gx-btn-primary gx-btn-sm" onClick={() => apply(course)}>
                                {applyLabel}
                              </button>
                            </td>
                          ) : null}
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
