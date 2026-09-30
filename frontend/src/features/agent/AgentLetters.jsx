import { useCallback, useEffect, useState } from 'react';
import Loading from '../../components/ui/Loading';
import Modal from '../../components/ui/Modal';
import PdfViewer from '../../components/ui/PdfViewer';
import { errorMessage } from '../../api/client';
import { applications, partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { downloadUrl, formatDate, resolveMediaUrl } from '../../lib/format';

const isPdf = (url) => /\.pdf($|\?)/i.test(url || '');

/**
 * Every letter issued to any of the agent's students.
 *
 * Preview it, download it, and send it to visa support. Sending earns nothing
 * by itself: the ₦50,000 visa commission is added when the visa desk confirms
 * the visa support is done.
 */
export default function AgentLetters() {
  const [letters, setLetters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewing, setViewing] = useState(null);
  const [sending, setSending] = useState(null);
  const toast = useToast();

  const load = useCallback(async (quiet = false) => {
    try {
      const { data } = await partners.letters();
      setLetters(data);
    } catch {
      if (!quiet) toast.error('Could not load your letters.');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  useLiveRefresh(() => load(true));

  const send = async (letter) => {
    setSending(letter.reference);
    try {
      await applications.transferToVisaSupport(letter.reference);
      setLetters((current) =>
        current.map((item) =>
          item.reference === letter.reference ? { ...item, sent_to_visa_support: true } : item,
        ),
      );
      toast.success(`${letter.student} sent to visa support.`);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not send this to visa support.'));
    } finally {
      setSending(null);
    }
  };

  if (loading) return <Loading label="Loading your letters" />;

  return (
    <div className="agent-stack">
      <div className="ag-page-head">
        <div>
          <h1 className="ag-page-title">Letters</h1>
          <p className="ag-page-sub">
            {letters.length} {letters.length === 1 ? 'letter' : 'letters'} issued to your students
          </p>
        </div>
      </div>

      <section className="agent-card">
        {letters.length === 0 ? (
          <div className="ag-empty">
            <p>No letters yet.</p>
            <span>When a university issues a letter for one of your students, it appears here and you get an email.</span>
          </div>
        ) : (
          <div className="ag-table-scroll" role="region" aria-label="Letters" tabIndex={0}>
            <table className="ag-table ag-table-letters">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Letter</th>
                  <th>University</th>
                  <th>Visa support</th>
                  <th className="ag-col-action">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {letters.map((letter) => {
                  const done = letter.visa_status === 'completed';
                  return (
                    <tr key={letter.id}>
                      <td>
                        <span className="ag-name">{letter.student}</span>
                        <span className="ag-sub">{letter.reference}</span>
                      </td>
                      <td>
                        <span className="ag-name">{letter.title}</span>
                        <span className="ag-sub">Issued {formatDate(letter.issued_at)}</span>
                      </td>
                      <td className="ag-wrap">{letter.university || '—'}</td>
                      <td>
                        {done ? (
                          <span className="tbl-badge approved">Done</span>
                        ) : letter.sent_to_visa_support ? (
                          <span className="tbl-badge pending">Sent</span>
                        ) : (
                          <span className="tbl-badge na">Not sent</span>
                        )}
                      </td>
                      <td className="ag-col-action">
                        <div className="ag-row-actions">
                          <button type="button" className="ag-text-btn" onClick={() => setViewing(letter)}>
                            Preview
                          </button>
                          <a className="ag-text-btn" href={downloadUrl(letter.url)} download>
                            Download
                          </a>
                          <button
                            type="button"
                            className="ag-open-btn ag-open-btn-primary"
                            onClick={() => send(letter)}
                            disabled={letter.sent_to_visa_support || sending === letter.reference}
                          >
                            {sending === letter.reference ? <span className="spinner-sm" aria-hidden="true" /> : null}
                            {letter.sent_to_visa_support ? 'Sent' : 'Send to visa support'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Modal
        open={Boolean(viewing)}
        onClose={() => setViewing(null)}
        variant="agent"
        title={viewing?.title || 'Letter'}
        subtitle={viewing ? `${viewing.student} · ${viewing.reference}` : ''}
        labelledBy="letter-preview-title"
        size={860}
        footer={
          viewing ? (
            <>
              <a className="agent-btn agent-btn-secondary" href={downloadUrl(viewing.url)} download>
                Download
              </a>
              <button type="button" className="agent-btn agent-btn-primary" onClick={() => setViewing(null)}>
                Close
              </button>
            </>
          ) : null
        }
      >
        {viewing ? (
          isPdf(viewing.url) ? (
            <PdfViewer url={resolveMediaUrl(viewing.url)} title={viewing.title} />
          ) : (
            <img className="letter-preview-img" src={resolveMediaUrl(viewing.url)} alt={viewing.title} />
          )
        ) : null}
      </Modal>
    </div>
  );
}
