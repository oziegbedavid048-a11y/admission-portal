# Gabstep frontend

React 19 + Vite single-page app for the Gabstep visa application platform.

```bash
npm install
npm run dev      # http://localhost:5173, proxying /api to Django on :8000
npm run build    # production bundle in dist/
npm run preview  # serve the built bundle
npm run lint     # oxlint
```

`VITE_API_URL` in `.env` points at the API. The default, `/api`, uses the dev
server proxy; set it to a full URL to talk to a deployed backend.

Setup, architecture and the design system are documented in the
[project README](../README.md).
