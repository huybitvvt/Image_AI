import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { listUploads, uploadImage } from '../api.js'
import { useImageViewer } from '../ImageViewerContext.jsx'
import { EyeIcon, UploadIcon, XIcon } from './icons.jsx'

// Ô upload ảnh trong node: nút chọn file → card preview với hành động
// xem ảnh gốc (lightbox) / đổi ảnh khác / gỡ ảnh.
function ImageUploadField({ value, onChange }) {
  const [uploading, setUploading] = useState(false)
  const [items, setItems] = useState([])
  const inputRef = useRef(null)
  const { openViewer } = useImageViewer()
  const url = value ? `/api/uploads/${value}` : null
  const selected = items.find((item) => item.file_id === value)
  const view = () => url && openViewer({
    src: url,
    filename: selected?.display_name || value,
  })

  const refresh = useCallback(() => {
    listUploads().then(setItems).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
    window.addEventListener('iw-library-change', refresh)
    return () => window.removeEventListener('iw-library-change', refresh)
  }, [refresh])

  const groups = useMemo(() => {
    const grouped = new Map()
    for (const item of items) {
      const key = item.collection || 'Chưa phân nhóm'
      if (!grouped.has(key)) grouped.set(key, [])
      grouped.get(key).push(item)
    }
    return [...grouped.entries()]
  }, [items])

  const pickFile = async (file) => {
    if (!file) return
    setUploading(true)
    try {
      const { file_id } = await uploadImage(file)
      onChange(file_id)
      window.dispatchEvent(new Event('iw-library-change'))
    } catch (err) {
      alert(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-field nodrag">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          pickFile(e.target.files?.[0])
          e.target.value = '' // cho phép chọn lại cùng một file
        }}
      />
      <div className="upload-picker-row">
        <select
          className="upload-library-select"
          value={value || ''}
          disabled={uploading}
          onFocus={refresh}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Chọn ảnh trong kho...</option>
          {value && !selected && <option value={value}>Ảnh đang dùng ({value})</option>}
          {groups.map(([group, rows]) => (
            <optgroup key={group} label={group}>
              {rows.map((item) => (
                <option key={item.file_id} value={item.file_id}>
                  {item.display_name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <button
          type="button"
          className="icon-btn upload-pick-button"
          title="Tải ảnh mới từ máy"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          <UploadIcon size={13} />
        </button>
      </div>
      {uploading && <div className="upload-state">Đang tải ảnh lên...</div>}
      {url && (
        <div className="upload-preview">
          <img src={url} alt={selected?.display_name || 'ảnh đã tải lên'} onClick={view} />
          <div className="upload-preview-actions">
            <button type="button" className="icon-btn" title="Xem ảnh (phóng to)" onClick={view}>
              <EyeIcon size={13} />
            </button>
            <button type="button" className="icon-btn" title="Đổi ảnh khác" disabled={uploading} onClick={() => inputRef.current?.click()}>
              <UploadIcon size={13} />
            </button>
            <button type="button" className="icon-btn" title="Gỡ ảnh" onClick={() => onChange('')}>
              <XIcon size={13} />
            </button>
          </div>
          <div className="upload-preview-name" title={selected?.display_name || value}>
            {selected?.display_name || value}
          </div>
        </div>
      )}
    </div>
  )
}

// Render một tham số của node theo ptype trong metadata backend.
export default function NodeParamField({ spec, value, onChange }) {
  switch (spec.ptype) {
    case 'textarea':
      return (
        <textarea
          className="nodrag"
          rows={3}
          placeholder={spec.label}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case 'select': {
      const opts = spec.options || []
      if (opts.length === 0) {
        return <span className="wf-param-empty">Chưa có cấu hình — mở ⚙ Model</span>
      }
      return (
        <select className="nodrag" value={value ?? spec.default} onChange={(e) => onChange(e.target.value)}>
          {opts.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      )
    }
    case 'number':
      return (
        <input
          className="nodrag"
          type="number"
          value={value ?? spec.default ?? 0}
          min={spec.min}
          max={spec.max}
          step={spec.step ?? 1}
          onChange={(e) => onChange(e.target.value === '' ? spec.default : Number(e.target.value))}
        />
      )
    case 'checkbox':
      return (
        <input
          className="nodrag"
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
        />
      )
    case 'image_upload':
      return <ImageUploadField value={value} onChange={onChange} />
    default:
      return (
        <input
          className="nodrag"
          type="text"
          placeholder={spec.label}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )
  }
}
