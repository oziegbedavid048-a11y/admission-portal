import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Loading from '../../../components/ui/Loading';
import PdfViewer from '../../../components/ui/PdfViewer';
import { errorMessage } from '../../../api/client';
import { partners } from '../../../api/endpoints';
import { useToast } from '../../../context/ToastContext';
import Icon from '../../../lib/icons';
import { formatLongDate } from '../../../lib/format';
import { useAgent } from '../AgentContext';
import SignaturePad from './SignaturePad';
import TypedSignature, { STYLES, renderTypedSignature } from './TypedSignature';

/**
 * The Sales Partnership Contract.
 *
 * A new agent lands here and cannot use the rest of the portal until it is
 * signed. The contract is the company's own document with the agent's name,
 * email, phone and address already filled in from sign-up; they read it, sign
 * (drawn, or their name in a handwriting style), tick that they agree and
 * press Sign. The date is the day they sign.
 *
 * Once signed, this page shows the signed contract with Download underneath,
 * and a copy is emailed to them. An agent whose paper contract staff uploaded
 * sees that copy here instead.
 */
export default function AgentContract() {
  const { profile, reload } = useAgent();
  const [info, setInfo] = useState(null);
  const [documentUrl, setDocumentUrl] = useState('');
  const [failed, setFailed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  // Survives the portal opening up around this page once the contract is signed.
  const justSigned = Boolean(location.state?.justSigned);
  const toast = useToast();

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const { data } = await partners.contract();
      setInfo(data);
      if (data.status === 'pending' || data.status === 'signed') {
        const response = data.status === 'signed' ? await partners.contractFile() : await partners.contractPreview();
        const type = data.status === 'signed' ? data.content_type || 'application/pdf' : 'application/pdf';
        // The previous address is released by the effect below.
        setDocumentUrl(URL.createObjectURL(new Blob([response.data], { type })));
      }
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => () => documentUrl && URL.revokeObjectURL(documentUrl), [documentUrl]);

  const onSigned = async () => {
    toast.success('Contract signed. A copy is on its way to your email.');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    navigate('/agent/contract', { replace: true, state: { justSigned: true } });
    await Promise.all([load(), reload().catch(() => null)]);
  };

  if (failed) {
    return (
      <div className="agent-stack">
        <section className="agent-card">
          <div className="ag-empty">
            <p>Your contract could not be loaded.</p>
            <span>Check your connection and try again.</span>
            <button type="button" className="agent-btn agent-btn-secondary contract-retry" onClick={load}>
              Try again
            </button>
          </div>
        </section>
      </div>
    );
  }
  if (!info || (info.status !== 'none' && !documentUrl)) return <Loading label="Opening your contract" />;

  if (info.status === 'signed') {
    return (
      <SignedContract
        info={info}
        url={documentUrl}
        email={profile?.email}
        justSigned={justSigned}
      />
    );
  }

  return (
    <div className="agent-stack">
      <div className="ag-page-head">
        <div>
          <h1 className="ag-page-title">Partnership contract</h1>
          <p className="ag-page-sub">
            Read your Apply Gabstep Sales Partnership Contract, then sign it below to open your partner portal.
          </p>
        </div>
      </div>

      <section className="agent-card contract-doc-card" aria-label="Your contract">
        <div className="contract-doc" tabIndex={0} aria-label="Contract document. Scroll to read every page.">
          <PdfViewer url={documentUrl} title="Sales Partnership Contract" />
        </div>
      </section>

      <SignPanel info={info} onSigned={onSigned} />
    </div>
  );
}

