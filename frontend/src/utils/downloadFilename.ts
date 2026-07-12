export function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) return null
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim())
    } catch {
      return utf8Match[1].trim()
    }
  }
  const asciiMatch = header.match(/filename="([^"]+)"/i) || header.match(/filename=([^;]+)/i)
  return asciiMatch?.[1]?.trim() || null
}

export async function downloadResponseBlob(response: Response, fallbackFilename: string): Promise<void> {
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = parseContentDispositionFilename(response.headers.get('Content-Disposition')) || fallbackFilename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
