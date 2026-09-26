import { statusTone } from '../../lib/format';

/** The same pill the agent portal uses, so one status looks the same everywhere. */
export default function SupervisorStatusBadge({ status }) {
  const [tone, label] = statusTone(status);
  return <span className={`tbl-badge ${tone}`}>{label}</span>;
}
