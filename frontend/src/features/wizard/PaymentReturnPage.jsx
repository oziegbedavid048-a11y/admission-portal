import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';
import { payments } from '../../api/endpoints';

/**
 * Where Paystack sends the applicant back to.
 *
 * Reached without a session, on purpose. The account's password was emailed and
 * never chosen, so nobody has signed in: this page confirms the payment and sends
 * them to the sign-in screen with the details from their inbox. It does not put
 * them inside a dashboard for an account they have not logged into.
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
                <h1 className="return-title">Application fee paid</h1>
                <p className="return-note">
                  {result?.display_total ? `${result.display_total} received. ` : ''}
                  Your application {result?.application || reference} is submitted and
                  with the admissions desk.
                </p>

                {result?.credentials_sent === false ? (
                  <div className="callout callout-warning return-callout">
                    <Icon name="alert" size={20} className="callout-icon" strokeWidth={2} />
                    <div className="callout-content">
                      Your payment is safe and your application is filed. We could not
                      send your sign-in details just now, so the admissions desk will
                      email them to you shortly.
                    </div>
                  </div>
                ) : (
                  <div className="callout callout-success return-callout">
                    <Icon name="mail" size={20} className="callout-icon" strokeWidth={2} />
                    <div className="callout-content">
                      Your sign-in details have been emailed to you. Use them to log in
                      and follow your application.
                    </div>
                  </div>
                )}

                <Link to="/?signin=1" className="btn btn-accent btn-lg">
                  <Icon name="signIn" size={16} strokeWidth={2} />
                  Go to login
                </Link>
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
                  not need to pay again: it clears on its own, and we email your
                  sign-in details the moment it does.
                </p>
                <Link to="/" className="btn btn-accent btn-lg">
                  Back to the site
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </Link>
              </>
            ) : null}

            {state === 'unknown' ? (
              <>
                <span className="return-mark is-wait" aria-hidden="true">
                  <Icon name="alert" size={26} strokeWidth={2} />
                </span>
                <h1 className="return-title">We could not check just now</h1>
                <p className="return-note">
                  Your payment may well have gone through. We email your sign-in
                  details once it clears. Get in touch if nothing arrives in a few
                  minutes, quoting {reference}.
                </p>
                <Link to="/" className="btn btn-accent btn-lg">
                  Back to the site
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
                </Link>
              </>
            ) : null}
          </div>
        </div>
      </main>
    </>
  );
}
