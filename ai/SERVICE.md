# Read-only AI service v1

`ksai serve` exposes the same normalized catalog and patch operations as the
CLI over a small localhost HTTP boundary.

| Method | Route | Input |
| --- | --- | --- |
| `GET` | `/v1/health` | none |
| `GET` | `/v1/catalog/search?q=...&limit=...` | query string |
| `GET` | `/v1/catalog/inspect?object=...` | exact object family or variant |
| `POST` | `/v1/patch/validate` | `{"source":"kpatch ..."}` |
| `POST` | `/v1/patch/explain` | `{"source":"kpatch ..."}` |

Responses are compact JSON. Invalid patch source returns HTTP 422 with the same
diagnostic codes as the CLI. Request bodies are limited to one MiB.

The server rejects non-loopback bind addresses. There are no routes for file
writes, catalog rebuilding, patch emission, target compilation, command queues,
USB, upload, SD access, or flashing. This makes it useful as a low-token shared
semantic boundary for an agent or future UI without making network access an
implicit authorization for device changes.

If mutation is added later, it should be a separate service with authenticated
sessions, optimistic revision IDs, dry-run reports, explicit per-operation
authorization, and an audit log. Device operations should remain a further
separate capability with human confirmation.
