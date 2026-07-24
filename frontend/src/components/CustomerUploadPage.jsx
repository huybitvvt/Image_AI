import { useMemo, useRef, useState } from 'react'
import { uploadImage } from '../api.js'
import { CheckIcon, ExternalLinkIcon, LogoIcon, UploadIcon } from './icons.jsx'

export default function CustomerUploadPage() {
  const [files, setFiles] = useState([])
  const [collection, setCollection] = useState('')
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const totalSize = useMemo(
    () => files.reduce((sum, file) => sum + file.size, 0),
    [files],
  )

  const chooseFiles = (incoming) => {
    setFiles([...incoming].filter((file) => file.type.startsWith('image/')).slice(0, 20))
    setResults([])
    setError('')
  }

  const submit = async () => {
    if (!files.length || uploading) return
    setUploading(true)
    setError('')
    const uploaded = []
    try {
      for (const file of files) {
        uploaded.push(await uploadImage(file, collection.trim()))
        setResults([...uploaded])
      }
      setFiles([])
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <main className="customer-page">
      <header className="customer-header">
        <a className="customer-brand" href="/">
          <LogoIcon size={22} />
          <span>Image Workflow</span>
        </a>
        <a className="btn customer-nav-action" href="/create" title="Tạo ảnh thành phẩm">
          <ExternalLinkIcon size={14} />
          <span className="customer-nav-label">Tạo ảnh thành phẩm</span>
        </a>
      </header>

      <section className="customer-upload-shell">
        <div className="customer-section-head">
          <h1>Gửi ảnh vào kho</h1>
          <span>Tối đa 20 ảnh, 40MB mỗi ảnh</span>
        </div>

        <label className="customer-field">
          <span>Nhóm ảnh</span>
          <input
            value={collection}
            onChange={(event) => setCollection(event.target.value)}
            placeholder="Ví dụ: Phào vuông, Sàn gỗ"
          />
        </label>

        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          hidden
          onChange={(event) => {
            chooseFiles(event.target.files || [])
            event.target.value = ''
          }}
        />
        <button
          type="button"
          className="customer-dropzone"
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault()
            chooseFiles(event.dataTransfer.files)
          }}
        >
          <UploadIcon size={24} />
          <strong>Chọn hoặc thả ảnh vào đây</strong>
        </button>

        {files.length > 0 && (
          <div className="customer-file-list">
            <div className="customer-file-summary">
              <span>{files.length} ảnh</span>
              <span>{(totalSize / 1024 / 1024).toFixed(1)}MB</span>
            </div>
            {files.map((file) => (
              <div className="customer-file-row" key={`${file.name}-${file.lastModified}`}>
                <span title={file.name}>{file.name}</span>
                <span>{(file.size / 1024 / 1024).toFixed(1)}MB</span>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          className="btn primary customer-submit"
          disabled={!files.length || uploading}
          onClick={submit}
        >
          <UploadIcon size={15} />
          {uploading ? `Đang tải ${results.length + 1}/${files.length}...` : 'Tải lên hệ thống'}
        </button>

        {results.length > 0 && !uploading && (
          <div className="customer-success">
            <CheckIcon size={16} /> Đã lưu {results.length} ảnh vào kho.
          </div>
        )}
        {error && <div className="customer-error">{error}</div>}
      </section>
    </main>
  )
}
