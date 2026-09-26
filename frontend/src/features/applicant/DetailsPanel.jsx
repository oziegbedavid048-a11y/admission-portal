import { useState } from 'react';
import Icon from '../../lib/icons';
import { formatLongDate } from '../../lib/format';
import Modal from '../../components/ui/Modal';
import { useApplication } from './ApplicationContext';
import CorrectionBottomSheetModal from './CorrectionBottomSheetModal';

export default function DetailsPanel() {
  const { application, reload } = useApplication();
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState(null);

  const programs = application.programs || [];
  const documents = application.documents || [];
  const corrections = application.corrections || [];

  return (
    <div className="portal-stack applicant-details-container">
      {/* ── Page Banner ── */}
      <section className="app-banner">
        <span className="app-greet-icon" aria-hidden="true">
          <Icon name="fileText" size={22} />
        </span>
        <div className="app-banner-text">
          <h2>Applicant Details</h2>
          <p>Your official application dossier, academic background, and institution selections.</p>
        </div>
        <div className="app-banner-actions">
          <button
            type="button"
            className="g-btn g-btn-primary"
            onClick={() => setCorrectionOpen(true)}
          >
            <Icon name="pencil" size={16} />
            <span>Request a Correction</span>
          </button>
        </div>
      </section>

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

      {/* ── Card 1: Personal Information ── */}
      <section className="card">
        <div className="card-head">
          <h2>Personal Information</h2>
          <span className="card-note">Verified applicant identity</span>
        </div>

        <div className="facts-grid">
          <div className="fact-item">
            <span className="fact-item-label">Full Legal Name</span>
            <span className="fact-item-value">{application.full_name || 'Not provided'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Email Address</span>
            <span className="fact-item-value">{application.email || 'Not provided'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Phone Number</span>
            <span className="fact-item-value">{application.phone || 'Not provided'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Residential Address</span>
            <span className="fact-item-value">{application.address || 'Not provided'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Country of Origin</span>
            <span className="fact-item-value">{application.origin_country || 'Not set'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Destination Country</span>
            <span className="fact-item-value">{application.destination_country || 'Not set'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Application Reference</span>
            <span className="fact-item-value fact-mono">{application.reference}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Submission Date</span>
            <span className="fact-item-value">
              {formatLongDate(application.submitted_at || new Date().toISOString())}
            </span>
          </div>
        </div>
      </section>

      {/* ── Card 2: Academic Record ── */}
      <section className="card">
        <div className="card-head">
          <h2>Academic Record</h2>
          <span className="card-note">Prior qualification history</span>
        </div>

        <div className="facts-grid">
          <div className="fact-item">
            <span className="fact-item-label">Highest Qualification</span>
            <span className="fact-item-value">{application.qualification || 'Not provided'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Previous School / Institution</span>
            <span className="fact-item-value">{application.previous_schools || 'Not provided'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Year Graduated</span>
            <span className="fact-item-value">{application.year_graduated || 'Not provided'}</span>
          </div>

          <div className="fact-item">
            <span className="fact-item-label">Grade / GPA</span>
            <span className="fact-item-value">{application.grade_gpa || 'Not provided'}</span>
          </div>
        </div>
      </section>

      {/* ── Card 3: Selected University & Programme ── */}
      <section className="card">
        <div className="card-head">
          <h2>Selected University & Programme</h2>
          <span className="card-note">Choice of institution</span>
        </div>

        <div className="facts-grid">
          <div className="fact-item fact-item-full">
            <span className="fact-item-label">Target Institution</span>
            <span className="fact-item-value fact-highlight">
              {application.institution?.name || 'Selected University'}
            </span>
          </div>

          {application.institution?.city ? (
            <div className="fact-item">
              <span className="fact-item-label">Campus Location</span>
              <span className="fact-item-value">
                {application.institution.city}, {application.destination_country}
              </span>
            </div>
          ) : null}

          <div className="fact-item">
            <span className="fact-item-label">Destination Country</span>
            <span className="fact-item-value">{application.destination_country}</span>
          </div>

          <div className="fact-item fact-item-full">
            <span className="fact-item-label">Selected Courses / Programmes</span>
            <div className="details-course-chips">
              {programs.length === 0 ? (
                <span className="empty-text">No courses on record.</span>
              ) : (
                programs.map((prog) => (
                  <div className="details-course-chip" key={prog.id}>
                    <div className="details-course-chip-title">{prog.name}</div>
                    {prog.level && (
                      <span className="details-course-chip-level">{prog.level}</span>
                    )}
                    {prog.duration && (
                      <span className="details-course-chip-duration">{prog.duration}</span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {application.institution?.tuition_summary ? (
            <div className="fact-item fact-item-full">
              <span className="fact-item-label">Tuition Summary</span>
              <span className="fact-item-value">
                {application.institution.tuition_summary}
              </span>
            </div>
          ) : null}
        </div>
      </section>

      {/* ── Card 4: Uploaded Credentials & Documents ── */}
      <section className="card">
        <div className="card-head">
          <h2>Uploaded Supporting Documents</h2>
          <span className="card-note">{documents.length} document(s) on file</span>
        </div>

        <div className="details-docs-list">
          {documents.length === 0 ? (
            <p className="empty-text empty-text-inset">
              No supporting documents uploaded yet.
            </p>
          ) : (
            documents.map((doc) => {
              const verified = doc.status === 'Verified';
              return (
                <div className="details-doc-card" key={doc.id}>
                  <div className="details-doc-main">
                    <div className="details-doc-icon">
                      <Icon name="document" size={20} />
                    </div>
                    <div>
                      <h4 className="details-doc-title">{doc.name}</h4>
                      <p className="details-doc-meta">
                        {doc.original_filename || 'Uploaded Document'} · {doc.human_size || 'PDF'}
                      </p>
                    </div>
                  </div>

                  <div className="details-doc-actions">
                    <span className={`pill ${verified ? 'pill-ok' : 'pill-wait'}`}>
                      <Icon name={verified ? 'check' : 'clock'} size={12} strokeWidth={2.6} />
                      {verified ? 'Verified' : 'In review'}
                    </span>
                    <button
                      type="button"
                      className="g-btn g-btn-quiet g-btn-sm"
                      onClick={() => setPreviewDoc(doc)}
                    >
                      Open Document
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* ── Card 5: Correction Requests History (Only when submitted) ── */}
      {corrections.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2>Correction Requests Log</h2>
            <span className="card-note">{corrections.length} request(s) recorded</span>
          </div>

          <div className="details-corrections-list">
            {corrections.map((corr) => {
              const isOpen = corr.status === 'open';
              const isVerified = corr.status === 'verified';

              return (
                <div className="details-corr-row" key={corr.id || corr.ticket}>
                  <div className="details-corr-info">
                    <div className="details-corr-header">
                      <span className="details-corr-ticket">{corr.ticket}</span>
                      <span className="details-corr-field">{corr.field}</span>
                    </div>
                    <div className="details-corr-values">
                      <span className="details-corr-lbl">Requested change:</span>{' '}
                      <strong>{corr.corrected_value}</strong>
                    </div>
                    {corr.reason ? (
                      <p className="details-corr-reason">Note: {corr.reason}</p>
                    ) : null}
                  </div>

                  <div className="details-corr-side">
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

      {/* ── Bottom Call To Action ── */}
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
            <span>Request a Correction</span>
          </button>
        </div>
      </section>

      {/* ── Correction Bottom Sheet Modal (Slides from under) ── */}
      <CorrectionBottomSheetModal
        open={correctionOpen}
        onClose={() => setCorrectionOpen(false)}
        application={application}
        onSuccess={reload}
      />

      {/* ── Document Preview Modal ── */}
      <Modal
        open={Boolean(previewDoc)}
        onClose={() => setPreviewDoc(null)}
        title={previewDoc?.name || 'Document Preview'}
        labelledBy="doc-preview-modal-title"
        size={600}
        footer={
          previewDoc?.file ? (
            <a
              className="g-btn g-btn-primary"
              href={previewDoc.file}
              target="_blank"
              rel="noopener noreferrer"
              download
            >
              <Icon name="download" size={16} />
              <span>Download File</span>
            </a>
          ) : null
        }
      >
        <div className="doc-preview-modal-content">
          <div className="doc-preview-info-bar">
            <div>
              <strong>{previewDoc?.original_filename || 'File'}</strong>
              <div className="doc-preview-size">
                {previewDoc?.human_size}
              </div>
            </div>
            <span
              className={`pill ${
                previewDoc?.status === 'Verified' ? 'pill-ok' : 'pill-wait'
              }`}
            >
              <Icon
                name={previewDoc?.status === 'Verified' ? 'check' : 'clock'}
                size={12}
                strokeWidth={2.6}
              />
              {previewDoc?.status === 'Verified' ? 'Verified' : 'In review'}
            </span>
          </div>

          <div className="doc-preview-placeholder">
            <Icon name="document" size={48} />
            <p>Stored securely on Gabstep Admissions servers.</p>
          </div>
        </div>
      </Modal>
    </div>
  );
}
