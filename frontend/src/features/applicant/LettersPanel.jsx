import { useState } from 'react';
import { applications } from '../../api/endpoints';
import { errorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import Modal from '../../components/ui/Modal';
import PdfViewer from '../../components/ui/PdfViewer';
import Icon from '../../lib/icons';
import { downloadUrl, formatLongDate, resolveMediaUrl } from '../../lib/format';
import { useApplication } from './ApplicationContext';
import ApplicationSwitcher from './ApplicationSwitcher';

export default function LettersPanel() {
  const { application, setApplication } = useApplication();
  const toast = useToast();
  const [viewing, setViewing] = useState(null);
  const [sending, setSending] = useState(false);
  const sent = Boolean(application?.transferred_to_visa_support);

  // Hands the letter to the Visa Support desk in the admin. One press: after
  // that the button stays disabled and says it was sent.
  const sendToVisa = async () => {
    if (sent || sending || !application) return;
    setSending(true);
    try {
      const { data } = await applications.transferToVisaSupport(application.reference);
      setApplication(data);
      toast.success('Sent to our visa support desk. An advisor will contact you.');
    } catch (error) {
      toast.error(errorMessage(error, 'It could not be sent. Try again in a moment.'));
    } finally {
      setSending(false);
    }
  };

  const letters = application?.letters || [];
  const institutionName = application?.institution?.name || 'Institution of Higher Education';
  const destinationCountry = application?.destination_country || '';
  const programName = application?.programs?.[0]?.name || 'Admitted Programme';

  return (
    <div className="portal-stack letters-clean-container">
      <ApplicationSwitcher />

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
                <div
                  className="letter-half-preview-box is-clickable"
                  role="button"
                  tabIndex={0}
                  aria-label={`Open ${letter.title}`}
                  onClick={() => fileUrl && setViewing({ ...letter, fileUrl, isPdf, isImg })}
                  onKeyDown={(event) => {
                    if ((event.key === 'Enter' || event.key === ' ') && fileUrl) {
                      event.preventDefault();
                      setViewing({ ...letter, fileUrl, isPdf, isImg });
                    }
                  }}
                >
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
                    <a
                      className="g-btn g-btn-quiet letter-main-download-btn"
                      href={downloadUrl(letter.file)}
                      download={letter.title || 'Official_Letter'}
                    >
                      <Icon name="download" size={16} strokeWidth={2.2} />
                      <span>Download</span>
                    </a>
                    <button
                      type="button"
                      className="g-btn g-btn-primary"
                      onClick={sendToVisa}
                      disabled={sent || sending}
                      aria-disabled={sent || sending}
                    >
                      {sending ? (
                        <span className="spinner-sm" aria-hidden="true" />
                      ) : (
                        <Icon name={sent ? 'check' : 'send'} size={16} strokeWidth={2.2} />
                      )}
                      <span>{sent ? 'Sent to visa support' : sending ? 'Sending' : 'Send to visa support'}</span>
                    </button>
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
