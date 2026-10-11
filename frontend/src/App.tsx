import { runExtraction } from './features/extraction/run-extraction';
import { UsageGuide } from './components/UsageGuide';
import { HelpIcon } from './components/icons';
import { readSavedBids, rememberBid, savedBidsKey, type SavedBid } from './lib/saved-bids';
import { useEffect, useRef, useState } from 'react';
import { NewWorkspaceIcon as Plus, WorkspaceIcon, AskIcon as MessageSquare, SearchIcon as Search, ExtractIcon as FileText, PanelLeftClose, PanelLeftOpen, FolderIcon as FolderOpen, DocumentsIcon, DiscoveryIcon as Fingerprint, WarningIcon as TriangleAlert, ReadyIcon as CheckCircle2, LoadingIcon as LoaderCircle, EmptyIcon } from './components/icons';
import { DisclosureLabel } from './components/DisclosureLabel';
import { ExistingFolder } from './features/existing-folder/ExistingFolder';
import { FolderQueue, type ChatFolder } from './features/folder-upload/FolderQueue';
import { processFoldersSequentially } from './lib/sequential-folder-processing';
import { ExtractFolder } from './features/extraction/ExtractFolder';
import { extractionRequest } from './features/extraction/extraction-request';
import { hasParsingNotices } from './features/folder-upload/processing-notices';
import { ExtractionContent } from './components/ExtractionContent';
import { AnswerContent } from './components/AnswerContent';
import { SourceCards } from './components/SourceCards';
import { DocumentList } from './components/DocumentList';
import { EvidencePanel } from './components/EvidencePanel';
import { getProcessingJob, queryDocuments, uploadFolder, type Citation, type Reply, type IndexedFolder } from './lib/api';

type Message = { id: string; question: string; mode: 'ask' | 'search' | 'extract'; folders: string[]; reply?: Reply; error?: string; progress?: string; draft?: string };
export type Chat = { id: string; name: string; folders: ChatFolder[]; status: 'empty' | 'selected' | 'processing' | 'ready'; error?: string; notice?: string; messages: Message[] };
const newChat = (): Chat => ({ id: crypto.randomUUID(), name: 'New bid chat', folders: [], status: 'empty', messages: [] });

