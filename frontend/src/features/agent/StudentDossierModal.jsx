import { useEffect, useState } from 'react';
import Modal from '../../components/ui/Modal';
import DocumentReplaceButton from '../../components/ui/DocumentReplaceButton';
import Icon from '../../lib/icons';
import { formatDate, formatNaira, resolveMediaUrl } from '../../lib/format';
import { errorMessage } from '../../api/client';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import StageTrack from '../applicant/StageTrack';
import FeePayment from './FeePayment';
import StatusBadge from './StatusBadge';
import { PaymentBadge } from './StudentsTable';
import { downloadStudentSummary } from './studentSummary';

const DOC_TONE = {
  Verified: ['approved', 'Verified'],
  Rejected: ['rejected', 'Needs replacing'],
};

/**
 * One student's progress, laid out the way the admissions desk sees the file
 * in the admin: payment, the four verification checks, the stages, each
 * document with its review, and any letters issued.
 *
 * The agent can act only where the desk expects them to: pay the fee, replace
 * a rejected document, and download the summary once the fee is paid.
 * Decisions stay with the desk.
 */
export default function StudentDossierModal({ student, onClose, onChanged }) {
  const [stages, setStages] = useState([]);
  const [downloading, setDownloading] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!student) return undefined;
    let cancelled = false;
    partners
      .studentStages(student.reference)
      .then(({ data }) => {
        if (!cancelled) setStages(data);
      })
      .catch(() => {
        if (!cancelled) setStages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [student?.reference]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!student) return null;

  const fee = student.fee_status;
  const payment = student.payment;
  const settled = fee === 'paid' || fee === 'waived';
  const checkpoints = student.verification?.checkpoints || [];

  const summary = async () => {
    setDownloading(true);
    try {
      await downloadStudentSummary(student.reference);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not download the summary.'));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      variant="agent"
      title={student.full_name}
      subtitle={`${student.reference} · ${student.origin_country} to ${student.destination_country}`}
      labelledBy="dossier-title"
      size={720}
      footer={
        <button type="button" className="agent-btn agent-btn-secondary" onClick={onClose}>
          Close
        </button>
      }
    >
      <div className="ds">
        <dl className="ds-facts">
          <div>
            <dt>University</dt>
            <dd>{student.institution || 'To be confirmed'}</dd>
          </div>
          <div>
            <dt>Course</dt>
            <dd>{student.program || '—'}</dd>
          </div>
          <div>
            <dt>Application</dt>
            <dd>
              <StatusBadge status={student.status} />
            </dd>
          </div>
          <div>
            <dt>Visa</dt>
            <dd>
              <StatusBadge status={student.visa_status} />
            </dd>
          </div>
          <div>
            <dt>Registered</dt>
            <dd>{formatDate(student.submitted_at)}</dd>
          </div>
          <div>
            <dt>Commission earned</dt>
            <dd>{formatNaira(student.commission_earned)}</dd>
          </div>
        </dl>

        <section className="ds-section">
          <div className="ds-section-head">
            <h3>Application fee</h3>
            <PaymentBadge status={fee} />
          </div>
          {settled ? (
            <div className="ds-row">
              <span>{fee === 'waived' ? 'No fee for this university.' : `Paid ${student.fee_display}.`}</span>
              <button type="button" className="agent-btn agent-btn-secondary agent-btn-sm" onClick={summary} disabled={downloading}>
                {downloading ? <span className="spinner-sm" aria-hidden="true" /> : null}
                Download student summary
              </button>
            </div>
          ) : fee === 'review' ? (
            <p className="ds-text">
              Your transfer receipt{payment?.transfer_bank ? ` for ${payment.transfer_bank}` : ''} is with the
              admissions desk. Your commission is credited once they confirm the money arrived.
            </p>
          ) : (
            <FeePayment
              reference={student.reference}
              rejectedNote={payment?.review_note || ''}
              onTransferSent={() => {
                toast.success('Receipt sent. We will confirm the payment shortly.');
                onChanged?.();
              }}
              onWaived={() => {
                toast.success('Done. No fee is due for this university.');
                onChanged?.();
              }}
            />
          )}
        </section>

        <section className="ds-section">
          <div className="ds-section-head">
            <h3>Verification</h3>
            <span className="ds-muted">{student.verification?.status_label}</span>
          </div>
          <ul className="ds-checks">
            {checkpoints.map((check) => (
              <li key={check.key} className={check.verified ? 'is-done' : ''}>
                <span className="ds-check-mark" aria-hidden="true">
                  {check.verified ? <Icon name="check" size={13} strokeWidth={3} /> : null}
                </span>
                <span>{check.label}</span>
                <span className="ds-check-state">{check.verified ? 'Verified' : 'Waiting'}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="ds-section">
          <div className="ds-section-head">
            <h3>Progress</h3>
          </div>
          <StageTrack stages={stages} />
        </section>

        <section className="ds-section">
          <div className="ds-section-head">
            <h3>Documents</h3>
            <span className="ds-muted">{student.documents.length}</span>
          </div>
          {student.documents.length === 0 ? (
            <p className="ds-text">No documents uploaded.</p>
          ) : (
            <ul className="ds-docs">
              {student.documents.map((doc) => {
                const [tone, label] = DOC_TONE[doc.status] || ['pending', 'In review'];
                return (
                  <li key={doc.id}>
                    <div className="ds-doc-row">
                      <span className="ds-doc-name">{doc.name}</span>
                      <span className={`tbl-badge ${tone}`}>{label}</span>
                    </div>
                    {doc.status === 'Rejected' ? (
                      <div className="ds-doc-review">
                        <p>{doc.review_note || 'Please upload a clearer, complete copy.'}</p>
                        <DocumentReplaceButton
                          reference={student.reference}
                          documentId={doc.id}
                          onReplaced={async () => {
                            toast.success('Replacement uploaded. It is back in review.');
                            await onChanged?.();
                          }}
                        />
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {student.letters?.length ? (
          <section className="ds-section">
            <div className="ds-section-head">
              <h3>Letters</h3>
            </div>
            <ul className="ds-docs">
              {student.letters.map((letter) => (
                <li key={letter.id}>
                  <div className="ds-doc-row">
                    <span className="ds-doc-name">
                      {letter.title}
                      <small>
                        {letter.kind} · {formatDate(letter.issued_at)}
                      </small>
                    </span>
                    <a
                      className="agent-btn agent-btn-secondary agent-btn-sm"
                      href={resolveMediaUrl(letter.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Open
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </Modal>
  );
}
