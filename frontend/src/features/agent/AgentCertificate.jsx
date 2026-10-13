import { useEffect, useState } from 'react';
import Modal from '../../components/ui/Modal';
import PdfViewer from '../../components/ui/PdfViewer';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import Icon from '../../lib/icons';
import { useAgent } from './AgentContext';

/**
 * The agent's partnership certificate.
 *
 * The page exists only once the certificate is ready (six hours after sign-up);
 * before that the portal has no link to it and says nothing about it. The PDF
 * is fetched once, so View and Download are instant. The card shows the top
 * half of the certificate as a clean preview; View opens the whole thing.
 */
export default function AgentCertificate() {
  const { profile } = useAgent();
  const [url, setUrl] = useState('');
  const [failed, setFailed] = useState(false);
  const [viewing, setViewing] = useState(false);
  const toast = useToast();

  const filename = `Apply-Gabstep-Partner-Certificate-${profile?.partner_code || 'agent'}.pdf`;

  useEffect(() => {
    let objectUrl = '';
    let cancelled = false;
    partners
      .certificate()
      .then(({ data }) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(new Blob([data], { type: 'application/pdf' }));
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, []);

  const download = () => {
    if (!url) return;
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    toast.success('Certificate downloaded.');
  };

  return (
    <div className="agent-stack">
      <div className="ag-page-head">
        <div>
          <h1 className="ag-page-title">Certificate</h1>
          <p className="ag-page-sub">Official partner of Apply Gabstep · {profile?.partner_code}</p>
        </div>
      </div>

      <section className="agent-card ag-cert-card">
        {failed ? (
          <div className="ag-empty">
            <p>The certificate could not be loaded.</p>
            <span>Refresh the page to try again.</span>
          </div>
        ) : (
          <>
            <div className="ag-cert-preview">
              {url ? <PdfViewer url={url} title="Partnership certificate" /> : null}
              <span className="ag-cert-fade" aria-hidden="true" />
              <button
                type="button"
                className="ag-cert-hit"
                onClick={() => setViewing(true)}
                disabled={!url}
                aria-label="View the full certificate"
              />
            </div>
            <div className="ag-cert-actions">
              <button
                type="button"
                className="agent-btn agent-btn-secondary"
                onClick={() => setViewing(true)}
                disabled={!url}
              >
                View
              </button>
              <button type="button" className="agent-btn agent-btn-primary" onClick={download} disabled={!url}>
                <Icon name="download" size={17} />
                Download
              </button>
            </div>
          </>
        )}
      </section>

      <Modal
        open={viewing}
        onClose={() => setViewing(false)}
        variant="agent"
        title="Partnership certificate"
        subtitle={profile?.partner_code || ''}
        labelledBy="certificate-preview-title"
        size={980}
        footer={
          <>
            <button type="button" className="agent-btn agent-btn-secondary" onClick={download}>
              Download
            </button>
            <button type="button" className="agent-btn agent-btn-primary" onClick={() => setViewing(false)}>
              Close
            </button>
          </>
        }
      >
        {viewing && url ? <PdfViewer url={url} title="Partnership certificate" /> : null}
      </Modal>
    </div>
  );
}
