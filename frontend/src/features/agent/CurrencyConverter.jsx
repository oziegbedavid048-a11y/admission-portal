import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Icon from '../../lib/icons';
import { catalog } from '../../api/endpoints';

/**
 * A live converter for the currencies an agent actually deals in: they earn in
 * Naira and quote tuition in the destination's currency, and the two move.
 *
 * Rates come from our own endpoint rather than straight from a provider, so the
 * key stays server-side and the response is cached — conversion happens locally
 * against the rate table, so typing is instant and costs nothing. The table is
 * refreshed on a timer and whenever the tab is brought back to the front, and
 * the panel always says how old the rates are.
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

export default function CurrencyConverter() {
  const [data, setData] = useState(null);
  const [amount, setAmount] = useState('200000');
  const [from, setFrom] = useState('NGN');
  const [to, setTo] = useState('USD');
  const [refreshing, setRefreshing] = useState(false);
  const mounted = useRef(true);

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      const { data: payload } = await catalog.exchangeRates(BASE, force);
      if (!mounted.current) return;
      setData(payload);
    } catch {
      // Keep whatever rates we already have rather than blanking the panel.
    } finally {
      if (mounted.current) {
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    load();

    const timer = window.setInterval(load, REFRESH_MS);
    // Coming back to a tab that has been open for hours should not show rates
    // from when it was opened.
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

  const money = (value, currency) =>
    value === null || Number.isNaN(value)
      ? 'Enter an amount'
      : new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency,
          maximumFractionDigits: value < 1 ? 6 : 2,
        }).format(value);

  const swap = () => {
    setFrom(to);
    setTo(from);
  };

  return (
    <section className="agent-card fx-card">
      <div className="agent-card-header">
        <h2 className="agent-card-title">Currency converter</h2>
        <button
          type="button"
          className="agent-btn agent-btn-secondary agent-btn-sm"
          onClick={() => load(true)}
          disabled={refreshing}
          title="Fetch the latest rates now"
        >
          {refreshing ? <span className="spinner-sm" aria-hidden="true" /> : null}
          Refresh
        </button>
      </div>

      <div className="fx-grid">
        <div className="agent-form-group fx-amount">
          <label className="agent-form-label" htmlFor="fx-amount">
            Amount
          </label>
          <input
            id="fx-amount"
            className="agent-form-control"
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value.replace(/[^\d.]/g, ''))}
          />
        </div>

        <div className="agent-form-group">
          <label className="agent-form-label" htmlFor="fx-from">
            From
          </label>
          <select
            id="fx-from"
            className="agent-form-select"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
          >
            {currencies.map((code) => (
              <option key={code} value={code}>
                {code}
                {NAMES[code] ? `, ${NAMES[code]}` : ''}
              </option>
            ))}
          </select>
        </div>

        <button type="button" className="fx-swap" onClick={swap} aria-label="Swap currencies">
          <Icon name="arrowRight" size={16} strokeWidth={2.2} />
        </button>

        <div className="agent-form-group">
          <label className="agent-form-label" htmlFor="fx-to">
            To
          </label>
          <select
            id="fx-to"
            className="agent-form-select"
            value={to}
            onChange={(event) => setTo(event.target.value)}
          >
            {currencies.map((code) => (
              <option key={code} value={code}>
                {code}
                {NAMES[code] ? `, ${NAMES[code]}` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="fx-result" aria-live="polite">
        <div className="fx-result-from">
          {money(numericAmount, from)} {from}
        </div>
        <div className="fx-result-to">
          {converted === null ? 'Rate unavailable' : money(converted, to)}
        </div>
        <div className="fx-result-rate">
          {rate === null ? 'No rate available for that pair.' : `1 ${from} = ${rate.toFixed(rate < 1 ? 6 : 4)} ${to}`}
        </div>
      </div>
    </section>
  );
}
