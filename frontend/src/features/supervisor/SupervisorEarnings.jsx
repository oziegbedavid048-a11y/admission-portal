import { useEffect, useMemo, useState } from 'react';
import Loading from '../../components/ui/Loading';
import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';
import { formatDate, formatNaira } from '../../lib/format';
import { errorMessage } from '../../api/client';
import { supervisors } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import useLiveRefresh from '../../hooks/useLiveRefresh';
import { useSupervisor } from './SupervisorContext';
import SupervisorStatusBadge from './SupervisorStatusBadge';

// Mirrors SUPERVISOR_BONUS_NGN on the server; only ever shown, never charged.
const BONUS = 2000;
// Used only for the moment before the profile loads and supplies the real one.
const FALLBACK_MINIMUM = 100000;

/** Every bonus, the payouts requested against them, and the request button. */
export default function SupervisorEarnings() {
  const { profile, setProfile, reload } = useSupervisor();
  const [bonuses, setBonuses] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = async (quiet = false) => {
    try {
      const [bonusResponse, payoutResponse] = await Promise.all([
        supervisors.bonuses(),
        supervisors.withdrawals(),
      ]);
      setBonuses(bonusResponse.data);
      setPayouts(payoutResponse.data);
    } catch {
      if (!quiet) toast.error('Could not load your earnings.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A bonus lands when a student's application fee is paid, and the desk marks
  // payouts sent. Neither involves the Sales Manager, so the page refetches
  // rather than waiting to be reloaded.
  useLiveRefresh(() => {
    load(true);
    reload().catch(() => {});
  });

  const minimum = Number(profile?.minimum_withdrawal) || FALLBACK_MINIMUM;
  const available = Number(profile?.available_balance) || 0;
  const canWithdraw = profile?.can_withdraw ?? available >= minimum;
  const shortfall = Math.max(0, minimum - available);
  const hasPayoutAccount = Boolean(profile?.bank_name && profile?.account_number);
  const belowMinimum = Number(amount) > 0 && Number(amount) < minimum;

  const pending = useMemo(
    () => payouts.filter((item) => item.status === 'pending').length,
    [payouts],
  );

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
      const { data } = await supervisors.withdraw(requested);
      setProfile(data.profile);
      setPayouts((current) => [data.withdrawal, ...current]);
      setWithdrawOpen(false);
      setAmount('');
      toast.success(
        `${formatNaira(data.withdrawal.amount)} requested. The desk will send it to your bank.`,
      );
    } catch (error) {
      toast.error(errorMessage(error, 'Could not start that withdrawal.'));
    } finally {
      setBusy(false);
    }
  };

  if (loading || !profile) return <Loading label="Loading your earnings" />;

  return (
    <div className="agent-stack">

      <section className="agent-card balance-card">
        <div className="balance-top">
          <div className="balance-lead">
            <span className="agent-icon accent" aria-hidden="true">
              <Icon name="trend" size={22} />
            </span>
            <span className="balance-lead-text">
              <span className="balance-label">Available to withdraw</span>
              <span className="balance-amount">{formatNaira(available)}</span>
            </span>
          </div>

          <div className="balance-actions">
            <button
              type="button"
              className="agent-btn agent-btn-primary"
              onClick={() => setWithdrawOpen(true)}
              disabled={!canWithdraw || !hasPayoutAccount}
              title={
                !hasPayoutAccount
                  ? 'Add your payout account on your profile first.'
                  : canWithdraw
                    ? undefined
                    : `You need ${formatNaira(minimum)} available to withdraw.`
              }
            >
              <Icon name="download" size={18} />
              Withdraw
            </button>
          </div>
        </div>

        <dl className="balance-split">
          <div className="fig">
            <dt className="fig-label">Bonus earned</dt>
            <dd className="fig-value">{formatNaira(profile.bonus_total)}</dd>
          </div>
          <div className="fig">
            <dt className="fig-label">Students registered</dt>
            <dd className="fig-value">{bonuses.length}</dd>
          </div>
          <div className="fig">
            <dt className="fig-label">Withdrawn</dt>
            <dd className="fig-value">{formatNaira(profile.total_withdrawn)}</dd>
          </div>
        </dl>

        {!hasPayoutAccount ? (
          <p className="balance-hint">
            Add your bank details on your profile before withdrawing. That is where
            the money is sent.
          </p>
        ) : !canWithdraw ? (
          <p className="balance-hint">
            Withdrawals start at {formatNaira(minimum)}. You are {formatNaira(shortfall)}{' '}
            short, which is {Math.ceil(shortfall / BONUS)} more registration
            {Math.ceil(shortfall / BONUS) === 1 ? '' : 's'}.
          </p>
        ) : pending > 0 ? (
          <p className="balance-hint">
            You have {pending} payout{pending === 1 ? '' : 's'} being processed. That
            amount has already left your available balance.
          </p>
        ) : null}
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Withdrawals</h2>
          <span className="agent-card-note">Minimum {formatNaira(minimum)}</span>
        </div>

        <div className="agent-table-wrap">
          <table className="agent-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th className="t-num">Amount</th>
                <th>Status</th>
                <th className="t-hide-sm">Requested</th>
                <th className="t-hide-sm">Paid</th>
              </tr>
            </thead>
            <tbody>
              {payouts.length === 0 ? (
                <tr className="row-empty">
                  <td colSpan={5}>
                    <div className="agent-empty-state">
                      <p>No withdrawals yet</p>
                      <small>
                        Once your balance reaches {formatNaira(minimum)} you can request
                        a payout here.
                      </small>
                    </div>
                  </td>
                </tr>
              ) : (
                payouts.map((payout) => (
                  <tr key={payout.id}>
                    <td data-label="Reference">
                      <span className="agent-ref">{payout.reference}</span>
                    </td>
                    <td data-label="Amount" className="t-num col-amount">
                      {formatNaira(payout.amount)}
                    </td>
                    <td data-label="Status">
                      <SupervisorStatusBadge status={payout.status} />
                    </td>
                    <td data-label="Requested" className="t-hide-sm">
                      {formatDate(payout.created_at)}
                    </td>
                    <td data-label="Paid" className="t-hide-sm">
                      {payout.paid_at ? formatDate(payout.paid_at) : 'Not yet'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="agent-card">
        <div className="agent-card-header">
          <h2 className="agent-card-title">Bonus history</h2>
          <span className="agent-card-note">{formatNaira(BONUS)} per paid application</span>
        </div>

        <div className="agent-table-wrap">
          <table className="agent-table">
            <thead>
              <tr>
                <th>Student</th>
                <th className="t-hide-sm">Agent</th>
                <th className="t-hide-sm">Institution</th>
                <th className="t-num">Bonus</th>
                <th>Earned</th>
              </tr>
            </thead>
            <tbody>
              {bonuses.length === 0 ? (
                <tr className="row-empty">
                  <td colSpan={5}>
                    <div className="agent-empty-state">
                      <p>No bonuses yet</p>
                      <small>
                        You earn {formatNaira(BONUS)} each time a student one of
                        your agents registered pays their application fee.
                      </small>
                    </div>
                  </td>
                </tr>
              ) : (
                bonuses.map((bonus) => (
                  <tr key={bonus.id}>
                    <td data-label="Student">
                      <span className="cell">
                        <span className="col-name">{bonus.student}</span>
                        <span className="col-sub">{bonus.reference}</span>
                      </span>
                    </td>
                    <td data-label="Agent" className="t-hide-sm">
                      {bonus.agent || 'Agent removed'}
                    </td>
                    <td data-label="Institution" className="t-hide-sm">
                      <span className="col-inst">{bonus.institution}</span>
                    </td>
                    <td data-label="Bonus" className="t-num col-amount">
                      {formatNaira(bonus.amount)}
                    </td>
                    <td data-label="Earned">{formatDate(bonus.earned_at)}</td>
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
        labelledBy="sv-withdraw-title"
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
              Request withdrawal
            </button>
          </>
        }
      >
        <div className="agent-form-group">
          <label className="agent-form-label" htmlFor="sv-wd-amount">
            Amount (₦)
          </label>
          <input
            id="sv-wd-amount"
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
          <div className="payout-calc-row">
            <span>Requested</span>
            <strong>{formatNaira(Number(amount) || 0)}</strong>
          </div>
          <div className="payout-calc-row total">
            <span>You receive</span>
            <strong>{formatNaira(Number(amount) || 0)}</strong>
          </div>
        </div>

        <p className="agent-card-note">
          Paid to {profile.bank_name} · {profile.account_number} ({profile.account_name}).
        </p>
      </Modal>
    </div>
  );
}
