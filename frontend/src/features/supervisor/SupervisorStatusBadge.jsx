import { statusTone } from '../../lib/format';

// A payout reads as money moving, not as a review outcome.
const PAYOUT = {
  pending: ['pending', 'In review'],
  sending: ['in-progress', 'Sending'],
  completed: ['completed', 'Paid out'],
  rejected: ['rejected', 'Failed'],
};

/** The same pill the agent portal uses, so one status looks the same everywhere. */
export default function SupervisorStatusBadge({ status, payout = false }) {
  const [tone, label] = (payout && PAYOUT[status]) || statusTone(status);
  return <span className={`tbl-badge ${tone}`}>{label}</span>;
}
