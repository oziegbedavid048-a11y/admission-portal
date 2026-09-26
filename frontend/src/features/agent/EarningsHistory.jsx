import { Link } from 'react-router-dom';
import Icon from '../../lib/icons';
import { formatNaira, timeAgo } from '../../lib/format';

/**
 * An agent's commission ledger.
 *
 * It used to fall back to four invented commissions and a made-up balance when
 * the API returned nothing, so a brand-new agent was shown four students they
 * had never registered and a ₦120,000 total they had never earned. An empty
 * ledger now says it is empty.
 */

export default function EarningsHistory({ commissions = [], wallet }) {
  const displayItems = commissions;
  const totalEarned = Number(wallet?.total_earned ?? 0);
  const available = Number(wallet?.available_balance ?? 0);

  return (
    <div className="eh-wrapper">
      {/* Top Balance & Settlement Header */}
      <div className="eh-header-row">
        <div className="eh-balance-col">
          <span className="eh-balance-sub">Available Balance</span>
          <span className="eh-balance-val">{formatNaira(available)}</span>
        </div>
        <div className="eh-balance-col text-right">
          <span className="eh-balance-sub">Total Earned</span>
          <span className="eh-balance-val is-earned">{formatNaira(totalEarned)}</span>
        </div>
      </div>

      {displayItems.length === 0 ? (
        <div className="eh-empty">
          <Icon name="wallet" size={26} strokeWidth={1.6} />
          <p className="eh-empty-title">No commission yet</p>
          <p className="eh-empty-note">
            You earn {formatNaira(30000)} when a student you registered has their
            application fee settled, and the same again when their visa is verified.
          </p>
          <Link to="/agent/students/new" className="agent-btn agent-btn-primary agent-btn-sm">
            <Icon name="userPlus" size={15} strokeWidth={2.2} />
            Register a student
          </Link>
        </div>
      ) : (
      <div className="eh-ledger">
        {displayItems.map((item) => {
          const isVisa = item.kind === 'visa';
          const milestoneText =
            item.kind_display ||
            (isVisa ? 'Visa verification approved' : 'Admission offer verified');

          return (
            <div className="eh-ledger-row" key={item.id}>
              <div className="eh-row-left">
                <span className="eh-student-name">{item.student_name || 'Student Candidate'}</span>
                <div className="eh-row-sub">
                  <span className="eh-milestone-text">{milestoneText}</span>
                </div>
              </div>

              <div className="eh-row-right">
                <span className="eh-amount">+{formatNaira(item.amount)}</span>
                <div className="eh-row-status-line">
                  <span className="eh-status-pill">{item.status || 'Settled'}</span>
                  <span className="eh-date">{timeAgo(item.earned_at)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      )}

      <div className="eh-footer">
        <span className="eh-footer-count">
          {displayItems.length === 0
            ? 'Nothing settled yet'
            : `Showing the latest ${displayItems.length} commission payout${displayItems.length === 1 ? '' : 's'}`}
        </span>
        <Link to="/agent/wallet" className="agent-btn agent-btn-secondary agent-btn-sm eh-action-btn">
          Manage wallet
        </Link>
      </div>
    </div>
  );
}
