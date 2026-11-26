export type BackgroundKind = 'image' | 'gif' | 'video'
export const BACKGROUND_ACCEPT = '.jpg,.jpeg,.png,.webp,.gif,.mp4,.webm,.ogv'
export function backgroundInfo(file: Pick<File, 'name' | 'size'>) {
  const extension = file.name.split('.').pop()?.toLowerCase()
  const formats: Record<string, { kind: BackgroundKind; mime: string }> = {
    jpg: { kind: 'image', mime: 'image/jpeg' }, jpeg: { kind: 'image', mime: 'image/jpeg' },
    png: { kind: 'image', mime: 'image/png' }, webp: { kind: 'image', mime: 'image/webp' },
    gif: { kind: 'gif', mime: 'image/gif' }, mp4: { kind: 'video', mime: 'video/mp4' },
    webm: { kind: 'video', mime: 'video/webm' }, ogv: { kind: 'video', mime: 'video/ogg' },
  }
  const info = formats[extension ?? '']
  if (!info) throw new Error('请选择 JPG、PNG、WebP、GIF 图片，或 MP4、WebM、OGV 视频。')
  if (!file.size) throw new Error('文件为空，请重新选择。')
  if (file.size > (info.kind === 'video' ? 50 : 10) * 1024 * 1024) throw new Error(info.kind === 'video' ? '视频不能超过 50 MB。' : '图片或 GIF 不能超过 10 MB。')
  return info
}
export async function validateSignature(file: File, mime: string) {
  const bytes = new Uint8Array(await file.slice(0, 16).arrayBuffer())
  const ascii = (start: number, end: number) => String.fromCharCode(...bytes.slice(start, end))
  const valid = mime === 'image/jpeg' ? bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255
    : mime === 'image/png' ? bytes[0] === 137 && ascii(1, 4) === 'PNG'
    : mime === 'image/webp' ? ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP'
    : mime === 'image/gif' ? ['GIF87a', 'GIF89a'].includes(ascii(0, 6))
    : mime === 'video/mp4' ? ascii(4, 8) === 'ftyp'
    : mime === 'video/webm' ? [26, 69, 223, 163].every((value, i) => bytes[i] === value)
    : mime === 'video/ogg' && ascii(0, 4) === 'OggS'
  if (!valid) throw new Error('文件内容与扩展名不符或文件已损坏，请重新选择。')
}
async function frame(source: CanvasImageSource, width: number, height: number): Promise<Blob> {
  const scale = Math.min(1, 2560 / Math.max(width, height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(width * scale)); canvas.height = Math.max(1, Math.round(height * scale))
  const context = canvas.getContext('2d')
  if (!context) throw new Error('当前浏览器无法处理背景。')
  context.fillStyle = '#eef2ed'; context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(source, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('背景处理失败。')), 'image/jpeg', 0.86))
}
export async function prepareBackground(file: File): Promise<{ image: Blob; poster: Blob | null; kind: BackgroundKind }> {
  const info = backgroundInfo(file)
  await validateSignature(file, info.mime)
  const media = file.slice(0, file.size, info.mime)
  const url = URL.createObjectURL(media)
  try {
    if (info.kind === 'video') {
      const video = document.createElement('video')
      if (!video.canPlayType(info.mime)) throw new Error('当前浏览器不支持此视频格式，请转为 H.264 编码的 MP4 或 WebM。')
      video.muted = true; video.playsInline = true; video.preload = 'auto'
      try {
        await new Promise<void>((resolve, reject) => {
          const timer = window.setTimeout(() => finish(new Error('视频读取超时，请换用较短的视频。')), 15000)
          const finish = (cause?: Error) => { clearTimeout(timer); video.onloadeddata = null; video.onerror = null; cause ? reject(cause) : resolve() }
          video.onloadeddata = () => finish()
          video.onerror = () => finish(new Error('视频无法解码，请换用 H.264 MP4 或 WebM 文件。'))
          video.src = url; video.load()
        })
        if (!video.videoWidth || video.videoWidth * video.videoHeight > 3840 * 2160) throw new Error('视频分辨率过高，请使用不超过 4K 的背景。')
        return { image: media, kind: 'video', poster: await frame(video, video.videoWidth, video.videoHeight) }
      } finally { video.pause(); video.removeAttribute('src'); video.load() }
    }
    const image = new Image(); image.src = url
    try { await image.decode() } catch { throw new Error('图片无法读取，请重新选择。') }
    if (!image.naturalWidth || image.naturalWidth * image.naturalHeight > (info.kind === 'gif' ? 3840 * 2160 : 80_000_000)) throw new Error('图片分辨率过高，请先缩小图片。')
    const poster = await frame(image, image.naturalWidth, image.naturalHeight)
    return info.kind === 'gif' ? { image: media, kind: 'gif', poster } : { image: poster, kind: 'image', poster: null }
  } finally { URL.revokeObjectURL(url) }
}
