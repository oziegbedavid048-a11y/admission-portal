import { useState } from 'react';
import Icon from '../../lib/icons';
import PdfViewer from '../../components/ui/PdfViewer';
import { downloadUrl, formatLongDate, resolveMediaUrl } from '../../lib/format';
import Modal from '../../components/ui/Modal';
import { useApplication } from './ApplicationContext';
import ApplicationSwitcher from './ApplicationSwitcher';
import CorrectionBottomSheetModal from './CorrectionBottomSheetModal';
import DocumentReplaceButton from '../../components/ui/DocumentReplaceButton';

const DOC_STATE = {
  Verified: { pill: 'pill-ok', icon: 'check', label: 'Verified' },
  Rejected: { pill: 'pill-bad', icon: 'alert', label: 'Needs replacing' },
};
const docState = (status) => DOC_STATE[status] || { pill: 'pill-wait', icon: 'clock', label: 'In review' };

export default function DetailsPanel() {
  const { application, reload } = useApplication();
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState(null);

  const programs = application?.programs || [];
  const documents = application?.documents || [];
  const corrections = application?.corrections || [];

  return (
    <div className="portal-stack applicant-details-container">
      <ApplicationSwitcher />

      {/* ── Active Correction Notice (If open requests exist) ── */}
      {corrections.some((c) => c.status === 'open') && (
        <div className="correction-status-banner">
          <div className="correction-status-banner-content">
            <span className="correction-status-indicator" />
            <div>
              <strong>Pending Correction Request in Review</strong>
              <p>
                You have active correction requests currently undergoing admissions desk review.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Section 1: Personal Information ── */}
      <section className="card details-clean-card">
        <div className="card-head">
          <h2>Personal details</h2>
        </div>

        <div className="facts-clean-grid">
          <div className="fact-clean-item">
            <span className="fact-clean-label">Full legal name</span>
            <span className="fact-clean-value">{application?.full_name || 'Not provided'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Email address</span>
            <span className="fact-clean-value">{application?.email || 'Not provided'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Phone number</span>
            <span className="fact-clean-value">{application?.phone || 'Not provided'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Residential address</span>
            <span className="fact-clean-value">{application?.address || 'Not provided'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Country of Origin</span>
            <span className="fact-clean-value">{application?.origin_country || 'Not set'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Destination country</span>
            <span className="fact-clean-value">{application?.destination_country || 'Not set'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Application reference</span>
            <span className="fact-clean-value fact-mono">{application?.reference}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Submission date</span>
            <span className="fact-clean-value">
              {formatLongDate(application?.submitted_at || new Date().toISOString())}
            </span>
          </div>
        </div>
      </section>

      {/* ── Section 2: Academic Record ── */}
      <section className="card details-clean-card">
        <div className="card-head">
          <h2>Academic record</h2>
        </div>

        <div className="facts-clean-grid">
          <div className="fact-clean-item">
            <span className="fact-clean-label">Highest qualification</span>
            <span className="fact-clean-value">{application?.qualification || 'Not provided'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Previous School / Institution</span>
            <span className="fact-clean-value">{application?.previous_schools || 'Not provided'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Year graduated</span>
            <span className="fact-clean-value">{application?.year_graduated || 'Not provided'}</span>
          </div>

          <div className="fact-clean-item">
            <span className="fact-clean-label">Grade / GPA</span>
            <span className="fact-clean-value">{application?.grade_gpa || 'Not provided'}</span>
          </div>
        </div>
      </section>

      {/* ── Section 3: Selected University & Programme ── */}
      <section className="card details-clean-card">
        <div className="card-head">
          <h2>University and course</h2>
        </div>

        <div className="facts-clean-grid">
          <div className="fact-clean-item fact-clean-full">
            <span className="fact-clean-label">Target institution</span>
            <span className="fact-clean-value fact-highlight">
              {application?.institution?.name || 'Selected University'}
            </span>
          </div>

          {application?.institution?.city ? (
            <div className="fact-clean-item">
              <span className="fact-clean-label">Campus location</span>
              <span className="fact-clean-value">
                {application.institution.city}, {application.destination_country}
              </span>
            </div>
          ) : null}

          <div className="fact-clean-item">
            <span className="fact-clean-label">Destination country</span>
            <span className="fact-clean-value">{application?.destination_country}</span>
          </div>

          <div className="fact-clean-item fact-clean-full">
            <span className="fact-clean-label">Selected Courses / Programmes</span>
            <div className="details-course-clean-list">
              {programs.length === 0 ? (
                <span className="empty-text">No courses on record.</span>
              ) : (
                programs.map((prog) => (
                  <div className="details-course-clean-item" key={prog.id}>
                    <div className="details-course-info">
                      <strong className="details-course-name">{prog.name}</strong>
                      <div className="details-course-tags">
                        {prog.level && <span className="details-course-badge">{prog.level}</span>}
                        {prog.duration && <span className="details-course-duration">{prog.duration}</span>}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {application?.institution?.tuition_summary ? (
            <div className="fact-clean-item fact-clean-full">
              <span className="fact-clean-label">Tuition summary</span>
              <span className="fact-clean-value">
                {application.institution.tuition_summary}
              </span>
            </div>
          ) : null}
        </div>
      </section>

      {/* ── Section 4: Uploaded Credentials & Documents ── */}
      <section className="card details-clean-card">
        <div className="card-head">
          <h2>Documents</h2>
        </div>

        <div className="details-docs-clean-list">
          {documents.length === 0 ? (
            <p className="empty-text empty-text-inset">
              No supporting documents uploaded yet.
            </p>
          ) : (
            documents.map((doc) => {
              const state = docState(doc.status);
              const rejected = doc.status === 'Rejected';
              return (
                <div className={`details-doc-row${rejected ? ' is-rejected' : ''}`} key={doc.id}>
                  <div className="details-doc-left">
                    <div className="details-doc-avatar">
                      <Icon name="document" size={18} />
                    </div>
                    <div className="details-doc-text">
                      <h4 className="details-doc-title">{doc.name}</h4>
                      <span className="details-doc-sub">
                        {doc.original_filename || 'Uploaded Document'} · {doc.human_size || 'File'}
                      </span>
                    </div>
                  </div>

                  <div className="details-doc-right">
                    <span className={`pill ${state.pill}`}>
                      <Icon name={state.icon} size={12} strokeWidth={2.6} />
                      {state.label}
                    </span>
                    <button
                      type="button"
                      className="g-btn g-btn-secondary g-btn-sm"
                      onClick={() => setPreviewDoc(doc)}
                      title="View document in portal"
                    >
                      <Icon name="document" size={14} />
                      <span>Open document</span>
                    </button>
                  </div>

                  {rejected ? (
                    <div className="details-doc-review">
                      <p>
                        <strong>Why it was not accepted</strong>
                        {doc.review_note || 'Please upload a clearer, complete copy.'}
                      </p>
                      <DocumentReplaceButton
                        reference={application.reference}
                        documentId={doc.id}
                        onReplaced={reload}
                      />
                    </div>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* ── Section 5: Correction Requests History (Only when present) ── */}
      {corrections.length > 0 && (
        <section className="card details-clean-card">
          <div className="card-head">
            <h2>Correction requests</h2>
          </div>

          <div className="details-corrections-clean-list">
            {corrections.map((corr) => {
              const isOpen = corr.status === 'open';
              const isVerified = corr.status === 'verified';

              return (
                <div className="details-corr-clean-row" key={corr.id || corr.ticket}>
                  <div className="details-corr-main">
                    <div className="details-corr-heading">
                      <span className="details-corr-ticket">{corr.ticket}</span>
                      <strong className="details-corr-field">{corr.field}</strong>
                    </div>
                    <div className="details-corr-change">
                      <span className="details-corr-lbl">Requested change:</span>{' '}
                      <span className="details-corr-val">{corr.corrected_value}</span>
                    </div>
                    {corr.reason ? (
                      <p className="details-corr-reason">Note: {corr.reason}</p>
                    ) : null}
                  </div>

                  <div className="details-corr-meta">
                    <span
                      className={`pill ${
                        isVerified ? 'pill-ok' : isOpen ? 'pill-wait' : 'pill-bad'
                      }`}
                    >
                      <Icon
                        name={isVerified ? 'check' : isOpen ? 'clock' : 'closeCircle'}
                        size={12}
                        strokeWidth={2.6}
                      />
                      {isVerified ? 'Approved' : isOpen ? 'Under review' : 'Declined'}
                    </span>
                    <span className="details-corr-date">
                      {formatLongDate(corr.created_at)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Section 6: Request a correction Action Card ── */}
      <section className="card details-cta-card">
        <div className="details-cta-content">
          <div>
            <h3>Need to update any of your details?</h3>
            <p>
              You can request corrections to your name, contact information, academic background,
              or chosen university at any time.
            </p>
          </div>
          <button
            type="button"
            className="g-btn g-btn-primary"
            onClick={() => setCorrectionOpen(true)}
          >
            <Icon name="pencil" size={16} />
            <span>Request a correction</span>
          </button>
        </div>
      </section>

      {/* ── Correction Bottom Sheet Modal (Responsive) ── */}
      <CorrectionBottomSheetModal
        open={correctionOpen}
        onClose={() => setCorrectionOpen(false)}
        application={application}
        onSuccess={reload}
      />

      {/* ── In-App Document Preview Modal (No external page or new tab needed) ── */}
      <Modal
        open={Boolean(previewDoc)}
        onClose={() => setPreviewDoc(null)}
        title={previewDoc?.name || 'Document Viewer'}
        subtitle={previewDoc?.original_filename || ''}
        labelledBy="doc-preview-modal-title"
        size={760}
        footer={
          <div className="doc-modal-footer">
            <button
              type="button"
              className="g-btn g-btn-plain"
              onClick={() => setPreviewDoc(null)}
            >
              Close
            </button>
            {previewDoc?.file ? (
              <a
                className="g-btn g-btn-primary"
                href={downloadUrl(previewDoc.file)}
                download={previewDoc.original_filename || 'document'}
              >
                <Icon name="download" size={16} />
                <span>Download document</span>
              </a>
            ) : null}
          </div>
        }
      >
        {previewDoc && (
          <div className="doc-inapp-viewer">
            <div className="doc-inapp-bar">
              <div className="doc-inapp-fileinfo">
                <strong>{previewDoc.original_filename || previewDoc.name}</strong>
                {previewDoc.human_size ? (
                  <span className="doc-inapp-filesize">({previewDoc.human_size})</span>
                ) : null}
              </div>
              <span className={`pill ${docState(previewDoc.status).pill}`}>
                <Icon name={docState(previewDoc.status).icon} size={12} strokeWidth={2.6} />
                {docState(previewDoc.status).label}
              </span>
            </div>

            <div className="doc-inapp-body">
              {(() => {
                const url = resolveMediaUrl(previewDoc.file);
                if (!url) {
                  return (
                    <div className="doc-inapp-empty">
                      <Icon name="document" size={44} />
                      <p>No document file attached.</p>
                    </div>
                  );
                }

                const isPdf =
                  url.toLowerCase().includes('.pdf') ||
                  (previewDoc.original_filename &&
                    previewDoc.original_filename.toLowerCase().endsWith('.pdf'));

                const isImg =
                  !isPdf &&
                  (/\.(jpe?g|png|webp|gif|svg)(\?.*)?$/i.test(url) ||
                    (previewDoc.original_filename &&
                      /\.(jpe?g|png|webp|gif|svg)$/i.test(previewDoc.original_filename)));

                if (isImg) {
                  return (
                    <div className="doc-inapp-img-frame">
                      <img
                        src={url}
                        alt={previewDoc.name}
                        className="doc-inapp-preview-img"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none';
                          const errEl = document.getElementById('doc-preview-error');
                          if (errEl) errEl.style.display = 'flex';
                        }}
                      />
                      <div id="doc-preview-error" className="doc-inapp-empty" style={{ display: 'none' }}>
                        <Icon name="alertCircle" size={40} />
                        <p>Image preview unavailable. Use download button below.</p>
                      </div>
                    </div>
                  );
                }

                // PDFs are drawn in the page with pdf.js, so they read here on a
                // phone too instead of opening another app.
                return <PdfViewer url={url} title={previewDoc.name} />;
              })()}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
