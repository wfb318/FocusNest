export const DEFAULT_STYLE = { fontScale: 1, textColor: '#263c34', glassColor: '#ffffff' }
export type StylePreferences = typeof DEFAULT_STYLE
export function normalizeStyle(value: Partial<StylePreferences> = {}): StylePreferences {
  const color = (candidate: unknown, fallback: string) => typeof candidate === 'string' && /^#[0-9a-f]{6}$/i.test(candidate) ? candidate.toLowerCase() : fallback
  return {
    fontScale: typeof value.fontScale === 'number' && Number.isFinite(value.fontScale) ? Math.min(1.5, Math.max(0.8, value.fontScale)) : 1,
    textColor: color(value.textColor, DEFAULT_STYLE.textColor),
    glassColor: color(value.glassColor, DEFAULT_STYLE.glassColor),
  }
}
export function styleVariables(value: StylePreferences): Record<string, string> {
  const normalized = normalizeStyle(value)
  const rgb = (hex: string) => [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16)).join(',')
  return {
    '--ui-font-scale': String(normalized.fontScale), '--text-primary': normalized.textColor,
    '--text-muted': `rgba(${rgb(normalized.textColor)},.88)`, '--glass-rgb': rgb(normalized.glassColor),
    '--el-text-color-primary': normalized.textColor, '--el-text-color-regular': normalized.textColor,
    '--el-font-size-base': `calc(14px * ${normalized.fontScale})`,
    '--el-font-size-small': `calc(12px * ${normalized.fontScale})`,
    '--el-font-size-large': `calc(18px * ${normalized.fontScale})`,
  }
}
