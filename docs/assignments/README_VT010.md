# VT-010 notification slice

## Run the focused tests

From the repository root (Node.js >= 22.12):

```bash
npm ci --prefix frontend
npm --prefix frontend test -- src/features/search/business-notification.test.ts src/features/search/Feedback.test.tsx
```

Run the frontend checks:

```bash
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

This slice sends a browser notification only after durable feedback returns successfully, only when browser permission is already `granted`. It does not request permission and does not implement an operator email/push provider. The 100-task test is a synthetic local helper harness; it does not exercise HTTP, FastAPI, PostgreSQL, or 100 real browser sessions.
