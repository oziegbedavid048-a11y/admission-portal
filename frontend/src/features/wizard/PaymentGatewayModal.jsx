import Modal from '../../components/ui/Modal';
import Icon from '../../lib/icons';
import { formatMoney } from '../../lib/format';

/**
 * Confirming the application fee.
 *
 * This used to be a stand-in for a gateway: tabs for card, transfer and mobile
 * money, with a card number, an expiry and a CVV already typed in. All of it was
 * inert, and none of it should ever be real — card details belong to the
 * provider's own page, never to ours, and a form that asks for them teaches
 * people the wrong habit even when it does nothing with them.
 *
 * So there are no card fields. The dialog says what is owed and what happens
 * next, and the next thing is one of two:
 *
 *   - a provider is configured, so confirming hands the applicant over to it,
 *   - or it is not, so the fee is recorded as outstanding and paid by transfer
 *     to the account the API supplies.
 *
 * Either way the file is submitted when this closes. Nothing here marks anything
 * as paid: settlement comes from the provider's signed webhook or from the desk
 * confirming the transfer landed.
 */
export default function PaymentGatewayModal({ open, onClose, onConfirm, quote, email, busy }) {
  const online = quote?.provider === 'paystack';
  const account = quote?.transfer_account;

  return (
    <Modal
      open={open}
      onClose={busy ? undefined : onClose}
      dismissable={!busy}
      title="Application fee"
      subtitle={
        online
          ? 'One fee per institution, however many courses you picked.'
          : 'One fee per institution. Transfer it and the desk confirms receipt.'
      }
      labelledBy="gateway-modal-title"
      size={480}
      footer={
        <button
          type="button"
          className="btn btn-accent btn-lg"
          onClick={onConfirm}
          disabled={busy}
        >
          {busy ? <span className="spinner-sm" aria-hidden="true" /> : null}
          {busy
            ? 'Uploading your documents'
            : online
              ? 'Proceed to payment'
              : 'Submit application'}
        </button>
      }
    >
      {busy ? (
        <div className="callout callout-info">
          <Icon name="clock" size={20} className="callout-icon" strokeWidth={2} />
          <div className="callout-content">
            Your documents are uploading. This takes a few seconds, then you go
            straight to the payment page. Do not close this.
          </div>
        </div>
      ) : null}

      <div className="pay-summary">
        <div className="pay-summary-left">
          <span className="pay-summary-label">Paying as</span>
          <span className="pay-summary-value">{email}</span>
        </div>
        <div className="pay-summary-right">
          <span className="pay-summary-label">Amount due</span>
          <span className="pay-summary-amount">
            {quote ? formatMoney(quote.amount, quote.currency) : ''}
          </span>
        </div>
      </div>

      {!online && account ? (
        <>
          <div className="bank-transfer-box">
            <div className="bank-row">
              <span className="pay-row-label">Bank</span>
              <strong>{account.bank}</strong>
            </div>
            <div className="bank-row">
              <span className="pay-row-label">Account number</span>
              <strong className="pay-row-account">{account.account_number}</strong>
            </div>
            <div className="bank-row">
              <span className="pay-row-label">Beneficiary</span>
              <strong>{account.beneficiary}</strong>
            </div>
          </div>
          <div className="callout callout-info">
            <Icon name="info" size={20} className="callout-icon" strokeWidth={2} />
            <div className="callout-content">
              Quote your application reference on the transfer. The desk confirms it and your file moves on; you will get an email either way.
            </div>
          </div>
        </>
      ) : null}
    </Modal>
  );
}
