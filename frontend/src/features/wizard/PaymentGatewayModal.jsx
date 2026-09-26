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
          {busy ? 'Submitting' : online ? 'Continue to payment' : 'Submit application'}
        </button>
      }
    >
      <div className="pay-summary">
        <div>
          <span className="pay-summary-label">Paying as</span>
          <span className="pay-summary-value">{email}</span>
        </div>
        <div className="pay-summary-right">
          <span className="pay-summary-label">Amount due</span>
          <span className="pay-summary-amount">
            {quote ? formatMoney(quote.total, quote.currency) : 'Calculating'}
          </span>
        </div>
      </div>

      {online ? (
        <div className="callout callout-info">
          <Icon name="lock" size={20} className="callout-icon" strokeWidth={2} />
          <div className="callout-content">
            Your application is submitted first, then you are taken to our payment
            provider to pay. Your card details are entered on their page and never
            reach us.
          </div>
        </div>
      ) : (
        <>
          {account ? (
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
          ) : null}
          <div className="callout callout-info">
            <Icon name="info" size={20} className="callout-icon" strokeWidth={2} />
            <div className="callout-content">
              {account
                ? 'Quote your application reference on the transfer. The desk confirms it and your file moves on; you will get an email either way.'
                : 'Your application is submitted with the fee outstanding. The admissions desk will send you the payment details.'}
            </div>
          </div>
        </>
      )}
    </Modal>
  );
}
