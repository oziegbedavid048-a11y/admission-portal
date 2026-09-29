import { useEffect, useState } from 'react';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { formatDate, formatNaira } from '../../lib/format';
import { errorMessage } from '../../api/client';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import { useAgent } from './AgentContext';
import StatusBadge from './StatusBadge';

const MIN = 10000;
const MAX = 80000;
const PRESETS = [10000, 25000, 50000, 80000];

const PLATFORMS = [
  'Facebook Ads',
  'Instagram Ads',
  'Google Search Ads',
  'TikTok Video Ads',
  'Offline Campus Outreach',
];

export default function AgentLoans() {
  const { profile } = useAgent();
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState(25000);
  const [purpose, setPurpose] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();

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
      setAmount(25000);
      toast.success(`${formatNaira(amount)} requested. We review the campaign and disburse within 24 hours.`);
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

      <section className="agent-card">
        <form onSubmit={submit}>
          <div className="loan-hero-module">
            <div className="loan-amount-hero">
              <div className="loan-amount-eyebrow">Requested budget</div>
              <div className="loan-slider-amount-large">{formatNaira(amount)}</div>
            </div>

            <div className="loan-presets-wrap">
              {PRESETS.map((preset) => (
                <button
                  type="button"
                  key={preset}
                  className={`loan-preset-chip ${amount === preset ? 'active' : ''}`.trim()}
                  onClick={() => setAmount(preset)}
                >
                  {formatNaira(preset)}
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
                step={1000}
                value={amount}
                style={{ '--pct': `${percent}%` }}
                aria-valuetext={formatNaira(amount)}
                onChange={(event) => setAmount(Number(event.target.value))}
              />
              <div className="loan-ticks-row" aria-hidden="true">
                <span>{formatNaira(MIN)} min</span>
                <span>{formatNaira(25000)}</span>
                <span>{formatNaira(50000)}</span>
                <span>{formatNaira(MAX)} max</span>
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
              <strong>Reviewed by the admissions desk</strong>
            </div>
          </div>

          <button type="submit" className="agent-btn agent-btn-primary" disabled={busy}>
            {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
            <Icon name="arrowRight" size={18} strokeWidth={2.2} />
            Submit request
          </button>
        </form>
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="clock" size={18} />
            </span>
            Request history
          </h2>
        </div>
        <div className="agent-table-wrap">
          <table className="agent-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th className="t-num">Requested</th>
                <th className="t-num t-hide-sm">Disbursed</th>
                <th className="t-hide-sm">Platform</th>
                <th className="t-hide-sm">Date</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loans.length === 0 ? (
                <tr className="row-empty">
                  <td colSpan={6}>
                    <div className="agent-empty-state">
                      <p>No funding requests yet</p>
                      <small>Pick an amount above to fund your recruitment campaigns.</small>
                    </div>
                  </td>
                </tr>
              ) : (
                loans.map((loan) => (
                  <tr key={loan.id}>
                    <td data-label="Reference">
                      <span className="agent-ref">{loan.reference}</span>
                    </td>
                    <td data-label="Requested" className="t-num col-amount">
                      {formatNaira(loan.requested_amount)}
                    </td>
                    <td data-label="Disbursed" className="t-num t-hide-sm">
                      {loan.approved_amount ? (
                        <span className="col-amount">{formatNaira(loan.approved_amount)}</span>
                      ) : (
                        <span className="tbl-amount-zero">Not yet</span>
                      )}
                    </td>
                    <td data-label="Platform" className="t-hide-sm">
                      {loan.purpose}
                    </td>
                    <td data-label="Date" className="t-hide-sm">
                      {formatDate(loan.requested_at)}
                    </td>
                    <td data-label="Status">
                      <StatusBadge status={loan.status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
