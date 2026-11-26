import type { NoteFolder } from '../api/noteFolders'

export interface FolderRow { folder: NoteFolder; depth: number; path: string; hasChildren: boolean; visible: boolean }
// Iterative traversal avoids overflowing the JS stack for deeply nested folders.
export function folderRows(folders: NoteFolder[], collapsed: Set<string>): FolderRow[] {
  const children = new Map<string | null, NoteFolder[]>()
  for (const folder of folders) {
    const siblings = children.get(folder.parent_id) ?? []
    siblings.push(folder); children.set(folder.parent_id, siblings)
  }
  const stack = [...(children.get(null) ?? [])].reverse().map(folder => ({ folder, depth: 0, path: folder.name, visible: true }))
  const rows: FolderRow[] = []
  const visited = new Set<string>()
  while (stack.length) {
    const item = stack.pop()!
    if (visited.has(item.folder.id)) continue
    visited.add(item.folder.id)
    const descendants = children.get(item.folder.id) ?? []
    rows.push({ ...item, hasChildren: descendants.length > 0 })
    for (const folder of [...descendants].reverse()) {
      stack.push({ folder, depth: item.depth + 1, path: `${item.path} / ${folder.name}`, visible: item.visible && !collapsed.has(item.folder.id) })
    }
  }
  return rows
}
