import { formatDate } from '../../lib/format';
import StatusBadge from './StatusBadge';

/**
 * The agent's students as a plain, scrollable table. Used on the overview (the
 * five newest) and on Students (all of them), so both read the same way.
 * Every row ends with Open, which shows that student's progress.
 */

// How the application fee stands, in the words the admin uses.
export const PAYMENT_LABEL = {
  paid: ['approved', 'Paid'],
  waived: ['approved', 'Waived'],
  review: ['pending', 'Awaiting confirmation'],
  pending: ['na', 'Not paid'],
  unpaid: ['na', 'Not paid'],
};

export function PaymentBadge({ status }) {
  const [tone, label] = PAYMENT_LABEL[status] || PAYMENT_LABEL.unpaid;
  return <span className={`tbl-badge ${tone}`}>{label}</span>;
}

export default function StudentsTable({ students, onOpen, compact = false }) {
  return (
    <div className="ag-table-scroll" role="region" aria-label="Students" tabIndex={0}>
      <table className="ag-table">
        <thead>
          <tr>
            <th>Student</th>
            <th>Reference</th>
            <th>University</th>
            {compact ? null : <th>Course</th>}
            <th>Payment</th>
            <th>Status</th>
            {compact ? null : <th>Registered</th>}
            <th className="ag-col-action">
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {students.map((student) => (
            <tr key={student.reference}>
              <td>
                <span className="ag-name">{student.full_name}</span>
                <span className="ag-sub">{student.destination_country}</span>
              </td>
              <td className="ag-mono">{student.reference}</td>
              <td className="ag-wrap">{student.institution || 'To be confirmed'}</td>
              {compact ? null : <td className="ag-wrap">{student.program || '—'}</td>}
              <td>
                <PaymentBadge status={student.fee_status} />
              </td>
              <td>
                <StatusBadge status={student.status} />
              </td>
              {compact ? null : <td className="ag-nowrap">{formatDate(student.submitted_at)}</td>}
              <td className="ag-col-action">
                <button type="button" className="ag-open-btn" onClick={() => onOpen(student)}>
                  Open
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
