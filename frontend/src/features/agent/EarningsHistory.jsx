import { Link } from 'react-router-dom';
import { formatNaira } from '../../lib/format';
import { LedgerDate, LedgerDateLine, LedgerStatus } from './Ledger';

/**
 * The agent's commissions on the Overview, one row per student milestone.
 *
 * It used to fall back to four invented commissions and a made-up balance when
 * the API returned nothing, so a brand-new agent was shown four students they
 * had never registered and a ₦120,000 total they had never earned. An empty
 * ledger now says it is empty.
 */
export default function EarningsHistory({ commissions = [], wallet }) {
  const totalEarned = Number(wallet?.total_earned ?? 0);
  const available = Number(wallet?.available_balance ?? 0);

  return (
    <div className="eh-wrapper">
      <div className="eh-header-row">
        <div className="eh-balance-col">
          <span className="eh-balance-sub">Available balance</span>
          <span className="eh-balance-val">{formatNaira(available)}</span>
        </div>
        <div className="eh-balance-col text-right">
          <span className="eh-balance-sub">Total earned</span>
          <span className="eh-balance-val is-earned">{formatNaira(totalEarned)}</span>
        </div>
      </div>

      <div className="ledger-scroll is-short" role="region" aria-label="Commissions" tabIndex={0}>
        {commissions.length === 0 ? (
          <div className="ledger-empty">
            <p>No commission yet</p>
            <small>Earnings appear here once a student&rsquo;s application fee is paid.</small>
          </div>
        ) : (
          <table className="ledger-table">
            <thead>
              <tr>
                <th scope="col">Student</th>
                <th scope="col" className="t-num">Amount</th>
                <th scope="col" className="ledger-wide-only">Date</th>
                <th scope="col" className="ledger-wide-only">Status</th>
              </tr>
            </thead>
            <tbody>
              {commissions.map((item) => (
                <tr key={item.id}>
                  <td className="ledger-lead">
                    <span className="ledger-main">{item.student_name || 'Student'}</span>
                    <span className="ledger-sub">
                      {item.kind === 'visa' ? 'Visa commission' : 'Registration commission'}
                    </span>
                    <LedgerDateLine value={item.earned_at} />
                  </td>
                  <td className="t-num">
                    <span className="ledger-amount is-in">+{formatNaira(item.amount)}</span>
                    <span className="ledger-compact-only ledger-status-line">
                      <LedgerStatus tone="good">Settled</LedgerStatus>
                    </span>
                  </td>
                  <td className="ledger-wide-only">
                    <LedgerDate value={item.earned_at} />
                  </td>
                  <td className="ledger-wide-only">
                    <LedgerStatus tone="good">Settled</LedgerStatus>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="eh-footer">
        <span className="eh-footer-count">
          {commissions.length === 0
            ? 'Nothing settled yet'
            : `${commissions.length} latest commission${commissions.length === 1 ? '' : 's'}`}
        </span>
        <Link to="/agent/wallet" className="agent-btn agent-btn-secondary agent-btn-sm eh-action-btn">
          Manage wallet
        </Link>
      </div>
    </div>
  );
}
