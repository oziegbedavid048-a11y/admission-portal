import { useState } from 'react';
import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';
import { formatLongDate } from '../../lib/format';
import { useApplication } from './ApplicationContext';

export default function ProgrammePanel() {
  const { application } = useApplication();
  const [receiptOpen, setReceiptOpen] = useState(false);
  const payment = application.payment;
  const settled = payment && (payment.status === 'paid' || payment.status === 'waived');

  return (
    <div className="portal-stack">
      <section className="app-banner">
        <span className="app-greet-icon" aria-hidden="true">
          <Icon name="cap" size={22} animate />
        </span>
        <div className="app-banner-text">
          <h2>Programme</h2>
          <p>Where you applied and what you chose.</p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Your application</h2>
          {payment ? (
            <button
              type="button"
              className="g-btn g-btn-quiet g-btn-sm"
              onClick={() => setReceiptOpen(true)}
            >
              Receipt
            </button>
          ) : null}
        </div>

        <div className="facts">
          <div className="fact">
            <div className="fact-label">Reference</div>
            <div className="fact-value">{application.reference}</div>
          </div>
          <div className="fact">
            <div className="fact-label">Destination</div>
            <div className="fact-value">{application.destination_country}</div>
          </div>
          <div className="fact facts-full">
            <div className="fact-label">Institution</div>
            <div className="fact-value">{application.institution?.name || 'Not set'}</div>
          </div>
          <div className="fact facts-full">
            <div className="fact-label">Courses</div>
            <div className="chips">
              {application.programs.length === 0 ? (
                <span className="empty">None chosen.</span>
              ) : (
                application.programs.map((program) => (
                  <span className="chip" key={program.id}>
                    {program.name}
                  </span>
                ))
              )}
            </div>
          </div>
          <div className="fact facts-full">
            <div className="fact-label">Payment</div>
            <div className="fact-value">
              <span className={`pill ${settled ? 'pill-ok' : 'pill-wait'}`}>
                {settled ? payment.display_total : 'Not settled'}
              </span>
            </div>
          </div>
        </div>
      </section>

      {application.institution?.tuition_summary ? (
        <section className="card">
          <div className="card-head">
            <h2>Tuition</h2>
          </div>
          <p className="card-body-text">
            {application.institution.name} lists {application.institution.tuition_summary}.
            Tuition is paid to the institution after your offer letter is issued and is
            separate from the application fee.
          </p>
        </section>
      ) : null}

      <Modal
        open={receiptOpen}
        onClose={() => setReceiptOpen(false)}
        title="Payment receipt"
        labelledBy="receipt-title"
        size={600}
        footer={
          <button type="button" className="btn btn-secondary" onClick={() => window.print()}>
            <Icon name="printer" size={16} strokeWidth={2} />
            Print or save as PDF
          </button>
        }
      >
        <div className="receipt-paper">
          <div className="receipt-head">
            <div className="receipt-brand">
              <img src="/assets/logo.png" alt="" className="receipt-logo" />
              <div>
                <span className="receipt-brand-name">Gabstep</span>
                <span className="receipt-brand-sub">Admissions escrow</span>
              </div>
            </div>
            <div className="receipt-stamp">
              {payment?.status === 'waived' ? 'Waived' : 'Paid'}
            </div>
          </div>

          <div className="receipt-rule">
            <div className="invoice-row">
              <span>Receipt</span>
              <span>{payment?.reference}</span>
            </div>
            <div className="invoice-row">
              <span>Paid on</span>
              <span>
                {payment?.paid_at ? formatLongDate(payment.paid_at) : 'Not settled'}
              </span>
            </div>
            <div className="invoice-row">
              <span>Method</span>
              <span>{payment?.gateway || 'Partner waiver'}</span>
            </div>
            <div className="invoice-row">
              <span>Application</span>
              <span>{application.reference}</span>
            </div>
            <div className="invoice-row">
              <span>Applicant</span>
              <span>{application.full_name}</span>
            </div>
          </div>

          <div className="receipt-total">
            <span className="receipt-total-label">Total paid</span>
            <span className="receipt-total-value">{payment?.display_total}</span>
          </div>
        </div>
      </Modal>
    </div>
  );
}
