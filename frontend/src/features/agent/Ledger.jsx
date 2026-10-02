import { useState } from 'react';
import { formatDateTimeParts } from '../../lib/format';

/**
 * Small pieces shared by the agent's money tables (earning history,
 * withdrawals, Ads funding requests, overview commissions): a date with its
 * time under it, a status written as a word beside a coloured dot rather than
 * a button-like pill, and Show more for long lists.
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

/**
 * Long lists show ten rows at first, with Show more under the table, so the
 * page stays short without putting the table in a box of its own that
 * scrolls up and down (that box caught the swipe and the page stopped
 * scrolling).
 */
export function useShowMore(rows, step = 10) {
  const [limit, setLimit] = useState(step);
  return {
    visible: rows.slice(0, limit),
    hasMore: rows.length > limit,
    more: () => setLimit((current) => current + step),
  };
}

export function ShowMore({ list }) {
  if (!list.hasMore) return null;
  return (
    <div className="ledger-more">
      <button type="button" className="agent-btn agent-btn-secondary agent-btn-sm" onClick={list.more}>
        Show more
      </button>
    </div>
  );
}
