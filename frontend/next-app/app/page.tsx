import { api, type TenantHeaders } from "../lib/api";

export const dynamic = "force-dynamic";

// Minimal server component proof-of-wiring for the scaffold. Replace the demo
// tenant id with an authenticated session tenant before use.
export default async function Page() {
  const headers: TenantHeaders = { "x-tenant-id": "00000000-0000-0000-0000-000000000000" };
  let count = 0;
  try {
    count = (await api.listPatients(headers)).length;
  } catch {
    // backend not running in this scaffold environment
  }
  return (
    <main style={{ padding: 28 }}>
      <h1>Longithread</h1>
      <p style={{ opacity: 0.7 }}>
        Next.js scaffold · longitudinal care intelligence. Patients reachable: {count}.
        This starter is not yet wired to authentication or production integrations.
      </p>
    </main>
  );
}
