import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import Loading from '../../components/ui/Loading';
import { errorMessage } from '../../api/client';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { formatDate } from '../../lib/format';
import StudentDossierModal from './StudentDossierModal';
import StudentsTable from './StudentsTable';
import { useOnWalletChange } from './AgentContext';

const FILTERS = [
  { value: 'all', label: 'All statuses' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'in_review', label: 'In review' },
  { value: 'admission_granted', label: 'Admitted' },
  { value: 'rejected', label: 'Declined' },
  { value: 'fee:unpaid', label: 'Fee not paid' },
  { value: 'fee:review', label: 'Payment awaiting confirmation' },
];

/**
 * Every student this agent registered, and the registrations they saved to
 * finish later. Register a student sits on its own above both.
 */
export default function AgentStudents() {
  const [tab, setTab] = useState('students');
  const [students, setStudents] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [openRef, setOpenRef] = useState(null);
  const [deleting, setDeleting] = useState(null);
  // Deleting a draft cannot be undone, so it takes a second, explicit click.
  const [confirmId, setConfirmId] = useState(null);
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const load = useCallback(async (quiet = false) => {
    try {
      const [{ data: list }, { data: saved }] = await Promise.all([partners.students(), partners.drafts()]);
      setStudents(list);
      setDrafts(saved);
    } catch {
      if (!quiet) toast.error('Could not load your students.');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  // Opened from the overview's Open button.
  useEffect(() => {
    if (location.state?.open) setOpenRef(location.state.open);
  }, [location.state]);

  // Decisions are made by the desk, so the table keeps itself current.
  useLiveRefresh(() => load(true));
  useOnWalletChange(() => load(true));

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return students.filter((student) => {
      if (status.startsWith('fee:')) {
        const fee = status.slice(4);
        const current = student.fee_status === 'pending' ? 'unpaid' : student.fee_status;
        if (current !== fee) return false;
      } else if (status !== 'all' && student.status !== status) {
        return false;
      }
      if (!needle) return true;
      return [student.full_name, student.reference, student.institution, student.program, student.destination_country, student.email]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(needle));
    });
  }, [students, query, status]);

  const open = students.find((student) => student.reference === openRef) || null;

  const removeDraft = async (draft) => {
    setDeleting(draft.id);
    try {
      await partners.deleteDraft(draft.id);
      setDrafts((current) => current.filter((item) => item.id !== draft.id));
      toast.success('Draft deleted.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not delete that draft.'));
    } finally {
      setDeleting(null);
    }
  };

  if (loading) return <Loading label="Loading your students" />;

  return (
    <div className="agent-stack">
      <div className="ag-page-head">
        <div>
          <h1 className="ag-page-title">Students</h1>
          <p className="ag-page-sub">
            {students.length} registered{drafts.length ? ` · ${drafts.length} draft${drafts.length === 1 ? '' : 's'}` : ''}
          </p>
        </div>
        <Link className="agent-btn agent-btn-primary" to="/agent/students/new">
          Register a student
        </Link>
      </div>

      <section className="agent-card">
        <div className="ag-tabs" role="tablist" aria-label="Students and drafts">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'students'}
            className={`ag-tab${tab === 'students' ? ' is-active' : ''}`}
            onClick={() => setTab('students')}
          >
            Your students <span className="ag-tab-count">{students.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'drafts'}
            className={`ag-tab${tab === 'drafts' ? ' is-active' : ''}`}
            onClick={() => setTab('drafts')}
          >
            Drafts <span className="ag-tab-count">{drafts.length}</span>
          </button>
        </div>

        {tab === 'students' ? (
          <>
            <div className="ag-filters">
              <label className="sr-only" htmlFor="student-search">
                Search students
              </label>
              <input
                type="search"
                id="student-search"
                className="agent-form-control"
                placeholder="Search by name, reference or university"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
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

            {visible.length === 0 ? (
              <div className="ag-empty">
                <p>{students.length ? 'No students match.' : 'No students yet.'}</p>
                <span>{students.length ? 'Clear the search or filter to see everyone.' : 'Register one to get started.'}</span>
              </div>
            ) : (
              <StudentsTable students={visible} onOpen={(student) => setOpenRef(student.reference)} />
            )}
          </>
        ) : drafts.length === 0 ? (
          <div className="ag-empty">
            <p>No drafts.</p>
            <span>Use Save draft while registering a student to finish it later.</span>
          </div>
        ) : (
          <div className="ag-table-scroll" role="region" aria-label="Drafts" tabIndex={0}>
            <table className="ag-table ag-table-drafts">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Destination</th>
                  <th>Step</th>
                  <th>Documents</th>
                  <th>Last saved</th>
                  <th className="ag-col-action">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {drafts.map((draft) => {
                  const form = draft.data?.form || {};
                  return (
                    <tr key={draft.id}>
                      <td>
                        <span className="ag-name">{form.fullName || 'Unnamed student'}</span>
                        <span className="ag-sub">{form.email || 'No email yet'}</span>
                      </td>
                      <td className="ag-nowrap">{form.destinationCountry || '—'}</td>
                      <td className="ag-nowrap">{draft.step} of 5</td>
                      <td className="ag-nowrap">{draft.files.length}</td>
                      <td className="ag-nowrap">{formatDate(draft.updated_at)}</td>
                      <td className="ag-col-action">
                        <div className="ag-row-actions">
                          <button
                            type="button"
                            className={`ag-text-btn${confirmId === draft.id ? ' is-danger' : ''}`}
                            onClick={() => (confirmId === draft.id ? removeDraft(draft) : setConfirmId(draft.id))}
                            onBlur={() => setConfirmId((current) => (current === draft.id ? null : current))}
                            disabled={deleting === draft.id}
                          >
                            {deleting === draft.id ? 'Deleting' : confirmId === draft.id ? 'Confirm delete' : 'Delete'}
                          </button>
                          <button
                            type="button"
                            className="ag-open-btn"
                            onClick={() => navigate('/agent/students/new', { state: { draftId: draft.id } })}
                          >
                            Continue
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <StudentDossierModal
        student={open}
        onClose={() => setOpenRef(null)}
        onChanged={() => load(true)}
      />
    </div>
  );
}
