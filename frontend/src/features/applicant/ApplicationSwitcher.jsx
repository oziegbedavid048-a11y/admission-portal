import { useState } from 'react';
import { useToast } from '../../context/ToastContext';
import { useApplication } from './ApplicationContext';

/**
 * Chooses which application the page shows, when the applicant has applied to
 * more than one school. Hidden with a single application.
 */
export default function ApplicationSwitcher() {
  const { application, applicationsList, selectApplication } = useApplication();
  const toast = useToast();
  const [busy, setBusy] = useState('');

  if (!application || applicationsList.length < 2) return null;

  const open = async (reference) => {
    if (reference === application.reference || busy) return;
    setBusy(reference);
    try {
      const data = await selectApplication(reference);
      if (!data) toast.error('That application could not be opened.');
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="gx-segments gx-app-switch" role="group" aria-label="Your applications">
      {applicationsList.map((item) => {
        const label = item.institution || item.courses[0] || item.reference;
        const active = item.reference === application.reference;
        return (
          <button
            key={item.reference}
            type="button"
            className={`gx-segment${active ? ' is-active' : ''}`}
            aria-pressed={active}
            title={`${label} · ${item.reference}`}
            onClick={() => open(item.reference)}
            disabled={Boolean(busy)}
          >
            <span className="gx-app-switch-name">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
