import api from './client';

export const auth = {
  login: (email, password) => api.post('/auth/login/', { email, password }),
  // Clears the httpOnly refresh cookie server-side. Signing out has to be a
  // request, because the page cannot reach the cookie to delete it itself.
  logout: () => api.post('/auth/logout/', {}),
  registerApplicant: (payload) => api.post('/auth/register/applicant/', payload),
  registerAgent: (payload) => api.post('/auth/register/agent/', payload),
  me: () => api.get('/auth/me/'),
  updateMe: (payload) => api.patch('/auth/me/', payload),
  updateAvatar: (file) => {
    const form = new FormData();
    form.append('avatar', file);
    return api.patch('/auth/me/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  changePassword: (currentPassword, newPassword) =>
    api.post('/auth/password/', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  // Forgotten password. The request answers the same whether or not the
  // address has an account; the link in the email carries uid and token.
  forgotPassword: (email) => api.post('/auth/password/forgot/', { email }),
  // Email verification after signing up. Verifying returns a session.
  verifyEmail: (token) => api.post('/auth/verify-email/', { token }),
  resendVerification: (email) => api.post('/auth/verify-email/resend/', { email }),
  validateReset: (uid, token) => api.post('/auth/password/reset/validate/', { uid, token }),
  resetPassword: (uid, token, newPassword) =>
    api.post('/auth/password/reset/', { uid, token, new_password: newPassword }),
};

// Messages from the Support page. They are emailed to the support inbox with the
// sender as reply-to, and kept so the sender can see what they have sent.
export const support = {
  list: () => api.get('/auth/support/'),
  send: ({ topic, subject, message, attachment }) => {
    const form = new FormData();
    form.append('topic', topic);
    form.append('subject', subject);
    form.append('message', message);
    if (attachment) form.append('attachment', attachment);
    return api.post('/auth/support/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

export const catalog = {
  originCountries: () => api.get('/catalog/origin-countries/'),
  destinations: () => api.get('/catalog/destinations/'),
  institutions: (country) => api.get('/catalog/institutions/', { params: { country } }),
  faqs: () => api.get('/catalog/faqs/'),
  programs: (params) => api.get('/catalog/programs/', { params }),
  programLevels: () => api.get('/catalog/programs/levels/'),
  exchangeRates: (base = 'NGN', refresh = false) =>
    api.get('/catalog/exchange-rates/', { params: { base, refresh: refresh || undefined } }),
  // The fee belongs to the school, so the slug is not optional in the wizard:
  // without it the answer is a typical figure, not this applicant's.
  feeQuote: (origin, institution) =>
    api.get('/catalog/fee-quote/', { params: { origin, institution } }),
};

export const applications = {
  mine: () => api.get('/applications/mine/'),
  create: (payload) => api.post('/applications/', payload),
  updateContact: (reference, payload) => api.patch(`/applications/${reference}/`, payload),
  uploadDocument: (reference, { file, kind, name }) => {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', kind);
    form.append('name', name);
    return api.post(`/applications/${reference}/documents/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // A new copy of one document, usually after the admissions desk rejected it.
  replaceDocument: (reference, documentId, file) => {
    const form = new FormData();
    form.append('file', file);
    return api.post(`/applications/${reference}/documents/${documentId}/replace/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  requestCorrection: (reference, payload) => {
    const form = new FormData();
    Object.entries(payload).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') form.append(key, value);
    });
    return api.post(`/applications/${reference}/corrections/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  markNotificationsRead: (reference) =>
    api.post(`/applications/${reference}/notifications/read/`),
  transferToVisaSupport: (reference) =>
    api.post(`/applications/${reference}/transfer-to-visa-support/`),
  getDraft: () => api.get('/applications/draft/'),
  saveDraft: (payload) => api.put('/applications/draft/', payload),
  clearDraft: () => api.delete('/applications/draft/'),
};

export const payments = {
  quote: (reference) => api.get(`/payments/quote/${reference}/`),
  // Which provider collects the money is a server decision, not the browser's.
  checkout: (reference, returnTo = 'portal') =>
    api.post('/payments/checkout/', { application: reference, return_to: returnTo }),
  // A bank transfer to one of the company accounts: the receipt goes to the
  // desk, and the fee counts as paid only once they confirm the money arrived.
  transfer: (reference, { receipt, bank }) => {
    const form = new FormData();
    form.append('receipt', receipt);
    form.append('bank', bank);
    return api.post(`/payments/transfer/${reference}/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Asks the server what happened to a payment. The server asks Paystack, so the
  // browser is never the thing that decides a payment succeeded.
  // `gatewayReference` is the transaction reference Paystack appends to the return
  // URL. The server requires it when nobody is signed in, because an application
  // number is short enough to guess.
  status: (reference, gatewayReference) =>
    api.get(`/payments/status/${reference}/`, {
      params: gatewayReference ? { reference: gatewayReference } : undefined,
    }),
  receipt: (reference) => api.get(`/payments/receipt/${reference}/`),
};

export const partners = {
  profile: () => api.get('/partners/me/'),
  updateProfile: (payload) => api.patch('/partners/me/', payload),
  overview: () => api.get('/partners/overview/'),
  wallet: () => api.get('/partners/wallet/'),
  students: (params) => api.get('/partners/students/', { params }),
  createStudent: (payload) => api.post('/partners/students/', payload),
  studentStages: (reference) => api.get(`/partners/students/${reference}/stages/`),
  // One-page PDF: name, origin, destination and application reference.
  studentSummary: (reference) =>
    api.get(`/partners/students/${reference}/summary/`, { responseType: 'blob' }),
  drafts: () => api.get('/partners/drafts/'),
  draft: (id) => api.get(`/partners/drafts/${id}/`),
  createDraft: (payload) => api.post('/partners/drafts/', payload),
  updateDraft: (id, payload) => api.patch(`/partners/drafts/${id}/`, payload),
  deleteDraft: (id) => api.delete(`/partners/drafts/${id}/`),
  uploadDraftFile: (id, { slot, kind, name, file }) => {
    const form = new FormData();
    form.append('slot', slot);
    form.append('kind', kind);
    form.append('name', name);
    form.append('file', file);
    return api.post(`/partners/drafts/${id}/files/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  deleteDraftFile: (id, fileId) => api.delete(`/partners/drafts/${id}/files/${fileId}/`),
  loans: () => api.get('/partners/loans/'),
  requestLoan: (payload) => api.post('/partners/loans/', payload),
  withdrawals: () => api.get('/partners/withdrawals/'),
  withdraw: (amount) => api.post('/partners/withdrawals/', { amount }),
  moveToSavings: (amount) => api.post('/partners/wallet/savings/', { amount }),
  // Savings used to be one-way, so anything set aside stopped being withdrawable
  // for good. This is the way back.
  releaseFromSavings: (amount) =>
    api.delete('/partners/wallet/savings/', { data: { amount } }),
  commissions: () => api.get('/partners/commissions/'),
};

export const supervisors = {
  profile: () => api.get('/supervisors/me/'),
  updateProfile: (payload) => api.patch('/supervisors/me/', payload),
  overview: () => api.get('/supervisors/overview/'),
  agents: (params) => api.get('/supervisors/agents/', { params }),
  students: (params) => api.get('/supervisors/students/', { params }),
  bonuses: () => api.get('/supervisors/bonuses/'),
  withdrawals: () => api.get('/supervisors/withdrawals/'),
  withdraw: (amount) => api.post('/supervisors/withdrawals/', { amount }),
};
