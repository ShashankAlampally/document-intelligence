/** Upload folders one at a time and preserve completed uploads across retries. */
export type QueuedFolder = {
  id: string;
  name: string;
  files: File[];
  discoveryId?: string;
  jobId?: string;
};

export type FolderProgress =
  | { status: 'processing' }
  | { status: 'ready'; discoveryId: string }
  | { status: 'failed'; error: string };

export async function processFoldersSequentially(
  folders: QueuedFolder[],
  processFolder: (folder: QueuedFolder) => Promise<string>,
  onProgress: (folderId: string, progress: FolderProgress) => void,
): Promise<string[]> {
  const discoveryIds: string[] = [];
  for (const folder of folders) {
    if (folder.discoveryId) {
      discoveryIds.push(folder.discoveryId);
      continue;
    }
    onProgress(folder.id, { status: 'processing' });
    try {
      const discoveryId = await processFolder(folder);
      if (!discoveryId) throw new Error('Processing finished without a discovery ID.');
      discoveryIds.push(discoveryId);
      onProgress(folder.id, { status: 'ready', discoveryId });
    } catch (error) {
      onProgress(folder.id, {
        status: 'failed',
        error: error instanceof Error ? error.message : 'Unable to process folder.',
      });
      // Do not send additional uploads after failure. Retrying skips completed IDs.
      throw error;
    }
  }
  return [...new Set(discoveryIds)];
}
