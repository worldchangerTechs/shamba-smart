const MAX_UPLOAD_BYTES = 300 * 1024
const MAX_IMAGE_DIMENSION = 1800

function canvasBlob(canvas: HTMLCanvasElement, type: string, quality: number) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error('Could not compress this image. Choose a different photo.')),
      type,
      quality,
    )
  })
}

export async function compressImageForUpload(file: File) {
  if (!file.type.startsWith('image/')) {
    throw new Error('Choose an image file for the pest report.')
  }
  if (typeof createImageBitmap !== 'function') {
    throw new Error('This browser cannot compress photos locally. Try a newer browser or a smaller image.')
  }

  const image = await createImageBitmap(file)
  try {
    const scale = Math.min(1, MAX_IMAGE_DIMENSION / Math.max(image.width, image.height))
    let width = Math.max(1, Math.round(image.width * scale))
    let height = Math.max(1, Math.round(image.height * scale))
    const canvas = document.createElement('canvas')

    for (let resizePass = 0; resizePass < 5; resizePass += 1) {
      canvas.width = width
      canvas.height = height
      const context = canvas.getContext('2d')
      if (!context) throw new Error('Could not prepare the image for upload.')
      context.drawImage(image, 0, 0, width, height)

      for (const quality of [0.82, 0.72, 0.62, 0.52, 0.42, 0.32]) {
        const blob = await canvasBlob(canvas, 'image/webp', quality)
        if (blob.size <= MAX_UPLOAD_BYTES) {
          const baseName = file.name.replace(/\.[^.]+$/, '') || 'pest-report'
          return new File([blob], `${baseName}.webp`, { type: 'image/webp', lastModified: Date.now() })
        }
      }

      width = Math.max(1, Math.round(width * 0.75))
      height = Math.max(1, Math.round(height * 0.75))
    }

    throw new Error('This photo could not be reduced below 300 KB. Choose a smaller image.')
  } finally {
    image.close()
  }
}
