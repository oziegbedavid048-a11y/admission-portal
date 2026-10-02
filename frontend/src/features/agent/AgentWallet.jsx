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
import { LedgerDate, LedgerStatus, ShowMore, useShowMore, withdrawalStatus } from './Ledger';

const FALLBACK_MINIMUM = 100000;

// The withdrawals list may come back paginated; the table wants the rows.
const listOf = (data) => (Array.isArray(data) ? data : data?.results || []);

export default function AgentWallet() {
  const { profile, wallet, setWallet } = useAgent();
  const [withdrawals, setWithdrawals] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([partners.withdrawals(), partners.walletHistory()])
      .then(([payouts, moves]) => {
        if (cancelled) return;
        setWithdrawals(payouts.status === 'fulfilled' ? listOf(payouts.value.data) : []);
        setHistory(moves.status === 'fulfilled' ? listOf(moves.value.data) : []);
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
      const [{ data: freshWallet }, { data: payouts }, { data: moves }] = await Promise.all([
        partners.wallet(),
        partners.withdrawals(),
        partners.walletHistory(),
      ]);
      setWallet(freshWallet);
      setWithdrawals(listOf(payouts));
      setHistory(listOf(moves));
    } catch {
      // A missed tick is harmless; the next one will pick it up.
    }
  };
  useLiveRefresh(refreshWallet, { intervalMs: 6000 });
  useOnWalletChange(refreshWallet);

  const historyRows = useShowMore(history);
  const withdrawalRows = useShowMore(withdrawals);

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
      partners
        .walletHistory()
        .then(({ data: moves }) => setHistory(listOf(moves)))
        .catch(() => {});
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
          <h2 className="agent-card-title">Earning history</h2>
          <span className="agent-card-note">{formatNaira(wallet.total_earned)} earned</span>
        </div>
        <div className="ledger-scroll" role="region" aria-label="Earning history" tabIndex={0}>
          {history.length === 0 ? (
            <div className="ledger-empty">
              <p>No earnings yet</p>
              <small>Commissions, repayments and withdrawals will show here.</small>
            </div>
          ) : (
            <table className="ledger-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Details</th>
                  <th scope="col" className="t-num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {historyRows.visible.map((row) => {
                  const incoming = row.direction === 'in';
                  const [, statusLabel] = row.status ? withdrawalStatus(row.status) : [];
                  const sub = [row.detail, row.reference, statusLabel].filter(Boolean).join(' · ');
                  return (
                    <tr key={row.id}>
                      <td>
                        <LedgerDate value={row.at} />
                      </td>
                      <td>
                        <span className="ledger-main">{row.title}</span>
                        {sub ? <span className="ledger-sub">{sub}</span> : null}
                      </td>
                      <td className="t-num">
                        <span className={`ledger-amount${incoming ? ' is-in' : ''}`}>
                          {incoming ? '+' : '\u2212'}
                          {formatNaira(row.amount)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <ShowMore list={historyRows} />
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Withdrawals</h2>
          <span className="agent-card-note">{formatNaira(wallet.total_withdrawn)} withdrawn</span>
        </div>
        <div className="ledger-scroll" role="region" aria-label="Withdrawals" tabIndex={0}>
          {withdrawals.length === 0 ? (
            <div className="ledger-empty">
              <p>No withdrawals yet</p>
              <small>Your payouts will show here.</small>
            </div>
          ) : (
            <table className="ledger-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Reference</th>
                  <th scope="col" className="t-num">Amount</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {withdrawalRows.visible.map((item) => {
                  const [tone, label] = withdrawalStatus(item.status);
                  const deducted = Number(item.net_amount) !== Number(item.amount_requested);
                  return (
                    <tr key={item.id}>
                      <td>
                        <LedgerDate value={item.created_at} />
                      </td>
                      <td>
                        <span className="ledger-ref">{item.reference}</span>
                      </td>
                      <td className="t-num">
                        <span className="ledger-amount">{formatNaira(item.amount_requested)}</span>
                        {deducted ? (
                          <span className="ledger-sub">Paid {formatNaira(item.net_amount)}</span>
                        ) : null}
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
        <ShowMore list={withdrawalRows} />
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
