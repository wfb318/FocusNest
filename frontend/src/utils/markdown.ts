import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: false, linkify: false, breaks: true })
// Do not fetch remote image URLs embedded in private journal text.
markdown.disable('image')
markdown.renderer.rules.link_open = (tokens, index, options, _env, renderer) => {
  tokens[index]!.attrSet('target', '_blank')
  tokens[index]!.attrSet('rel', 'noopener noreferrer')
  return renderer.renderToken(tokens, index, options)
}
export function renderMarkdown(content: string): string { return markdown.render(content) }

const journalMarkdown = new MarkdownIt({ html: false, linkify: false, breaks: true })
// Even opening a link manually must not send a journal-derived URL.
journalMarkdown.disable(['image', 'link', 'autolink'])
export function renderJournalMarkdown(content: string): string { return journalMarkdown.render(content) }
