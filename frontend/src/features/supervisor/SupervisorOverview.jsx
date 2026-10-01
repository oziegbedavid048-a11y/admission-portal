import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PieChart, chartTone } from '../../components/charts/Chart';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { firstNameOf, formatNaira, timeAgo } from '../../lib/format';
import { supervisors } from '../../api/endpoints';
import WeatherBanner from '../../components/ui/WeatherBanner';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import AgentCodeCard from './AgentCodeCard';
import { useSupervisor } from './SupervisorContext';
import SupervisorStatusBadge from './SupervisorStatusBadge';

export default function SupervisorOverview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { setProfile } = useSupervisor();
  const toast = useToast();
  const navigate = useNavigate();

  const load = useCallback(
    async (quiet = false) => {
      try {
        const { data: payload } = await supervisors.overview();
        setData(payload);
        setProfile(payload.profile);
      } catch {
        if (!quiet) toast.error('Could not load your overview.');
      } finally {
        setLoading(false);
      }
    },
    [setProfile, toast],
  );

  useEffect(() => {
    load();
  }, [load]);

  // A bonus lands when a student's application fee is paid, so the page keeps
  // itself current rather than waiting for a reload.
  useLiveRefresh(() => load(true));

  if (loading) return <Loading label="Loading your team" />;
  if (!data) return null;

  const { profile, stats, earnings, pipeline, top_agents: top, recent_students: recent, activity } = data;
  const hasTeam = stats.agents > 0;
  const hasStudents = stats.students > 0;

  // One slice per agent who has earned something. The ramp is ordinal and the
  // rows arrive sorted, so the biggest contributor takes the darkest green.
  const RAMP = ['--g-chart-4', '--g-chart-3', '--g-chart-2', '--g-chart-1'];
  const FALLBACK = ['#0b5c43', '#227152', '#4e9f79', '#7fbe9c'];
  const bonusRows = (earnings.by_agent || [])
    .filter((row) => Number(row.amount) > 0)
    .map((row, index) => ({
      label: row.agent,
      value: Number(row.amount),
      color: chartTone(
        RAMP[Math.min(index, RAMP.length - 1)],
        FALLBACK[Math.min(index, FALLBACK.length - 1)],
      ),
    }));

  return (
    <div className="agent-stack">
      <WeatherBanner
        userName={firstNameOf(profile?.full_name || profile?.business_name || '')}
        subtitle="Your agents, their students, and what you have earned."
      />

      <AgentCodeCard code={profile.agent_code} agentCount={stats.agents} />

      <div className="agent-stats">
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="users" size={20} />
          </span>
          <span className="s-label">Agents</span>
          <span className="s-value">{stats.agents}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="cap" size={20} />
          </span>
          <span className="s-label">Students</span>
          <span className="s-value">{stats.students}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="currency" size={20} />
          </span>
          <span className="s-label">Bonus per student</span>
          <span className="s-value">{formatNaira(earnings.per_student)}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="trend" size={20} />
          </span>
          <span className="s-label">Bonus earned</span>
          <span className="s-value">{formatNaira(earnings.bonus_total)}</span>
        </div>
      </div>

      <div className="chart-row">
        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">Student pipeline</h2>
          </div>
          {hasStudents ? (
            <PieChart
              height={260}
              valueLabel="Students"
              centreLabel={stats.students === 1 ? 'student' : 'students'}
              centreValue={String(stats.students)}
              ariaLabel={`Pipeline: ${pipeline.awaiting_fee} awaiting fee, ${pipeline.in_review} in review, ${pipeline.admitted} admitted, ${pipeline.visa_verified} verified`}
              rows={[
                {
                  label: 'Awaiting fee',
                  value: pipeline.awaiting_fee,
                  color: chartTone('--g-chart-muted', '#948a78'),
                },
                {
                  label: 'In review',
                  value: pipeline.in_review,
                  color: chartTone('--g-chart-1', '#7fbe9c'),
                },
                {
                  label: 'Admitted',
                  value: pipeline.admitted,
                  color: chartTone('--g-chart-3', '#227152'),
                },
                {
                  label: 'Visa verified',
                  value: pipeline.visa_verified,
                  color: chartTone('--g-chart-4', '#0b5c43'),
                },
              ]}
            />
          ) : (
            <p className="chart-empty">
              No students yet. They appear here as soon as your agents file them.
            </p>
          )}
        </section>

        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">Bonus by agent</h2>
          </div>
          {bonusRows.length > 0 ? (
            <PieChart
              height={260}
              valueLabel="Bonus"
              format={formatNaira}
              centreLabel="earned"
              centreValue={formatNaira(earnings.bonus_total)}
              ariaLabel={`Bonus by agent: ${bonusRows
                .map((row) => `${row.label} ${formatNaira(row.value)}`)
                .join(', ')}`}
              rows={bonusRows}
            />
          ) : (
            <p className="chart-empty">No bonuses yet</p>
          )}
        </section>
      </div>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Your agents</h2>
        </div>

        {!hasTeam ? (
          <div className="agent-empty-msg">
            <p>No agents have joined yet.</p>
            <small>
              Share your code <strong>{profile.agent_code}</strong> with an agent and they
              appear here the moment they register.
            </small>
          </div>
        ) : (
          <>
            <div className="agent-table-wrap">
              <table className="agent-table">
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th className="t-num">Students</th>
                    <th className="t-num t-hide-sm">Admitted</th>
                    <th className="t-num">Visas</th>
                    <th className="t-num t-hide-sm">Your bonus</th>
                  </tr>
                </thead>
                <tbody>
                  {top.map((agent) => (
                    <tr key={agent.id}>
                      <td data-label="Agent">
                        <span className="cell">
                          <span className="col-name">{agent.full_name}</span>
                          <span className="col-sub">{agent.email}</span>
                        </span>
                      </td>
                      <td data-label="Students" className="t-num">
                        {agent.students}
                      </td>
                      <td data-label="Admitted" className="t-num t-hide-sm">
                        {agent.admitted}
                      </td>
                      <td data-label="Visas" className="t-num col-amount">
                        {agent.visas_verified}
                      </td>
                      <td data-label="Your bonus" className="t-num t-hide-sm col-amount">
                        {formatNaira(agent.bonus_from_agent)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card-foot-action">
              <Link className="agent-btn agent-btn-secondary agent-btn-sm" to="/sales-manager/agents">
                View all agents
                <Icon name="arrowRight" size={15} strokeWidth={2} />
              </Link>
            </div>
          </>
        )}
      </section>

      {hasStudents ? (
        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">Recent students</h2>
          </div>

          <div className="agent-table-wrap">
            <table className="agent-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th className="t-hide-sm">Filed by</th>
                  <th>Destination</th>
                  <th>Admission</th>
                  <th>Visa</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((student) => (
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
                      <span className="badge-country">{student.destination_country}</span>
                    </td>
                    <td data-label="Admission">
                      <SupervisorStatusBadge status={student.status} />
                    </td>
                    <td data-label="Visa">
                      <SupervisorStatusBadge status={student.visa_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card-foot-action">
            <button
              type="button"
              className="agent-btn agent-btn-secondary agent-btn-sm"
              onClick={() => navigate('/sales-manager/students')}
            >
              View all students
              <Icon name="arrowRight" size={15} strokeWidth={2} />
            </button>
          </div>
        </section>
      ) : null}

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="clock" size={18} />
            </span>
            Recent activity
          </h2>
        </div>
        <div className="agent-activity">
          {activity.length === 0 ? (
            <p className="chart-empty">Nothing has happened yet.</p>
          ) : (
            activity.map((event) => (
              <div className="row" key={`${event.at}-${event.text}`}>
                <div>
                  <div className="text">{event.text}</div>
                  <div className="when">{timeAgo(event.at)}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
