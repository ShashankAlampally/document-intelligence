import { useRef, type InputHTMLAttributes } from 'react';
import { FolderIcon as FolderOpen, UploadIcon as Upload, PdfIcon as FileText, ArrowRight, CloseIcon as X } from '../../components/icons';

export const supportedDocument = (file: File) => /\.(pdf|html?)$/i.test(file.name);
export function FolderUpload({ files, onSelect, onProcess, onClear, busy }: {
  files: File[]; onSelect: (files: File[], skipped: number) => void; onProcess: () => void; onClear: () => void; busy: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const folderAttributes = { webkitdirectory: '', directory: '' } as InputHTMLAttributes<HTMLInputElement>;
  const folderName = files[0]?.webkitRelativePath.split('/')[0] || 'Selected documents';
  return <section className="upload-card">
    <input {...folderAttributes} ref={input} type="file" multiple className="hidden" onChange={event => {
      const selected = Array.from(event.target.files || []);
      onSelect(selected.filter(supportedDocument), selected.filter(file => !supportedDocument(file)).length);
      event.target.value = '';
    }} aria-label="Choose a bid folder" />
    {files.length === 0 ? <>
      <div className="folder-illustration"><FolderOpen size={39} strokeWidth={1.4}/><span><Upload size={15}/></span></div>
      <h2>Start with your bid folder</h2>
      <p>Select a folder containing the RFP, addendums, specifications,<br className="desktop-break"/> and supporting documents. We’ll keep them together in this chat.</p>
      <button className="primary-button" onClick={() => input.current?.click()}><FolderOpen size={17}/> Choose folder <ArrowRight size={16}/></button>
      <div className="upload-footnote">PDF, HTML & HTM files · Includes subfolders</div>
    </> : <>
      <div className="selected-folder-heading"><div><span className="eyebrow">SELECTED FOLDER</span><h2>{folderName}</h2></div><button className="icon-button" onClick={onClear} disabled={busy} aria-label="Clear selected folder"><X size={18}/></button></div>
      <p>{files.length} supported document{files.length === 1 ? '' : 's'} · Review before processing</p>
      <ul className="file-review">{files.map(file => <li key={file.webkitRelativePath || file.name}><FileText size={17}/><span title={file.webkitRelativePath}>{file.webkitRelativePath || file.name}</span><small>{(file.size / 1024).toFixed(0)} KB</small></li>)}</ul>
      <button className="primary-button" disabled={busy} onClick={onProcess}>{busy ? 'Processing documents…' : 'Process folder'} {!busy && <ArrowRight size={16}/>}</button>
    </>}
  </section>;
}