export default function App({ initialChats }: { initialChats?: Chat[] } = {}) {
  const [chats, setChats] = useState<Chat[]>(() => initialChats || [newChat()]);
  const [activeId, setActiveId] = useState('');
  const [mode, setMode] = useState<'ask' | 'search' | 'extract'>('ask');
  const [question, setQuestion] = useState('');
  const [source, setSource] = useState<{ sources: Citation[]; index: number } | null>(null);
  const [sidebar, setSidebar] = useState(false);
  const [guideOpen, setGuideOpen] = useState(true);
  const [savedBids, setSavedBids] = useState<SavedBid[]>(() => {
    try { return readSavedBids(window.localStorage); } catch { return []; }
  });
  const [storageNotice, setStorageNotice] = useState('');
  useEffect(() => {
    try { window.localStorage.setItem(savedBidsKey, JSON.stringify(savedBids)); setStorageNotice(''); }
    catch { setStorageNotice('Browser storage is unavailable. Bid IDs will only be remembered until you refresh.'); }
  }, [savedBids]);
  const [documentsVisible, setDocumentsVisible] = useState(false);
  const [pending, setPending] = useState<string[]>([]);
  const mounted = useRef(true);
  const conversationEnd = useRef<HTMLDivElement>(null);
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const chat = chats.find(item => item.id === activeId) || chats[0];
  const selectedIds = chat.folders.flatMap(folder => folder.discoveryId ? [folder.discoveryId] : []);
  const hasNotices = chat.folders.some(folder => hasParsingNotices(folder.processingDetail));
  const fileCount = chat.folders.reduce((total, folder) => total + (folder.documentNames?.length ?? folder.files.length), 0);
  const processingChats = useRef(new Set<string>());
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    const input = questionInput.current;
    if (input) { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 100)}px`; }
  }, [question, mode]);
  useEffect(() => {
    const mobile = window.matchMedia('(max-width: 760px)');
    const collapse = () => { if (mobile.matches) { setSidebar(false); setDocumentsVisible(false); } };
    mobile.addEventListener('change', collapse);
    return () => mobile.removeEventListener('change', collapse);
  }, []);
  useEffect(() => { conversationEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [chat.messages.length, pending.length]);
  const updateChat = (id: string, patch: Partial<Chat>) => setChats(current => current.map(item => item.id === id ? { ...item, ...patch } : item));
  function selectChat(id: string) { setActiveId(id); setQuestion(''); setSource(null); if (window.innerWidth <= 760) setSidebar(false); }
  function createChat() { const next = newChat(); setChats(current => [...current, next]); selectChat(next.id); }
  function addFolder(files: File[], skipped: number) {
    if (!files.length) { updateChat(chat.id, { error: 'No PDF or HTML documents were found in this folder.' }); return; }
    if (chat.folders.length >= 20) return;
    const signature = (items: File[]) => items.map(file => `${file.webkitRelativePath}:${file.size}:${file.lastModified}`).sort().join('|');
    if (chat.folders.some(folder => signature(folder.files) === signature(files))) {
      updateChat(chat.id, { error: 'This folder is already queued in this chat.' }); return;
    }
    const name = files[0].webkitRelativePath.split('/')[0] || 'Selected documents';
    const folders: ChatFolder[] = [...chat.folders, { id: crypto.randomUUID(), name, files, status: 'selected' }];
    updateChat(chat.id, { folders, name: folders.map(folder => folder.name).join(' + '), status: 'selected', error: undefined,
      notice: skipped ? `${skipped} unsupported files skipped.` : undefined });
  }
  function attachFolder(saved: IndexedFolder) {
    setSavedBids(current => rememberBid(current, { discoveryId: saved.discovery_id, name: saved.folder_name }));
    const target = chat.id;
    setChats(current => current.map(item => {
      if (item.id !== target || item.folders.some(folder => folder.discoveryId === saved.discovery_id)) return item;
      const folder: ChatFolder = {
        id: crypto.randomUUID(), name: saved.folder_name, files: [], status: 'ready',
        discoveryId: saved.discovery_id, documentNames: saved.files.map(file => file.relative_path),
        processingDetail: `Indexed ${saved.stored_chunks} chunks. ${saved.files.reduce((total, file) => total + file.issues.length, 0)} parsing notices.`,
      };
      const folders = [...item.folders, folder];
      return { ...item, folders, name: folders.map(value => value.name).join(' + '),
        status: folders.every(value => value.discoveryId) ? 'ready' : 'selected', error: undefined };
    }));
  }
  function removeFolder(id: string) {
    const folders = chat.folders.filter(folder => folder.id !== id);
    updateChat(chat.id, { folders, name: folders.map(folder => folder.name).join(' + ') || 'New bid chat', status: folders.length ? 'selected' : 'empty', error: undefined });
  }
  async function processFolder() {
    const id = chat.id;
    if (processingChats.current.has(id)) return;
    processingChats.current.add(id);
    updateChat(id, { status: 'processing', error: undefined });
    try {
      await processFoldersSequentially(chat.folders, async folder => {
        let job = folder.jobId ? await getProcessingJob(folder.jobId) : await uploadFolder(folder.files);
        setChats(current => current.map(item => item.id === id ? { ...item, folders: item.folders.map(value => value.id === folder.id ? { ...value, jobId: job.id } : value) } : item));
        const deadline = Date.now() + 10 * 60 * 1000;
        while (job.status === 'processing' && Date.now() < deadline && mounted.current) {
          await new Promise(resolve => setTimeout(resolve, 1500));
          if (!mounted.current) throw new Error('Workspace closed.');
          job = await getProcessingJob(job.id);
        }
        if (job.status === 'failed') setChats(current => current.map(item => item.id === id ? { ...item, folders: item.folders.map(value => value.id === folder.id ? { ...value, jobId: undefined } : value) } : item));
        if (job.status !== 'ready' || !job.discovery_id) throw new Error(job.detail || 'Processing did not return a discovery ID. Please retry.');
        const processingDetail = job.detail;
        setSavedBids(current => rememberBid(current, { discoveryId: job.discovery_id!, name: folder.name }));
        setChats(current => current.map(item => item.id === id ? { ...item, folders: item.folders.map(value => value.id === folder.id ? { ...value, processingDetail } : value) } : item));
        return job.discovery_id;
      }, (folderId, progress) => {
        if (!mounted.current) return;
        setChats(current => current.map(item => item.id === id ? { ...item, folders: item.folders.map(folder => folder.id === folderId ? {
          ...folder, status: progress.status,
          discoveryId: progress.status === 'ready' ? progress.discoveryId : folder.discoveryId,
          error: progress.status === 'failed' ? progress.error : undefined,
        } : folder) } : item));
      });
      if (mounted.current) updateChat(id, { status: 'ready', error: undefined });
    } catch (error) { if (mounted.current) updateChat(id, { status: 'selected', error: error instanceof Error ? error.message : 'Unable to process folders.' }); }
    finally { processingChats.current.delete(id); }
  }
  async function submitRequest(request: string, discoveryIds: string[], names: string[], messageMode: 'ask' | 'search' | 'extract') {
    if (!request.trim() || chat.status !== 'ready' || !discoveryIds.length || pending.includes(chat.id)) return;
    const id = chat.id;
    const message: Message = { id: crypto.randomUUID(), question: request.trim(), mode: messageMode, folders: names };
    setSource(null);
    setPending(current => [...current, id]);
    setChats(current => current.map(item => item.id === id ? { ...item, messages: [...item.messages, message] } : item));
    try {
      const reply = messageMode === 'extract'
        ? await runExtraction(discoveryIds[0], job => {
          setChats(current => current.map(item => item.id === id ? { ...item, messages: item.messages.map(entry => entry.id === message.id ? {
            ...entry, progress: job.detail,
            draft: Object.entries(job.fields).map(([name, field]) => `${name}: ${field.value || field.notes || 'Not found in documents'}`).join('\n'),
          } : entry) } : item));
        })
        : await queryDocuments(discoveryIds, message.question, messageMode);
      setChats(current => current.map(item => item.id === id ? { ...item, messages: item.messages.map(entry => entry.id === message.id ? { ...entry, reply } : entry) } : item));
    } catch (error) {
      setChats(current => current.map(item => item.id === id ? { ...item, messages: item.messages.map(entry => entry.id === message.id ? { ...entry, error: error instanceof Error ? error.message : 'Unable to get a response.' } : entry) } : item));
    } finally { setPending(current => current.filter(item => item !== id)); }
  }
  async function submitQuestion() {
    if (!question.trim() || chat.status !== 'ready' || pending.includes(chat.id) || mode === 'extract') return;
    const request = question;
    setQuestion('');
    await submitRequest(request, selectedIds, chat.folders.map(folder => folder.name), mode);
  }
  function extractFolder(folder: ChatFolder) {
    if (!folder.discoveryId) return;
    const request = extractionRequest(folder.discoveryId);
    void submitRequest(request.question, request.discoveryIds, [folder.name], 'extract');
  }
  function findOriginal(citation: Citation): File | undefined {
    const folders = chat.folders.filter(folder => folder.discoveryId === citation.discovery_id);
    const matches = folders.flatMap(folder => folder.files).filter(file => file.name === citation.file || file.webkitRelativePath === citation.file);
    return matches.length === 1 ? matches[0] : undefined;
  }
  return <div className={`app-shell simple-workspace ${sidebar ? '' : 'sidebar-hidden'} ${source ? 'evidence-open' : ''} ${chat.status === 'ready' && documentsVisible ? 'folders-open' : ''}`}>
    {sidebar && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebar(false)}/>}
    {sidebar && <aside className="sidebar">
      <div className="sidebar-title">Bid workspaces</div>
      <button className="new-chat-button" onClick={createChat}><Plus size={18}/> New workspace</button>
      <nav aria-label="Bid chats">{chats.map(item => <button key={item.id} className={`chat-link ${item.id === chat.id ? 'active' : ''}`} onClick={() => selectChat(item.id)}>
        <WorkspaceIcon size={18} aria-hidden="true"/><span>{item.name}<small>{item.folders.length} folders · {item.status === 'ready' ? 'Ready' : item.status === 'processing' ? 'Processing' : 'Not processed'}</small></span>
      </button>)}</nav>
      <p className="session-note">Workspaces clear on refresh.</p>
    </aside>}
    <main className="workspace">
      <header className="topbar">
        <div className="breadcrumb"><button className="icon-button" aria-label={sidebar ? 'Hide sidebar' : 'Show sidebar'} onClick={() => setSidebar(value => !value)}>{sidebar ? <PanelLeftClose size={19}/> : <PanelLeftOpen size={19}/>}</button><WorkspaceIcon size={20} className="app-title-icon" aria-hidden="true"/><strong>RFP Intelligence</strong></div>
        <div className="topbar-actions">
          <button type="button" className="guide-toggle" aria-haspopup="dialog" onClick={() => setGuideOpen(true)}><HelpIcon size={18} aria-hidden="true"/>How to use</button>
          {chat.status === 'ready' && <button className="documents-toggle" aria-label="Toggle chat folders" aria-pressed={documentsVisible && !source} onClick={() => { setSource(null); setDocumentsVisible(value => !value); }}><DocumentsIcon size={18} aria-hidden="true"/><span>Documents ({fileCount})</span></button>}
          <span className={`status-pill ${chat.status === 'ready' ? 'ready' : ''}`}>{chat.status === 'ready' ? <CheckCircle2 size={15} aria-hidden="true"/> : chat.status === 'processing' ? <LoaderCircle size={15} className="loading-icon" aria-hidden="true"/> : <EmptyIcon size={16} aria-hidden="true"/>}{chat.status === 'ready' ? `${selectedIds.length} bids ready` : chat.status === 'processing' ? 'Processing' : 'No bids ready'}</span>
        </div>
      </header>
      <div className="workspace-body">
        <div className="conversation">
          {chat.status !== 'ready' ? <div className="setup-area">
            <FolderQueue folders={chat.folders} busy={chat.status === 'processing'} onAdd={addFolder} onRemove={removeFolder} onProcess={processFolder}/>
          </div> : <>
            <section className="bid-summary" aria-label="Bids in this workspace">
              <h1>Your bids</h1>
              <div className="bid-chips">{chat.folders.map(folder => <span className="bid-chip" key={folder.id}><FolderOpen size={15}/>{folder.name}<small>{folder.documentNames?.length ?? folder.files.length} {(folder.documentNames?.length ?? folder.files.length) === 1 ? 'document' : 'documents'}</small></span>)}</div>
            </section>
            {hasNotices && <details className="processing-summary" open><summary><DisclosureLabel icon={TriangleAlert}>Processing warnings</DisclosureLabel></summary>{chat.folders.filter(folder => hasParsingNotices(folder.processingDetail)).map(folder => <p key={folder.id} className="notice-banner" role="status"><strong>{folder.name}:</strong> {folder.processingDetail}</p>)}</details>}
          </>}
          <ExistingFolder key={chat.id} busy={chat.status === 'processing' || pending.includes(chat.id)} discoveryIds={selectedIds} savedBids={savedBids} onForget={id => setSavedBids(current => current.filter(bid => bid.discoveryId !== id))} onAttach={attachFolder}/>
          {storageNotice && <p className="notice-banner" role="status">{storageNotice}</p>}
          {chat.notice && <p className="notice-banner" role="status">{chat.notice}</p>}{chat.error && <p className="error-banner" role="alert">{chat.error}</p>}
          {chat.status === 'ready' && <div className="message-list">{chat.messages.map(message => <article key={message.id} className="message">
            <div className="request-heading"><strong>{message.mode === 'extract' ? 'Extraction' : message.mode === 'search' ? 'Search' : 'Question'}</strong><span>{message.question}</span></div>
            <p className="result-scope">{message.folders.join(' · ')}</p>
            <div className="answer-heading">{message.mode === 'extract' ? <FileText size={18} aria-hidden="true"/> : message.mode === 'search' ? <Search size={18} aria-hidden="true"/> : <MessageSquare size={18} aria-hidden="true"/>}<strong>{message.mode === 'extract' ? 'Bid fields' : message.mode === 'search' ? 'Matching passages' : 'Answer'}</strong></div>
            {message.reply ? <>
              {message.mode === 'extract' ? <ExtractionContent text={message.reply.answer}/> : <AnswerContent text={message.reply.answer}/>}
              <SourceCards sources={message.reply.sources} search={message.mode === 'search'} onOpen={index => setSource({ sources: message.reply!.sources, index })}/>
            </> : message.error ? <p className="error-banner" role="alert">{message.error}</p> : <p className="muted" role="status">{message.mode === 'extract' ? message.progress || 'Extracting 20 fields. This may take several minutes.' : message.mode === 'search' ? 'Searching documents…' : 'Preparing an answer…'}</p>}
            {!message.reply && message.draft && <details><summary>Saved partial draft — not final validation</summary><ExtractionContent text={message.draft}/></details>}
          </article>)}<div ref={conversationEnd}/></div>}
        </div>
        {(source || (chat.status === 'ready' && documentsVisible)) && <button className="panel-backdrop" aria-label="Close document panel" onClick={() => { setSource(null); setDocumentsVisible(false); }}/>} 
        {chat.status === 'ready' && <aside className={`documents-panel ${documentsVisible ? '' : 'panel-hidden'}`}>
          <div className="panel-heading"><h2><DocumentsIcon size={18} aria-hidden="true"/>Documents</h2><span>{fileCount}</span></div><DocumentList key={chat.id} folders={chat.folders}/>
          <details className="technical-details"><summary><DisclosureLabel icon={Fingerprint}>Discovery IDs</DisclosureLabel></summary>{chat.folders.map(folder => <div key={folder.id} className="discovery-entry"><strong>{folder.name}</strong><input aria-label={`Discovery ID for ${folder.name}`} readOnly value={folder.discoveryId || ''} onFocus={event => event.target.select()}/></div>)}</details>
        </aside>}
        {source && <EvidencePanel sources={source.sources} index={source.index} original={findOriginal(source.sources[source.index])} onNavigate={index => setSource({ ...source, index })} onClose={() => setSource(null)}/>}
      </div>
      {chat.status === 'ready' && <footer className="composer-area">
        <div className="composer">
          <div className="mode-toggle" role="group" aria-label="Document action">
            <button type="button" aria-pressed={mode === 'ask'} className={mode === 'ask' ? 'selected' : ''} onClick={() => setMode('ask')}><MessageSquare size={18} aria-hidden="true"/> Ask</button>
            <button type="button" aria-pressed={mode === 'search'} className={mode === 'search' ? 'selected' : ''} onClick={() => setMode('search')}><Search size={18} aria-hidden="true"/> Search</button>
            <button type="button" aria-pressed={mode === 'extract'} className={mode === 'extract' ? 'selected' : ''} onClick={() => setMode('extract')}><FileText size={18} aria-hidden="true"/> Extract</button>
          </div>
          {mode === 'extract' ? <ExtractFolder key={chat.id} folders={chat.folders} busy={pending.includes(chat.id)} onExtract={extractFolder}/> : <form onSubmit={event => { event.preventDefault(); void submitQuestion(); }}>
            <p className="action-scope">{mode === 'ask' ? 'Ask a question' : 'Find exact passages'} across {selectedIds.length} bid{selectedIds.length === 1 ? '' : 's'}.</p>
            <div className="input-row"><textarea ref={questionInput} rows={1} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submitQuestion(); } }} aria-label={mode === 'ask' ? 'Question about your bid' : 'Search document passages'} value={question} onChange={event => setQuestion(event.target.value)} placeholder={mode === 'ask' ? 'Enter your question…' : 'Enter search terms…'}/>
              <button className="primary-button submit-request" disabled={!selectedIds.length || !question.trim() || pending.includes(chat.id)} aria-label={mode === 'ask' ? 'Ask question' : 'Search documents'}>{mode === 'ask' ? <MessageSquare size={17} aria-hidden="true"/> : <Search size={17} aria-hidden="true"/>}{mode === 'ask' ? 'Ask' : 'Search'}</button>
            </div>
          </form>}
        </div>
      </footer>}
    </main>
    <UsageGuide open={guideOpen} onClose={() => setGuideOpen(false)}/>
  </div>;
}
