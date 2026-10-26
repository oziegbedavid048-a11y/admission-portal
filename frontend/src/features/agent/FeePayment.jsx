import { useEffect, useRef, useState } from 'react';
import { errorMessage } from '../../api/client';
import { payments } from '../../api/endpoints';
import { compressImageFile } from '../../lib/compress';
import { formatNaira, formatStudent } from '../../lib/format';
import PlanChooser from '../wizard/PlanChooser';

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
 *
 * "Send a payment link" is for a student who pays themselves, usually one
 * outside Nigeria: the agent copies the link or shares it on WhatsApp, the
 * student pays by card on their own phone, and the file shows as paid here
 * (with the commission credited) the moment Paystack confirms it.
 *
 * One fee covers up to three schools (the 1st choice holds it). It can be paid
 * in full or "small small": ₦100,000 now and the rest weekly. Once a deposit
 * is in, this offers the next instalment or the whole balance.
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
  const [link, setLink] = useState('');
  const [plan, setPlan] = useState('full');
  const [payWhat, setPayWhat] = useState('next');
  const [linkCopied, setLinkCopied] = useState(false);
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
  const canLink = Boolean(quote.paystack_available);
  // Pay small small: a deposit is in, the rest is owed.
  const progress = quote.plan || null;
  const instalments = (quote.instalments || []).map((row) => Number(row.amount_ngn));
  const nextAmount = progress?.next ? Number(progress.next.amount_ngn) : 0;
  const balance = progress ? Number(progress.balance_ngn) : Number(quote.amount_ngn);
  const offerNext = Boolean(progress) && nextAmount > 0 && nextAmount < balance;
  // What this payment is for, in Naira, and what the server is told.
  const dueNow = progress
    ? (payWhat === 'next' && offerNext ? nextAmount : balance)
    : plan === 'instalments' && instalments.length > 1
      ? instalments[0]
      : Number(quote.amount_ngn);
  const payOptions = progress ? { pay: payWhat === 'next' && offerNext ? 'next' : 'balance' } : { plan };
  const bank = accounts.find((account) => account.id === bankId) || null;
  // The application fee in the university's own currency. Paystack's checkout
  // shows the Naira charge, so it is not converted here.
  // Fee amounts in the student's own country's currency, and only that.
  const money = (ngn) => formatStudent(ngn, quote.student_currency);
  const applicationFee = money(quote.amount_ngn);
  // A transfer is sent in Naira: the fee at today's rate, rounded up to ₦100.
  const transferTotal = formatNaira(
    progress || plan === 'instalments' ? Math.ceil(dueNow / 100) * 100 : (quote.transfer_amount_ngn ?? quote.amount_ngn),
  );

  const payWithPaystack = async () => {
    setBusy(true);
    setError('');
    try {
      const { data } = await payments.checkout(reference, 'agent', payOptions);
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
      const { data } = await payments.transfer(reference, { receipt, bank: bank.id, ...payOptions });
      onTransferSent?.(data.payment);
    } catch (err) {
      setError(errorMessage(err, 'Could not send the receipt. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  const makeLink = async () => {
    setBusy(true);
    setError('');
    try {
      const { data } = await payments.createLink(reference);
      setLink(data.url);
    } catch (err) {
      setError(errorMessage(err, 'Could not create the payment link. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setLinkCopied(true);
      window.setTimeout(() => setLinkCopied(false), 1600);
    } catch {
      // Clipboard can be blocked; the link is on screen to select.
    }
  };

  const whatsappHref = link
    ? `https://wa.me/?text=${encodeURIComponent(
        // The page shows the amount in the student's own currency, so the
        // message leaves it out rather than quote it in another one.
        `Please pay your Gabstep application fee here: ${link}`,
      )}`
    : '';

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

      {progress ? (
        <div className="pay-progress">
          <div className="pay-amount">
            <span>Paid so far</span>
            <strong>
              {money(progress.paid_ngn)} of {money(progress.total_ngn)}
            </strong>
          </div>
          {offerNext ? (
            <fieldset className="pay-methods">
              <legend className="nf-label">Pay now</legend>
              <label className={`pay-method${payWhat === 'next' ? ' is-selected' : ''}`}>
                <input type="radio" name={`what-${reference}`} checked={payWhat === 'next'} onChange={() => setPayWhat('next')} />
                <span className="pay-method-text">
                  <strong>Next payment: {money(nextAmount)}</strong>
                  <small>
                    {progress.next?.due_on
                      ? `Due ${new Date(progress.next.due_on).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}.`
                      : 'Due a week after the deposit.'}
                  </small>
                </span>
              </label>
              <label className={`pay-method${payWhat === 'balance' ? ' is-selected' : ''}`}>
                <input type="radio" name={`what-${reference}`} checked={payWhat === 'balance'} onChange={() => setPayWhat('balance')} />
                <span className="pay-method-text">
                  <strong>The whole balance: {money(balance)}</strong>
                  <small>Clears the fee now; the commission is added once it is paid.</small>
                </span>
              </label>
            </fieldset>
          ) : (
            <p className="pay-hint">Balance to pay: {money(balance)}.</p>
          )}
        </div>
      ) : (
        <PlanChooser totalNgn={quote.amount_ngn} plan={plan} onChange={setPlan} name={`plan-${reference}`} money={money} />
      )}

      {canTransfer || canLink ? (
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
          {canLink ? (
            <label className={`pay-method${method === 'link' ? ' is-selected' : ''}`}>
              <input
                type="radio"
                name={`pay-${reference}`}
                value="link"
                checked={method === 'link'}
                onChange={() => setMethod('link')}
              />
              <span className="pay-method-text">
                <strong>Send a payment link</strong>
                <small>The student pays by card from any country. Confirmed instantly.</small>
              </span>
            </label>
          ) : null}
          {canTransfer ? (
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
          ) : null}
        </fieldset>
      ) : null}

      {method === 'link' && canLink ? (
        <div className="pay-panel">
          <div className="pay-amount">
            <span>Application fee</span>
            <strong>{applicationFee}</strong>
          </div>
          <p className="pay-hint">
            Send this link to the student. They pay by card on their own phone, in any country, and Paystack adds
            its card fee. When Paystack confirms, the fee shows as paid here and your commission is added.
          </p>
          {link ? (
            <>
              <div className="pay-link-box">
                <input
                  className="pay-link-input"
                  value={link}
                  readOnly
                  aria-label="Payment link"
                  onFocus={(event) => event.target.select()}
                />
                <button type="button" className="pay-copy" onClick={copyLink}>
                  {linkCopied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <a
                className="agent-btn agent-btn-primary agent-btn-block"
                href={whatsappHref}
                target="_blank"
                rel="noopener noreferrer"
              >
                Share on WhatsApp
              </a>
            </>
          ) : (
            <button
              type="button"
              className="agent-btn agent-btn-primary agent-btn-block"
              onClick={makeLink}
              disabled={busy}
            >
              {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
              {busy ? 'Creating the link' : 'Create payment link'}
            </button>
          )}
        </div>
      ) : method === 'paystack' || !canTransfer ? (
        <div className="pay-panel">
          <div className="pay-amount">
            <span>{progress || plan === 'instalments' ? 'To pay now' : 'Application fee'}</span>
            <strong>{progress || plan === 'instalments' ? money(dueNow) : applicationFee}</strong>
          </div>
          <p className="pay-hint">
            {Number(quote.school_count) > 1 ? `Covers ${quote.school_count} schools. ` : ''}
            Paystack shows the amount in Naira, with its card processing fee.
          </p>
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
                  <dd className="pay-account-amount">
                    {transferTotal}
                    <small className="pay-account-note">
                      {progress || plan === 'instalments'
                        ? 'This payment of the application fee'
                        : `Application fee ${applicationFee} at today's rate`}
                    </small>
                  </dd>
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
                {busy ? 'Sending' : `I have sent ${transferTotal}`}
              </button>
            </>
          ) : null}
        </div>
      )}

      {error ? <p className="pay-error" role="alert">{error}</p> : null}
    </div>
  );
}
