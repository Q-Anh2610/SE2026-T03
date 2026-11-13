# VT-010 execution evidence

- Repo: `https://github.com/Q-Anh2610/SE2026-T03`
- Branch: `test/23001854-vt-010-notification`
- Baseline: `ccd7e01e21a7712af8688c59feedd53fc3ea5364` (`origin/develop`).
- The test-only phase, before the helper existed: `npm --prefix frontend test -- src/features/search/business-notification.test.ts src/features/search/Feedback.test.tsx` failed to resolve `./business-notification`; this is the expected red state for a missing implementation. The initial run before `npm ci` was invalid (`vitest: command not found`) and is not counted as evidence.
- After implementation: focused tests `36 passed`; full frontend suite `392 passed` / 18 files; lint, typecheck and production build passed.
- Focused helper coverage: `business-notification.ts` statements 21/21, branches 10/10, functions 3/3, lines 20/20 (100% each).
- Suite coverage summary: statements 694/697 (99.56%), branches 740/753 (98.27%), functions 173/173 (100%), lines 598/598 (100%). Global figures hide whether risk-specific behavior is checked; see traceability and mutation result.
- Mutation: temporary `count > limit` → `count >= limit`; test `accepts a title exactly at the 120-character boundary` with 120 emoji code points failed (`expected true; received false`). The implementation was restored to `>` and the tests passed again. The mutant is not present in the final branch.
- Pairwise harness: 12 selected combinations across permission (granted/denied/default/unsupported), sender (ok/throws), title (under/exact/over 120), and body (under/over 240). Selection covers all pairs of factor values; exact-limit title remains an explicit boundary test.
- Synthetic burst: 100 Promise.all tasks; observed p95 `0.010 ms`, wall `1.241 ms`; local Vitest run. This is not a server load test and cannot establish system p95 under HTTP/DB/browser load.
- Flaky review: fixed input; no wall-clock sleeps, random data, network, or shared DB; Notification globals and constructor spy reset after each test. Current tests still use jsdom and mocked `fetch`; actual browser permission UX is not covered.

## AI-generated test cases reviewed

1. Removed the suggestion “request permission automatically and assert the prompt” because it conflicts with AC-5 and would add an unrequested browser side effect.
2. Reworked the generic suggestion “successful feedback shows a message and notification” into independent assertions: live persistence success invokes the notifier; mock feedback does not; notification construction failure leaves the committed feedback success visible. This guards the invariant rather than only checking a status message.
