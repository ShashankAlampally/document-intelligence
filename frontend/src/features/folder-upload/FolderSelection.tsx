type ReadyFolder = { id: string; name: string; sessionId?: string };

export function FolderSelection({ folders, selectedIds, onChange }: {
  folders: ReadyFolder[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  return <section aria-label="Folders to search">
    <h2>Search these folders</h2>
    <p>Select one folder, or select several to compare them.</p>
    {folders.map(folder => <label key={folder.id} style={{ display: 'block', margin: '12px 0' }}>
      <input type="checkbox" checked={selectedIds.includes(folder.sessionId!)}
        onChange={event => onChange(event.target.checked
          ? [...selectedIds, folder.sessionId!]
          : selectedIds.filter(id => id !== folder.sessionId))} />
      {' '}{folder.name} <small>({folder.sessionId?.slice(0, 8)})</small>
    </label>)}
    {!selectedIds.length && <p role="status">Select at least one folder before asking.</p>}
  </section>;
}
