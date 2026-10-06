import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { catalog } from '../../api/endpoints';

/**
 * A live converter for the currencies an agent actually deals in: they earn in
 * Naira and quote tuition in the destination's currency, and the two move.
 *
 * Rates come from our own endpoint rather than straight from a provider, so the
 * key stays server-side and the response is cached. Conversion happens locally
 * against the rate table, so typing is instant. The table refreshes on a timer
 * and whenever the tab comes back to the front.
 *
 * Deliberately plain: two rows, "Amount" and "Converted", each with its
 * currency beside it, and the rate in one line underneath. No icons.
 */

const REFRESH_MS = 5 * 60 * 1000;
const BASE = 'NGN';

const NAMES = {
  NGN: 'Nigerian Naira',
  USD: 'US Dollar',
  GBP: 'Pound Sterling',
  EUR: 'Euro',
  CAD: 'Canadian Dollar',
  AUD: 'Australian Dollar',
  GHS: 'Ghanaian Cedi',
  ZAR: 'South African Rand',
  KES: 'Kenyan Shilling',
  INR: 'Indian Rupee',
  CNY: 'Chinese Yuan',
  AED: 'UAE Dirham',
};

const number = (value, digits = 2) =>
  new Intl.NumberFormat('en-US', { minimumFractionDigits: 0, maximumFractionDigits: digits }).format(value);

// Starts on Naira to the agent's own currency (US dollars for agents in Nigeria).
export default function CurrencyConverter({ currency = 'NGN' }) {
  const [data, setData] = useState(null);
  const [amount, setAmount] = useState('200000');
  const [from, setFrom] = useState('NGN');
  const [to, setTo] = useState(currency && currency !== 'NGN' ? currency : 'USD');
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const { data: payload } = await catalog.exchangeRates(BASE, false);
      if (mounted.current) setData(payload);
    } catch {
      // Keep whatever rates we already have rather than blanking the panel.
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    load();
    const timer = window.setInterval(load, REFRESH_MS);
    const onVisible = () => {
      if (document.visibilityState === 'visible') load();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load]);

  const rates = data?.rates || {};

  const currencies = useMemo(() => {
    const all = Object.keys(rates).sort();
    if (!all.includes(BASE)) all.unshift(BASE);
    return all;
  }, [rates]);

  // Rates are quoted against one base, so crossing two currencies is the ratio
  // of their rates rather than a second lookup.
  const rate = useMemo(() => {
    if (from === to) return 1;
    const fromRate = from === BASE ? 1 : rates[from];
    const toRate = to === BASE ? 1 : rates[to];
    if (!fromRate || !toRate) return null;
    return toRate / fromRate;
  }, [rates, from, to]);

  const numericAmount = Number(String(amount).replace(/,/g, '')) || 0;
  const converted = rate === null ? null : numericAmount * rate;

  const options = currencies.map((code) => (
    <option key={code} value={code} title={NAMES[code] || code}>
      {code}
    </option>
  ));

  return (
    <section className="agent-card fx2">
      <div className="agent-card-header">
        <h2 className="agent-card-title">Currency converter</h2>
        <button
          type="button"
          className="fx2-swap"
          onClick={() => {
            setFrom(to);
            setTo(from);
          }}
        >
          Swap
        </button>
      </div>

      <div className="fx2-rows">
        <div className="fx2-row">
          <label className="fx2-label" htmlFor="fx-amount">
            Amount
          </label>
          <div className="fx2-field">
            <input
              id="fx-amount"
              className="fx2-input"
              inputMode="decimal"
              autoComplete="off"
              value={amount}
              onChange={(event) => setAmount(event.target.value.replace(/[^\d.]/g, ''))}
            />
            <select
              className="fx2-select"
              aria-label="Convert from"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
            >
              {options}
            </select>
          </div>
        </div>

        <div className="fx2-row">
          <span className="fx2-label" id="fx-result-label">
            Converted
          </span>
          <div className="fx2-field fx2-field-result">
            <output className="fx2-result" aria-labelledby="fx-result-label" aria-live="polite">
              {converted === null ? 'Unavailable' : number(converted, converted < 1 ? 6 : 2)}
            </output>
            <select
              className="fx2-select"
              aria-label="Convert to"
              value={to}
              onChange={(event) => setTo(event.target.value)}
            >
              {options}
            </select>
          </div>
        </div>
      </div>

      <p className="fx2-rate">
        {rate === null
          ? 'No rate available for that pair.'
          : `1 ${from} = ${number(rate, rate < 1 ? 6 : 4)} ${to}`}
      </p>
    </section>
  );
}
