import { useEffect, useState, type FormEvent } from "react";
import {
  fetchLoginEvents,
  fetchUsers,
  onboardUser,
  type LoginEvent,
  type UserAccount,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useTenant } from "../context/TenantContext";

export function UsersPanel() {
  const { isAdmin: tenantIsAdmin } = useTenant();
  const { user: authUser } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [makeAdmin, setMakeAdmin] = useState(false);
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [events, setEvents] = useState<LoginEvent[]>([]);
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const bootstrapMode = users.length === 0;
  const canManageUsers =
    bootstrapMode || tenantIsAdmin || Boolean(authUser?.authenticated && authUser.is_admin);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [nextUsers, nextEvents] = await Promise.all([fetchUsers(), fetchLoginEvents()]);
      setUsers(nextUsers);
      setEvents(nextEvents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load users.");
      setUsers([]);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    setTemporaryPassword(null);
    try {
      const result = await onboardUser({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        is_admin: bootstrapMode || makeAdmin,
      });
      setTemporaryPassword(result.temporary_password);
      setMessage(result.message);
      setFirstName("");
      setLastName("");
      setEmail("");
      setMakeAdmin(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not onboard user.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!canManageUsers) {
    return (
      <section className="panel">
        <h1>Users</h1>
        <p className="result-muted">
          Sign in as a platform admin, or select the admin tenant, to onboard users and review login
          activity.
        </p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h1>User onboarding</h1>
      <p className="result-muted">
        {bootstrapMode
          ? "No users exist yet. Create the first platform admin account below."
          : "Create accounts with a temporary password. Users must change their password on first login."}
      </p>

      <form className="settings-form" onSubmit={(event) => void onSubmit(event)}>
        <fieldset className="settings-fieldset">
          <legend>New user</legend>
          <label className="field">
            <span>First name</span>
            <input type="text" value={firstName} onChange={(event) => setFirstName(event.target.value)} required />
          </label>
          <label className="field">
            <span>Last name</span>
            <input type="text" value={lastName} onChange={(event) => setLastName(event.target.value)} required />
          </label>
          <label className="field">
            <span>Email</span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          {!bootstrapMode ? (
            <label className="field checkbox-field">
              <input
                type="checkbox"
                checked={makeAdmin}
                onChange={(event) => setMakeAdmin(event.target.checked)}
              />
              <span>Platform admin</span>
            </label>
          ) : null}
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "Creating..." : bootstrapMode ? "Create admin account" : "Create user"}
          </button>
        </fieldset>
      </form>

      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="form-success">{message}</p> : null}
      {temporaryPassword ? (
        <div className="onboard-password-box">
          <p>
            <strong>Temporary password:</strong> <code>{temporaryPassword}</code>
          </p>
          <p className="result-muted">Copy this now. It will not be shown again.</p>
        </div>
      ) : null}

      <h2>Users</h2>
      {loading ? <p className="result-muted">Loading...</p> : null}
      {!loading && users.length === 0 ? <p className="result-muted">No users onboarded yet.</p> : null}
      {!loading && users.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Admin</th>
                <th>Must change password</th>
                <th>Last login</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.full_name || `${user.first_name} ${user.last_name}`.trim()}</td>
                  <td>{user.email}</td>
                  <td>{user.is_admin ? "Yes" : "No"}</td>
                  <td>{user.must_change_password ? "Yes" : "No"}</td>
                  <td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <h2>Login activity</h2>
      {!loading && events.length === 0 ? <p className="result-muted">No login events recorded yet.</p> : null}
      {!loading && events.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Email</th>
                <th>Method</th>
                <th>Success</th>
                <th>IP</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{event.created_at ? new Date(event.created_at).toLocaleString() : ""}</td>
                  <td>{event.email}</td>
                  <td>{event.method}</td>
                  <td>{event.success ? "Yes" : "No"}</td>
                  <td>{event.ip_address || "-"}</td>
                  <td>{event.failure_reason || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
