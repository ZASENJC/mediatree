export interface Cue {
  start: number
  end: number
  text: string
  style?: Record<string, string | number>
  position?: { left?: string; right?: string; top?: string; bottom?: string; align?: string }
}

export function parseSubtitle(raw: string): Cue[] {
  if (/\[Script Info\]|\[V4\+? Styles\]|\[Events\]/i.test(raw)) return parseAss(raw)
  return parseVtt(raw)
}

export function parseVtt(raw: string): Cue[] {
  const cues: Cue[] = []
  const lines = raw.replace(/^\uFEFF/, '').split(/\r?\n/)
  let i = 0

  while (i < lines.length) {
    const line = lines[i].trim()
    if (!line || line === 'WEBVTT' || line.startsWith('NOTE') || line.startsWith('STYLE') || line.startsWith('REGION')) {
      i++
      continue
    }
    const m = line.match(/^((?:\d+:)?\d{1,2}:\d{2}[\.,]\d{3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[\.,]\d{3})/)
    if (m) {
      const start = parseTimestamp(m[1])
      const end = parseTimestamp(m[2])
      const textLines: string[] = []
      i++
      while (i < lines.length && lines[i].trim() !== '') {
        textLines.push(lines[i])
        i++
      }
      const text = cleanCueText(textLines.join('\n').trim())
      if (text) {
        cues.push({ start, end, text })
      }
    } else {
      i++
    }
  }

  return cues
}

function parseTimestamp(ts: string): number {
  const parts = ts.replace(',', '.').split(':')
  if (parts.length === 2) {
    return parseInt(parts[0]) * 60 + parseFloat(parts[1])
  }
  return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2])
}

function cleanCueText(text: string): string {
  return text
    .replace(/<c(?:\.[^>]*)?>/g, '')
    .replace(/<\/c>/g, '')
    .replace(/<v(?:\s+[^>]*)?>/g, '')
    .replace(/<\/v>/g, '')
    .replace(/<\d{1,2}:\d{2}(?::\d{2})?[\.,]\d{3}>/g, '')
    .replace(/\{\\[^}]*\}/g, '')
}

function parseAss(raw: string): Cue[] {
  const lines = raw.replace(/^\uFEFF/, '').split(/\r?\n/)
  const styles: Record<string, Record<string, string>> = {}
  let section = ''
  let styleFormat: string[] = []
  let eventFormat: string[] = []
  const cues: Cue[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith(';')) continue
    const sec = trimmed.match(/^\[(.+)\]$/)
    if (sec) { section = sec[1].toLowerCase(); continue }

    if (section.includes('styles')) {
      if (trimmed.startsWith('Format:')) {
        styleFormat = trimmed.slice(7).split(',').map(s => s.trim())
      } else if (trimmed.startsWith('Style:') && styleFormat.length) {
        const values = splitAssFields(trimmed.slice(6), styleFormat.length)
        const style: Record<string, string> = {}
        styleFormat.forEach((k, i) => { style[k] = values[i] || '' })
        if (style.Name) styles[style.Name] = style
      }
    } else if (section === 'events') {
      if (trimmed.startsWith('Format:')) {
        eventFormat = trimmed.slice(7).split(',').map(s => s.trim())
      } else if (trimmed.startsWith('Dialogue:') && eventFormat.length) {
        const values = splitAssFields(trimmed.slice(9), eventFormat.length)
        const event: Record<string, string> = {}
        eventFormat.forEach((k, i) => { event[k] = values[i] || '' })
        const text = event.Text || ''
        if (isAssDrawingEvent(text)) continue
        const baseStyle = styles[event.Style || 'Default'] || styles.Default || {}
        const cue = assTextToCue(text, baseStyle)
        if (cue.text) {
          cues.push({
            start: parseAssTimestamp(event.Start || '0:00:00.00'),
            end: parseAssTimestamp(event.End || '0:00:00.00'),
            ...cue,
          })
        }
      }
    }
  }
  return cues.sort((a, b) => a.start - b.start)
}

