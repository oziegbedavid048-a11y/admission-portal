import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { formatDate } from '../../lib/format';
import { supervisors } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import SupervisorStatusBadge from './SupervisorStatusBadge';

const FILTERS = [
  { value: 'all', label: 'All statuses' },
  { value: 'admission_granted', label: 'Admitted' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'in_review', label: 'In review' },
];

/** Every student filed by any agent on this Sales Manager's team. */
export default function SupervisorStudents() {
  const location = useLocation();
  const [students, setStudents] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [agent, setAgent] = useState(String(location.state?.agent || 'all'));
  const toast = useToast();

  const load = async (quiet = false) => {
    try {
      const [studentsResponse, agentsResponse] = await Promise.all([
        supervisors.students(),
        supervisors.agents(),
      ]);
      setStudents(studentsResponse.data);
      setAgents(agentsResponse.data);
    } catch {
      if (!quiet) toast.error('Could not load the student list.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useLiveRefresh(() => load(true));

  // The list is a team's worth of students, small enough to filter in the
  // browser, so typing does not wait on a round trip.
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return students.filter((student) => {
      if (status !== 'all' && student.status !== status) return false;
      if (agent !== 'all' && String(student.agent_id) !== agent) return false;
      if (!needle) return true;
      return [
        student.full_name,
        student.reference,
        student.institution,
        student.agent,
        student.destination_country,
      ]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(needle));
    });
  }, [students, query, status, agent]);

  const verified = students.filter((s) => s.visa_status === 'completed').length;

  if (loading) return <Loading label="Loading students" />;

  return (
    <div className="agent-stack">

      <div className="agent-stats">
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="cap" size={20} />
          </span>
          <span className="s-label">Students</span>
          <span className="s-value">{students.length}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="badgeCheck" size={20} />
          </span>
          <span className="s-label">Admitted</span>
          <span className="s-value">
            {students.filter((s) => s.status === 'admission_granted').length}
          </span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="passport" size={20} />
          </span>
          <span className="s-label">Visas verified</span>
          <span className="s-value">{verified}</span>
        </div>
      </div>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Team students</h2>
          <span className="agent-card-note">
            {visible.length} of {students.length}
          </span>
        </div>

        <div className="applicants-filter-bar">
          <div className="applicants-search-wrap">
            <Icon name="search" size={18} />
            <label className="sr-only" htmlFor="sv-student-search">
              Search students
            </label>
            <input
              type="search"
              id="sv-student-search"
              className="agent-form-control"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>

          <div className="applicants-select-wrap">
            <label className="sr-only" htmlFor="sv-agent-filter">
              Filter by agent
            </label>
            <select
              id="sv-agent-filter"
              className="agent-form-select"
              value={agent}
              onChange={(event) => setAgent(event.target.value)}
            >
              <option value="all">All agents</option>
              {agents.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.full_name}
                </option>
              ))}
            </select>
          </div>

          <div className="applicants-select-wrap">
            <label className="sr-only" htmlFor="sv-status-filter">
              Filter by status
            </label>
            <select
              id="sv-status-filter"
              className="agent-form-select"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              {FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="agent-table-wrap">
          <table className="agent-table">
            <thead>
              <tr>
                <th>Student</th>
                <th className="t-hide-sm">Filed by</th>
                <th>Destination</th>
                <th className="t-hide-sm">Fee</th>
                <th>Admission</th>
                <th>Visa</th>
                <th className="t-hide-sm">Filed</th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <tr className="row-empty">
                  <td colSpan={7}>
                    <div className="agent-empty-state">
                      <p>No students found</p>
                      <small>
                        {students.length
                          ? 'Clear the filters to see everyone.'
                          : 'They appear here as soon as one of your agents files an application.'}
                      </small>
                    </div>
                  </td>
                </tr>
              ) : (
                visible.map((student) => (
                  <tr key={student.reference}>
                    <td data-label="Student">
                      <span className="cell">
                        <span className="col-name">{student.full_name}</span>
                        <span className="col-sub">{student.reference}</span>
                      </span>
                    </td>
                    <td data-label="Filed by" className="t-hide-sm">
                      <span className="col-inst">{student.agent}</span>
                    </td>
                    <td data-label="Destination">
                      <span className="cell">
                        <span className="col-name">{student.destination_country}</span>
                        <span className="col-sub">{student.institution}</span>
                      </span>
                    </td>
                    <td data-label="Fee" className="t-hide-sm">
                      <SupervisorStatusBadge
                        status={
                          student.fee_status === 'paid'
                            ? 'Paid'
                            : student.fee_status === 'waived'
                              ? 'waived'
                              : 'pending'
                        }
                      />
                    </td>
                    <td data-label="Admission">
                      <SupervisorStatusBadge status={student.status} />
                    </td>
                    <td data-label="Visa">
                      <SupervisorStatusBadge status={student.visa_status} />
                    </td>
                    <td data-label="Filed" className="t-hide-sm">
                      {formatDate(student.submitted_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
