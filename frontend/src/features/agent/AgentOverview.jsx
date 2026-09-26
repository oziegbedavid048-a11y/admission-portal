import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PipelinePieChart from './PipelinePieChart';
import EarningsHistory from './EarningsHistory';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { firstNameOf, formatNaira, timeAgo } from '../../lib/format';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import CurrencyConverter from './CurrencyConverter';
import { useAgent } from './AgentContext';
import StatusBadge from './StatusBadge';
import WeatherBanner from '../../components/ui/WeatherBanner';

const ACTIONS = [
  {
    to: '/agent/students/new',
    icon: 'userPlus',
    title: 'Register a student',
    sub: 'File a full application on their behalf',
  },
  {
    to: '/agent/wallet',
    icon: 'download',
    title: 'Withdraw your earnings',
    sub: 'Move confirmed commission to your bank',
  },
  {
    to: '/agent/loans',
    icon: 'adsLoan',
    title: 'Request Ads Loan',
    sub: '0% interest capital to recruit more students',
  },
];

export default function AgentOverview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { profile, setWallet } = useAgent();
  const toast = useToast();
  const navigate = useNavigate();

  const load = useCallback(
    async (quiet = false) => {
      try {
        const { data: payload } = await partners.overview();
        setData(payload);
        setWallet(payload.wallet);
      } catch {
        if (!quiet) toast.error('Could not load your overview.');
      } finally {
        setLoading(false);
      }
    },
    [setWallet, toast],
  );

  useEffect(() => {
    load();
  }, [load]);

  // Commissions and statuses change when the admissions desk approves something,
  // so the overview refetches quietly rather than waiting for a reload.
  useLiveRefresh(() => load(true));

  if (loading) return <Loading label="Loading your overview" />;
  if (!data) return null;

  const { stats, pipeline, recent_students: recent, activity } = data;

  return (
    <div className="agent-stack">
      <WeatherBanner
        userName={firstNameOf(profile?.full_name || profile?.business_name || '')}
        subtitle="Your recruitment commissions and student pipeline overview."
      />

      <div className="agent-stats">
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="users" size={20} />
          </span>
          <span className="s-label">Students</span>
          <span className="s-value">{stats.students}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="badgeCheck" size={20} />
          </span>
          <span className="s-label">Admitted</span>
          <span className="s-value">{stats.admitted}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="passport" size={20} />
          </span>
          <span className="s-label">Visas verified</span>
          <span className="s-value">{stats.visas_verified}</span>
        </div>
        <div className="agent-stat">
          <span className="agent-icon" aria-hidden="true">
            <Icon name="trend" size={20} />
          </span>
          <span className="s-label">Earned</span>
          <span className="s-value">{formatNaira(data.wallet.total_earned)}</span>
        </div>
      </div>

      <div className="chart-row">
        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">Student pipeline</h2>
            <span className="agent-card-note">
              {stats.students} {stats.students === 1 ? 'applicant' : 'applicants'}
            </span>
          </div>
          <PipelinePieChart pipeline={pipeline} totalStudents={stats.students} />
        </section>

        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">Earning history</h2>
          </div>
          <EarningsHistory
            commissions={data.recent_commissions || []}
            wallet={data.wallet}
          />
        </section>
      </div>

      <CurrencyConverter />

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Recent students</h2>
        </div>

        {recent.length === 0 ? (
          <div className="agent-empty-msg">
            <p>No active student applications yet.</p>
            <button
              type="button"
              className="agent-btn agent-btn-primary agent-btn-sm"
              style={{ marginTop: 10 }}
              onClick={() => navigate('/agent/students/new')}
            >
              Register your first student
            </button>
          </div>
        ) : (
          <div className="agent-table-wrap">
            <table className="agent-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Destination</th>
                  <th className="t-hide-sm">Institution</th>
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
                        {student.email ? <span className="col-sub">{student.email}</span> : null}
                      </span>
                    </td>
                    <td data-label="Destination">
                      <span className="badge-country">{student.destination_country}</span>
                    </td>
                    <td data-label="Institution" className="t-hide-sm">
                      <span className="col-inst">{student.institution}</span>
                    </td>
                    <td data-label="Admission">
                      <StatusBadge status={student.status} />
                    </td>
                    <td data-label="Visa">
                      <StatusBadge status={student.visa_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {recent.length > 0 ? (
          <div className="card-foot-action">
            <Link className="agent-btn agent-btn-secondary agent-btn-sm" to="/agent/students">
              View all students
              <Icon name="arrowRight" size={15} strokeWidth={2} />
            </Link>
          </div>
        ) : null}
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="badgeCheck" size={18} />
            </span>
            What you can do
          </h2>
        </div>
        <div className="agent-action-list">
          {ACTIONS.map((action) => (
            <Link className="agent-action" to={action.to} key={action.to}>
              <span className="agent-icon accent" aria-hidden="true">
                <Icon name={action.icon} size={20} />
              </span>
              <span className="agent-action-text">
                <span className="agent-action-title">{action.title}</span>
                <span className="agent-action-sub">{action.sub}</span>
              </span>
              <Icon name="chevronRight" size={18} className="agent-action-go" />
            </Link>
          ))}
        </div>
      </section>

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
