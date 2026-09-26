import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { formatMoney, formatTuition } from '../../lib/format';
import { catalog } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { useCatalog } from '../../hooks/useCatalog';

/**
 * Every course on the platform, in one searchable place.
 *
 * Agents are asked "what can you get me into?" constantly, and the answer used
 * to mean walking the registration wizard to look. Filtering happens on the
 * server because there are a few hundred programmes across the partners and
 * more will be added.
 */

const PAGE_SIZE = 50;

const LEVEL_ICONS = {
  bachelors: 'book',
  masters: 'cap',
  phd: 'flask',
  diplomas: 'medal',
  other: 'document',
};

export default function AgentCourses() {
  const { destinations } = useCatalog();
  const toast = useToast();
  const navigate = useNavigate();

  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [country, setCountry] = useState('all');
  const [level, setLevel] = useState('all');
  const [feeFree, setFeeFree] = useState(false);
  const [levels, setLevels] = useState([]);

  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);

  // Typing should not fire a request per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    catalog
      .programLevels()
      .then(({ data }) => setLevels(data))
      .catch(() => setLevels([]));
  }, []);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    try {
      const { data } = await catalog.programs({
        search: query || undefined,
        country: country === 'all' ? undefined : country,
        level: level === 'all' ? undefined : level,
        fee_free: feeFree ? 'true' : undefined,
        page,
      });
      // A slow earlier request must not overwrite a newer, faster one.
      if (id !== requestId.current) return;
      setRows(data.results);
      setCount(data.count);
    } catch {
      if (id === requestId.current) toast.error('Could not load the course list.');
    } finally {
      if (id === requestId.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, country, level, feeFree, page]);

  useEffect(() => {
    load();
  }, [load]);

  // Staff add and reorder courses in the admin, so the list refetches rather
  // than showing whatever it happened to load when the page opened.
  useLiveRefresh(() => load(), { intervalMs: 20000 });

  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const filtered = query || country !== 'all' || level !== 'all' || feeFree;

  const summary = useMemo(() => {
    if (loading) return 'Searching…';
    if (count === 0) return 'No courses match';
    const first = (page - 1) * PAGE_SIZE + 1;
    const last = Math.min(count, page * PAGE_SIZE);
    return `Showing ${first} to ${last} of ${count} course${count === 1 ? '' : 's'}`;
  }, [loading, count, page]);

  const reset = () => {
    setSearch('');
    setCountry('all');
    setLevel('all');
    setFeeFree(false);
    setPage(1);
  };

  return (
    <div className="agent-stack">
      <section className="agent-banner">
        <span className="agent-icon" aria-hidden="true">
          <Icon name="cap" size={22} animate />
        </span>
        <div className="agent-banner-text">
          <h2>Courses</h2>
          <p>Every programme available across our partner institutions.</p>
        </div>
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="search" size={18} />
            </span>
            Find a course
          </h2>
          <span className="agent-card-note">{summary}</span>
        </div>

        <div className="course-filter-bar">
          <div className="applicants-search-wrap">
            <Icon name="search" size={18} />
            <label className="sr-only" htmlFor="course-search">
              Search courses
            </label>
            <input
              type="search"
              id="course-search"
              className="agent-form-control"
              placeholder="Search a course, institution or city"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className="applicants-select-wrap">
            <label className="sr-only" htmlFor="course-country">
              Destination
            </label>
            <select
              id="course-country"
              className="agent-form-select"
              value={country}
              onChange={(event) => {
                setCountry(event.target.value);
                setPage(1);
              }}
            >
              <option value="all">All destinations</option>
              {destinations.map((item) => (
                <option key={item.id} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <div className="applicants-select-wrap">
            <label className="sr-only" htmlFor="course-level">
              Level
            </label>
            <select
              id="course-level"
              className="agent-form-select"
              value={level}
              onChange={(event) => {
                setLevel(event.target.value);
                setPage(1);
              }}
            >
              <option value="all">All levels</option>
              {levels.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label} ({item.count})
                </option>
              ))}
            </select>
          </div>

          <label className="course-toggle">
            <input
              type="checkbox"
              checked={feeFree}
              onChange={(event) => {
                setFeeFree(event.target.checked);
                setPage(1);
              }}
            />
            <span>Fee-free only</span>
          </label>

          {filtered ? (
            <button type="button" className="agent-btn agent-btn-secondary agent-btn-sm" onClick={reset}>
              Clear
            </button>
          ) : null}
        </div>

        {loading && rows.length === 0 ? (
          <Loading label="Loading courses" />
        ) : rows.length === 0 ? (
          <div className="agent-empty-state">
            <p>No courses match</p>
            <small>Try a broader search, or clear the filters.</small>
          </div>
        ) : (
          <div className="course-list">
            {rows.map((course) => (
              <article className="course-row" key={course.id}>
                <span className="course-icon" aria-hidden="true">
                  <Icon name={LEVEL_ICONS[course.level] || 'document'} size={20} animate />
                </span>

                <div className="course-body">
                  <h3 className="course-name">{course.name}</h3>
                  <div className="course-where">
                    <Icon name="building" size={13} strokeWidth={2} />
                    {course.institution}
                    <span className="course-dot" aria-hidden="true" />
                    <Icon name="pin" size={13} strokeWidth={2} />
                    {course.location || course.country}
                  </div>

                  <div className="course-tags">
                    <span className="badge badge-brand">{course.level_display}</span>
                    {course.duration ? <span className="course-tag">{course.duration}</span> : null}
                    {course.qualification_level ? (
                      <span className="course-tag">{course.qualification_level}</span>
                    ) : null}
                    {course.intake ? <span className="course-tag">Intake: {course.intake}</span> : null}
                    {course.is_fee_free ? (
                      <span className="badge badge-success">Fee-free application</span>
                    ) : (
                      <span className="course-tag">
                        App fee {formatMoney(course.application_fee, course.currency)}
                      </span>
                    )}
                  </div>

                  {course.scholarship || course.note ? (
                    <p className="course-note">{course.scholarship || course.note}</p>
                  ) : null}
                </div>

                <div className="course-side">
                  <div className="course-tuition">
                    {course.tuition ? formatTuition(course.tuition, course.currency) : 'Tuition on request'}
                  </div>
                  <button
                    type="button"
                    className="agent-btn agent-btn-primary agent-btn-sm"
                    onClick={() =>
                      navigate('/agent/students/new', {
                        state: { destination: course.country, institution: course.institution_slug },
                      })
                    }
                  >
                    Apply a student
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}

        {pages > 1 ? (
          <div className="course-pager">
            <button
              type="button"
              className="agent-btn agent-btn-secondary agent-btn-sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              <Icon name="arrowLeft" size={15} strokeWidth={2} />
              Previous
            </button>
            <span className="course-pager-label">
              Page {page} of {pages}
            </span>
            <button
              type="button"
              className="agent-btn agent-btn-secondary agent-btn-sm"
              disabled={page >= pages || loading}
              onClick={() => setPage((current) => Math.min(pages, current + 1))}
            >
              Next
              <Icon name="arrowRight" size={15} strokeWidth={2} />
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
