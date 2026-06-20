import { useState } from 'react'

export function FileUploader({ onUpload }: { onUpload: (file: File) => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  async function submit() {
    if (!file) return
    setUploading(true)
    try {
      await onUpload(file)
      setFile(null)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="uploader">
      <input type="file" accept=".xlsx,.xls,.csv,.pdf,.txt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      <button onClick={submit} disabled={!file || uploading}>{uploading ? '上传中' : '上传文件'}</button>
    </div>
  )
}
