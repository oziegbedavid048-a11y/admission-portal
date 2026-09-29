import { useCallback, useEffect, useState } from 'react';
import { support } from '../../api/endpoints';
import { errorMessage, fieldErrors } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import Icon from '../../lib/icons';
import { compressImageFile } from '../../lib/compress';
import { formatDate } from '../../lib/format';
import { isLiveChatConfigured, openLiveChat } from '../../lib/liveChat';

/**
 * Support, shared by every portal.
 *
 * Two ways to reach a person: live chat, when a chat provider is configured,
 * and a message form that goes straight to the support inbox. The form replaces
 * a mailto link, which dropped people into whatever mail app their device had,
 * or none. Replies come back to the email address on the account.
 */

const TOPICS = [
  { value: 'application', label: 'My application' },
  { value: 'payment', label: 'Payment' },
  { value: 'documents', label: 'Documents and letters' },
  { value: 'account', label: 'Account and sign-in' },
  { value: 'technical', label: 'Something is not working' },
  { value: 'other', label: 'Something else' },
];

const BLANK = { topic: 'application', subject: '', message: '', attachment: null };

export default function SupportPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState(BLANK);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(null);
  const [history, setHistory] = useState([]);
  const [chatBusy, setChatBusy] = useState(false);
  const chatReady = isLiveChatConfigured();

  const loadHistory = useCallback(() => {
    support
      .list()
      .then(({ data }) => setHistory(Array.isArray(data) ? data : data.results || []))
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const update = (patch) => {
    setForm((current) => ({ ...current, ...patch }));
    setErrors((current) => {
      const next = { ...current };
      Object.keys(patch).forEach((key) => delete next[key]);
      return next;
    });
  };

  const chooseFile = async (event) => {
    const raw = event.target.files?.[0];
    if (!raw) return;
    if (raw.size > 5 * 1024 * 1024 && !raw.type.startsWith('image/')) {
      toast.warning('Keep the attachment under 5MB.');
      event.target.value = '';
      return;
    }
    update({ attachment: await compressImageFile(raw) });
  };

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (form.subject.trim().length < 3) found.subject = 'Add a short subject.';
    if (form.message.trim().length < 10) found.message = 'Tell us a little more, so we can help.';
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      const { data } = await support.send({
        topic: form.topic,
        subject: form.subject.trim(),
        message: form.message.trim(),
        attachment: form.attachment,
      });
      setSent(data);
      setForm(BLANK);
      loadHistory();
    } catch (error) {
      const fields = fieldErrors(error);
      if (Object.keys(fields).length) setErrors(fields);
      toast.error(errorMessage(error, 'Your message could not be sent. Try again.'));
    } finally {
      setBusy(false);
    }
  };

  const startChat = async () => {
    setChatBusy(true);
    try {
      await openLiveChat({ name: user?.full_name, email: user?.email });
    } catch (error) {
      toast.error(error.message || 'Live chat could not be opened.');
    } finally {
      setChatBusy(false);
    }
  };

  return (
    <div className="gx-page">
      <div className="gx-support-grid">
        <section className="gx-card gx-support-chat" aria-labelledby="chat-title">
          <span className="gx-icon-tile" aria-hidden="true">
            <Icon name="chat" size={22} />
          </span>
          <h2 id="chat-title" className="gx-card-title">Live chat</h2>
          <p className="gx-muted">
            {chatReady ? 'Talk to our team now.' : 'Live chat is not available yet. Send us a message instead.'}
          </p>
          {chatReady ? (
            <button type="button" className="gx-btn gx-btn-primary" onClick={startChat} disabled={chatBusy}>
              {chatBusy ? <span className="spinner-sm" aria-hidden="true" /> : <Icon name="chat" size={17} />}
              {chatBusy ? 'Opening' : 'Start live chat'}
            </button>
          ) : null}
        </section>

        <section className="gx-card gx-support-chat" aria-labelledby="reply-title">
          <span className="gx-icon-tile" aria-hidden="true">
            <Icon name="mail" size={22} />
          </span>
          <h2 id="reply-title" className="gx-card-title">Replies by email</h2>
          <p className="gx-muted">
            We answer at <strong>{user?.email}</strong>, usually within one working day.
          </p>
        </section>
      </div>

      <section className="gx-card" aria-labelledby="message-title">
        <div className="gx-card-head">
          <h2 id="message-title" className="gx-card-title">Send a message</h2>
        </div>

        {sent ? (
          <div className="gx-success" role="status">
            <span className="gx-success-icon" aria-hidden="true">
              <Icon name="checkCircle" size={26} />
            </span>
            <div>
              <h3>Message sent</h3>
              <p className="gx-muted">
                Reference <strong>{sent.reference}</strong>. We will reply to {user?.email}.
              </p>
            </div>
            <button type="button" className="gx-btn gx-btn-secondary" onClick={() => setSent(null)}>
              Send another
            </button>
          </div>
        ) : (
          <form className="gx-form" onSubmit={submit} noValidate>
            <div className="gx-field">
              <label htmlFor="support-topic">Topic</label>
              <select
                id="support-topic"
                className="gx-input"
                value={form.topic}
                onChange={(event) => update({ topic: event.target.value })}
              >
                {TOPICS.map((topic) => (
                  <option key={topic.value} value={topic.value}>
                    {topic.label}
                  </option>
                ))}
              </select>
            </div>

            <div className={`gx-field ${errors.subject ? 'has-error' : ''}`.trim()}>
              <label htmlFor="support-subject">Subject</label>
              <input
                id="support-subject"
                className="gx-input"
                maxLength={160}
                value={form.subject}
                onChange={(event) => update({ subject: event.target.value })}
                aria-invalid={Boolean(errors.subject)}
                aria-describedby={errors.subject ? 'support-subject-error' : undefined}
              />
              {errors.subject ? (
                <span id="support-subject-error" className="gx-error">
                  {String(errors.subject)}
                </span>
              ) : null}
            </div>

            <div className={`gx-field ${errors.message ? 'has-error' : ''}`.trim()}>
              <label htmlFor="support-message">Message</label>
              <textarea
                id="support-message"
                className="gx-input"
                rows={6}
                maxLength={5000}
                value={form.message}
                onChange={(event) => update({ message: event.target.value })}
                aria-invalid={Boolean(errors.message)}
                aria-describedby={errors.message ? 'support-message-error' : undefined}
              />
              {errors.message ? (
                <span id="support-message-error" className="gx-error">
                  {String(errors.message)}
                </span>
              ) : null}
            </div>

            <div className="gx-field">
              <span className="gx-label">Attachment (optional)</span>
              <label className="gx-attach" htmlFor="support-attachment">
                <Icon name="paperclip" size={17} />
                <span>{form.attachment ? form.attachment.name : 'Add a screenshot or PDF'}</span>
              </label>
              <input
                id="support-attachment"
                type="file"
                className="sr-only"
                accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif"
                onChange={chooseFile}
              />
              {errors.attachment ? <span className="gx-error">{String(errors.attachment)}</span> : null}
            </div>

            <div className="gx-form-actions">
              <button type="submit" className="gx-btn gx-btn-primary" disabled={busy}>
                {busy ? <span className="spinner-sm" aria-hidden="true" /> : <Icon name="send" size={16} />}
                {busy ? 'Sending' : 'Send message'}
              </button>
            </div>
          </form>
        )}
      </section>

      {history.length ? (
        <section className="gx-card" aria-labelledby="history-title">
          <div className="gx-card-head">
            <h2 id="history-title" className="gx-card-title">Your messages</h2>
          </div>
          <ul className="gx-list">
            {history.map((ticket) => (
              <li key={ticket.reference} className="gx-list-row">
                <div className="gx-list-main">
                  <span className="gx-list-title">{ticket.subject}</span>
                  <span className="gx-muted gx-small">
                    {ticket.reference} · {ticket.topic_display} · {formatDate(ticket.created_at)}
                  </span>
                </div>
                <span className={`gx-pill ${ticket.status === 'resolved' ? 'is-ok' : 'is-wait'}`}>
                  {ticket.status_display}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
