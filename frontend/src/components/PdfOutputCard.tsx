type PdfOutputCardProps = {
  downloadUrl: string;
  filename: string;
  status: string;
  onClear?: () => void;
};

export function PdfOutputCard({ downloadUrl, filename, status, onClear }: PdfOutputCardProps) {
  return (
    <div className="pdf-output-card">
      <p className="pdf-output-status">{status}</p>
      <div className="pdf-output-actions">
        <a className="primary-button pdf-download-link" href={downloadUrl} download={filename}>
          Download {filename}
        </a>
        {onClear ? (
          <button type="button" className="secondary-button" onClick={onClear}>
            Clear
          </button>
        ) : null}
      </div>
    </div>
  );
}
