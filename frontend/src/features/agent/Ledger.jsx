import { formatDateTimeParts } from '../../lib/format';

/**
 * Small pieces shared by the agent's money tables (earning history,
 * withdrawals, Ads funding requests): a date with its time under it, and a
 * status written as a word beside a coloured dot rather than a button-like pill.
 */

export function LedgerDate({ value }) {
  const { date, time } = formatDateTimeParts(value);
  return (
    <span className="ledger-date">
      <span className="ledger-date-day">{date}</span>
      {time ? <span className="ledger-date-time">{time}</span> : null}
    </span>
  );
}

// The same moment on one line, for the compact layout: "2 Oct 2026 · 14:05".
export function LedgerDateLine({ value }) {
  const { date, time } = formatDateTimeParts(value);
  return <span className="ledger-sub ledger-compact-only">{time ? `${date} · ${time}` : date}</span>;
}

// tone: good (green), wait (amber), bad (red), muted (grey).
export function LedgerStatus({ tone = 'muted', children }) {
  return <span className={`ledger-status is-${tone}`}>{children}</span>;
}

const WITHDRAWAL_STATUS = {
  pending: ['wait', 'In review'],
  completed: ['good', 'Paid out'],
  rejected: ['bad', 'Failed'],
};

export function withdrawalStatus(status) {
  return WITHDRAWAL_STATUS[status] || ['muted', String(status || 'Not set')];
}

const LOAN_STATUS = {
  pending: ['wait', 'In review'],
  approved: ['good', 'Approved'],
  disbursed: ['good', 'Disbursed'],
  repaid: ['muted', 'Repaid'],
  declined: ['bad', 'Declined'],
};

export function loanStatus(status) {
  return LOAN_STATUS[status] || ['muted', String(status || 'Not set')];
}
