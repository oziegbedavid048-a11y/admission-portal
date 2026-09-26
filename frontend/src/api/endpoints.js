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
  checkout: (reference) => api.post('/payments/checkout/', { application: reference }),
  // Asks the server what happened to a payment. The server asks Paystack, so the
  // browser is never the thing that decides a payment succeeded.
  status: (reference) => api.get(`/payments/status/${reference}/`),
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
