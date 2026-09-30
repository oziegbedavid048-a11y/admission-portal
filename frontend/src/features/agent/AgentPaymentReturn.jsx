import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { payments } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import { useAgent } from './AgentContext';
import { downloadStudentSummary } from './studentSummary';

/**
 * Where Paystack sends an agent back after paying a student's fee.
 *
 * The browser never decides that a payment worked: it asks the server, and the
 * server asks Paystack. When Paystack confirms, the fee is settled and the
 * agent's commission is credited on the server in the same step.
 */

const ATTEMPTS = 8;
const GAP_MS = 2500;

export default function AgentPaymentReturn() {
  const { reference } = useParams();
  const [params] = useSearchParams();
  const gatewayReference = params.get('reference') || params.get('trxref') || '';
  const [state, setState] = useState('checking');
  const [result, setResult] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const attempt = useRef(0);
  const timer = useRef(null);
  const navigate = useNavigate();
  const toast = useToast();
  const { reload } = useAgent();

  const poll = useCallback(async () => {
    attempt.current += 1;
    try {
      const { data } = await payments.status(reference, gatewayReference);
      setResult(data);
      if (data.settled) {
        setState('settled');
        reload?.().catch(() => null);
        return;
      }
      if (attempt.current >= ATTEMPTS) {
        setState('pending');
        return;
      }
      timer.current = window.setTimeout(poll, GAP_MS);
    } catch {
      setState('unknown');
    }
  }, [reference, gatewayReference, reload]);

  useEffect(() => {
    poll();
    return () => window.clearTimeout(timer.current);
  }, [poll]);

  const summary = async () => {
    setDownloading(true);
    try {
      await downloadStudentSummary(reference);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not download the summary.'));
    } finally {
      setDownloading(false);
    }
  };

  const total = result?.payment?.display_total || result?.display_total || '';

  return (
    <div className="agent-stack">
      <div className="nf-card nf-done">
        {state === 'checking' ? (
          <>
            <span className="nf-done-mark is-wait" aria-hidden="true">
              <span className="spinner-sm" />
            </span>
            <h2>Confirming your payment</h2>
            <p className="nf-done-lede">We are checking with Paystack. This takes a few seconds.</p>
          </>
        ) : null}

        {state === 'settled' ? (
          <>
            <span className="nf-done-mark" aria-hidden="true">
              <Icon name="check" size={26} strokeWidth={2.4} />
            </span>
            <h2>Payment successful</h2>
            <p className="nf-done-lede">The application fee is paid and the file is with the admissions desk.</p>
            <dl className="nf-done-facts">
              <div>
                <dt>Application reference</dt>
                <dd>{reference}</dd>
              </div>
              {total ? (
                <div>
                  <dt>Amount paid</dt>
                  <dd>{total}</dd>
                </div>
              ) : null}
            </dl>
            <div className="nf-done-actions">
              <button type="button" className="agent-btn agent-btn-primary" onClick={summary} disabled={downloading}>
                {downloading ? <span className="spinner-sm" aria-hidden="true" /> : null}
                Download student summary
              </button>
              <button type="button" className="agent-btn agent-btn-secondary" onClick={() => navigate('/agent/students')}>
                Go to students
              </button>
            </div>
          </>
        ) : null}

        {state === 'pending' || state === 'unknown' ? (
          <>
            <span className="nf-done-mark is-wait" aria-hidden="true">
              <Icon name="clock" size={26} strokeWidth={2.4} />
            </span>
            <h2>{state === 'pending' ? 'Payment not confirmed yet' : 'We could not check the payment'}</h2>
            <p className="nf-done-lede">
              {state === 'pending'
                ? 'Paystack has not confirmed this payment. If money left your account it will be confirmed shortly; nothing is charged twice.'
                : 'Your connection dropped while checking. Try again, or open the student from Students.'}
            </p>
            <div className="nf-done-actions">
              <button
                type="button"
                className="agent-btn agent-btn-primary"
                onClick={() => {
                  attempt.current = 0;
                  setState('checking');
                  poll();
                }}
              >
                Check again
              </button>
              <button type="button" className="agent-btn agent-btn-secondary" onClick={() => navigate('/agent/students')}>
                Go to students
              </button>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
