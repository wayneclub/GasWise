/**
 * Utility for compressing user-uploaded images via HTML5 Canvas.
 * Resizes the image proportionally to a maximum width and converts to WebP.
 */
export function compressImageFile(
  file: File,
  maxWidth = 400,
  quality = 0.85,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Failed to read image file'))
    reader.onload = (e) => {
      const src = e.target?.result as string
      if (!src) {
        reject(new Error('Empty image source'))
        return
      }
      const img = new Image()
      img.onerror = () => reject(new Error('Failed to load image'))
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const scale = Math.min(1, maxWidth / img.width)
        canvas.width = Math.round(img.width * scale)
        canvas.height = Math.round(img.height * scale)
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('Failed to get 2D canvas context'))
          return
        }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        const compressed = canvas.toDataURL('image/webp', quality)
        resolve(compressed)
      }
      img.src = src
    }
    reader.readAsDataURL(file)
  })
}
