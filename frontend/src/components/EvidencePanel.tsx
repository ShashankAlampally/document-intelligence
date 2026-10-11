import { useEffect, useRef, useState } from 'react';
import { CloseIcon as X, CopyIcon as Copy, ChevronLeft, ChevronRight, ExternalLink, DetailsIcon as Info, EvidenceIcon } from './icons';
import type { Citation } from '../lib/api';
import { DisclosureLabel } from './DisclosureLabel';
import { SourceHeader } from './SourceCards';

export function EvidencePanel({ sources, index, original, onNavigate, onClose }: {
  sources: Citation[]; index: number; original?: File; onNavigate: (index: number) => void; onClose: () => void;
}) {
  const source = sources[index];
  const [copied, setCopied] = useState('');
  const [url, setUrl] = useState('');
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    return () => previous?.focus();
  }, []);
  useEffect(() => {
    setCopied('');
    if (!original || !/\.pdf$/i.test(original.name)) { setUrl(''); return; }
    const objectUrl = URL.createObjectURL(original); setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [original, index]);
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setCopied('Copied'); }
    catch { setCopied('Copy unavailable. Select the text to copy it.'); }
  }
  return <aside className="evidence-panel" aria-label="Supporting evidence" onKeyDown={event => { if (event.key === 'Escape') onClose(); }}>
    <div className="panel-heading"><h2><EvidenceIcon size={18} aria-hidden="true"/>Supporting evidence</h2><button ref={closeButton} className="icon-button" aria-label="Close evidence" onClick={onClose}><X size={20}/></button></div>
    <SourceHeader source={source} number={index + 1}/>
    <div className="evidence-navigation"><button className="icon-button" disabled={index === 0} aria-label="Previous source" onClick={() => onNavigate(index - 1)}><ChevronLeft size={19}/></button><span>Source {index + 1} of {sources.length}</span><button className="icon-button" disabled={index === sources.length - 1} aria-label="Next source" onClick={() => onNavigate(index + 1)}><ChevronRight size={19}/></button></div>
    {source.table_id && <span className="table-badge">{source.table_complete === true ? 'Complete table' : source.table_complete === false ? 'Partial table' : 'Table evidence'}</span>}
    <span className="eyebrow">EXACT RETRIEVED PASSAGE</span><blockquote className="evidence-passage">{source.text}</blockquote>
    <div className="evidence-actions"><button className="secondary-button" onClick={() => void copy(source.text)}><Copy size={17} aria-hidden="true"/> Copy passage</button>{url && <a href={`${url}${source.page ? `#page=${source.page}` : ''}`} target="_blank" rel="noopener noreferrer"><ExternalLink size={17} aria-hidden="true"/> Open original PDF</a>}</div><p role="status" className="muted">{copied}</p>
    <details className="technical-details"><summary><DisclosureLabel icon={Info}>Technical details</DisclosureLabel></summary><dl>{Object.entries({ 'Upload ID': source.discovery_id, 'Chunk ID': source.chunk_id, 'Vector similarity': source.similarity, 'Retrieval score': source.retrieval_score, 'Reranker score': source.rerank_score, 'Keyword score': source.keyword_score }).filter(([, value]) => value !== undefined && value !== null).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{typeof value === 'number' ? value.toFixed(4) : value}</dd></div>)}</dl>{source.discovery_id && <button className="evidence-button" onClick={() => void copy(source.discovery_id!)}><Copy size={16} aria-hidden="true"/>Copy upload ID</button>}<p className="muted">Retrieval scores describe matching, not answer confidence.</p></details>
  </aside>;
}
