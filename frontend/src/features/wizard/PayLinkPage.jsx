import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { payments } from '../../api/endpoints';
import { formatFee, formatNaira } from '../../lib/format';

/**
 * The page behind a payment link an agent sends a student.
 *
 * No sign-in: the student opens the link on their own phone, sees what the
 * fee is for, and pays by card through Paystack, from any country. Paystack
 * sends them back here, and the page asks the server, which asks Paystack, so
 * the browser never decides whether a payment succeeded. The agent sees the
 * fee as paid, with their commission, the moment Paystack confirms.
 */

const ATTEMPTS = 6;
const GAP_MS = 2500;

export default function PayLinkPage() {
  const { code } = useParams();
  const [params] = useSearchParams();
  const gatewayReference = params.get('reference') || params.get('trxref') || '';

  const [info, setInfo] = useState(null);
  const [state, setState] = useState(gatewayReference ? 'confirming' : 'loading');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // Before anything is paid: "full" or "instalments". After the deposit:
  // "next" (the next instalment) or "balance" (everything left).
  const [choice, setChoice] = useState('');
  const attempt = useRef(0);
  const timer = useRef(null);

  const load = useCallback(async () => {
    attempt.current += 1;
    try {
      const { data } = await payments.payLink(code, gatewayReference);
      setInfo(data);
      // A deposit or instalment just paid: the fee is still "due", but this
      // payment is in.
      if (gatewayReference && data.status === 'due' && data.received) {
        setState('received');
        return;
      }
      if (data.status !== 'due' || !gatewayReference) {
        setState(data.status);
        return;
      }
      // Back from Paystack but not confirmed yet: ask again for a little while.
      if (attempt.current >= ATTEMPTS) {
        setState('settling');
        return;
      }
      timer.current = window.setTimeout(load, GAP_MS);
    } catch (err) {
      setError(
        err?.response?.status === 404
          ? 'This payment link is not valid. Ask the person who sent it for a new one.'
          : errorMessage(err, 'We could not load this payment. Check your connection and try again.'),
      );
      setState('error');
    }
  }, [code, gatewayReference]);

  useEffect(() => {
    load();
    return () => window.clearTimeout(timer.current);
  }, [load]);

  const pay = async () => {
    setBusy(true);
    setError('');
    try {
      const options = info?.options || {};
      const partPaid = Number(options.paid_ngn) > 0;
      const picked = choice || (partPaid ? 'next' : 'full');
      const { data } = await payments.startPayLink(
        code,
        partPaid ? { pay: picked === 'balance' ? 'balance' : 'next' } : { plan: picked === 'instalments' ? 'instalments' : 'full' },
      );
      window.location.assign(data.authorization_url);
    } catch (err) {
      if (err?.response?.data?.code === 'paid') {
        setState('paid');
      } else {
        setError(errorMessage(err, 'The card payment page could not be opened. Please try again.'));
      }
      setBusy(false);
    }
  };

  const courses = (info?.courses || []).filter(Boolean).join(' & ');
  const otherSchools = (info?.schools || []).slice(1);
  const options = info?.options || {};
  const partPaid = Number(options.paid_ngn) > 0;
  const picked = choice || (partPaid ? 'next' : 'full');
  const nextAmount = Number(options.next?.amount_ngn) || 0;
  const canSplit = !partPaid && (options.instalments || []).length > 1;
  const offerNext = partPaid && nextAmount > 0 && nextAmount < Number(options.balance_ngn);
  const dueDate = (value) =>
    value ? new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  const withLocal = (naira, local) => `${formatNaira(naira)}${local ? ` (about ${local})` : ''}`;

  return (
    <>
      <SiteHeader />
      <main className="section">
        <div className="container">
          <div className="return-card">
            {state === 'loading' || state === 'confirming' ? (
              <>
                <span className="spinner" aria-hidden="true" />
                <h1 className="return-title">
                  {state === 'confirming' ? 'Confirming your payment' : 'Loading your payment'}
                </h1>
                {state === 'confirming' ? (
                  <p className="return-note">This takes a few seconds. Do not close the page.</p>
                ) : null}
              </>
            ) : null}

            {state === 'due' && info ? (
              <>
                <h1 className="return-title">Application fee</h1>
                <p className="return-note">
                  {info.student ? `For ${info.student}'s application to ` : 'For an application to '}
                  <strong>{info.institution || 'a partner university'}</strong>
                  {courses ? ` (${courses})` : ''}
                  {otherSchools.length ? `, and ${otherSchools.join(' and ')} under the same fee` : ''}.
                </p>
                {/* In the student's own currency when they are outside Nigeria;
                    the card is charged in Naira and their bank converts it. */}
                <div className="paylink-amount">
                  <span>Amount{info.local_display ? ` in ${info.local_currency}` : ''}</span>
                  <strong>
                    {info.local_display
                      ? `about ${info.local_display}`
                      : formatFee(info.amount, info.currency, info.symbol)}
                  </strong>
                  <small>
                    {info.local_display
                      ? `Application fee ${formatFee(info.amount, info.currency, info.symbol)}, charged as ${formatNaira(info.amount_ngn)} at today's rate`
                      : info.currency && info.currency.toUpperCase() !== 'NGN'
                        ? `Charged as ${formatNaira(info.amount_ngn)} at today's rate`
                        : 'Application fee'}
                  </small>
                </div>
                {partPaid ? (
                  <fieldset className="pay-methods paylink-choices">
                    <legend className="nf-label">
                      {formatNaira(options.paid_ngn)} paid. Pay now:
                    </legend>
                    {offerNext ? (
                      <label className={`pay-method${picked === 'next' ? ' is-selected' : ''}`}>
                        <input type="radio" name="paylink-choice" checked={picked === 'next'} onChange={() => setChoice('next')} />
                        <span className="pay-method-text">
                          <strong>Next payment: {withLocal(nextAmount, options.next_local)}</strong>
                          {options.next?.due_on ? <small>Due {dueDate(options.next.due_on)}.</small> : null}
                        </span>
                      </label>
                    ) : null}
                    <label className={`pay-method${picked === 'balance' || !offerNext ? ' is-selected' : ''}`}>
                      <input
                        type="radio"
                        name="paylink-choice"
                        checked={picked === 'balance' || !offerNext}
                        onChange={() => setChoice('balance')}
                      />
                      <span className="pay-method-text">
                        <strong>The whole balance: {withLocal(options.balance_ngn, options.balance_ngn_local)}</strong>
                      </span>
                    </label>
                  </fieldset>
                ) : canSplit ? (
                  <fieldset className="pay-methods paylink-choices">
                    <legend className="nf-label">How do you want to pay?</legend>
                    <label className={`pay-method${picked === 'full' ? ' is-selected' : ''}`}>
                      <input type="radio" name="paylink-choice" checked={picked === 'full'} onChange={() => setChoice('full')} />
                      <span className="pay-method-text">
                        <strong>Pay in full</strong>
                      </span>
                    </label>
                    <label className={`pay-method${picked === 'instalments' ? ' is-selected' : ''}`}>
                      <input
                        type="radio"
                        name="paylink-choice"
                        checked={picked === 'instalments'}
                        onChange={() => setChoice('instalments')}
                      />
                      <span className="pay-method-text">
                        <strong>Pay small small</strong>
                        <small>
                          {withLocal(options.deposit_ngn, options.deposit_ngn_local)} now, then{' '}
                          {options.instalments.slice(1).map((amount) => formatNaira(amount)).join(' and ')} a week apart.
                        </small>
                      </span>
                    </label>
                  </fieldset>
                ) : null}
                <p className="return-note paylink-small">
                  You pay by card on Paystack&apos;s secure page. Paystack adds its card fee
                  {info.local_display ? ', and your bank converts the Naira charge, so the final figure can differ slightly' : ''}.
                </p>
                {info.card_available ? (
                  <button type="button" className="btn btn-accent btn-lg" onClick={pay} disabled={busy}>
                    {busy ? <span className="spinner-sm" aria-hidden="true" /> : <Icon name="lock" size={16} strokeWidth={2} />}
                    {busy
                      ? 'Opening Paystack'
                      : partPaid
                        ? `Pay ${formatNaira(picked === 'balance' || !offerNext ? options.balance_ngn : nextAmount)} with card`
                        : picked === 'instalments'
                          ? `Pay ${formatNaira(options.deposit_ngn)} with card`
                          : 'Pay with card'}
                  </button>
                ) : (
                  <p className="return-note">Card payments are not available right now. Please try again later.</p>
                )}
                {error ? <p className="pay-error" role="alert">{error}</p> : null}
              </>
            ) : null}

            {state === 'paid' ? (
              <>
                <span className="return-mark is-ok" aria-hidden="true">
                  <Icon name="checkCircle" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">{info?.settled_now ? 'Payment successful' : 'This fee is paid'}</h1>
                <p className="return-note">
                  {info?.paid_total ? `${info.paid_total} received` : 'The application fee has been received'}
                  {info?.institution ? ` for the application to ${info.institution}` : ''}. Your education agent can
                  see it now. There is nothing more to pay.
                </p>
              </>
            ) : null}

            {state === 'received' ? (
              <>
                <span className="return-mark is-ok" aria-hidden="true">
                  <Icon name="checkCircle" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">Payment received</h1>
                <p className="return-note">
                  Thank you. Work on the application has started.{' '}
                  {info?.options?.balance_ngn
                    ? `${formatNaira(info.options.balance_ngn)} of the application fee is still to pay${
                        info.options.next?.due_on
                          ? `; the next payment is due ${new Date(info.options.next.due_on).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`
                          : ''
                      }. Use this same link to pay it.`
                    : ''}
                </p>
              </>
            ) : null}

            {state === 'settling' ? (
              <>
                <span className="return-mark is-wait" aria-hidden="true">
                  <Icon name="clock" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">Still confirming</h1>
                <p className="return-note">
                  Your bank has not confirmed this payment yet. Do not pay again: it clears on its own, and your
                  education agent sees it the moment it does.
                </p>
              </>
            ) : null}

            {state === 'review' ? (
              <>
                <span className="return-mark is-wait" aria-hidden="true">
                  <Icon name="clock" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">Payment already sent</h1>
                <p className="return-note">
                  A bank transfer for this application is waiting for confirmation, so there is nothing to pay
                  here. Contact your education agent if you have questions.
                </p>
              </>
            ) : null}

            {state === 'no_fee' ? (
              <>
                <span className="return-mark is-ok" aria-hidden="true">
                  <Icon name="checkCircle" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">No fee to pay</h1>
                <p className="return-note">This university does not charge an application fee.</p>
              </>
            ) : null}

            {state === 'error' ? (
              <>
                <span className="return-mark is-wait" aria-hidden="true">
                  <Icon name="alert" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">Payment unavailable</h1>
                <p className="return-note">{error}</p>
                <button type="button" className="btn btn-ghost" onClick={() => window.location.reload()}>
                  Try again
                </button>
              </>
            ) : null}
          </div>
        </div>
      </main>
    </>
  );
}
