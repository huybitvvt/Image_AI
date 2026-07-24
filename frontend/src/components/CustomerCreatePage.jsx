import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  listUploads,
  listWorkflows,
  loadWorkflow,
  openRunSocket,
} from '../api.js'
import {
  DownloadIcon,
  ExternalLinkIcon,
  ImageIcon,
  LogoIcon,
  PlayIcon,
  UploadIcon,
} from './icons.jsx'

function groupedAssets(items) {
  const groups = new Map()
  for (const item of items) {
    const key = item.collection || 'Chưa phân nhóm'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(item)
  }
  return [...groups.entries()]
}

export default function CustomerCreatePage() {
  const initialWorkflow = new URLSearchParams(location.search).get('workflow') || ''
  const [workflows, setWorkflows] = useState([])
  const [workflowName, setWorkflowName] = useState(initialWorkflow)
  const [workflow, setWorkflow] = useState(null)
  const [assets, setAssets] = useState([])
  const [selections, setSelections] = useState({})
  const [selectionVersion, setSelectionVersion] = useState(0)
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState(null)
  const socketRef = useRef(null)
  const latestImageRef = useRef(null)
  const lastRunVersionRef = useRef(0)

  useEffect(() => {
    Promise.all([listWorkflows(), listUploads()])
      .then(([workflowRows, imageRows]) => {
        setWorkflows(workflowRows)
        setAssets(imageRows)
        const preferred = workflowRows.find((item) => item.name === initialWorkflow)?.name
          || workflowRows[0]?.name
          || ''
        setWorkflowName(preferred)
      })
      .catch((error) => setStatus(error.message))
  }, [initialWorkflow])

  useEffect(() => {
    const refreshAssets = () => listUploads().then(setAssets).catch(() => {})
    window.addEventListener('focus', refreshAssets)
    return () => window.removeEventListener('focus', refreshAssets)
  }, [])

  useEffect(() => {
    if (!workflowName) {
      setWorkflow(null)
      return
    }
    loadWorkflow(workflowName)
      .then((data) => {
        setWorkflow(data)
        setSelections({})
        setSelectionVersion(0)
        setStatus('')
        const url = new URL(location.href)
        url.searchParams.set('workflow', workflowName)
        history.replaceState(null, '', url)
      })
      .catch((error) => setStatus(error.message))
  }, [workflowName])

  const imageNodes = useMemo(
    () => workflow?.nodes?.filter((node) => node.type === 'load_image') || [],
    [workflow],
  )
  const assetGroups = useMemo(() => groupedAssets(assets), [assets])
  const allSelected = imageNodes.length > 0
    && imageNodes.every((node) => selections[node.id])

  const run = useCallback(() => {
    if (!workflow || !allSelected || running) return
    lastRunVersionRef.current = selectionVersion
    const payload = {
      ...workflow,
      nodes: workflow.nodes.map((node) => (
        node.type === 'load_image'
          ? {
              ...node,
              params: { ...node.params, file_id: selections[node.id] },
            }
          : node
      )),
    }

    setRunning(true)
    setStatus('Đang tạo ảnh...')
    latestImageRef.current = null
    const socket = openRunSocket()
    socketRef.current = socket
    let ended = false

    socket.onopen = () => socket.send(JSON.stringify({
      workflow: payload,
      target: null,
      force: [],
    }))
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data)
      if (event.type === 'node_finished') {
        const imageOutput = Object.values(event.outputs || {})
          .find((output) => output.dtype === 'image')
        if (imageOutput) {
          latestImageRef.current = {
            src: imageOutput.sha ? `/api/cache-image/${imageOutput.sha}` : event.preview,
            preview: event.preview,
          }
          setResult(latestImageRef.current)
        }
        const saved = Object.values(event.outputs || {})
          .find((output) => output.dtype === 'text'
            && output.value?.startsWith('/api/outputs/'))
        if (saved) {
          latestImageRef.current = { src: saved.value, preview: saved.value }
          setResult(latestImageRef.current)
        }
      } else if (event.type === 'run_finished') {
        ended = true
        setRunning(false)
        setStatus('Hoàn thành')
      } else if (event.type === 'run_error') {
        ended = true
        setRunning(false)
        setStatus(event.message || 'Workflow chạy thất bại.')
      }
    }
    socket.onclose = () => {
      if (!ended) {
        setRunning(false)
        setStatus('Mất kết nối với hệ thống.')
      }
    }
  }, [workflow, allSelected, running, selections, selectionVersion])

  useEffect(() => {
    if (!selectionVersion || selectionVersion <= lastRunVersionRef.current
        || !allSelected || running) return undefined
    const timer = setTimeout(run, 350)
    return () => clearTimeout(timer)
  }, [selectionVersion, allSelected, running, run])

  useEffect(() => () => socketRef.current?.close(), [])

  return (
    <main className="customer-page">
      <header className="customer-header">
        <a className="customer-brand" href="/">
          <LogoIcon size={22} />
          <span>Image Workflow</span>
        </a>
        <a className="btn customer-nav-action" href="/upload" title="Gửi ảnh vào kho">
          <UploadIcon size={14} />
          <span className="customer-nav-label">Gửi ảnh vào kho</span>
        </a>
      </header>

      <div className="customer-create-layout">
        <section className="customer-config-panel">
          <div className="customer-section-head">
            <h1>Tạo ảnh thành phẩm</h1>
            <span>Tự chạy khi đã chọn đủ ảnh</span>
          </div>

          <label className="customer-field">
            <span>Mẫu xử lý</span>
            <select
              value={workflowName}
              disabled={running}
              onChange={(event) => setWorkflowName(event.target.value)}
            >
              <option value="">Chọn workflow...</option>
              {workflows.map((item) => (
                <option value={item.name} key={item.name}>{item.name}</option>
              ))}
            </select>
          </label>

          {workflow && imageNodes.length === 0 && (
            <div className="customer-error">Workflow này không có node “Tải ảnh lên”.</div>
          )}

          <div className="customer-source-list">
            {imageNodes.map((node, index) => {
              const label = node.params?.image_label?.trim() || `Ảnh đầu vào ${index + 1}`
              const selected = assets.find((item) => item.file_id === selections[node.id])
              return (
                <label className="customer-source" key={node.id}>
                  <span className="customer-source-label">{label}</span>
                  <select
                    value={selections[node.id] || ''}
                    disabled={running}
                    onChange={(event) => {
                      setSelections((current) => ({
                        ...current,
                        [node.id]: event.target.value,
                      }))
                      setSelectionVersion((value) => value + 1)
                    }}
                  >
                    <option value="">Chọn ảnh...</option>
                    {assetGroups.map(([group, rows]) => (
                      <optgroup label={group} key={group}>
                        {rows.map((item) => (
                          <option value={item.file_id} key={item.file_id}>
                            {item.display_name}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  {selected && (
                    <img
                      className="customer-source-preview"
                      src={selected.url}
                      alt={selected.display_name}
                    />
                  )}
                </label>
              )
            })}
          </div>

          <button
            type="button"
            className="btn primary customer-run"
            disabled={!allSelected || running}
            onClick={run}
          >
            <PlayIcon size={14} />
            {running ? 'Đang xử lý...' : 'Tạo lại ảnh'}
          </button>
          {status && (
            <div className={status === 'Hoàn thành' ? 'customer-success' : 'customer-status'}>
              {status}
            </div>
          )}
        </section>

        <section className="customer-result-panel">
          {result ? (
            <>
              <img src={result.preview || result.src} alt="Ảnh thành phẩm" />
              <div className="customer-result-actions">
                <a className="btn" href={result.src} target="_blank" rel="noreferrer">
                  <ExternalLinkIcon size={14} /> Xem ảnh gốc
                </a>
                <a className="btn primary" href={result.src} download>
                  <DownloadIcon size={14} /> Tải ảnh
                </a>
              </div>
            </>
          ) : (
            <div className="customer-result-empty">
              <ImageIcon size={32} />
              <span>Ảnh thành phẩm</span>
            </div>
          )}
          {running && <div className="customer-result-running">Đang xử lý ảnh...</div>}
        </section>
      </div>
    </main>
  )
}
