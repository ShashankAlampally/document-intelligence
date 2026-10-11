import { useState } from 'react';
import { ExtractIcon as FileText, LoadingIcon } from '../../components/icons';
import type { ChatFolder } from '../folder-upload/FolderQueue';

export function ExtractFolder({ folders, busy, onExtract }: {
  folders: ChatFolder[]; busy: boolean; onExtract: (folder: ChatFolder) => void;
}) {
  const [selected, setSelected] = useState('');
  const folder = folders.find(item => item.id === selected) || folders[0];
  return <section className="extraction-action" aria-label="Extract bid details">
    <p className="action-scope">Extract 20 fields from one bid.</p>
    <div className="extraction-controls"><select aria-label="Folder to extract" value={folder?.id || ''} disabled={busy} onChange={event => setSelected(event.target.value)}>{folders.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button className="secondary-button" disabled={busy || !folder?.discoveryId} onClick={() => folder && onExtract(folder)}><>{busy ? <LoadingIcon size={18} className="loading-icon" aria-hidden="true"/> : <FileText size={18} aria-hidden="true"/>}</>{busy ? 'Request in progress…' : 'Extract fields'}</button></div>
  </section>;
}
