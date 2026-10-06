import { useEffect, useState } from 'react';
import Loading from '../../components/ui/Loading';
import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import { useAgent } from './AgentContext';
import { LedgerDate, LedgerStatus, ShowMore, loanStatus, useShowMore } from './Ledger';

// The range is set in Naira (₦10,000 to ₦80,000). Outside Nigeria the server
// sends it in the agent's currency at today's rate, as loan_min and loan_max.
const NAIRA_MIN = 10000;
const NAIRA_MAX = 80000;

function roundTo(value, step) {
  return Math.round(value / step) * step;
}

// Four quick picks across the range: the minimum, about a third, about two
// thirds, and the maximum, in round figures for the currency.
function presetsFor(min, max, naira) {
  if (naira) return [10000, 25000, 50000, 80000];
  const step = max >= 5000 ? 100 : max >= 500 ? 10 : 1;
  const third = Math.min(max, Math.max(min, roundTo(min + (max - min) * 0.2, step)));
  const twoThirds = Math.min(max, Math.max(min, roundTo(min + (max - min) * 0.57, step)));
  return Array.from(new Set([min, third, twoThirds, max]));
}

const PLATFORMS = [
  'Facebook Ads',
  'Instagram Ads',
  'Google Search Ads',
  'TikTok Video Ads',
  'Offline Campus Outreach',
];

// Statuses that mean a loan is still in play. A new request waits until none is.
const OPEN_STATUSES = ['pending', 'approved', 'disbursed'];

