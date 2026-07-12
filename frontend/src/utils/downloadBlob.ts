import { parseContentDispositionFilename } from './downloadFilename'

export async function downloadBlobWithDisposition(
  blob: Blob,
  contentDisposition: string | null,
  fallbackFilename: string,
): Promise<void> {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = parseContentDispositionFilename(contentDisposition) || fallbackFilename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
