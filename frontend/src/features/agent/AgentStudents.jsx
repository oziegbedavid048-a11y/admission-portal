import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { partners, payments } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { formatNaira } from '../../lib/format';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { useAgent } from './AgentContext';
import { useToast } from '../../context/ToastContext';
import StatusBadge from './StatusBadge';
import StudentDossierModal from './StudentDossierModal';

const FILTERS = [
  { value: 'all', label: 'All statuses' },
  { value: 'admission_granted', label: 'Admitted' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'in_review', label: 'In review' },
];

export default function AgentStudents() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [open, setOpen] = useState(null);
  const [paying, setPaying] = useState(null);
  const { setWallet } = useAgent();
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    partners
      .students()
      .then(({ data }) => {
        if (!cancelled) setStudents(data);
      })
      .catch(() => {
        if (!cancelled) toast.error('Could not load your students.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Filtering happens here rather than on the server: an agent's list is small
  // enough to hold, and typing should not wait on a round trip.
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return students.filter((student) => {
      if (status !== 'all' && student.status !== status) return false;
      if (!needle) return true;
      return [
        student.full_name,
        student.reference,
        student.institution,
        student.program,
        student.destination_country,
      ]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(needle));
    });
  }, [students, query, status]);

  // Admission and visa decisions are made by the desk, so the table keeps
  // itself current instead of showing yesterday's statuses.
  useLiveRefresh(async () => {
    try {
      const { data } = await partners.students();
      setStudents(data);
    } catch {
      // Ignore a failed tick.
    }
  });

  const admitted = students.filter((item) => item.status === 'admission_granted').length;

  const payFee = async (student) => {
    setPaying(student.reference);
    try {
      const { data } = await payments.checkout(student.reference, 'Paystack');
      if (data.wallet) setWallet(data.wallet);
      const commission = Number(data.commission_paid) || 0;
      setStudents((current) =>
        current.map((item) =>
          item.reference === student.reference
            ? { ...item, fee_status: 'paid', fee_display: data.payment.display_total }
            : item,
        ),
      );
      toast.success(
        commission
          ? `Fee settled. ${formatNaira(commission)} added to your balance.`
          : 'Fee settled.',
      );
    } catch (error) {
      toast.error(errorMessage(error, 'Could not settle that fee.'));
    } finally {
      setPaying(null);
    }
  };

  if (loading) return <Loading label="Loading your students" />;

  return (
    <div className="agent-stack">

      <div className="agent-stats">
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="users" size={20} />
          </span>
          <span className="s-label">Registered</span>
          <span className="s-value">{students.length}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="badgeCheck" size={20} />
          </span>
          <span className="s-label">Admitted</span>
          <span className="s-value">{admitted}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="clock" size={20} />
          </span>
          <span className="s-label">In review</span>
          <span className="s-value">{students.length - admitted}</span>
        </div>
      </div>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="users" size={18} />
            </span>
            Your students
          </h2>
          <Link className="agent-btn agent-btn-primary agent-btn-sm" to="/agent/students/new">
            <Icon name="userPlus" size={16} />
            Register a student
          </Link>
        </div>

        <div className="applicants-filter-bar">
          <div className="applicants-search-wrap">
            <Icon name="search" size={18} />
            <label className="sr-only" htmlFor="student-search">
              Search students
            </label>
            <input
              type="search"
              id="student-search"
              className="agent-form-control"
              placeholder="Search name, reference or institution"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className="applicants-select-wrap">
            <label className="sr-only" htmlFor="student-status">
              Filter by status
            </label>
            <select
              id="student-status"
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
                <th>Destination</th>
                <th className="t-hide-sm">Programme</th>
                <th>Fee</th>
                <th>Admission</th>
                <th>Visa</th>
                <th className="t-num">
                  <span className="sr-only">Details</span>
                </th>
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
                          : 'Register one to get started.'}
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
                        <span className="col-sub">{student.email}</span>
                      </span>
                    </td>
                    <td data-label="Destination">
                      <span className="cell">
                        <span className="col-name">{student.destination_country}</span>
                        <span className="col-sub">{student.institution}</span>
                      </span>
                    </td>
                    <td data-label="Programme" className="t-hide-sm">
                      <span className="cell">
                        <span>{student.program}</span>
                        <span className="col-sub">{student.qualification}</span>
                      </span>
                    </td>
                    <td data-label="Fee">
                      {student.fee_status === 'unpaid' ? (
                        <button
                          type="button"
                          className="agent-btn agent-btn-primary agent-btn-sm"
                          onClick={() => payFee(student)}
                          disabled={paying === student.reference}
                        >
                          {paying === student.reference ? (
                            <span className="spinner-sm" aria-hidden="true" />
                          ) : null}
                          Pay fee
                        </button>
                      ) : (
                        <span className="cell">
                          <StatusBadge
                            status={student.fee_status === 'waived' ? 'waived' : 'Paid'}
                          />
                          <span className="col-sub">{student.fee_display}</span>
                        </span>
                      )}
                    </td>
                    <td data-label="Admission">
                      <StatusBadge status={student.status} />
                    </td>
                    <td data-label="Visa">
                      <StatusBadge status={student.visa_status} />
                    </td>
                    <td data-label="Details" className="t-num">
                      <button
                        type="button"
                        className="agent-btn agent-btn-secondary agent-btn-sm"
                        onClick={() => setOpen(student)}
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <StudentDossierModal student={open} onClose={() => setOpen(null)} />
    </div>
  );
}
