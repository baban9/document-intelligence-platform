type JsonResultViewProps = {
  value: unknown;
};

export function JsonResultView({ value }: JsonResultViewProps) {
  const text =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return <pre className="result-text-preview json-result">{text}</pre>;
}
