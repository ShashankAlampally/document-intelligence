import { Fragment, type ReactNode } from 'react';

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part.startsWith('`') && part.endsWith('`') ? <code key={i}>{part.slice(1, -1)}</code> : <Fragment key={i}>{part}</Fragment>);
}
const cells = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(value => value.trim());
/** A small text-only formatter; raw model HTML is never executed. */
export function AnswerContent({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n'); const blocks: ReactNode[] = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^```/.test(line)) { const content: string[] = []; i++; while (i < lines.length && !/^```/.test(lines[i])) content.push(lines[i++]); i++; blocks.push(<pre key={i}><code>{content.join('\n')}</code></pre>); continue; }
    if (line.includes('|') && i + 1 < lines.length && cells(lines[i + 1]).every(value => /^:?-{3,}:?$/.test(value))) {
      const headers = cells(line); const rows: string[][] = []; i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(cells(lines[i++]));
      blocks.push(<div className="answer-table-scroll" key={i}><table><thead><tr>{headers.map((header, j) => <th key={j}>{inline(header)}</th>)}</tr></thead><tbody>{rows.map((row, j) => <tr key={j}>{headers.map((_, k) => <td key={k}>{inline(row[k] || '')}</td>)}</tr>)}</tbody></table></div>); continue;
    }
    const heading = line.match(/^#{1,6}\s+(.+)/); if (heading) { blocks.push(<h3 key={i}>{inline(heading[1])}</h3>); i++; continue; }
    const list = line.match(/^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)/);
    if (list) { const ordered = /^\s*\d/.test(line); const items: string[] = []; while (i < lines.length) { const match = lines[i].match(ordered ? /^\s*\d+[.)]\s+(.+)/ : /^\s*[-*+]\s+(.+)/); if (!match) break; items.push(match[1]); i++; } const contents = items.map((item, j) => <li key={j}>{inline(item)}</li>); blocks.push(ordered ? <ol key={i}>{contents}</ol> : <ul key={i}>{contents}</ul>); continue; }
    blocks.push(<p key={i}>{inline(line)}</p>); i++;
  }
  return <div className="formatted-answer">{blocks}</div>;
}
