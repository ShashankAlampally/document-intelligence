import { useEffect, useRef, useState } from 'react';
import { CloseIcon, HelpIcon, WarningIcon } from './icons';
import './usage-guide.css';

export function UsageGuide({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const [scroll, setScroll] = useState({ height: 100, top: 0 });
  function syncScroll() {
    const element = content.current;
    if (!element) return;
    const height = Math.min(100, element.clientHeight / Math.max(1, element.scrollHeight) * 100);
    const range = element.scrollHeight - element.clientHeight;
    setScroll({ height, top: range > 0 ? element.scrollTop / range * (100 - height) : 0 });
  }
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
    syncScroll();
    const observer = new ResizeObserver(syncScroll);
    if (content.current) observer.observe(content.current);
    return () => observer.disconnect();
  }, [open]);

  return <dialog ref={dialog} className="usage-guide" aria-labelledby="usage-guide-title" onCancel={onClose} onClose={onClose}>
    <header className="guide-heading">
      <div><HelpIcon size={22} aria-hidden="true"/><h2 id="usage-guide-title">How to use RFP Intelligence</h2></div>
      <button type="button" className="icon-button" aria-label="Close guide" onClick={onClose} autoFocus><CloseIcon size={20}/></button>
    </header>
    <div className="guide-scroll-area">
    <div ref={content} id="guide-scroll-content" className="guide-content" tabIndex={0} aria-label="Usage instructions" onScroll={syncScroll}>
      <p className="guide-intro">Process your bid documents, ask questions, find evidence, and extract bid fields.</p>
      <section aria-labelledby="guide-workflow">
        <h3 id="guide-workflow">Getting started</h3>
        <ol className="guide-steps">
          <li><strong>Add your folders.</strong> Select one or more folders, review the files, then process them. Folders are processed sequentially. You can also open an already indexed folder.</li>
          <li><strong>Wait until the bids are ready.</strong> PDF indexing includes generating 1,024-dimensional embeddings locally, so it can take a little time. Larger documents or folders may take several minutes, depending on your computer. Check any processing warnings.</li>
          <li><strong>Choose an action.</strong><dl className="guide-actions">
            <div><dt>Ask</dt><dd>Get an answer across the folders in your workspace. Try “What is the submission deadline?”</dd></div>
            <div><dt>Search</dt><dd>Find matching document passages without a Groq model call.</dd></div>
            <div><dt>Extract</dt><dd>Select one folder to extract the 20 bid fields. On Groq’s free tier, allow approximately 7–9 minutes; larger documents or rate limits may take longer. Follow the progress; a partial draft is not a final result.</dd></div>
          </dl></li>
          <li><strong>Check the evidence.</strong> Open the source cards to review the file, page or section, and supporting passage. Use Documents to browse the workspace files.</li>
        </ol>
      </section>
      <section aria-labelledby="guide-setup" className="guide-section">
        <h3 id="guide-setup">Groq setup & execution</h3>
        <p>Ask and extraction require a Groq API key. Set <code>RFP_GROQ_API_KEY</code> in the backend <code>.env</code> file, then restart the backend. Keep the key on the backend; do not paste it into a chat.</p>
        <p>A free Groq account can work. Its lower usage limits can make extraction wait or fail after retries. Paid accounts have higher limits, but execution time also depends on the documents, your computer, and the configured request pacing.</p>
        <p>Folder processing and Search do not require a Groq key. Ask and extraction require internet access and send selected document passages to Groq.</p>
        <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">Create a Groq key</a>
      </section>
      <section aria-labelledby="guide-limits" className="guide-section">
        <h3 id="guide-limits"><WarningIcon size={18} aria-hidden="true"/>Things to know</h3>
        <ul>
          <li><strong>Documents:</strong> PDF, HTML and HTM only.</li>
          <li><strong>Default upload limits:</strong> 200 files per folder, 50 MB per file, and 200 MB per folder. A workspace supports up to 20 folders.</li>
          <li><strong>Questions are independent:</strong> Previous messages are not used as context. Include the details needed in each question.</li>
          <li><strong>Refresh clears chats:</strong> Workspace messages and selections are kept in browser memory. Successfully opened or processed bid IDs and folder names are remembered on this browser. Use “Open an existing bid” to select a saved bid after refreshing. The backend index must still exist.</li>
          <li><strong>Local demo:</strong> This app has no user accounts or access controls. Use it on your own computer.</li>
        </ul>
      </section>
    </div>
    <div className="guide-scroll-track" aria-hidden="true" onPointerDown={event => {
      const element = content.current;
      if (!element || scroll.height >= 100) return;
      event.preventDefault();
      const track = event.currentTarget;
      const bounds = track.getBoundingClientRect();
      const thumbHeight = bounds.height * scroll.height / 100;
      const thumbTop = bounds.height * scroll.top / 100;
      const position = event.clientY - bounds.top;
      const offset = position >= thumbTop && position <= thumbTop + thumbHeight ? position - thumbTop : thumbHeight / 2;
      const move = (clientY: number) => {
        const ratio = Math.max(0, Math.min(1, (clientY - bounds.top - offset) / (bounds.height - thumbHeight)));
        element.scrollTop = ratio * (element.scrollHeight - element.clientHeight);
      };
      move(event.clientY);
      track.setPointerCapture(event.pointerId);
      track.onpointermove = moveEvent => move(moveEvent.clientY);
      const stop = () => { track.onpointermove = null; track.onpointerup = null; track.onpointercancel = null; };
      track.onpointerup = stop;
      track.onpointercancel = stop;
    }}><div className="guide-scroll-thumb" style={{ height: `${scroll.height}%`, top: `${scroll.top}%` }}/></div>
    </div>
    <footer className="guide-footer"><span>Reopen this guide from “How to use” at the top.</span><button type="button" className="primary-button" onClick={onClose}>Get started</button></footer>
  </dialog>;
}
