import { API_ORIGIN } from '../api/client';

// Formatting helpers shared by the portals. Everything that turns a number or
// a date into something a person reads lives here, so the same amount never
// appears two different ways on two different screens.

const NAIRA = '₦';

export function formatNaira(value) {
  return NAIRA + Number(value || 0).toLocaleString('en-NG', { maximumFractionDigits: 0 });
}

/**
 * An agent's amount in the currency their wallet is kept in: "₦30,000" for
 * Naira, "KSh 2,520" or "KSh 2,520.50" for anything else. Whole amounts show
 * no decimals.
 */
export function formatCurrency(value, currency = 'NGN', symbol = '') {
  const code = (currency || 'NGN').toUpperCase();
  if (code === 'NGN') return formatNaira(value);
  const number = Number(value || 0);
  const whole = Number.isInteger(Math.round(number * 100) / 100) && Math.round(number * 100) % 100 === 0;
  const text = number.toLocaleString('en-US', {
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  });
  return `${symbol || code} ${text}`;
}

export function formatMoney(amount, currency = 'NGN') {
  const number = Number(amount || 0).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${currency} ${number}`;
}

const TUITION_SYMBOLS = { EUR: '€', GBP: '£', USD: '$', CAD: 'C$', AUD: 'A$' };

export function formatTuition(amount, currency) {
  if (!amount) return '';
  const symbol = TUITION_SYMBOLS[currency] || (currency ? `${currency} ` : '');
  return `${symbol}${Number(amount).toLocaleString('en-US')} / year`;
}

const SIGNS = { NGN: '₦', EUR: '€', GBP: '£', USD: '$', CAD: 'C$', AUD: 'A$' };

/** The sign a currency is written with, or its code: "€", "C$", "GMD ". */
export function currencySign(currency, symbol = '') {
  const code = (currency || '').toUpperCase();
  const sign = symbol || SIGNS[code];
  return sign || (code ? `${code} ` : '');
}

/**
 * An application fee in the school's currency: "€120", "C$179", "€150.50".
 * Whole amounts show no decimals.
 */
export function formatFee(amount, currency, symbol = '') {
  const number = Number(amount || 0);
  const whole = Math.round(number * 100) % 100 === 0;
  const text = number.toLocaleString('en-US', {
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  });
  return `${currencySign(currency, symbol)}${text}`;
}

/**
 * A school's tuition summary with its currency on it. Staff sometimes type
 * only a number ("8400"), which read as a bare figure; it is shown as
 * "€8,400". A summary that already names its currency is left as written.
 */
export function tuitionText(summary, currency, symbol = '') {
  const text = String(summary || '').trim();
  if (!text) return 'Varies by course';
  if (/^[\d.,\s]+$/.test(text)) {
    const number = Number(text.replace(/[,\s]/g, ''));
    if (!number) return 'Varies by course';
    return `${currencySign(currency, symbol)}${number.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  }
  const sign = currencySign(currency, symbol).trim();
  const code = (currency || '').toUpperCase();
  const named = (sign && text.includes(sign)) || (code && text.toUpperCase().includes(code));
  if (!named && /\d/.test(text)) {
    // Each bare number gets the sign: "6000 - 7500" becomes "€6,000 - €7,500".
    return text.replace(/\d[\d,]*(\.\d+)?/g, (match) => {
      const number = Number(match.replace(/,/g, ''));
      return `${currencySign(currency, symbol)}${number.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
    });
  }
  // Thousands separators on any large number typed without them: "€6000" reads "€6,000".
  return text.replace(/(?<![\d,.])\d{4,}(?![\d,.])/g, (match) => Number(match).toLocaleString('en-US'));
}

/**
 * A school's tuition deposit, always as an amount.
 *
 * A flat deposit set in the admin is shown as it is ("€1,000"). Otherwise the
 * admin's percentage, or 50% when none is set, is worked out on the tuition:
 * 50% of €5,000 shows "€2,500", and 50% of a range "€4,900 - €11,900" shows
 * "€2,450 - €5,950". The figures come from the school's tuition line, or from
 * its courses' tuition when that line has none. Only a school with no tuition
 * figure anywhere shows "Varies by course", as its tuition does.
 */
export const DEFAULT_DEPOSIT_PERCENT = 50;

export function depositText(school) {
  if (!school) return 'Varies by course';
  const sign = currencySign(school.currency, school.tuition_symbol);
  const amount = Number(school.tuition_deposit_amount || 0);
  if (amount > 0) return formatFee(amount, school.currency, school.tuition_symbol);
  const percent = Number(school.tuition_deposit_percent || 0) || DEFAULT_DEPOSIT_PERCENT;

  let figures = (String(school.tuition_summary || '').match(/\d[\d,]*(\.\d+)?/g) || [])
    .map((match) => Number(match.replace(/,/g, '')))
    .filter((number) => number > 0);
  if (!figures.length) {
    const courses = (school.programs || []).map((course) => Number(course.tuition || 0)).filter((n) => n > 0);
    if (courses.length) {
      const low = Math.min(...courses);
      const high = Math.max(...courses);
      figures = low === high ? [low] : [low, high];
    }
  }
  if (!figures.length) return 'Varies by course';
  return figures
    .map((number) => `${sign}${Math.round((number * percent) / 100).toLocaleString('en-US')}`)
    .join(' - ');
}

export function formatDate(value) {
  if (!value) return 'Not set';
  return new Date(value).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/** A moment as two short lines for a table: "2 Oct 2026" and "14:05". */
export function formatDateTimeParts(value) {
  if (!value) return { date: 'Not set', time: '' };
  const moment = new Date(value);
  return {
    date: moment.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }),
    time: moment.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
  };
}

export function formatLongDate(value) {
  if (!value) return 'Not set';
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

// "3 days ago" reads better than a date in an activity feed, where what
// matters is how recent something is rather than exactly when it happened.
export function timeAgo(value) {
  if (!value) return '';
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return 'Just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
  return formatDate(value);
}

export function fileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function initialsOf(name) {
  const parts = String(name || '').split(' ').filter(Boolean);
  return parts.slice(0, 2).map((p) => p[0].toUpperCase()).join('') || 'GA';
}

export function firstNameOf(name) {
  return String(name || '').split(' ').filter(Boolean)[0] || 'there';
}

export function greetingFor(date = new Date()) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) {
    return {
      text: 'Good morning',
      icon: 'sunrise',
      period: 'morning',
      image: '/assets/weather/morning.jpg',
      label: 'Morning',
    };
  }
  if (hour >= 12 && hour < 17) {
    return {
      text: 'Good afternoon',
      icon: 'sun',
      period: 'afternoon',
      image: '/assets/weather/afternoon.jpg',
      label: 'Afternoon',
    };
  }
  return {
    text: 'Good evening',
    icon: 'moon',
    period: 'night',
    image: '/assets/weather/night.jpg',
    label: 'Evening',
  };
}

// The statuses the API speaks, mapped to the tone and wording the tables show.
export const STATUS_LABELS = {
  admission_granted: ['admitted', 'Admitted'],
  pending: ['pending', 'In review'],
  in_review: ['pending', 'In review'],
  submitted: ['in-progress', 'Submitted'],
  draft: ['na', 'Draft'],
  rejected: ['rejected', 'Rejected'],
  completed: ['completed', 'Verified'],
  in_progress: ['in-progress', 'In progress'],
  approved: ['approved', 'Approved'],
  disbursed: ['disbursed', 'Disbursed'],
  repaid: ['completed', 'Repaid'],
  declined: ['rejected', 'Declined'],
  new: ['na', 'Not started'],
  Paid: ['completed', 'Paid'],
  waived: ['approved', 'Waived'],
  // Pay small small: the deposit is in, the rest of the fee is owed.
  part_paid: ['pending', 'Part paid'],
};

export function statusTone(status) {
  return STATUS_LABELS[status] || ['na', String(status || 'Not set')];
}

/** Where to fetch an uploaded file from. See API_ORIGIN in api/client.js. */
export function resolveMediaUrl(url) {
  if (!url) return '';
  const s = String(url).trim();
  if (!s) return '';
  if (/^(https?:|\/\/|blob:|data:)/i.test(s)) return s;
  return `${API_ORIGIN}${s.startsWith('/') ? s : `/${s}`}`;
}

/** The same file, served as a download rather than shown. */
export function downloadUrl(url) {
  const resolved = resolveMediaUrl(url);
  if (!resolved || /^(blob:|data:)/i.test(resolved)) return resolved;
  return `${resolved}${resolved.includes('?') ? '&' : '?'}download=1`;
}
