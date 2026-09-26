import { useEffect, useState } from 'react';
import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';
import { formatDate, formatNaira } from '../../lib/format';
import { partners } from '../../api/endpoints';
import StageTrack from '../applicant/StageTrack';
import StatusBadge from './StatusBadge';

/**
 * Everything on one student, including the same stage track the student sees,
 * so the agent can answer "where are they?" without asking anyone.
 *
 * It is deliberately read-only. Milestones are recorded by the admissions desk
 * in the admin, because each one pays commission and an agent should not be
 * able to mark their own student admitted.
 */
export default function StudentDossierModal({ student, onClose }) {
  const [stages, setStages] = useState([]);

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
  }, [student]);

  if (!student) return null;

  const admitted = student.status === 'admission_granted';
  const visaDone = student.visa_status === 'completed';

  const waitingOn = visaDone
    ? null
    : admitted
      ? 'Visa verification. Your second commission is paid when the study permit is confirmed.'
      : 'The admissions decision. Your first commission is paid when the offer is issued.';

  return (
    <Modal
      open
      onClose={onClose}
      variant="agent"
      title={student.full_name}
      subtitle={student.email}
      labelledBy="dossier-title"
      size={640}
      footer={
        <button type="button" className="agent-btn agent-btn-secondary" onClick={onClose}>
          Close
        </button>
      }
    >
      <div className="dossier-grid">
        <div className="dossier-item">
          <span className="d-label">Phone</span>
          <span className="d-val">{student.phone || 'Not provided'}</span>
        </div>
        <div className="dossier-item">
          <span className="d-label">Route</span>
          <span className="d-val">
            {student.origin_country} to {student.destination_country}
          </span>
        </div>
        <div className="dossier-item">
          <span className="d-label">Admission</span>
          <div>
            <StatusBadge status={student.status} />
          </div>
        </div>
        <div className="dossier-item dossier-item-wide">
          <span className="d-label">Institution</span>
          <span className="d-val d-val-accent">
            {student.institution}
          </span>
          <span className="d-val d-val-sm">
            {student.program}
          </span>
        </div>
        <div className="dossier-item">
          <span className="d-label">Academics</span>
          <span className="d-val">
            {student.qualification} ({student.year_graduated})
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--g-ink-3)' }}>{student.grade_gpa}</span>
        </div>
        <div className="dossier-item">
          <span className="d-label">Registered</span>
          <span className="d-val">{formatDate(student.submitted_at)}</span>
        </div>
        <div className="dossier-item">
          <span className="d-label">Commission earned</span>
          <span className="d-val">{formatNaira(student.commission_earned)}</span>
        </div>
        <div className="dossier-item">
          <span className="d-label">Visa</span>
          <div>
            <StatusBadge status={student.visa_status} />
          </div>
        </div>
        <div className="dossier-item dossier-item-wide">
          <span className="d-label">Documents</span>
          <div className="dossier-tags">
            {student.documents.length === 0 ? (
              <span className="d-val">None uploaded.</span>
            ) : (
              student.documents.map((doc) => (
                <span className="doc-tag" key={doc}>
                  {doc}
                </span>
              ))
            )}
          </div>
        </div>
        {student.notes ? (
          <div className="dossier-item dossier-item-wide">
            <span className="d-label">Notes</span>
            <p className="d-note">
              {student.notes}
            </p>
          </div>
        ) : null}
      </div>

      <h4 className="dossier-section-title">Progress</h4>
      <StageTrack stages={stages} />

      {waitingOn ? (
        <div className="callout callout-info">
          <Icon name="clock" size={20} className="callout-icon" strokeWidth={2} />
          <div className="callout-content">
            <strong>Waiting on:</strong> {waitingOn}
          </div>
        </div>
      ) : (
        <div className="callout callout-success">
          <Icon name="checkCircle" size={20} className="callout-icon" strokeWidth={2} />
          <div className="callout-content">
            <strong>Complete.</strong> Both commissions on this student have been paid.
          </div>
        </div>
      )}
    </Modal>
  );
}
