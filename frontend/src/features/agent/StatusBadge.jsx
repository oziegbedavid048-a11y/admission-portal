import { statusTone } from '../../lib/format';

export default function StatusBadge({ status }) {
  const [tone, label] = statusTone(status);
  return <span className={`tbl-badge ${tone}`}>{label}</span>;
}
