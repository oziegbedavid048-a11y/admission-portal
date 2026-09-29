import { API_ORIGIN } from '../api/client';

// Formatting helpers shared by the portals. Everything that turns a number or
// a date into something a person reads lives here, so the same amount never
// appears two different ways on two different screens.

const NAIRA = '₦';

export function formatNaira(value) {
  return NAIRA + Number(value || 0).toLocaleString('en-NG', { maximumFractionDigits: 0 });
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

export function formatDate(value) {
  if (!value) return 'Not set';
  return new Date(value).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
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
