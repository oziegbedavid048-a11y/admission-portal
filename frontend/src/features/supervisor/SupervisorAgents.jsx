import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { formatDate, formatNaira } from '../../lib/format';
import { supervisors } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { useSupervisor } from './SupervisorContext';

/** Everyone who signed up with this Sales Manager's code, and what they have done. */
export default function SupervisorAgents() {
  const { profile } = useSupervisor();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const toast = useToast();
  const navigate = useNavigate();

  const load = async (quiet = false) => {
    try {
      const { data } = await supervisors.agents();
      setAgents(data);
    } catch {
      if (!quiet) toast.error('Could not load your agents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useLiveRefresh(() => load(true));

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return agents;
    return agents.filter((agent) =>
      [agent.full_name, agent.email, agent.agency_name, agent.partner_code]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(needle)),
    );
  }, [agents, query]);

  const totals = useMemo(
    () =>
      agents.reduce(
        (sum, agent) => ({
          students: sum.students + agent.students,
          visas: sum.visas + agent.visas_verified,
          bonus: sum.bonus + Number(agent.bonus_from_agent || 0),
        }),
        { students: 0, visas: 0, bonus: 0 },
      ),
    [agents],
  );

  if (loading) return <Loading label="Loading your agents" />;

  return (
    <div className="agent-stack">

      <div className="agent-stats">
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="users" size={20} />
          </span>
          <span className="s-label">Agents</span>
          <span className="s-value">{agents.length}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="cap" size={20} />
          </span>
          <span className="s-label">Students filed</span>
          <span className="s-value">{totals.students}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="passport" size={20} />
          </span>
          <span className="s-label">Visas verified</span>
          <span className="s-value">{totals.visas}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="trend" size={20} />
          </span>
          <span className="s-label">Bonus from team</span>
          <span className="s-value">{formatNaira(totals.bonus)}</span>
        </div>
      </div>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Your team</h2>
          <span className="agent-card-note">Code {profile?.agent_code}</span>
        </div>

        {agents.length === 0 ? (
          <div className="agent-empty-state">
            <p>No agents yet</p>
            <small>
              Share your code <strong>{profile?.agent_code}</strong>. An agent enters it
              on the sign-up form and appears here straight away.
            </small>
          </div>
        ) : (
          <>
            <div className="applicants-filter-bar">
              <div className="applicants-search-wrap">
                <Icon name="search" size={18} />
                <label className="sr-only" htmlFor="agent-search">
                  Search agents
                </label>
                <input
                  type="search"
                  id="agent-search"
                  className="agent-form-control"
                  placeholder="Search a name, email or agency"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
            </div>

            <div className="agent-table-wrap">
              <table className="agent-table">
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th className="t-hide-sm">Joined</th>
                    <th className="t-num">Students</th>
                    <th className="t-num t-hide-sm">Fees paid</th>
                    <th className="t-num">Visas</th>
                    <th className="t-num t-hide-sm">Your bonus</th>
                    <th className="t-num">
                      <span className="sr-only">Students</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visible.length === 0 ? (
                    <tr className="row-empty">
                      <td colSpan={7}>
                        <div className="agent-empty-state">
                          <p>No agents match</p>
                          <small>Clear the search to see everyone.</small>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    visible.map((agent) => (
                      <tr key={agent.id}>
                        <td data-label="Agent">
                          <span className="cell">
                            <span className="col-name">{agent.full_name}</span>
                            <span className="col-sub">{agent.email}</span>
                          </span>
                        </td>
                        <td data-label="Joined" className="t-hide-sm">
                          {formatDate(agent.joined_at)}
                        </td>
                        <td data-label="Students" className="t-num">
                          {agent.students}
                        </td>
                        <td data-label="Fees paid" className="t-num t-hide-sm">
                          {agent.fees_paid}
                        </td>
                        <td data-label="Visas" className="t-num col-amount">
                          {agent.visas_verified}
                        </td>
                        <td data-label="Your bonus" className="t-num t-hide-sm col-amount">
                          {formatNaira(agent.bonus_from_agent)}
                        </td>
                        <td data-label="Students" className="t-num">
                          <button
                            type="button"
                            className="agent-btn agent-btn-secondary agent-btn-sm"
                            onClick={() =>
                              navigate('/sales-manager/students', { state: { agent: agent.id } })
                            }
                          >
                            Students
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
