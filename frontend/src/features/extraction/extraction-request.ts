export function extractionRequest(discoveryId: string) {
  if (!discoveryId) throw new Error('Select an indexed folder for extraction.');
  return {
    question: 'Extract all 20 structured bid fields for this folder, with supporting citations.',
    discoveryIds: [discoveryId],
    mode: 'ask' as const,
  };
}
