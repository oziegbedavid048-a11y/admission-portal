import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';
import { payments } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';

/**
 * Where Paystack sends the applicant back to.
 *
 * Reachable without a session, so a payment made on one device can still be
 * confirmed on another; a signed-in applicant is offered their dashboard.
 *
 * The browser is not told whether the payment succeeded, and could not be trusted
 * if it were: it asks the server, and the server asks Paystack. Paystack's webhook
 * is the primary path, so the payment is usually settled before this loads; when
 * it is not, the status endpoint verifies the reference directly rather than
 * leaving somebody watching a spinner until a webhook turns up.
 *
 * Paystack appends the transaction reference to the return URL, and the server
 * requires it, because an application number is short enough to guess.
 */

const ATTEMPTS = 6;
const GAP_MS = 2500;

export default function PaymentReturnPage() {
  const { reference } = useParams();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const gatewayReference = params.get('reference') || params.get('trxref') || '';

  const [state, setState] = useState('checking');
  const [result, setResult] = useState(null);
  const attempt = useRef(0);
  const timer = useRef(null);

  const poll = useCallback(async () => {
    attempt.current += 1;
    try {
      const { data } = await payments.status(reference, gatewayReference);
      setResult(data);
      if (data.settled) {
        setState('settled');
        return;
      }
      if (attempt.current >= ATTEMPTS) {
        setState('pending');
        return;
      }
      timer.current = window.setTimeout(poll, GAP_MS);
    } catch {
      // A failed check is not a failed payment. Say so plainly rather than
      // implying the money is gone.
      setState('unknown');
    }
  }, [reference, gatewayReference]);

  useEffect(() => {
    poll();
    return () => window.clearTimeout(timer.current);
  }, [poll]);

  const continueLink = user ? (
    <Link to="/portal" className="btn btn-accent btn-lg">
      Go to my dashboard
      <Icon name="arrowRight" size={16} strokeWidth={2} />
    </Link>
  ) : (
    <Link to="/" state={{ signIn: true }} className="btn btn-accent btn-lg">
      <Icon name="signIn" size={16} strokeWidth={2} />
      Sign in
    </Link>
  );

  return (
    <>
      <SiteHeader />
      <main className="section">
        <div className="container">
          <div className="return-card">
            {state === 'checking' ? (
              <>
                <span className="spinner" aria-hidden="true" />
                <h1 className="return-title">Confirming your payment</h1>
                <p className="return-note">
                  This takes a few seconds. Do not close the page.
                </p>
              </>
            ) : null}

            {state === 'settled' ? (
              <>
                <span className="return-mark is-ok" aria-hidden="true">
                  <Icon name="checkCircle" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">Payment successful</h1>
                <p className="return-note">
                  {result?.display_total ? `${result.display_total} received. ` : ''}
                  Application {result?.application || reference} is submitted and with
                  the admissions desk.
                </p>

                {continueLink}
              </>
            ) : null}

            {state === 'pending' ? (
              <>
                <span className="return-mark is-wait" aria-hidden="true">
                  <Icon name="clock" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">Still settling</h1>
                <p className="return-note">
                  Your bank has not confirmed this one yet. Nothing is lost and you do
                  not need to pay again: it clears on its own, and your dashboard
                  updates the moment it does.
                </p>
                {continueLink}
              </>
            ) : null}

            {state === 'unknown' ? (
              <>
                <span className="return-mark is-wait" aria-hidden="true">
                  <Icon name="alert" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">We could not check just now</h1>
                <p className="return-note">
                  Your payment may well have gone through. Your dashboard shows it
                  once it clears. If it does not within a few minutes, contact
                  Support quoting {reference}.
                </p>
                {continueLink}
              </>
            ) : null}
          </div>
        </div>
      </main>
    </>
  );
}
