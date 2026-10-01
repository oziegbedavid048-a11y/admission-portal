import { useEffect, useState } from 'react';
import Modal from '../../components/ui/Modal';
import Loading from '../../components/ui/Loading';
import Icon from '../../lib/icons';
import { formatNaira } from '../../lib/format';
import { errorMessage } from '../../api/client';
import { partners } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { useAgent, useOnWalletChange } from './AgentContext';
import StatusBadge from './StatusBadge';

const FALLBACK_MINIMUM = 100000;

export default function AgentWallet() {
  const { profile, wallet, setWallet } = useAgent();
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    partners
      .withdrawals()
      .then(({ data }) => {
        if (!cancelled) setWithdrawals(data);
      })
      .catch(() => {
        if (!cancelled) setWithdrawals([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The desk approves payouts and disburses loans from the admin, so the wallet
  // refetches on a timer and whenever the tab comes back to the front.
  const refreshWallet = async () => {
    try {
      const [{ data: freshWallet }, { data: history }] = await Promise.all([
        partners.wallet(),
        partners.withdrawals(),
      ]);
      setWallet(freshWallet);
      setWithdrawals(history);
    } catch {
      // A missed tick is harmless; the next one will pick it up.
    }
  };
  useLiveRefresh(refreshWallet, { intervalMs: 6000 });
  useOnWalletChange(refreshWallet);

  const minimum = Number(wallet?.minimum_withdrawal) || FALLBACK_MINIMUM;
  const available = Number(wallet?.available_balance) || 0;
  const [releasing, setReleasing] = useState(false);

  const releaseSavings = async () => {
    const amount = Number(wallet?.saved_balance) || 0;
    if (!amount) return;
    setReleasing(true);
    try {
      const { data } = await partners.releaseFromSavings(amount);
      setWallet(data);
      toast.success(`${formatNaira(amount)} is available to withdraw again.`);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not release that amount.'));
    } finally {
      setReleasing(false);
    }
  };
  const canWithdraw = wallet?.can_withdraw ?? available >= minimum;

  // Nothing is deducted from a withdrawal: the agent receives what they ask for.
  const requestedAmount = Number(amount) || 0;

  const belowMinimum = Number(amount) > 0 && Number(amount) < minimum;

  const withdraw = async () => {
    const requested = Number(amount);
    if (!requested || requested <= 0) {
      toast.warning('Enter an amount.');
      return;
    }
    if (requested < minimum) {
      toast.warning(`The smallest withdrawal is ${formatNaira(minimum)}.`);
      return;
    }
    if (requested > available) {
      toast.error('That is more than your available balance.');
      return;
    }

    setBusy(true);
    try {
      const { data } = await partners.withdraw(requested);
      setWallet(data.wallet);
      setWithdrawals((current) => [data.withdrawal, ...current]);
      setWithdrawOpen(false);
      setAmount('');
      toast.success(`${formatNaira(data.withdrawal.net_amount)} on its way.`);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not start that withdrawal.'));
    } finally {
      setBusy(false);
    }
  };


  if (loading || !wallet) return <Loading label="Loading your wallet" />;

  return (
    <div className="agent-stack">

      <section className="agent-card balance-card">
        <div className="balance-top">
          <div className="balance-lead">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="wallet" size={22} animate />
            </span>
            <span className="balance-lead-text">
              <span className="balance-label">Available to withdraw</span>
              <span className="balance-amount">{formatNaira(wallet.available_balance)}</span>
            </span>
          </div>
          <div className="balance-actions">
            <button
              type="button"
              className="agent-btn agent-btn-primary"
              onClick={() => setWithdrawOpen(true)}
              disabled={!canWithdraw}
              title={
                canWithdraw
                  ? undefined
                  : `You need ${formatNaira(minimum)} available to withdraw.`
              }
            >
              <Icon name="payout" size={18} />
              Withdraw
            </button>
          </div>
        </div>

        <dl className="balance-split">
          <div className="fig">
            <dt className="fig-label">Loan owed</dt>
            <dd className="fig-value neg">{formatNaira(wallet.loan_balance)}</dd>
          </div>
          <div className="fig">
            <dt className="fig-label">Withdrawn</dt>
            <dd className="fig-value">{formatNaira(wallet.total_withdrawn)}</dd>
          </div>
          {Number(wallet.saved_balance) > 0 ? (
            <div className="fig">
              <dt className="fig-label">Set aside</dt>
              <dd className="fig-value">
                {formatNaira(wallet.saved_balance)}
                {/* Savings is subtracted from what is withdrawable, so without a
                    way back out this money would be stranded for good. */}
                <button
                  type="button"
                  className="fig-release"
                  onClick={releaseSavings}
                  disabled={releasing}
                >
                  {releasing ? 'Releasing' : 'Release'}
                </button>
              </dd>
            </div>
          ) : null}
        </dl>
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="trend" size={18} />
            </span>
            Earnings
          </h2>
          <span className="agent-card-note">{formatNaira(wallet.total_earned)} lifetime</span>
        </div>
        <dl className="rate-list">
          <div className="rate-row">
            <dt>
              Registration fees
              <small>Paid the moment a student&rsquo;s application fee clears</small>
            </dt>
            <dd>{formatNaira(wallet.registration_commission_total)}</dd>
          </div>
          <div className="rate-row">
            <dt>
              Visa fees
              <small>Paid once the admissions desk verifies the visa</small>
            </dt>
            <dd>{formatNaira(wallet.visa_commission_total)}</dd>
          </div>
        </dl>
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="payout" size={18} />
            </span>
            Withdrawals
          </h2>
        </div>
        <div className="agent-table-wrap">
          <table className="agent-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th className="t-num">Requested</th>
                <th className="t-num">Paid out</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {withdrawals.length === 0 ? (
                <tr className="row-empty">
                  <td colSpan={4}>
                    <div className="agent-empty-state">
                      <p>No withdrawals yet</p>
                      <small>Your payouts will show up here.</small>
                    </div>
                  </td>
                </tr>
              ) : (
                withdrawals.map((item) => (
                  <tr key={item.id}>
                    <td data-label="Reference">
                      <span className="agent-ref">{item.reference}</span>
                    </td>
                    <td data-label="Requested" className="t-num col-amount">
                      {formatNaira(item.amount_requested)}
                    </td>
                    <td data-label="Paid out" className="t-num col-amount">
                      {formatNaira(item.net_amount)}
                    </td>
                    <td data-label="Status">
                      <StatusBadge status={item.status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Modal
        open={withdrawOpen}
        onClose={() => setWithdrawOpen(false)}
        variant="agent"
        title="Withdraw"
        labelledBy="withdraw-title"
        footer={
          <>
            <button
              type="button"
              className="agent-btn agent-btn-secondary"
              onClick={() => setWithdrawOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="agent-btn agent-btn-primary"
              onClick={withdraw}
              disabled={busy || belowMinimum || !Number(amount)}
            >
              {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
              Withdraw
            </button>
          </>
        }
      >
        <div className="agent-form-group">
          <label className="agent-form-label" htmlFor="wd-amount">
            Amount (₦)
          </label>
          <input
            id="wd-amount"
            type="number"
            className="agent-form-control"
            min={minimum}
            max={available}
            step="1000"
            inputMode="numeric"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
          <span className="form-helper">
            Minimum {formatNaira(minimum)} · available {formatNaira(available)}
          </span>
          {belowMinimum ? (
            <span className="field-error">
              The smallest withdrawal is {formatNaira(minimum)}.
            </span>
          ) : null}
        </div>

        <div className="payout-calc-box">
          <div className="payout-calc-row total">
            <span>You receive</span>
            <strong>{formatNaira(requestedAmount)}</strong>
          </div>
        </div>

        <p className="agent-card-note">
          Paid to {profile?.bank_name} · {profile?.account_number} ({profile?.account_name}).
        </p>
      </Modal>
    </div>
  );
}
