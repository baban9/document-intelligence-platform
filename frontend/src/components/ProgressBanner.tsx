import type { ProgressUpdate } from "../api/client";

function humanJobStatus(status: string): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Processing";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return status.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }
}

type ProgressBannerProps = {
  progress: ProgressUpdate;
};

export function ProgressBanner({ progress }: ProgressBannerProps) {
  return (
    <div className="status-banner">
      <strong>{humanJobStatus(progress.jobStatus)}</strong>
      <span>{progress.message}</span>
      {progress.progress > 0 ? <span>{progress.progress}% complete</span> : null}
    </div>
  );
}
