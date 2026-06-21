import { useState, type FormEvent } from "react";
import { useAuth } from "../context/AuthContext";

type ChangePasswordModalProps = {
  open: boolean;
  forced?: boolean;
  onComplete?: () => void;
};

export function ChangePasswordModal({ open, forced = false, onComplete }: ChangePasswordModalProps) {
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return null;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      onComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" role="presentation">
      <div className="modal-card change-password-modal" role="dialog" aria-modal="true">
        <h2>{forced ? "Set a new password" : "Change password"}</h2>
        <p className="result-muted">
          {forced
            ? "Your account uses a temporary password. Choose a new password before continuing."
            : "Update your account password."}
        </p>
        <form onSubmit={(event) => void onSubmit(event)}>
          <label className="field">
            <span>Current password</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label className="field">
            <span>New password</span>
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <label className="field">
            <span>Confirm new password</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "Saving..." : "Save password"}
          </button>
          {!forced ? (
            <button type="button" className="secondary-button" onClick={() => onComplete?.()}>
              Cancel
            </button>
          ) : null}
        </form>
      </div>
    </div>
  );
}
