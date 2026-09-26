import { Link } from 'react-router-dom';
import Icon from '../../lib/icons';
import { firstNameOf, timeAgo } from '../../lib/format';
import { useApplication } from './ApplicationContext';
import ApplicantPieChart from './ApplicantPieChart';
import WeatherBanner from '../../components/ui/WeatherBanner';

export default function OverviewPanel() {
  const { application } = useApplication();

  const stages = application.stages || [];
  const liveIndex = Math.max(0, application.current_stage_index || 0);
  const notifications = application.notifications || [];

  return (
    <div className="portal-stack">
      {/* ── Weather Dynamic Greeting Banner ── */}
      <WeatherBanner userName={firstNameOf(application.full_name)} />

      <div className="stat-row">
        <div className="stat">
          <div className="stat-label">Documents</div>
          <div className="stat-value">{application.documents.length}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Fee paid</div>
          <div className="stat-value">{application.payment?.display_total || 'Not paid'}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Destination</div>
          <div className="stat-value">{application.destination_country || 'Not set'}</div>
        </div>
      </div>

      {/* ── Main Two-Column Intelligence Grid ── */}
      <div className="dash-grid">
        {/* Left Column: Application Progression & Activity */}
        <div className="dash-col">
          {/* Application Verification Status: placed before Application Timeline */}
          <section className="card">
            <div className="card-head">
              <h2 className="verif-card-title">Application Verification Status</h2>
            </div>

            <ApplicantPieChart
              application={application}
              documents={application.documents || []}
            />
          </section>

          {/* Application Timeline */}
          <section className="card">
            <div className="card-head">
              <h2>Application Timeline</h2>
              <span className="card-note">
                Stage {liveIndex + 1} of {stages.length}
              </span>
            </div>

            <div className="app-timeline-box">
              {stages.map((stage, idx) => {
                const isDone = stage.status === 'Completed';
                const isLive = stage.status === 'In Progress' || idx === liveIndex;
                const statusClass = isDone ? 'is-done' : isLive ? 'is-live' : 'is-pending';

                return (
                  <div key={stage.id || stage.name} className={`app-timeline-row ${statusClass}`}>
                    <div className="app-timeline-mark">
                      {isDone ? (
                        <Icon name="check" size={13} strokeWidth={3} />
                      ) : (
                        idx + 1
                      )}
                    </div>
                    {idx < stages.length - 1 ? <div className="app-timeline-line" /> : null}
                    <div className="app-timeline-content">
                      <div className="app-timeline-head">
                        <span className="app-timeline-title">{stage.name}</span>
                        <span className="app-timeline-badge">
                          {isDone ? 'Completed' : isLive ? 'In Review' : 'Upcoming'}
                        </span>
                      </div>
                      {stage.note && isLive ? (
                        <p className="app-timeline-note">{stage.note}</p>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* Right Column: Programme Details & Activity Log */}
        <div className="dash-col">
          {/* Selected Programme Summary */}
          <section className="card">
            <div className="card-head">
              <h2>Programme Details</h2>
              <Link className="g-btn g-btn-plain g-btn-sm" to="/portal/details">
                View Full
              </Link>
            </div>

            <div className="app-prog-info-list">
              <div className="app-prog-info-item">
                <span className="app-prog-info-key">Destination Country</span>
                <span className="app-prog-info-value">{application.destination_country}</span>
              </div>

              <div className="app-prog-info-item">
                <span className="app-prog-info-key">Institution</span>
                <span className="app-prog-info-value">{application.institution?.name || 'Selected University'}</span>
              </div>

              <div className="app-prog-info-item">
                <span className="app-prog-info-key">Degree & Major</span>
                <span className="app-prog-info-value">
                  {application.programs?.map((p) => p.name).join(', ') || 'Undergraduate Programme'}
                </span>
              </div>

              <div className="app-prog-info-item">
                <span className="app-prog-info-key">Prior Qualification</span>
                <span className="app-prog-info-value">{application.qualification || 'Not provided'}</span>
              </div>
            </div>
          </section>

          {/* Activity Log */}
          <section className="card">
            <div className="card-head">
              <h2>Recent Activity</h2>
              <span className="card-note">Admissions desk feed</span>
            </div>

            <div className="app-activity-stream">
              {notifications.length === 0 ? (
                <p className="card-body-text" style={{ margin: 0, padding: '12px 0' }}>
                  No recent activity updates yet. Milestones and verification notices will appear here.
                </p>
              ) : (
                notifications.slice(0, 5).map((item) => (
                  <div className="app-activity-row" key={item.id}>
                    <div className="app-activity-text">{item.text}</div>
                    <div className="app-activity-time">{timeAgo(item.created_at)}</div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
