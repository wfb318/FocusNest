export const MAX_IMPORT_BYTES = 512 * 1024
export const IMPORT_ACCEPT = '.md,.markdown,.txt'

export interface ImportedNote { title: string; content: string }

// Read only the file explicitly selected by the user. Saving uses the normal note API.
export async function readNoteFile(file: File): Promise<ImportedNote> {
  if (!/\.(md|markdown|txt)$/i.test(file.name)) {
    throw new Error('暂支持 Markdown（.md、.markdown）和纯文本（.txt），请先将其他格式导出为文本。')
  }
  if (file.size > MAX_IMPORT_BYTES) throw new Error('文件不能超过 512 KB，请拆分后导入。')
  let content: string
  try {
    content = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer())
  } catch { throw new Error('文件无法读取或不是 UTF-8 编码，请另存为 UTF-8 后重试。') }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(content)) {
    throw new Error('文件包含二进制或不支持的控制字符，请选择纯文本文件。')
  }
  if (!content.trim()) throw new Error('文件内容为空，无法导入笔记。')
  if (Array.from(content).length > 100000) throw new Error('正文不能超过 100000 字符，请拆分后导入。')
  const basename = file.name.split(/[\\/]/).pop()!.replace(/\.(md|markdown|txt)$/i, '')
  const title = Array.from(basename.replace(/[\u0000-\u001f\u007f]/g, '').trim()).slice(0, 200).join('') || '导入的笔记'
  return { title, content }
}
