# PWA & Notification Release Matrix

Automated coverage runs in CI (`lint-and-typecheck`, `test-suite`,
`playwright-e2e`); this matrix records what automation proves and what
still needs a physical browser or device. Unavailable devices are marked
**pending** — never passed.

## Automated (CI, this repo)

| Check | Spec | Result |
|---|---|---|
| Manifest stable id + raster/maskable icons + ingress contract | `tests/integration/test_deployment_contract.py` | pass |
| No SW control in dev, no cached API impersonation | `web/tests/e2e/specs/pwa-offline.spec.ts` (×3 viewports) | pass |
| No unsolicited update prompt on fresh load | `web/tests/e2e/specs/pwa-update.spec.ts` (×3 viewports) | pass |
| Notification center read/dismiss persistence | `web/tests/e2e/specs/notification-center.spec.ts` (×3) | pass |
| Push opt-in timing (no pre-consent permission request) | `web/tests/e2e/specs/push-settings.spec.ts` (×3) | pass |
| Push delivery retry/deactivation, payload privacy | `tests/integration/test_push_delivery.py` | pass |
| Safe notification deep-link fallback | covered in `notification-center.spec.ts` | pass |
| Production precache bundle emits versioned SW | `vite build` → `dist/sw.js` + `dist/workbox-*.js` (21 entries) | pass |

## Physical verification (pending — complete before release)

| Device / browser | Install | Offline shell | Update accept | Push receive | Push click → deep link |
|---|---|---|---|---|---|
| Chrome desktop (HTTPS origin) | pending | pending | pending | pending | pending |
| Edge desktop | pending | pending | pending | pending | pending |
| Firefox desktop | pending | pending | pending | n/a (own push service; verify separately) | pending |
| Safari macOS | pending | pending | pending | pending (macOS 13+ web push) | pending |
| Android Chrome (installed) | pending | pending | pending | pending | pending |
| iOS Safari (Add to Home Screen, 16.4+) | pending | pending | pending | pending | pending |
| iPadOS | pending | pending | pending | pending | pending |

## Notes

- Production Push and install require the HTTPS ingress
  (`infra/caddy/Caddyfile`); plain-HTTP LAN delivery is not
  release-capable and must not be claimed as such.
- Updates apply only after the user accepts the in-app banner; verify
  on one device that dismissing keeps the running version coherent.
- Push payloads carry only `{version, notification_id, deep_link}`;
  verify on the wire that no filename, error text, or credential ever
  appears in an OS notification.
