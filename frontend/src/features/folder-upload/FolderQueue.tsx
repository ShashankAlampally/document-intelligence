import { useRef, type InputHTMLAttributes } from 'react';
import { FolderIcon as FolderOpen, UploadIcon as FolderPlus, PdfIcon as FileText, CloseIcon as X, ArrowRight, LoadingIcon as LoaderCircle, QueuedIcon, ReadyIcon, ErrorIcon, DocumentsIcon, HtmlIcon } from '../../components/icons';
import { DisclosureLabel } from '../../components/DisclosureLabel';
import { supportedDocument } from './FolderUpload';
import type { QueuedFolder } from '../../lib/sequential-folder-processing';
import { hasParsingNotices } from './processing-notices';

export type ChatFolder = QueuedFolder & {
  status: 'selected' | 'processing' | 'ready' | 'failed';
  error?: string;
  processingDetail?: string;
  documentNames?: string[];
};

export function FolderQueue({ folders, busy, onAdd, onRemove, onProcess }: {
  folders: ChatFolder[];
  busy: boolean;
  onAdd: (files: File[], skipped: number) => void;
  onRemove: (id: string) => void;
  onProcess: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const attributes = { webkitdirectory: '', directory: '' } as InputHTMLAttributes<HTMLInputElement>;
  const unfinished = folders.filter(folder => !folder.discoveryId);
  return <section className="upload-card folder-queue">
    <input {...attributes} ref={input} type="file" multiple className="hidden" aria-label="Add a bid folder" disabled={busy} onChange={event => {
      const files = Array.from(event.target.files || []);
      onAdd(files.filter(supportedDocument), files.filter(file => !supportedDocument(file)).length);
      event.target.value = '';
    }}/>
    <div className="selected-folder-heading"><span className="heading-icon"><FolderPlus size={22} aria-hidden="true"/></span><div><h2>{folders.length ? `${folders.length} bid folder${folders.length === 1 ? '' : 's'}` : 'Add bid documents'}</h2></div></div>
    <p>Each folder is one bid. Include its RFP, addenda, and supporting documents.</p>
    {folders.map(folder => <div key={folder.id} className="queued-folder">
      <div className="queued-folder-heading"><FolderOpen size={18} aria-hidden="true"/><strong>{folder.name}</strong><span className="queue-status">{folder.status === 'ready' ? <ReadyIcon size={16} aria-hidden="true"/> : folder.status === 'failed' ? <ErrorIcon size={16} aria-hidden="true"/> : folder.status === 'processing' ? <LoaderCircle size={16} className="loading-icon" aria-hidden="true"/> : <QueuedIcon size={16} aria-hidden="true"/>}{folder.status === 'selected' ? 'Queued' : folder.status === 'ready' ? 'Indexed' : folder.status === 'failed' ? 'Failed' : 'Processing…'}</span><button className="icon-button" disabled={busy || !!folder.discoveryId} onClick={() => onRemove(folder.id)} aria-label={`Remove ${folder.name}`}><X size={16}/></button></div>
      <details><summary><DisclosureLabel icon={DocumentsIcon}>{folder.documentNames?.length ?? folder.files.length} documents</DisclosureLabel></summary><ul className="file-review">{folder.documentNames?.map(name => <li key={name}><>{/\.html?$/i.test(name) ? <HtmlIcon size={16} aria-hidden="true"/> : <FileText size={16} aria-hidden="true"/>}</><span>{name}</span></li>)}{folder.files.map(file => <li key={file.webkitRelativePath || file.name}><>{/\.html?$/i.test(file.name) ? <HtmlIcon size={16} aria-hidden="true"/> : <FileText size={16} aria-hidden="true"/>}</><span>{file.webkitRelativePath || file.name}</span><small>{(file.size / 1024).toFixed(0)} KB</small></li>)}</ul></details>
      {folder.discoveryId && <p className="folder-indexed-note">{hasParsingNotices(folder.processingDetail) ? 'Indexed · review processing notices' : 'Ready for questions and search'}</p>}
      {hasParsingNotices(folder.processingDetail) && <p className="notice-banner">{folder.processingDetail}</p>}
      {folder.error && <p className="error-banner" role="alert">{folder.error}</p>}
    </div>)}
    <div className="queue-actions"><button type="button" className={folders.length ? "secondary-button" : "primary-button"} disabled={busy || folders.length >= 20} onClick={() => input.current?.click()}><FolderPlus size={17} aria-hidden="true"/> {folders.length ? 'Add another folder' : 'Choose folder'}</button>{folders.length > 0 && <button className="primary-button" onClick={onProcess} disabled={busy || unfinished.length === 0}>{busy && <LoaderCircle size={17} className="loading-icon" aria-hidden="true"/>}{busy ? 'Processing folders…' : folders.some(folder => folder.status === 'failed') ? 'Retry remaining folders' : 'Process documents'}{!busy && <ArrowRight size={16}/>}</button>}</div>
    <div className="upload-footnote">PDF, HTML & HTM · Up to 20 folders · Includes subfolders</div>
  </section>;
}
