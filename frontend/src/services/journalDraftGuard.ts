const allow = async () => true
let guard: () => Promise<boolean> = allow
export function registerJournalDraftGuard(value: () => Promise<boolean>) {
  guard = value
  return () => { if (guard === value) guard = allow }
}
export function confirmJournalLeave() { return guard() }
