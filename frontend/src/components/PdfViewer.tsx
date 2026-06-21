type PdfViewerProps = {
  url: string;
  title: string;
};

export function PdfViewer({ url, title }: PdfViewerProps) {
  return (
    <div className="pdf-viewer">
      <div className="pdf-viewer-toolbar">
        <span className="result-muted">Document preview</span>
        <a className="secondary-button pdf-viewer-open-tab" href={url} target="_blank" rel="noreferrer">
          Open in new tab
        </a>
      </div>
      <iframe className="pdf-viewer-frame" title={title} src={url} />
    </div>
  );
}
