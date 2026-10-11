import { useState } from 'react';
import { ExistingBidIcon as FolderSearch, ExistingBidIcon as FolderOpen, LoadingIcon as LoaderCircle } from '../../components/icons';
import { DisclosureLabel } from '../../components/DisclosureLabel';
import { getIndexedFolder, type IndexedFolder } from '../../lib/api';

export function ExistingFolder({ busy, discoveryIds, onAttach }: {
  busy: boolean;
  discoveryIds: string[];
  onAttach: (folder: IndexedFolder) => void;
}) {
  const [id, setId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  async function attach() {
    const value = id.trim().toLowerCase();
    if (discoveryIds.includes(value)) { setError('This folder is already in this chat.'); return; }
    setLoading(true);
    setError('');
    try {
      const folder = await getIndexedFolder(value);
      onAttach(folder);
      setId('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to open this folder.');
    } finally { setLoading(false); }
  }
  return <details className="existing-folder">
    <summary><DisclosureLabel icon={FolderSearch}>Open an existing bid</DisclosureLabel></summary>
    <form onSubmit={event => { event.preventDefault(); void attach(); }}>
      <label htmlFor="existing-discovery-id">Discovery ID</label>
      <div className="existing-folder-controls">
        <input id="existing-discovery-id" value={id} onChange={event => setId(event.target.value)}
          required pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
          disabled={busy || loading || discoveryIds.length >= 20} placeholder="Paste discovery ID" />
        <button className="secondary-button" disabled={busy || loading || !id.trim() || discoveryIds.length >= 20}>
          {loading ? <LoaderCircle size={17} className="loading-icon" aria-hidden="true"/> : <FolderOpen size={17} aria-hidden="true"/>}{loading ? 'Checking…' : 'Open folder'}
        </button>
      </div>
    </form>
    {error && <p className="error-banner" role="alert">{error}</p>}
  </details>;
}
