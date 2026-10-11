import { useState } from 'react';
import { FolderIcon as FolderOpen, PdfIcon as FileText, HtmlIcon } from './icons';
import { DisclosureLabel } from './DisclosureLabel';
import type { ChatFolder } from '../features/folder-upload/FolderQueue';
export function DocumentList({ folders }: { folders: ChatFolder[] }) {
  const [filter, setFilter] = useState('');
  return <><input className="document-filter" aria-label="Filter documents by filename" placeholder="Filter documents…" value={filter} onChange={event => setFilter(event.target.value)}/>{folders.map(folder => {
    if (folder.documentNames) {
      const names = folder.documentNames.filter(name => name.toLowerCase().includes(filter.toLowerCase()));
      if (!names.length) return null;
      return <details className="document-folder" key={folder.id} open={filter ? true : undefined}>
        <summary><DisclosureLabel icon={FolderOpen}><strong>{folder.name}</strong><span className="document-count">{names.length}</span></DisclosureLabel></summary>
        {names.map(name => <div className="document-item" key={name}><>{/\.html?$/i.test(name) ? <HtmlIcon size={17} aria-hidden="true"/> : <FileText size={17} aria-hidden="true"/>}</>
          <div><strong>{name}</strong><small>Indexed document</small></div></div>)}
      </details>;
    }
    const files = folder.files.filter(file => (file.webkitRelativePath || file.name).toLowerCase().includes(filter.toLowerCase()));
    if (!files.length) return null;
    return <details className="document-folder" key={folder.id} open={filter ? true : undefined}><summary><DisclosureLabel icon={FolderOpen}><strong>{folder.name}</strong><span className="document-count">{files.length}</span></DisclosureLabel></summary>{files.map(file => <div className="document-item" key={file.webkitRelativePath || file.name}><>{/\.html?$/i.test(file.name) ? <HtmlIcon size={17} aria-hidden="true"/> : <FileText size={17} aria-hidden="true"/>}</><div><strong title={file.webkitRelativePath}>{file.name}</strong><small>{file.name.split('.').pop()?.toUpperCase()} · {(file.size / 1024).toFixed(0)} KB</small></div></div>)}</details>;
  })}{filter && !folders.some(folder => folder.files.some(file => (file.webkitRelativePath || file.name).toLowerCase().includes(filter.toLowerCase())) || folder.documentNames?.some(name => name.toLowerCase().includes(filter.toLowerCase()))) && <p className="muted">No matching documents.</p>}</>;
}
