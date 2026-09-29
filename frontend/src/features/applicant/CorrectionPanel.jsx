import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../../lib/icons';
import { errorMessage } from '../../api/client';
import { applications } from '../../api/endpoints';
import { useToast } from '../../context/ToastContext';
import { useApplication } from './ApplicationContext';

const FIELDS = [
  { value: 'Legal name', hint: 'Must match your passport exactly' },
  { value: 'Date of birth', hint: 'As printed on your passport' },
  { value: 'Institution', hint: 'Locked once your fee is paid' },
  { value: 'Course', hint: 'Changing this may restart the review' },
  { value: 'Something else', hint: 'Describe it below' },
];

export default function CorrectionPanel() {
  const { application, reload } = useApplication();
  const [field, setField] = useState('Legal name');
  const [corrected, setCorrected] = useState('');
  const [reason, setReason] = useState('');
  const [evidence, setEvidence] = useState(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  // Saves the applicant retyping what the record already says.
  const currentValue = useMemo(() => {
    const known = {
      'Legal name': application.full_name,
      Institution: application.institution?.name,
      Course: application.programs.map((program) => program.name).join(', '),
    };
    return known[field] || '';
  }, [field, application]);

  const submit = async (event) => {
    event.preventDefault();
    if (!corrected.trim()) {
      toast.warning('Tell us what it should say.');
      return;
    }
    if (!reason.trim()) {
      toast.warning('Tell us why it needs changing.');
      return;
    }

    setBusy(true);
    try {
      const { data } = await applications.requestCorrection(application.reference, {
        field,
        current_value: currentValue,
        corrected_value: corrected.trim(),
        reason: reason.trim(),
        evidence,
      });
      await reload();
      toast.success(`Logged as ${data.ticket}. An advisor will verify it.`);
      navigate('/portal/details');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not log that correction.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="portal-stack">
      <section className="app-banner">
        <span className="app-greet-icon" aria-hidden="true">
          <Icon name="pencil" size={22} animate />
        </span>
        <div className="app-banner-text">
          <h2>Request a correction</h2>
          <p>Tell us what is wrong and we will verify it against your documents.</p>
        </div>
      </section>

      <form onSubmit={submit}>
        <section className="card">
          <div className="card-head">
            <h2>What needs correcting</h2>
          </div>
          <div className="choice-list">
            {FIELDS.map((option) => (
              <label className="choice" key={option.value}>
                <input
                  type="radio"
                  name="correction-field"
                  value={option.value}
                  checked={field === option.value}
                  onChange={() => setField(option.value)}
                />
                <span className="choice-text">
                  <span className="choice-title">{option.value}</span>
                  <span className="choice-sub">{option.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>The correct value</h2>
          </div>
          <div className="field-grid">
            <div className="field">
              <label htmlFor="correction-current">What it says now</label>
              <input type="text" id="correction-current" value={currentValue} readOnly />
            </div>
            <div className="field">
              <label htmlFor="correction-correct">What it should say</label>
              <input
                type="text"
                id="correction-correct"
                value={corrected}
                onChange={(event) => setCorrected(event.target.value)}
              />
            </div>
          </div>

          <div className="field" style={{ marginTop: 20 }}>
            <label htmlFor="correction-reason">Why it needs changing</label>
            <textarea
              id="correction-reason"
              rows={4}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>

          <div className="field" style={{ marginTop: 20 }}>
            <label htmlFor="correction-proof">Supporting document (optional)</label>
            <input
              type="file"
              id="correction-proof"
              accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif"
              onChange={(event) => setEvidence(event.target.files?.[0] || null)}
            />
          </div>
        </section>

        <div className="form-actions">
          <button
            type="button"
            className="g-btn g-btn-quiet"
            onClick={() => navigate('/portal/details')}
          >
            Cancel
          </button>
          <button type="submit" className="g-btn g-btn-primary" disabled={busy}>
            {busy ? 'Sending' : 'Submit request'}
          </button>
        </div>
      </form>

      {application.corrections?.length ? (
        <section className="card">
          <div className="card-head">
            <h2>Open requests</h2>
          </div>
          <div className="docs">
            {application.corrections.map((item) => (
              <div className="doc" key={item.id}>
                <div className="doc-text">
                  <h3>{item.field}</h3>
                  <div className="doc-meta">
                    {item.ticket} · {item.corrected_value}
                  </div>
                </div>
                <div className="doc-side">
                  <span className="pill pill-wait">{item.status}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
