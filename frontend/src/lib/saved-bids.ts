export type SavedBid = { discoveryId: string; name: string };
export const savedBidsKey = 'rfp-intelligence.saved-bids.v1';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function readSavedBids(storage: Pick<Storage, 'getItem'>): SavedBid[] {
  try {
    const value: unknown = JSON.parse(storage.getItem(savedBidsKey) || '[]');
    if (!Array.isArray(value)) return [];
    const seen = new Set<string>();
    return value.flatMap(item => {
      if (!item || typeof item.discoveryId !== 'string' || !uuid.test(item.discoveryId) || typeof item.name !== 'string' || !item.name.trim()) return [];
      const discoveryId = item.discoveryId.toLowerCase();
      if (seen.has(discoveryId)) return [];
      seen.add(discoveryId);
      return [{ discoveryId, name: item.name.slice(0, 240) }];
    }).slice(0, 50);
  } catch { return []; }
}

export function rememberBid(bids: SavedBid[], bid: SavedBid): SavedBid[] {
  return [{ ...bid, discoveryId: bid.discoveryId.toLowerCase() }, ...bids.filter(item => item.discoveryId !== bid.discoveryId.toLowerCase())].slice(0, 50);
}
