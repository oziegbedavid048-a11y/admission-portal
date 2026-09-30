import { useEffect, useRef, useState } from 'react';
import { errorMessage } from '../../api/client';
import { payments } from '../../api/endpoints';
import { compressImageFile } from '../../lib/compress';
import { formatMoney, formatNaira } from '../../lib/format';

/**
 * Paying one student's application fee.
 *
 * Paystack is always offered. Company account appears only when the server
 * says this agent may transfer (agents in Nigeria); the server also refuses a
 * transfer from anyone else, so hiding it here is not the only guard.
 *
 * Paystack sends the agent to the checkout page and back to
 * /agent/payment/<reference>. A transfer asks for the bank first, shows that
 * account, then takes the receipt; the fee then waits for the desk to confirm.
 */
export default function FeePayment({ reference, rejectedNote = '', onTransferSent, onWaived }) {
  const [quote, setQuote] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [method, setMethod] = useState('paystack');
  const [bankId, setBankId] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const fileInput = useRef(null);

  useEffect(() => {
    let cancelled = false;
    payments
      .quote(reference)
      .then(({ data }) => {
        if (!cancelled) setQuote(data);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(errorMessage(err, 'Could not load the fee. Refresh to try again.'));
      });
    return () => {
      cancelled = true;
    };
  }, [reference]);

  if (loadError) return <p className="pay-error" role="alert">{loadError}</p>;
  if (!quote) {
    return (
      <div className="pay-loading">
        <span className="spinner-sm" aria-hidden="true" /> Loading the fee
      </div>
    );
  }

  // A university that charges no fee: one click records the waiver.
  if (quote.waived) {
    const confirmWaiver = async () => {
      setBusy(true);
      setError('');
      try {
        await payments.checkout(reference, 'agent');
        onWaived?.();
      } catch (err) {
        setError(errorMessage(err, 'Could not complete this. Please try again.'));
      } finally {
        setBusy(false);
      }
    };
    return (
      <div className="pay">
        <div className="pay-panel">
          <p className="pay-free">This university does not charge an application fee.</p>
          <button type="button" className="agent-btn agent-btn-primary agent-btn-block" onClick={confirmWaiver} disabled={busy}>
            {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
            {busy ? 'Completing' : 'Complete without a fee'}
          </button>
        </div>
        {error ? <p className="pay-error" role="alert">{error}</p> : null}
      </div>
    );
  }

  const accounts = quote.transfer_accounts || [];
  const canTransfer = Boolean(quote.transfer_allowed && accounts.length);
  const bank = accounts.find((account) => account.id === bankId) || null;
  const cardTotal = formatMoney(quote.total, quote.currency);
  const transferTotal = formatNaira(quote.amount_ngn);

  const payWithPaystack = async () => {
    setBusy(true);
    setError('');
    try {
      const { data } = await payments.checkout(reference, 'agent');
      if (data.already_settled) {
        window.location.assign(`/agent/payment/${reference}`);
        return;
      }
      if (!data.authorization_url) {
        setError('Paystack is not available right now. Please try again shortly.');
        setBusy(false);
        return;
      }
      window.location.assign(data.authorization_url);
    } catch (err) {
      setError(errorMessage(err, 'Could not open Paystack. Please try again.'));
      setBusy(false);
    }
  };

  const sendTransfer = async () => {
    if (!bank || !receipt) return;
    setBusy(true);
    setError('');
    try {
      const { data } = await payments.transfer(reference, { receipt, bank: bank.id });
      onTransferSent?.(data.payment);
    } catch (err) {
      setError(errorMessage(err, 'Could not send the receipt. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  const copyNumber = async () => {
    try {
      await navigator.clipboard.writeText(bank.account_number);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard can be blocked; the number is on screen to type.
    }
  };

  return (
    <div className="pay">
      {rejectedNote ? (
        <div className="pay-note pay-note-bad" role="status">
          <strong>Your last transfer was not confirmed</strong>
          <span>{rejectedNote}</span>
        </div>
      ) : null}

      {canTransfer ? (
        <fieldset className="pay-methods">
          <legend className="nf-label">Pay with</legend>
          <label className={`pay-method${method === 'paystack' ? ' is-selected' : ''}`}>
            <input
              type="radio"
              name={`pay-${reference}`}
              value="paystack"
              checked={method === 'paystack'}
              onChange={() => setMethod('paystack')}
            />
            <span className="pay-method-text">
              <strong>Paystack</strong>
              <small>Card, bank or USSD. Confirmed instantly.</small>
            </span>
          </label>
          <label className={`pay-method${method === 'transfer' ? ' is-selected' : ''}`}>
            <input
              type="radio"
              name={`pay-${reference}`}
              value="transfer"
              checked={method === 'transfer'}
              onChange={() => setMethod('transfer')}
            />
            <span className="pay-method-text">
              <strong>Company account</strong>
              <small>Bank transfer. Confirmed once we see the money.</small>
            </span>
          </label>
        </fieldset>
      ) : null}

      {method === 'paystack' || !canTransfer ? (
        <div className="pay-panel">
          <div className="pay-amount">
            <span>Amount</span>
            <strong>{cardTotal}</strong>
          </div>
          <button
            type="button"
            className="agent-btn agent-btn-primary agent-btn-block"
            onClick={payWithPaystack}
            disabled={busy}
          >
            {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
            {busy ? 'Opening Paystack' : 'Pay with Paystack'}
          </button>
        </div>
      ) : (
        <div className="pay-panel">
          <div className="nf-field">
            <label className="nf-label" htmlFor={`bank-${reference}`}>
              Bank <span className="nf-req" aria-hidden="true">*</span>
            </label>
            <select
              id={`bank-${reference}`}
              className="agent-form-select"
              value={bankId}
              onChange={(event) => setBankId(event.target.value)}
            >
              <option value="">Choose a bank</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.bank}
                </option>
              ))}
            </select>
          </div>

          {bank ? (
            <>
              <dl className="pay-account">
                <div>
                  <dt>Bank</dt>
                  <dd>{bank.bank}</dd>
                </div>
                <div>
                  <dt>Account number</dt>
                  <dd className="pay-account-number">
                    <span>{bank.account_number}</span>
                    <button type="button" className="pay-copy" onClick={copyNumber}>
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </dd>
                </div>
                <div>
                  <dt>Account name</dt>
                  <dd>{bank.beneficiary}</dd>
                </div>
                <div>
                  <dt>Amount to send</dt>
                  <dd className="pay-account-amount">{transferTotal}</dd>
                </div>
              </dl>

              <div className="nf-field">
                <span className="nf-label">
                  Transfer receipt <span className="nf-req" aria-hidden="true">*</span>
                </span>
                <input
                  ref={fileInput}
                  type="file"
                  hidden
                  accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,application/pdf,image/*"
                  onChange={async (event) => {
                    const picked = event.target.files?.[0];
                    event.target.value = '';
                    if (picked) setReceipt(await compressImageFile(picked));
                  }}
                />
                <div className="nf-file">
                  <span className={`nf-file-name${receipt ? '' : ' is-empty'}`}>
                    {receipt ? receipt.name : 'No receipt chosen'}
                  </span>
                  <button
                    type="button"
                    className="agent-btn agent-btn-secondary agent-btn-sm"
                    onClick={() => fileInput.current?.click()}
                  >
                    {receipt ? 'Change' : 'Upload receipt'}
                  </button>
                </div>
              </div>

              <button
                type="button"
                className="agent-btn agent-btn-primary agent-btn-block"
                onClick={sendTransfer}
                disabled={busy || !receipt}
              >
                {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
                {busy ? 'Sending' : 'I have sent it'}
              </button>
            </>
          ) : null}
        </div>
      )}

      {error ? <p className="pay-error" role="alert">{error}</p> : null}
    </div>
  );
}
