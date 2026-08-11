# Browser Play Delivery Examples

These directories are read-only references for the UI generation Agent. Each
Example expects an upstream assembly step to provide an asset-imported,
compiled native Engine project and demonstrates only the final browser delivery
handoff.

| Example | Demonstrates |
| --- | --- |
| `BrowserPlayExample` | Engine-neutral Browser Serving session bootstrap, `stream_url` presentation, input focus, fullscreen, recovery, and the thin launcher contract |

Generated Browser Play output must remain task-owned and independent of these
Examples. Backend implementation and stream transport remain framework-owned.
