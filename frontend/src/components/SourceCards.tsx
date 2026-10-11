import { useState } from 'react';
import { PdfIcon as FileText, HtmlIcon, EvidenceIcon, ChevronDown } from './icons';
import type { Citation } from '../lib/api';
export function SourceHeader({ source, number }: { source: Citation; number: number }) {
  return <div className="citation-header"><span className="source-number">{number}</span><>{/\.html?$/i.test(source.file) ? <HtmlIcon size={17} aria-hidden="true"/> : <FileText size={17} aria-hidden="true"/>}</><div className="source-identity"><strong>{source.file}</strong><span>{source.folder_name || 'Uploaded folder'}</span></div><span className="page-badge">{source.page ? `Page ${source.page}` : source.section ? `Section: ${source.section}` : 'Page unavailable'}</span></div>;
}
export function SourceCards({ sources, search, onOpen }: { sources: Citation[]; search: boolean; onOpen: (index: number) => void }) {
  const [expanded, setExpanded] = useState(false);
  if (!sources.length) return null;
  return <section className={`source-cards ${search ? '' : 'compact-sources'}`} aria-label={search ? 'Matching passages' : 'Supporting sources'}><h4>{search ? 'Matching passages' : 'Supporting sources'} <span>{sources.length}</span></h4>{(expanded ? sources : sources.slice(0, 3)).map((source, i) => <article className="source-card" key={`${source.discovery_id}:${source.chunk_id || i}`}><SourceHeader source={source} number={i + 1}/>{search && <p className="passage-preview">{source.text}</p>}{source.table_id && <span className="table-badge">{source.table_complete === true ? 'Complete table' : source.table_complete === false ? 'Partial table' : 'Table evidence'}</span>}<button className="evidence-button" onClick={() => onOpen(i)}><EvidenceIcon size={17} aria-hidden="true"/>View evidence</button></article>)}{sources.length > 3 && <button className="evidence-button" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}><ChevronDown size={16} className={expanded ? 'expanded-icon' : ''} aria-hidden="true"/>{expanded ? 'Show fewer sources' : `View all ${sources.length} sources`}</button>}</section>;
}
