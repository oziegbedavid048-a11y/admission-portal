import { useState } from 'react';
import Icon from '../../lib/icons';
import { formatLongDate } from '../../lib/format';
import { useApplication } from './ApplicationContext';
import { applications } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';

export default function LettersPanel() {
  const { application, setApplication } = useApplication();
  const [transferring, setTransferring] = useState(false);
  const toast = useToast();

  const letters = application?.letters || [];
  const isTransferred = Boolean(application?.transferred_to_visa_support);
  const institutionName = application?.institution?.name || 'Institution of Higher Education';
  const destinationCountry = application?.destination_country || '';
  const programName = application?.programs?.[0]?.name || 'Admitted Programme';

  const handleTransfer = async () => {
    if (isTransferred) return;
    setTransferring(true);
    try {
      const { data } = await applications.transferToVisaSupport(application.reference);
      if (setApplication) {
        setApplication(data);
      }
      toast.success('Your file and letter have been transferred to the Visa Support Assistant desk.');
    } catch {
      toast.error('Could not complete transfer to Visa Support. Please try again.');
    } finally {
      setTransferring(false);
    }
  };

  return (
    <div className="portal-stack letter-panel-container">
      {/* Sleek, minimal header bar without verbose paragraphs */}
      <div className="letter-header-row">
        <div>
          <h2 className="letter-page-title">Letters</h2>
          <p className="letter-page-subtitle">Official letters & university correspondence</p>
        </div>
        {isTransferred && (
          <div className="visa-support-header-badge" title="Active in Visa Support Queue">
            <Icon name="checkCircle" size={15} />
            <span>Visa Support Active</span>
          </div>
        )}
      </div>

      {letters.length === 0 ? (
        <section className="card letter-empty-card">
          <div className="letter-empty-icon" aria-hidden="true">
            <Icon name="document" size={26} />
          </div>
          <h3 className="letter-empty-title">No letters issued yet</h3>
          <p className="letter-empty-sub">
            Your official admission or offer letter will appear here once issued by the admissions desk.
          </p>
        </section>
      ) : (
        <div className="letter-cards-list">
          {letters.map((letter) => (
            <section className="card letter-modern-card" key={letter.id}>
              {/* Miniature Letter Document Preview */}
              <div className="letter-preview-wrapper">
                <div className="letter-mini-sheet" aria-label={`Preview of ${letter.title}`}>
                  <div className="mini-sheet-letterhead">
                    <div className="mini-sheet-crest">
                      <Icon name="cap" size={14} />
                    </div>
                    <div className="mini-sheet-inst-info">
                      <span className="mini-sheet-inst-name">{institutionName}</span>
                      {destinationCountry && (
                        <span className="mini-sheet-inst-country">{destinationCountry}</span>
                      )}
                    </div>
                  </div>

                  <div className="mini-sheet-divider" />

                  <div className="mini-sheet-body">
                    <span className="mini-sheet-doc-badge">OFFICIAL LETTER</span>
                    <h4 className="mini-sheet-doc-title">{letter.title}</h4>

                    <div className="mini-sheet-rows">
                      <div className="mini-sheet-row">
                        <span className="mini-row-lbl">Candidate:</span>
                        <span className="mini-row-val">{application?.full_name || 'Applicant'}</span>
                      </div>
                      <div className="mini-sheet-row">
                        <span className="mini-row-lbl">Programme:</span>
                        <span className="mini-row-val">{programName}</span>
                      </div>
                      <div className="mini-sheet-row">
                        <span className="mini-row-lbl">Issued:</span>
                        <span className="mini-row-val">{formatLongDate(letter.issued_at)}</span>
                      </div>
                      <div className="mini-sheet-row">
                        <span className="mini-row-lbl">Reference:</span>
                        <span className="mini-row-val">{application?.reference}</span>
                      </div>
                    </div>

                    {letter.note && (
                      <div className="mini-sheet-note">
                        &ldquo;{letter.note.length > 70 ? letter.note.slice(0, 70) + '...' : letter.note}&rdquo;
                      </div>
                    )}
                  </div>

                  <div className="mini-sheet-seal">
                    <div className="mini-seal-badge">
                      <Icon name="badgeCheck" size={13} />
                      <span>OFFICIAL VERIFICATION</span>
                    </div>
                  </div>
                </div>
                <span className="letter-preview-caption">Document Preview</span>
              </div>

              {/* Letter Information & Actions */}
              <div className="letter-info-column">
                <div className="letter-info-header">
                  <span className="letter-kind-pill">{letter.kind_display || 'Official Document'}</span>
                  <h3 className="letter-display-title">{letter.title}</h3>
                  <p className="letter-date-meta">Issued on {formatLongDate(letter.issued_at)}</p>
                </div>

                {letter.note ? (
                  <p className="letter-description-text">{letter.note}</p>
                ) : null}

                <div className="letter-action-row">
                  {/* Download Button */}
                  <a
                    className="g-btn g-btn-primary letter-action-btn"
                    href={letter.file}
                    target="_blank"
                    rel="noopener noreferrer"
                    download
                  >
                    <Icon name="download" size={16} strokeWidth={2} />
                    <span>Download Letter</span>
                  </a>

                  {/* Celebrate Button */}
                  <button
                    type="button"
                    className="g-btn g-btn-plain letter-action-btn"
                    onClick={() =>
                      window.dispatchEvent(
                        new CustomEvent('gabstep:celebrate-letter', { detail: letter })
                      )
                    }
                    title="View admission celebration"
                  >
                    <Icon name="mail" size={15} />
                    <span>Celebrate</span>
                  </button>

                  {/* Transfer to Visa Support Assistant Button */}
                  {isTransferred ? (
                    <div className="visa-transferred-status-pill">
                      <Icon name="checkCircle" size={15} />
                      <span>Transferred to Visa Support Assistant</span>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="g-btn g-btn-secondary letter-action-btn letter-transfer-btn"
                      onClick={handleTransfer}
                      disabled={transferring}
                    >
                      <Icon name="plane" size={16} />
                      <span>{transferring ? 'Transferring...' : 'Transfer to Visa Support Assistant'}</span>
                    </button>
                  )}
                </div>

                {isTransferred && (
                  <p className="visa-transferred-note">
                    Your student details and attached letter have been transferred to the Visa Support Assistant desk.
                  </p>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
