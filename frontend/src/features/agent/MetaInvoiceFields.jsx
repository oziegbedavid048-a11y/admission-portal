import { useEffect, useState } from 'react';
import { partners } from '../../api/endpoints';

/**
 * The Meta ads invoice an approved Ads funding loan pays (agents in Nigeria).
 *
 * Once the desk approves, the agent chooses "Add funds" by bank transfer in
 * Ads Manager for the approved amount, which gives an invoice with an account
 * number, the name "Meta Ads" and a bank (usually OPay). The agent copies
 * those here with their Ads Manager link and presses Pay. The account is
 * checked with Paystack as it is typed, and the server checks it again: only
 * an account in Meta's name is paid, at once, so the invoice cannot expire.
 *
 * `value` is { link, bankCode, accountNumber };
 * `onChange(next)` gets the whole object back.
 */

// The same rule as the server (loan_payouts.is_meta_account_name), which is
// the one that counts: "Meta" or "Facebook" as a whole word anywhere in the name.
const isMetaName = (name) => {
  const words = (name || '').toUpperCase().split(/[^A-Z0-9]+/).filter(Boolean);
  return words.includes('META') || words.includes('FACEBOOK');
};

export default function MetaInvoiceFields({ value, onChange, amount }) {
  const [banks, setBanks] = useState([]);
  const [check, setCheck] = useState({ state: 'idle', name: '' });
  const set = (patch) => onChange({ ...value, ...patch });

  useEffect(() => {
    let cancelled = false;
    partners
      .banks()
      .then(({ data }) => {
        if (cancelled) return;
        const list = data?.banks || [];
        setBanks(list);
        // Meta's invoices are usually at OPay: start there.
        if (!value.bankCode) {
          const opay = list.find((bank) => /opay/i.test(bank.name));
          if (opay) onChange({ ...value, bankCode: opay.code });
        }
      })
      .catch(() => null);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Check the account with Paystack once ten digits and a bank are in. A new
  // account clears the agent's confirmation of the name.
  useEffect(() => {
    if (value.confirmedName) onChange({ ...value, confirmedName: '' });
    if (!value.bankCode || !/^\d{10}$/.test(value.accountNumber || '')) {
      setCheck({ state: 'idle', name: '' });
      return undefined;
    }
    let cancelled = false;
    setCheck({ state: 'checking', name: '' });
    partners
      .resolveBank(value.bankCode, value.accountNumber)
      .then(({ data }) => {
        if (!cancelled) setCheck({ state: isMetaName(data.account_name) ? 'meta' : 'other', name: data.account_name });
      })
      .catch(() => {
        if (!cancelled) setCheck({ state: 'unknown', name: '' });
      });
    return () => {
      cancelled = true;
    };
  }, [value.bankCode, value.accountNumber]);

  return (
    <div className="meta-invoice">
      <p className="meta-invoice-intro">
        In Ads Manager, choose <strong>Add funds</strong> by bank transfer for exactly <strong>{amount}</strong>, then
        copy the invoice details below and press Pay. We pay Meta straight away.
      </p>

      <div className="agent-form-group">
        <label className="agent-form-label" htmlFor="meta-link">
          Ads Manager link *
        </label>
        <input
          id="meta-link"
          className="agent-form-control"
          inputMode="url"
          placeholder="https://adsmanager.facebook.com/...act=..."
          value={value.link || ''}
          onChange={(event) => set({ link: event.target.value.trim() })}
        />
      </div>

      <div className="meta-invoice-grid">
        <div className="agent-form-group">
          <label className="agent-form-label" htmlFor="meta-bank">
            Bank on the invoice *
          </label>
          <select
            id="meta-bank"
            className="agent-form-select"
            value={value.bankCode || ''}
            onChange={(event) => set({ bankCode: event.target.value })}
          >
            <option value="" />
            {banks.map((bank) => (
              <option key={bank.code} value={bank.code}>
                {bank.name}
              </option>
            ))}
          </select>
        </div>
        <div className="agent-form-group">
          <label className="agent-form-label" htmlFor="meta-account">
            Account number on the invoice *
          </label>
          <input
            id="meta-account"
            className="agent-form-control"
            inputMode="numeric"
            maxLength={10}
            value={value.accountNumber || ''}
            onChange={(event) => set({ accountNumber: event.target.value.replace(/\D/g, '').slice(0, 10) })}
          />
        </div>
      </div>

      {check.state === 'meta' || check.state === 'other' ? (
        <div className={`meta-invoice-name is-${check.state}`} role="status">
          <span>Account name</span>
          <strong>{check.name}</strong>
        </div>
      ) : null}

      {check.state === 'meta' ? (
        <label className="meta-invoice-confirm">
          <input
            type="checkbox"
            checked={value.confirmedName === check.name}
            onChange={(event) => set({ confirmedName: event.target.checked ? check.name : '' })}
          />
          <span>This is the same account name shown on my Meta invoice.</span>
        </label>
      ) : check.state !== 'idle' ? (
        <p className={`meta-invoice-check is-${check.state}`} role="status">
          {check.state === 'checking'
            ? 'Checking the account with Paystack…'
            : check.state === 'other'
              ? 'This name does not have Meta in it. Use the account on your Meta invoice.'
              : 'The account could not be checked right now. Check the number and bank, then try again.'}
        </p>
      ) : null}

    </div>
  );
}

/** What is missing before the invoice can be paid, or ''. */
export function metaInvoiceProblem(value) {
  if (!/facebook\.com/i.test(value.link || '') || !/[?&]act=\d+/.test(value.link || '')) {
    return 'Paste your Ads Manager link (it contains act= and your ad account number).';
  }
  if (!value.bankCode) return 'Choose the bank on your Meta invoice.';
  if (!/^\d{10}$/.test(value.accountNumber || '')) return 'Enter the 10-digit account number on your Meta invoice.';
  if (!value.confirmedName) return 'Confirm the account name matches the name on your Meta invoice.';
  return '';
}
