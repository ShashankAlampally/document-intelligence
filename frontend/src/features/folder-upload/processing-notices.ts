/** Backend currently reports notice counts in the processing job's detail string. */
export function hasParsingNotices(detail?: string): boolean {
  const count = detail?.match(/(\d+)\s+parsing notices?/i);
  return count ? Number(count[1]) > 0 : false;
}
