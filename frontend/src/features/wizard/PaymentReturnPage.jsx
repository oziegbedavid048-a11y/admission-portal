import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';
import { payments } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';

/**
 * Where Paystack sends the applicant back to.
 *
 * The browser is not told whether the payment succeeded and could not be trusted
 * if it were: it asks the server, and the server asks Paystack. Paystack's own
 * webhook is the primary path, so by the time this page loads the payment is
 * often already settled; when it is not, the status endpoint verifies the
 * reference directly rather than leaving the applicant looking at a spinner until
 * a webhook turns up.
 *
 * It retries for a short while because a card can sit in "processing" for a few
 * seconds, then stops and tells the applicant what to do. It never says the fee
 * is unpaid on the strength of one inconclusive answer.
 */

const ATTEMPTS = 6;
const GAP_MS = 2500;

export default function PaymentReturnPage() {
  const { reference } = useParams();
  const { adopt } = useAuth();
  const [state, setState] = useState('checking');
  const [payment, setPayment] = useState(null);
  const attempt = useRef(0);
  const timer = useRef(null);

  const poll = useCallback(async () => {
    attempt.current += 1;
    try {
      const { data } = await payments.status(reference);
      setPayment(data.payment);
      if (data.settled) {
        if (data.access && adopt) {
          adopt({ access: data.access, user: data.user });
        }
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
  }, [reference]);

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
                <h1 className="return-title">Payment Confirmed</h1>
                <p className="return-note">
                  {payment?.display_total ? `${payment.display_total} received for ${reference}. ` : ''}
                  Your file is now submitted and your login details have been sent to your email.
                </p>
                <div className="callout callout-success" style={{ margin: '18px 0', textAlign: 'left' }}>
                  <Icon name="checkCircle" size={20} className="callout-icon" strokeWidth={2} />
                  <div className="callout-content" style={{ fontSize: '0.875rem' }}>
                    <strong>Account activated:</strong> Check your inbox for your login credentials. You can access and track your application status anytime from your student dashboard.
                  </div>
                </div>
                <Link to="/portal" className="btn btn-accent btn-lg" style={{ marginTop: 8 }}>
                  Open my dashboard
                  <Icon name="arrowRight" size={16} strokeWidth={2} />
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
                  Your bank has not confirmed this one yet. Nothing is lost and you
                  do not need to pay again: it clears on its own, and we email you
                  the moment it does.
                </p>
                <Link to="/portal" className="btn btn-accent btn-lg">
                  Open my dashboard
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
                  Your payment may well have gone through. Open your dashboard to
                  see where {reference} stands, and get in touch if it still looks
                  unpaid in a few minutes.
                </p>
                <Link to="/portal" className="btn btn-accent btn-lg">
                  Open my dashboard
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