function isAssDrawingEvent(rawText: string): boolean {
  const tags = Array.from(rawText.matchAll(/\{([^}]*)\}/g)).map(m => m[1]).join('')
  const drawing = tags.match(/\\p(\d+)/)
  if (drawing && Number(drawing[1]) > 0) return true

  const cleaned = rawText
    .replace(/\{[^}]*\}/g, '')
    .replace(/\\[Nnh]/g, ' ')
    .trim()
  if (!cleaned) return false

  const drawingTokens = cleaned.match(/\b[mlbspc]\s*-?\d+(?:\.\d+)?/gi) || []
  const readableChars = cleaned.match(/[\p{L}\p{N}]/gu) || []
  return drawingTokens.length >= 4 && drawingTokens.length > readableChars.length
}

function splitAssFields(value: string, count: number): string[] {
  const parts = value.split(',')
  if (parts.length <= count) return parts.map(s => s.trim())
  const head = parts.slice(0, count - 1).map(s => s.trim())
  head.push(parts.slice(count - 1).join(',').trim())
  return head
}

function parseAssTimestamp(ts: string): number {
  const m = ts.trim().match(/^(\d+):(\d{2}):(\d{2})[.](\d{1,2})$/)
  if (!m) return 0
  return Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) + Number(m[4].padEnd(2, '0')) / 100
}

function assTextToCue(rawText: string, assStyle: Record<string, string>): Pick<Cue, 'text' | 'style' | 'position'> {
  const overrideTags = Array.from(rawText.matchAll(/\{([^}]*)\}/g)).map(m => m[1]).join('')
  const position = parseAssPosition(overrideTags, assStyle.Alignment)
  const style: Record<string, string | number> = {}
  const fontName = matchTag(overrideTags, /\\fn([^\\}]+)/)
  const fontSize = matchTag(overrideTags, /\\fs(\d+(?:\.\d+)?)/)
  const primaryColor = matchTag(overrideTags, /\\(?:1?c)&H([0-9A-Fa-f]{6,8})&/)
  const bold = /\\b1(?!\d)/.test(overrideTags) || assStyle.Bold === '-1' || assStyle.Bold === '1'
  const italic = /\\i1(?!\d)/.test(overrideTags) || assStyle.Italic === '-1' || assStyle.Italic === '1'

  style.fontFamily = `${fontName || assStyle.Fontname || 'sans-serif'}, sans-serif`
  style.fontSize = `${fontSize || assStyle.Fontsize || 32}px`
  const cssColor = assColorToCss(primaryColor || assStyle.PrimaryColour)
  if (cssColor) style.color = cssColor
  style.fontWeight = bold ? '700' : '400'
  style.fontStyle = italic ? 'italic' : 'normal'

  const text = rawText
    .replace(/\{[^}]*\}/g, '')
    .replace(/\\N/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\h/g, ' ')
    .trim()

  return { text, style, position }
}

function parseAssPosition(tags: string, alignment = ''): Cue['position'] {
  const pos = tags.match(/\\pos\(([-\d.]+),([-\d.]+)\)/)
  if (pos) {
    return {
      left: `${Math.max(0, Math.min(100, Number(pos[1]) / 19.2))}%`,
      top: `${Math.max(0, Math.min(100, Number(pos[2]) / 10.8))}%`,
      align: 'center',
    }
  }
  const align = Number(matchTag(tags, /\\an(\d)/) || alignment || 2)
  if ([7, 8, 9].includes(align)) return { top: '8%', align: alignToCss(align) }
  if ([4, 5, 6].includes(align)) return { top: '48%', align: alignToCss(align) }
  return { bottom: '14%', align: alignToCss(align) }
}

function alignToCss(align: number): string {
  if ([1, 4, 7].includes(align)) return 'left'
  if ([3, 6, 9].includes(align)) return 'right'
  return 'center'
}

function matchTag(tags: string, re: RegExp): string {
  const m = tags.match(re)
  return m ? m[1].trim() : ''
}

function assColorToCss(value?: string): string {
  if (!value) return ''
  const hex = value.replace(/^&H/i, '').replace(/&$/, '').padStart(6, '0')
  const rgb = hex.slice(-6)
  return `#${rgb.slice(4, 6)}${rgb.slice(2, 4)}${rgb.slice(0, 2)}`
}
