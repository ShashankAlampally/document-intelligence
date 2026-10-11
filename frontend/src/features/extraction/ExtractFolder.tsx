import { useState } from 'react';
import { ExtractIcon as FileText, LoadingIcon } from '../../components/icons';
import type { ChatFolder } from '../folder-upload/FolderQueue';

export function ExtractFolder({ folders, busy, onExtract }: {
  folders: ChatFolder[]; busy: boolean; onExtract: (folder: ChatFolder) => void;
}) {
  const [selected, setSelected] = useState('');
  const folder = folders.find(item => item.id === selected) || folders[0];
  const resumable = folder?.discoveryId && localStorage.getItem(`extraction-job:${folder.discoveryId}`);
  return <section className="extraction-action" aria-label="Extract bid details">
    <p className="action-scope">Extract 20 fields from one bid. Progress is saved; Groq limits may pause the run.</p>
    <p className="action-scope">On Groq’s free tier, allow approximately 7–9 minutes. This is an estimate; larger documents or rate limits may take longer.</p>
    <div className="extraction-controls"><select aria-label="Folder to extract" value={folder?.id || ''} disabled={busy} onChange={event => setSelected(event.target.value)}>{folders.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button className="secondary-button" disabled={busy || !folder?.discoveryId} onClick={() => folder && onExtract(folder)}><>{busy ? <LoadingIcon size={18} className="loading-icon" aria-hidden="true"/> : <FileText size={18} aria-hidden="true"/>}</>{busy ? 'Request in progress…' : resumable ? 'Resume extraction' : 'Extract fields'}</button></div>
  </section>;
}
