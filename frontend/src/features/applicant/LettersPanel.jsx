import { useState } from 'react';
import Modal from '../../components/ui/Modal';
import PdfViewer from '../../components/ui/PdfViewer';
import Icon from '../../lib/icons';
import { downloadUrl, formatLongDate, resolveMediaUrl } from '../../lib/format';
import { useApplication } from './ApplicationContext';

export default function LettersPanel() {
  const { application } = useApplication();
  const [viewing, setViewing] = useState(null);

  const letters = application?.letters || [];
  const institutionName = application?.institution?.name || 'Institution of Higher Education';
  const destinationCountry = application?.destination_country || '';
  const programName = application?.programs?.[0]?.name || 'Admitted Programme';

  return (
    <div className="portal-stack letters-clean-container">

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
        <div className="letters-clean-list">
          {letters.map((letter) => {
            const fileUrl = resolveMediaUrl(letter.file);
            const isPdf =
              fileUrl?.toLowerCase().includes('.pdf') ||
              (letter.title && letter.title.toLowerCase().endsWith('.pdf'));
            const isImg =
              !isPdf &&
              fileUrl &&
              /\.(jpe?g|png|webp|gif|svg)(\?.*)?$/i.test(fileUrl);

            return (
              <section className="card letter-preview-card" key={letter.id}>
                {/* ── Top / Half Preview of the Letter ── */}
                <div className="letter-half-preview-box">
                  {isImg ? (
                    <img
                      src={fileUrl}
                      alt={letter.title}
                      className="letter-half-img"
                    />
                  ) : isPdf ? (
                    <div className="letter-half-pdf">
                      <PdfViewer url={fileUrl} title={letter.title} />
                    </div>
                  ) : (
                    <div className="letter-stationery-preview">
                      <div className="stationery-head">
                        <span className="stationery-inst">{institutionName}</span>
                        {destinationCountry && (
                          <span className="stationery-country">{destinationCountry}</span>
                        )}
                      </div>
                      <div className="stationery-rule" />
                      <div className="stationery-body">
                        <span className="stationery-badge">OFFICIAL ADMISSION LETTER</span>
                        <h4 className="stationery-title">{letter.title}</h4>
                        <div className="stationery-row">
                          <span className="stationery-lbl">Applicant:</span>
                          <span className="stationery-val">{application?.full_name || 'Applicant'}</span>
                        </div>
                        <div className="stationery-row">
                          <span className="stationery-lbl">Programme:</span>
                          <span className="stationery-val">{programName}</span>
                        </div>
                        <div className="stationery-row">
                          <span className="stationery-lbl">Reference:</span>
                          <span className="stationery-val">{application?.reference}</span>
                        </div>
                      </div>
                    </div>
                  )}
                  {/* Subtle fade overlay indicating half-preview */}
                  <div className="letter-half-fade" aria-hidden="true" />
                </div>

                {/* ── Letter Details & Download Button ── */}
                <div className="letter-bottom-actions">
                  <div className="letter-meta-info">
                    <h3 className="letter-title-text">{letter.title}</h3>
                    <p className="letter-date-text">Issued on {formatLongDate(letter.issued_at)}</p>
                  </div>

                  {fileUrl ? (
                    <div className="letter-actions-row">
                    <button
                      type="button"
                      className="g-btn g-btn-quiet"
                      onClick={() => setViewing({ ...letter, fileUrl, isPdf, isImg })}
                    >
                      <Icon name="document" size={16} strokeWidth={2.2} />
                      <span>View</span>
                    </button>
                    <a
                      className="g-btn g-btn-primary letter-main-download-btn"
                      href={downloadUrl(letter.file)}
                      download={letter.title || 'Official_Letter'}
                    >
                      <Icon name="download" size={16} strokeWidth={2.2} />
                      <span>Download</span>
                    </a>
                    </div>
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>
      )}

      <Modal
        open={Boolean(viewing)}
        onClose={() => setViewing(null)}
        title={viewing?.title || 'Letter'}
        labelledBy="letter-view-title"
        size={760}
      >
        {viewing ? (
          viewing.isImg ? (
            <img src={viewing.fileUrl} alt={viewing.title} className="doc-inapp-preview-img" />
          ) : (
            <PdfViewer url={viewing.fileUrl} title={viewing.title} />
          )
        ) : null}
      </Modal>
    </div>
  );
}