export default function AgentLoans() {
  const { profile, wallet, setWallet, money, symbol, currency } = useAgent();
  const naira = currency === 'NGN';
  const MIN = Number(wallet?.loan_min) || NAIRA_MIN;
  const MAX = Number(wallet?.loan_max) || NAIRA_MAX;
  const PRESETS = presetsFor(MIN, MAX, naira);
  const STEP = naira ? 1000 : 1;
  const [loans, setLoans] = useState([]);
  const loanRows = useShowMore(loans);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState(() => PRESETS[1] || MIN);
  // When the wallet's range arrives or changes, start from the second pick.
  useEffect(() => {
    setAmount(PRESETS[1] || MIN);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [MIN, MAX]);
  const [purpose, setPurpose] = useState('');
  const [busy, setBusy] = useState(false);
  const [repayOpen, setRepayOpen] = useState(false);
  const [repayAmount, setRepayAmount] = useState('');
  const [repaying, setRepaying] = useState(false);
  const toast = useToast();

  const owed = Number(wallet?.loan_balance) || 0;
  const available = Number(wallet?.available_balance) || 0;
  const repayable = Math.min(owed, available);
  const inReview = loans.some((loan) => loan.status === 'pending');
  const blocked = owed > 0 || loans.some((loan) => OPEN_STATUSES.includes(loan.status));

  const openRepay = () => {
    setRepayAmount(String(repayable || ''));
    setRepayOpen(true);
  };

  const repay = async () => {
    const value = Number(repayAmount);
    if (!value || value <= 0) {
      toast.warning('Enter an amount to repay.');
      return;
    }
    if (value > owed) {
      toast.warning(`You owe ${money(owed)}. Enter that amount or less.`);
      return;
    }
    if (value > available) {
      toast.warning('That is more than your available balance.');
      return;
    }
    setRepaying(true);
    try {
      const { data } = await partners.repayLoan(value);
      setWallet(data.wallet);
      setLoans(data.loans);
      setRepayOpen(false);
      toast.success(
        Number(data.wallet.loan_balance) > 0
          ? `${money(value)} repaid. ${money(data.wallet.loan_balance)} left to repay.`
          : 'Ads funding fully repaid. You can request again.',
      );
    } catch (error) {
      toast.error(errorMessage(error, 'Could not repay that amount.'));
    } finally {
      setRepaying(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    partners
      .loans()
      .then(({ data }) => {
        if (!cancelled) setLoans(data);
      })
      .catch(() => {
        if (!cancelled) setLoans([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    if (!purpose) {
      toast.warning('Choose an advertising platform.');
      return;
    }

    setBusy(true);
    try {
      const { data } = await partners.requestLoan({
        requested_amount: amount,
        purpose,
        ad_account_link: 'https://business.facebook.com/adsmanager',
      });
      setLoans((current) => [data, ...current]);
      setPurpose('');
      setAmount(PRESETS[1] || MIN);
      toast.success(`${money(amount)} requested. We review the campaign and disburse within 24 hours.`);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not submit that request.'));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Loading label="Loading your funding" />;

  const percent = ((amount - MIN) / (MAX - MIN)) * 100;

  return (
    <div className="agent-stack">
      {owed > 0 ? (
        <section className="agent-card">
          <div className="agent-card-header">
            <h2 className="agent-card-title">
              <span className="agent-icon accent" aria-hidden="true">
                <Icon name="wallet" size={18} />
              </span>
              Ads funding owed
            </h2>
          </div>
          <div className="payout-calc-box" style={{ margin: '0 0 20px' }}>
            <div className="payout-calc-row total">
              <span>To repay</span>
              <strong>{money(owed)}</strong>
            </div>
            <div className="payout-calc-row">
              <span>Available balance</span>
              <strong>{money(available)}</strong>
            </div>
          </div>
          <button
            type="button"
            className="agent-btn agent-btn-primary"
            onClick={openRepay}
            disabled={repayable <= 0}
          >
            <Icon name="payout" size={18} />
            Repay from balance
          </button>
          {repayable <= 0 ? (
            <p className="agent-card-note" style={{ marginTop: 12 }}>
              Your balance is empty. Earn commission to repay from it.
            </p>
          ) : null}
        </section>
      ) : null}

      {blocked ? (
        <section className="agent-card">
          <div className="agent-empty-state">
            <p>{inReview ? 'Request in review' : 'Repay to request again'}</p>
            <small>
              {inReview
                ? 'The desk will come back to you on your current request first.'
                : 'You can request new Ads funding once your current funding is repaid.'}
            </small>
          </div>
        </section>
      ) : (
      <section className="agent-card">
        <form onSubmit={submit}>
          <div className="loan-hero-module">
            <div className="loan-amount-hero">
              <div className="loan-amount-eyebrow">Requested budget</div>
              <div className="loan-slider-amount-large">{money(amount)}</div>
            </div>

            <div className="loan-presets-wrap">
              {PRESETS.map((preset) => (
                <button
                  type="button"
                  key={preset}
                  className={`loan-preset-chip ${amount === preset ? 'active' : ''}`.trim()}
                  onClick={() => setAmount(preset)}
                >
                  {money(preset)}
                  {preset === MAX ? ' (max)' : ''}
                </button>
              ))}
            </div>

            <div className="loan-slider-container">
              <label className="sr-only" htmlFor="loan-amount">
                Amount
              </label>
              <input
                type="range"
                id="loan-amount"
                className="loan-custom-range"
                min={MIN}
                max={MAX}
                step={STEP}
                value={amount}
                style={{ '--pct': `${percent}%` }}
                aria-valuetext={money(amount)}
                onChange={(event) => setAmount(Number(event.target.value))}
              />
              <div className="loan-ticks-row" aria-hidden="true">
                <span>{money(MIN)} min</span>
                <span>{money(PRESETS[1])}</span>
                <span>{money(PRESETS[2])}</span>
                <span>{money(MAX)} max</span>
              </div>
            </div>
          </div>

          <div className="agent-form-group" style={{ marginTop: 20 }}>
            <label className="agent-form-label" htmlFor="loan-purpose">
              Advertising platform *
            </label>
            <select
              id="loan-purpose"
              className="agent-form-select"
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
            >
              <option value="" />
              {PLATFORMS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div className="payout-calc-box" style={{ margin: '20px 0' }}>
            <div className="payout-calc-row">
              <span>Paid to</span>
              <strong>
                {profile?.bank_name} ({profile?.account_number})
              </strong>
            </div>
            <div className="payout-calc-row">
              <span>Approval</span>
              <strong>Subject to approval</strong>
            </div>
          </div>

          <button type="submit" className="agent-btn agent-btn-primary" disabled={busy}>
            {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
            <Icon name="arrowRight" size={18} strokeWidth={2.2} />
            Submit request
          </button>
        </form>
      </section>
      )}

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Request history</h2>
        </div>
        <div className="ledger-scroll" role="region" aria-label="Request history" tabIndex={0}>
          {loans.length === 0 ? (
            <div className="ledger-empty">
              <p>No funding requests yet</p>
              <small>Your requests will show here.</small>
            </div>
          ) : (
            <table className="ledger-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Reference</th>
                  <th scope="col">Platform</th>
                  <th scope="col" className="t-num">Requested</th>
                  <th scope="col" className="t-num">Approved</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {loanRows.visible.map((loan) => {
                  const [tone, label] = loanStatus(loan.status);
                  return (
                    <tr key={loan.id}>
                      <td>
                        <LedgerDate value={loan.requested_at} />
                      </td>
                      <td>
                        <span className="ledger-ref">{loan.reference}</span>
                      </td>
                      <td>{loan.purpose}</td>
                      <td className="t-num">
                        <span className="ledger-amount">{money(loan.requested_amount)}</span>
                      </td>
                      <td className="t-num">
                        {loan.approved_amount ? (
                          <span className="ledger-amount">{money(loan.approved_amount)}</span>
                        ) : (
                          <span className="ledger-muted">Not yet</span>
                        )}
                      </td>
                      <td>
                        <LedgerStatus tone={tone}>{label}</LedgerStatus>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <ShowMore list={loanRows} />
      </section>

      <Modal
        open={repayOpen}
        onClose={() => setRepayOpen(false)}
        variant="agent"
        title="Repay Ads funding"
        labelledBy="repay-title"
        footer={
          <>
            <button
              type="button"
              className="agent-btn agent-btn-secondary"
              onClick={() => setRepayOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="agent-btn agent-btn-primary"
              onClick={repay}
              disabled={repaying || !Number(repayAmount)}
            >
              {repaying ? <span className="spinner-sm" aria-hidden="true" /> : null}
              Repay
            </button>
          </>
        }
      >
        <div className="agent-form-group">
          <label className="agent-form-label" htmlFor="repay-amount">
            Amount ({symbol || '₦'})
          </label>
          <input
            id="repay-amount"
            type="number"
            className="agent-form-control"
            min={1}
            max={repayable}
            step="1000"
            inputMode="numeric"
            value={repayAmount}
            onChange={(event) => setRepayAmount(event.target.value)}
          />
          <span className="form-helper">
            Owed {money(owed)} · available {money(available)}
          </span>
        </div>
        <p className="agent-card-note">Taken from your available balance. There is no interest.</p>
      </Modal>
    </div>
  );
}
