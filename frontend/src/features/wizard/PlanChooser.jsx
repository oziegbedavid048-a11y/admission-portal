import { formatNaira } from '../../lib/format';

/**
 * Pay in full, or "pay small small": ₦100,000 now and the rest in two equal
 * weekly parts. The figures mirror the server's (apps/payments/plans.py); the
 * server's are the ones charged.
 */

export const DEPOSIT_NGN = 100000;

/** [deposit, second, third] for a fee in Naira, or [fee] if too small to split. */
export function instalmentAmounts(totalNgn) {
  const total = Number(totalNgn) || 0;
  if (total <= DEPOSIT_NGN) return [total];
  const each = Math.round(((total - DEPOSIT_NGN) / 2) * 100) / 100;
  return [DEPOSIT_NGN, each, Math.round((total - DEPOSIT_NGN - each) * 100) / 100];
}

export default function PlanChooser({ totalNgn, plan, onChange, name = 'fee-plan' }) {
  const amounts = instalmentAmounts(totalNgn);
  if (amounts.length < 2) return null;
  const [deposit, second, third] = amounts;

  return (
    <fieldset className="pay-methods plan-chooser">
      <legend className="nf-label">How do you want to pay?</legend>
      <label className={`pay-method${plan === 'full' ? ' is-selected' : ''}`}>
        <input type="radio" name={name} value="full" checked={plan === 'full'} onChange={() => onChange('full')} />
        <span className="pay-method-text">
          <strong>Pay in full</strong>
          <small>{formatNaira(totalNgn)} now.</small>
        </span>
      </label>
      <label className={`pay-method${plan === 'instalments' ? ' is-selected' : ''}`}>
        <input
          type="radio"
          name={name}
          value="instalments"
          checked={plan === 'instalments'}
          onChange={() => onChange('instalments')}
        />
        <span className="pay-method-text">
          <strong>Pay small small</strong>
          <small>
            {formatNaira(deposit)} now, {formatNaira(second)} a week later and {formatNaira(third)} a week after.
            Work on your application starts once the first payment is in.
          </small>
        </span>
      </label>
    </fieldset>
  );
}
