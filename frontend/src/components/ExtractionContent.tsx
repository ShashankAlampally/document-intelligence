import { AnswerContent } from './AnswerContent';

/** Present the API's field: value lines without inventing field-level citations. */
export function ExtractionContent({ text }: { text: string }) {
  const lines = text.split(/\r?\n/).filter(line => line.trim());
  const fields = lines.map(line => line.match(/^([a-zA-Z][a-zA-Z0-9_ /()-]{0,90}):\s*(.*)$/));
  if (!fields.length || fields.some(field => !field)) return <AnswerContent text={text}/>;
  return <div className="formatted-answer answer-table-scroll"><table aria-label="Extracted bid fields"><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>{fields.map((field, index) => <tr key={index}><td>{field![1].replace(/_/g, ' ')}</td><td>{field![2]}</td></tr>)}</tbody></table></div>;
}
