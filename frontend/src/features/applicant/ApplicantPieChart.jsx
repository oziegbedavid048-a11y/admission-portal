import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../../lib/icons';
import StatusRing, { useSegmentTones } from '../../components/charts/StatusRing';

/**
 * What the admissions desk has and has not yet cleared on this file.
 *
 * Two checkpoints, the application fee and the uploaded documents, each an
 * equal half of the ring. Personal and academic details are not verified;
 * mistakes there are fixed with a correction request. Drawing is
 * handled by the shared StatusRing, so the colours are the brand tokens and
 * match the agent portal's ring rather than being a second palette.
 */

const CHECKPOINTS = [
  {
    key: 'payment',
    label: 'Application fee',
    shortLabel: 'Fee Clearance',
    description: 'Application fee settlement and payment confirmation.',
  },
  {
    key: 'documents',
    label: 'Uploaded documents',
    shortLabel: 'Uploads & Files',
    description: 'Passport data page, transcripts, and supporting uploads.',
  },
];

export default function ApplicantPieChart({ application = {}, documents = [], hasApplication = true }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const currentStatus =
    application?.verification_summary?.status ||
    application?.verification_status ||
    'unverified';

  const audit = useMemo(() => {
    const verification = application?.verification_summary || {};
    const docs = documents.length > 0 ? documents : application?.documents || [];
    const anyDocRejected = docs.some((doc) => doc.status === 'Rejected');
    const allDocsVerified =
      docs.length > 0 && docs.every((doc) => doc.status === 'Verified');

    const checkpoint = (key) =>
      Boolean(verification?.checkpoints?.find((c) => c.key === key)?.verified);

    const cleared = {
      payment: Boolean(
        application?.payment_verified ||
          ['paid', 'waived'].includes(application?.payment?.status) ||
          checkpoint('payment'),
      ),
      documents: Boolean(
        application?.documents_verified || allDocsVerified || checkpoint('documents'),
      ),
    };

    const inReview = currentStatus === 'in_review';

    const items = CHECKPOINTS.map((base) => {
      const verified = cleared[base.key];
      const needsAction = base.key === 'documents' && anyDocRejected && !verified;

      return {
        ...base,
        verified,
        needsAction,
        // The wording and the tone come from the same branch, so a segment can
        // never read as cleared while its chip says otherwise.
        statusLabel: needsAction
          ? 'Action required'
          : verified
            ? 'Verified'
            : inReview
              ? 'In review'
              : 'Pending',
        tone: needsAction ? 'bad' : verified ? 'done' : inReview ? 'active' : 'pending',
      };
    });

    const clearedCount = items.filter((item) => item.verified).length;

    return {
      items,
      clearedCount,
      totalCount: items.length,
      percentage: Math.round((clearedCount / items.length) * 100),
      isFullyVerified: clearedCount === items.length || currentStatus === 'verified',
      anyDocRejected,
      inReview,
    };
  }, [application, documents, currentStatus]);

  // The legend dots and the ring read the same resolved tones, so they cannot
  // disagree about what colour a checkpoint is.
  const { colors } = useSegmentTones(audit.items);

  const activeItem = hoveredIndex !== null ? audit.items[hoveredIndex] : null;

  const centreLabel = activeItem
    ? activeItem.shortLabel
    : audit.isFullyVerified
      ? 'Verified'
      : audit.inReview
        ? 'In review'
        : 'Cleared';

  return (
    <div className="applicant-pie-card">
      <div className="applicant-pie-body">
        <div className="applicant-pie-chart-wrap">
          <div className="applicant-canvas-box">
            <StatusRing
              segments={audit.items}
              weights="equal"
              onHoverChange={setHoveredIndex}
              tooltipLabel={(segment) => `${segment.label}: ${segment.statusLabel}`}
              ariaLabel={`Verification progress: ${audit.clearedCount} of ${audit.totalCount} checkpoints cleared`}
            >
              <div className="applicant-pie-center" aria-hidden="true">
                <span
                  className="applicant-pie-center-val"
                  style={
                    activeItem
                      ? { fontSize: '16px', color: colors[hoveredIndex] }
                      : undefined
                  }
                >
                  {activeItem ? activeItem.statusLabel : `${audit.percentage}%`}
                </span>
                <span className="applicant-pie-center-lbl">{centreLabel}</span>
              </div>
            </StatusRing>
          </div>
        </div>

        <div className="applicant-pie-legend">
          {audit.items.map((item, index) => (
            <div
              key={item.key}
              className={`applicant-pie-legend-row ${hoveredIndex === index ? 'is-active' : ''}`.trim()}
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              <div className="applicant-pie-legend-left">
                <span
                  className="applicant-pie-dot"
                  style={{ backgroundColor: colors[index] }}
                />
                <span className="applicant-pie-label">{item.label}</span>
              </div>
              <div className="applicant-pie-legend-right">
                <span
                  className={`verif-chip ${
                    item.needsAction
                      ? 'is-bad'
                      : item.verified
                        ? 'is-verified'
                        : audit.inReview
                          ? 'is-in-review'
                          : 'is-pending'
                  }`}
                >
                  {/* A drawn icon rather than a tick character: the chip has to
                      read the same on every platform's font. */}
                  <Icon
                    name={item.needsAction ? 'alert' : item.verified ? 'check' : 'clock'}
                    size={12}
                    strokeWidth={2.6}
                  />
                  {item.statusLabel}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="applicant-pie-action">
        <Link
          to={hasApplication ? '/portal/details' : '/portal/courses'}
          className="g-btn g-btn-primary g-btn-sm applicant-pie-cta"
        >
          {!hasApplication ? 'Start an application' : audit.isFullyVerified ? 'View verified details' : 'Review your details'}
          <Icon name="arrowRight" size={15} strokeWidth={2.2} />
        </Link>
      </div>
    </div>
  );
}