function SignedContract({ info, url, email, justSigned }) {
  const navigate = useNavigate();
  const isPdf = (info.content_type || 'application/pdf') === 'application/pdf';

  const download = () => {
    const link = document.createElement('a');
    link.href = url;
    link.download = info.filename || 'Apply-Gabstep-Sales-Partnership-Contract.pdf';
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="agent-stack">
      <div className="ag-page-head">
        <div>
          <h1 className="ag-page-title">Partnership contract</h1>
          <p className="ag-page-sub">
            {info.signed_on ? `Signed on ${formatLongDate(info.signed_on)}` : 'Signed'}
            {justSigned && email ? ` · A copy is on its way to ${email}` : ''}
          </p>
        </div>
      </div>

      <section className="agent-card contract-doc-card" aria-label="Your signed contract">
        <div className="contract-doc" tabIndex={0} aria-label="Signed contract. Scroll to read every page.">
          {isPdf ? (
            <PdfViewer url={url} title="Signed Sales Partnership Contract" />
          ) : (
            <img className="contract-doc-img" src={url} alt="Your signed partnership contract" />
          )}
        </div>
        <div className="contract-actions">
          <button type="button" className="agent-btn agent-btn-primary" onClick={download}>
            <Icon name="download" size={17} />
            Download
          </button>
          {justSigned ? (
            <button type="button" className="agent-btn agent-btn-secondary" onClick={() => navigate('/agent')}>
              Continue to your dashboard
            </button>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function SignPanel({ info, onSigned }) {
  const { details } = info;
  const pad = useRef(null);
  const [mode, setMode] = useState('drawn');
  const [hasDrawing, setHasDrawing] = useState(false);
  const [typedName, setTypedName] = useState(details.name || '');
  const [styleId, setStyleId] = useState(STYLES[0].id);
  const [address, setAddress] = useState(details.address || '');
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const toast = useToast();

  const needsAddress = !details.address;
  const signatureReady = mode === 'drawn' ? hasDrawing : typedName.trim().length >= 2;
  const ready = signatureReady && agreed && (!needsAddress || address.trim().length >= 5);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (!signatureReady) {
      setError(mode === 'drawn' ? 'Draw your signature in the box.' : 'Type the name you want to sign with.');
      return;
    }
    if (needsAddress && address.trim().length < 5) {
      setError('Enter your full address. It is printed on the contract.');
      return;
    }
    if (!agreed) {
      setError('Tick the box to confirm you have read and agree to the contract.');
      return;
    }
    setBusy(true);
    try {
      const signature =
        mode === 'drawn' ? pad.current.toDataURL() : await renderTypedSignature(typedName.trim(), styleId);
      await partners.signContract({
        signature,
        method: mode,
        agree: true,
        ...(needsAddress ? { address: address.trim() } : {}),
      });
      await onSigned();
    } catch (err) {
      const message = errorMessage(err, 'Your contract could not be signed. Please try again.');
      setError(message);
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="agent-card contract-sign" aria-labelledby="contract-sign-title">
      <div className="agent-card-header">
        <h2 className="agent-card-title" id="contract-sign-title">
          Sign the contract
        </h2>
      </div>

      <dl className="contract-details">
        <div>
          <dt>Name</dt>
          <dd>{details.name}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{details.email}</dd>
        </div>
        <div>
          <dt>Phone</dt>
          <dd>{details.phone || '—'}</dd>
        </div>
        {needsAddress ? null : (
          <div>
            <dt>Address</dt>
            <dd>{details.address}</dd>
          </div>
        )}
      </dl>

      <form onSubmit={submit} noValidate>
        {needsAddress ? (
          <div className="agent-form-group">
            <label className="agent-form-label" htmlFor="contract-address">
              Address
            </label>
            <input
              id="contract-address"
              className="agent-form-control"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              autoComplete="street-address"
              maxLength={255}
            />
            <span className="agent-form-hint">Your home or office address. It is printed on the contract.</span>
          </div>
        ) : null}

        <span className="agent-form-label" id="contract-signature-label">
          Signature
        </span>
        <div className="ag-tabs contract-tabs" role="tablist" aria-labelledby="contract-signature-label">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'drawn'}
            className={`ag-tab ${mode === 'drawn' ? 'is-active' : ''}`.trim()}
            onClick={() => setMode('drawn')}
          >
            Draw signature
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'typed'}
            className={`ag-tab ${mode === 'typed' ? 'is-active' : ''}`.trim()}
            onClick={() => setMode('typed')}
          >
            Use my name
          </button>
        </div>

        {/* Both stay mounted, so a drawn signature survives a look at the other tab. */}
        <div className="contract-draw" hidden={mode !== 'drawn'}>
          <SignaturePad ref={pad} onChange={setHasDrawing} />
          <div className="contract-draw-foot">
            <span className="agent-form-hint">Use your finger, a stylus or your mouse.</span>
            <button
              type="button"
              className="ag-text-btn"
              onClick={() => pad.current?.clear()}
              disabled={!hasDrawing}
            >
              Clear
            </button>
          </div>
        </div>
        {mode === 'typed' ? (
          <TypedSignature
            name={typedName}
            onNameChange={setTypedName}
            styleId={styleId}
            onStyleChange={setStyleId}
          />
        ) : null}

        <div className="contract-date">
          <span className="agent-form-label">Date</span>
          <span className="contract-date-value">{formatLongDate(info.today)}</span>
        </div>

        <label className="contract-agree">
          <input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
          <span>I have read the Apply Gabstep Sales Partnership Contract and I agree to its terms.</span>
        </label>

        {error ? (
          <p className="contract-error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="contract-actions">
          <button type="submit" className="agent-btn agent-btn-primary" disabled={busy || !ready}>
            {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
            {busy ? 'Signing' : 'Sign contract'}
          </button>
        </div>
      </form>
    </section>
  );
}
