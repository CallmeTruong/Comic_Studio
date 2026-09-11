import { useState, useRef, useEffect } from 'react'
import { Pencil, Settings2, LayoutTemplate, SlidersHorizontal, Image as ImageIcon, History, RotateCcw, X, Download, Save } from 'lucide-react'

type PanelMeta = { id: string; x: number; y: number; width: number; height: number; prompt: string; dialogues: { character_id?: string; text?: string; emotion?: string }[] }
type PageMeta = { url: string; pageWidth: number; pageHeight: number; panels: PanelMeta[] }
type LoraOption = { id: string; label: string }

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export default function App() {
  const [activeTab, setActiveTab] = useState<'prompt' | 'models' | 'layout'>('prompt')
  
  // Generation State
  const [prompt, setPrompt] = useState("")
  const [loading, setLoading] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [resultImages, setResultImages] = useState<string[]>([])
  const [history, setHistory] = useState<string[]>([])
  const [pageMeta, setPageMeta] = useState<Record<string, PageMeta>>({})
  const [editingPanel, setEditingPanel] = useState<{ pageUrl: string; panel: PanelMeta } | null>(null)
  const [panelPrompt, setPanelPrompt] = useState('')
  const [panelDialogues, setPanelDialogues] = useState('[]')
  const [panelEditMode, setPanelEditMode] = useState<'panel' | 'dialogue'>('panel')
  const [panelRegenerating, setPanelRegenerating] = useState(false)
  const [savedPages, setSavedPages] = useState<string[]>([])
  
  // Settings State (UI Demo)
  const [steps, setSteps] = useState(80)
  const [guidance, setGuidance] = useState(7.5)
  const [lora, setLora] = useState("ghibli")
  const [loras, setLoras] = useState<LoraOption[]>([])
  const [negativePrompt, setNegativePrompt] = useState("")
  const [seed, setSeed] = useState("")
  const [layoutStyle, setLayoutStyle] = useState("auto")
  const [mangaLayout, setMangaLayout] = useState("style1")

  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    // Fetch initial history
    fetch(`${API_BASE}/api/history`)
      .then(res => res.json())
      .then(data => {
        if (data.history && data.history.length > 0) {
      const fullUrls = data.history.map((url: string) => `${API_BASE}${url}`)
          setHistory(fullUrls)
        }
      })
      .catch(err => console.error("Could not load history", err))
  }, [])

  const loadPageMeta = async (pageUrl: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/page-meta?url=${encodeURIComponent(pageUrl)}`)
      if (!response.ok) throw new Error(await response.text())
      const meta = await response.json() as PageMeta
      setPageMeta(prev => ({ ...prev, [pageUrl]: meta }))
      return meta
    } catch (error) {
      setLogs(prev => [...prev, `[ERROR] Could not load panel metadata: ${error}`])
      return null
    }
  }

  useEffect(() => {
    fetch(`${API_BASE}/api/capabilities`)
      .then(res => res.json())
      .then(data => {
        const options = Array.isArray(data.loras) ? data.loras as LoraOption[] : []
        setLoras(options)
        if (options.length && !options.some(option => option.id === lora)) setLora(options[0].id)
      })
      .catch(err => console.error('Could not load LoRA catalog', err))
  }, [])

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setActiveTab('prompt') // Switch back to prompt tab to see logs
    setLogs(["[SYSTEM] Sending request..."])
    setResultImages([])

    try {
      const response = await fetch(`${API_BASE}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          prompt,
          layoutStyle,
          mangaLayout,
          steps,
          guidance,
          lora,
          negativePrompt,
          seed,
        })
      })
      
      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { value, done } = await reader.read()
        buffer += done ? decoder.decode() + '\n' : decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        
        for (const rawLine of lines) {
          const line = rawLine.replace(/\r$/, '')
          if (line.startsWith('data: ')) {
            const msg = line.substring(6)
            if (msg === '[DONE]') {
              setLoading(false)
            } else if (msg.startsWith('[RESULT]')) {
              const url = msg.substring(9).trim()
              const fullUrl = `${API_BASE}${url}`
              setResultImages(prev => [...prev, fullUrl])
              setHistory(prev => {
                // Prepend to history, avoid exact duplicates if immediately retried
                if (prev[0] !== fullUrl) {
                  return [fullUrl, ...prev]
                }
                return prev
              })
            } else if (msg.startsWith('[META]')) {
              const meta = JSON.parse(msg.substring(7)) as PageMeta
              setPageMeta(prev => ({ ...prev, [meta.url]: meta }))
            } else {
              setLogs(prev => [...prev, msg])
            }
          }
        }
        if (done) break
      }
    } catch (err) {
      console.error(err)
      setLogs(prev => [...prev, "[ERROR] Could not connect to the server."])
    } finally {
      setLoading(false)
    }
  }

  const openPanelEditor = (pageUrl: string, panel: PanelMeta) => {
    setEditingPanel({ pageUrl, panel })
    setPanelPrompt(panel.prompt)
    setPanelDialogues(JSON.stringify(panel.dialogues, null, 2))
    setPanelEditMode('panel')
  }

  const openPageFromHistory = async (url: string) => {
    const pageUrl = new URL(url).pathname
    setResultImages([url])
    const meta = pageMeta[pageUrl] ?? await loadPageMeta(pageUrl)
    if (meta?.panels.length) {
      setPageMeta(prev => ({ ...prev, [pageUrl]: meta }))
    }
  }

  const savePage = async (imageUrl: string, index: number) => {
    const cleanUrl = imageUrl.split('?')[0]
    try {
      const pageUrl = new URL(cleanUrl).pathname
      const response = await fetch(`${API_BASE}/api/save-page`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageUrl, filename: `comic-page-${index + 1}-${Date.now()}.png` }),
      })
      if (!response.ok) throw new Error(await response.text())
      setSavedPages(prev => prev.includes(cleanUrl) ? prev : [...prev, cleanUrl])
      setLogs(prev => [...prev, '[SYSTEM] Comic page saved to outputs/saved.'])
    } catch (error) {
      setLogs(prev => [...prev, `[ERROR] Could not save comic page: ${error}`])
    }
  }

  const downloadPage = (imageUrl: string, index: number) => {
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = `comic-page-${index + 1}.png`
    link.target = '_blank'
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  const regeneratePanel = async () => {
    if (!editingPanel) return
    let dialogues: PanelMeta['dialogues'] = editingPanel.panel.dialogues
    if (panelEditMode === 'dialogue') {
      try {
        dialogues = JSON.parse(panelDialogues)
        if (!Array.isArray(dialogues)) throw new Error('Dialogues must be an array')
      } catch (error) {
        setLogs(prev => [...prev, `[ERROR] Invalid dialogue JSON: ${error}`])
        return
      }
    }
    setPanelRegenerating(true)
    try {
      const response = await fetch(`${API_BASE}/api/regenerate-panel`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageUrl: editingPanel.pageUrl, panelId: editingPanel.panel.id, panelPrompt, dialogues, mode: panelEditMode, steps, guidance, lora, negativePrompt, seed })
      })
      if (!response.ok) throw new Error(await response.text())
      const data = await response.json()
      const updatedUrl = `${API_BASE}${data.url}?v=${Date.now()}`
      const oldPageUrl = editingPanel.pageUrl
      // Keep the image list and metadata keyed by the canonical URL. The
      // cache-busting query string is only for the <img>; using the new URL as
      // a metadata key was leaving the old panel image visible in some cases.
      setResultImages(prev => prev.map(url => url.split('?')[0] === `${API_BASE}${oldPageUrl}` ? updatedUrl : url))
      setPageMeta(prev => {
        const old = prev[oldPageUrl]
        if (!old) return prev
        const refreshed = { ...old, url: data.url, panels: old.panels.map(p => p.id === editingPanel.panel.id ? { ...p, prompt: panelPrompt, dialogues } : p) }
        return { ...prev, [oldPageUrl]: refreshed, [data.url]: refreshed }
      })
      setEditingPanel(null)
      setLogs(prev => [...prev, panelEditMode === 'panel' ? '[SYSTEM] Panel image regenerated successfully.' : '[SYSTEM] Speech bubbles updated without rerendering the panel.'])
    } catch (error) {
      setLogs(prev => [...prev, `[ERROR] Panel regeneration failed: ${error}`])
    } finally { setPanelRegenerating(false) }
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 font-sans overflow-hidden selection:bg-gray-200">
      
      {/* 1. Far Left Icon Sidebar */}
      <div className="w-16 bg-white border-r border-gray-200 flex flex-col items-center py-6 space-y-6 z-20 shadow-sm">
        <div className="w-10 h-10 bg-gray-900 rounded-lg flex items-center justify-center mb-4 shadow-sm">
          <ImageIcon className="text-white w-5 h-5" />
        </div>
        
        <button 
          onClick={() => setActiveTab('prompt')}
          className={`p-3 rounded-xl transition-all ${activeTab === 'prompt' ? 'bg-gray-100 text-gray-900 shadow-sm' : 'text-gray-400 hover:bg-gray-50 hover:text-gray-600'}`}
          title="Storyboard & Terminal"
        >
          <Pencil className="w-5 h-5" />
        </button>

        <button 
          onClick={() => setActiveTab('models')}
          className={`p-3 rounded-xl transition-all ${activeTab === 'models' ? 'bg-gray-100 text-gray-900 shadow-sm' : 'text-gray-400 hover:bg-gray-50 hover:text-gray-600'}`}
          title="AI Model Settings"
        >
          <Settings2 className="w-5 h-5" />
        </button>

        <button 
          onClick={() => setActiveTab('layout')}
          className={`p-3 rounded-xl transition-all ${activeTab === 'layout' ? 'bg-gray-100 text-gray-900 shadow-sm' : 'text-gray-400 hover:bg-gray-50 hover:text-gray-600'}`}
          title="Layout Settings"
        >
          <LayoutTemplate className="w-5 h-5" />
        </button>
      </div>

      {/* 2. Secondary Left Sidebar (Settings/Prompt Panel) */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col z-10 shadow-sm">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-lg font-semibold tracking-tight">
            {activeTab === 'prompt' && 'Storyboard'}
            {activeTab === 'models' && 'Model Settings'}
            {activeTab === 'layout' && 'Layout Settings'}
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {/* TAB: PROMPT */}
          {activeTab === 'prompt' && (
            <div className="flex flex-col h-full space-y-6">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Your Idea</label>
                <textarea
                  className="w-full h-40 p-3 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900 focus:border-gray-900 transition-all resize-none"
                  placeholder="Example: An astronaut walking on Mars..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={loading}
                />
              </div>

              <button
                onClick={handleGenerate}
                disabled={loading || !prompt.trim()}
                className="w-full py-2.5 bg-gray-900 hover:bg-gray-800 text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                ) : <Pencil className="w-4 h-4" />}
                {loading ? "Rendering..." : "Start Rendering"}
              </button>

              <div className="flex-1 flex flex-col min-h-0 bg-gray-900 rounded-md overflow-hidden mt-4">
                <div className="bg-black/50 px-3 py-2 text-[10px] font-medium text-gray-400 uppercase tracking-widest border-b border-gray-800 flex justify-between items-center">
                  <span>Terminal</span>
                  <SlidersHorizontal className="w-3 h-3" />
                </div>
                <div className="p-3 flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed text-gray-300">
                  {logs.length === 0 ? (
                    <div className="text-gray-500 italic">Waiting for commands...</div>
                  ) : (
                    logs.map((log, i) => (
                      <div key={i} className={log.includes('ERROR') ? 'text-red-400' : log.includes('RESULT') || log.includes('DONE') ? 'text-green-400' : ''}>
                        {log}
                      </div>
                    ))
                  )}
                  <div ref={logsEndRef} />
                </div>
              </div>
            </div>
          )}

          {/* TAB: MODELS */}
          {activeTab === 'models' && (
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Base Model & LoRA</label>
                <div className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-md text-sm">Stable Diffusion 1.5</div>
                <select 
                  value={lora}
                  onChange={(e) => setLora(e.target.value)}
                  className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                >
                  {loras.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
                </select>
                <p className="text-[11px] text-gray-400">Add a supported LoRA file to <code>models/loras</code>, then refresh.</p>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Sampling Steps</label>
                  <span className="text-xs text-gray-900 font-medium">{steps}</span>
                </div>
                <input 
                  type="range" min="10" max="100" step="1" 
                  value={steps} onChange={(e) => setSteps(parseInt(e.target.value))}
                  className="w-full accent-gray-900"
                />
                <p className="text-[11px] text-gray-400">SD sampling steps (Max: 100). Higher values improve detail but take longer.</p>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">CFG Scale</label>
                  <span className="text-xs text-gray-900 font-medium">{guidance}</span>
                </div>
                <input 
                  type="range" min="1" max="30" step="0.5" 
                  value={guidance} onChange={(e) => setGuidance(parseFloat(e.target.value))}
                  className="w-full accent-gray-900"
                />
                <p className="text-[11px] text-gray-400">Prompt adherence (Max: 30). The recommended range is 7.0–8.0.</p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Negative Prompt</label>
                <textarea
                  className="w-full h-20 p-2.5 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900 focus:border-gray-900 transition-all resize-none"
                  placeholder="Example: text, watermark, bad anatomy, deformed..."
                  value={negativePrompt}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Seed (Leave empty for random)</label>
                <input
                  type="text"
                  className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                  placeholder="Example: 123456"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* TAB: LAYOUT */}
          {activeTab === 'layout' && (
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Panel Grid</label>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => setLayoutStyle('auto')} className={`p-3 border rounded-md text-sm font-medium flex flex-col items-center gap-2 ${layoutStyle === 'auto' ? 'border-gray-900 bg-gray-50 text-gray-900' : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}>
                    <div className="flex flex-wrap gap-1 w-8 h-8 justify-center">
                      <div className="w-full h-3 bg-current rounded-sm"></div>
                      <div className="w-3.5 h-3.5 bg-current rounded-sm"></div>
                      <div className="w-3 h-3.5 bg-current rounded-sm"></div>
                    </div>
                    Automatic (AI)
                  </button>
                  <button onClick={() => setLayoutStyle('manga')} className={`p-3 border rounded-md text-sm font-medium flex flex-col items-center gap-2 ${layoutStyle === 'manga' ? 'border-gray-900 bg-gray-50 text-gray-900' : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}>
                    <div className="flex flex-wrap gap-1 w-8 h-8 justify-center items-center">
                      <div className="w-3.5 h-full bg-current rounded-sm"></div>
                      <div className="flex flex-col gap-1 w-3.5 h-full">
                        <div className="w-full h-3.5 bg-current rounded-sm"></div>
                        <div className="w-full h-3.5 bg-current rounded-sm"></div>
                      </div>
                    </div>
                    Manga Grid
                  </button>
                </div>
              </div>

              {layoutStyle === 'manga' && (
                <div className="space-y-3 p-4 bg-gray-50 border border-gray-200 rounded-lg animate-in fade-in slide-in-from-top-2 duration-200">
                  <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">Choose Detailed Layout</label>
                  <div className="grid grid-cols-3 gap-2">
                    <button onClick={() => setMangaLayout('style1')} className={`p-2 border rounded-md flex justify-center items-center h-16 ${mangaLayout === 'style1' ? 'border-gray-900 bg-white ring-1 ring-gray-900' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                      <div className="flex flex-wrap gap-1 w-8 h-8">
                        <div className="w-full h-3.5 bg-gray-300 rounded-[2px]"></div>
                        <div className="w-[14px] h-3.5 bg-gray-300 rounded-[2px]"></div>
                        <div className="w-[14px] h-3.5 bg-gray-300 rounded-[2px]"></div>
                      </div>
                    </button>
                    <button onClick={() => setMangaLayout('style2')} className={`p-2 border rounded-md flex justify-center items-center h-16 ${mangaLayout === 'style2' ? 'border-gray-900 bg-white ring-1 ring-gray-900' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                      <div className="flex gap-1 w-8 h-8">
                        <div className="w-3.5 h-full bg-gray-300 rounded-[2px]"></div>
                        <div className="flex flex-col gap-1 w-3.5">
                          <div className="w-full h-3.5 bg-gray-300 rounded-[2px]"></div>
                          <div className="w-full h-3.5 bg-gray-300 rounded-[2px]"></div>
                        </div>
                      </div>
                    </button>
                    <button onClick={() => setMangaLayout('style3')} className={`p-2 border rounded-md flex justify-center items-center h-16 ${mangaLayout === 'style3' ? 'border-gray-900 bg-white ring-1 ring-gray-900' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                      <div className="flex flex-col gap-1 w-8 h-8">
                        <div className="flex gap-1 w-full h-3.5">
                           <div className="w-4 h-full bg-gray-300 rounded-[2px]"></div>
                           <div className="w-3 h-full bg-gray-300 rounded-[2px]"></div>
                        </div>
                        <div className="flex gap-1 w-full h-3.5">
                           <div className="w-3 h-full bg-gray-300 rounded-[2px]"></div>
                           <div className="w-4 h-full bg-gray-300 rounded-[2px]"></div>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>
              )}

              <div className="space-y-2 mt-6">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Speech Bubble Options</label>
                <label className="flex items-center gap-2 mt-2">
                  <input type="checkbox" defaultChecked className="rounded border-gray-300 text-gray-900 focus:ring-gray-900" />
                  <span className="text-sm text-gray-700">Automatically add speech bubbles</span>
                </label>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Main Content - Result Display */}
      <div className="flex-1 relative flex flex-col items-center justify-start p-8 overflow-y-auto bg-gray-50/50">
        {resultImages.length > 0 ? (
          <div className="flex flex-col gap-6 w-full max-w-4xl pb-16 items-center animate-in fade-in zoom-in-95 duration-300">
            {resultImages.map((image, index) => {
              const pageUrl = image.split('?')[0].replace(API_BASE, '')
              const meta = pageMeta[pageUrl]
              return <div key={`${image}-${index}`} className="relative w-full pt-14">
                <div className="pointer-events-none absolute inset-x-0 top-0 z-30 flex justify-end px-3">
                  <div className="pointer-events-auto flex gap-2">
                  <button
                    onClick={() => { void savePage(image, index) }}
                    title={savedPages.includes(image.split('?')[0]) ? 'Saved' : 'Save comic page'}
                    className={`flex items-center gap-1 rounded-md border px-3 py-2 text-xs font-medium shadow-lg backdrop-blur ${savedPages.includes(image.split('?')[0]) ? 'border-green-200 bg-green-50/95 text-green-700' : 'border-white bg-gray-900/90 text-white hover:bg-gray-700'}`}
                  ><Save className="h-4 w-4" />{savedPages.includes(image.split('?')[0]) ? 'Saved' : 'Save'}</button>
                  <button
                    onClick={() => downloadPage(image, index)}
                    title="Download comic page"
                    className="flex items-center gap-1 rounded-md border border-white bg-gray-900/90 px-3 py-2 text-xs font-medium text-white shadow-lg backdrop-blur hover:bg-gray-700"
                  ><Download className="h-4 w-4" />Download</button>
                  </div>
                </div>
                <div className="relative w-full">
                  <img src={image} alt={`Generated Comic Page ${index + 1}`} className="w-full h-auto object-contain rounded-sm shadow-lg border border-gray-200 bg-white" />
                  {meta?.panels.map(panel => <button
                    key={panel.id}
                    onClick={() => openPanelEditor(pageUrl, panel)}
                    title={`Regenerate ${panel.id}`}
                    className="absolute z-20 flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-gray-900/90 text-white shadow-lg transition hover:scale-105 hover:bg-gray-700"
                    style={{
                      left: `${((panel.x + panel.width - 58) / meta.pageWidth) * 100}%`,
                      top: `${((panel.y + 10) / meta.pageHeight) * 100}%`,
                    }}
                  ><RotateCcw className="h-4 w-4" /></button>)}
                </div>
              </div>
            })}
          </div>
        ) : (
          <div className="text-center space-y-4 text-gray-400 max-w-sm">
            <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <ImageIcon className="w-8 h-8 text-gray-300" />
            </div>
            <h3 className="text-gray-900 font-medium">Empty Canvas</h3>
            <p className="text-sm">Choose the Storyboard tab, enter your idea, and click Start Rendering.</p>
          </div>
        )}
      </div>

      {editingPanel && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-2xl">
          <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Edit and regenerate {editingPanel.panel.id}</h2><button onClick={() => setEditingPanel(null)}><X className="h-5 w-5" /></button></div>
          <div className="mb-4 flex rounded-lg bg-gray-100 p-1">
            <button onClick={() => setPanelEditMode('panel')} className={`flex-1 rounded-md px-3 py-2 text-sm font-medium ${panelEditMode === 'panel' ? 'bg-white shadow-sm' : 'text-gray-500'}`}>Edit image prompt</button>
            <button onClick={() => setPanelEditMode('dialogue')} className={`flex-1 rounded-md px-3 py-2 text-sm font-medium ${panelEditMode === 'dialogue' ? 'bg-white shadow-sm' : 'text-gray-500'}`}>Edit speech bubbles</button>
          </div>
          {panelEditMode === 'panel' ? <>
            <label className="mb-1 block text-xs font-semibold uppercase text-gray-500">Panel image prompt</label>
            <textarea value={panelPrompt} onChange={e => setPanelPrompt(e.target.value)} className="mb-2 h-32 w-full rounded-md border border-gray-300 p-3 text-sm" />
            <p className="mb-4 text-xs text-gray-500">Only this panel is sent through SD 1.5. Existing speech bubbles are preserved.</p>
          </> : <>
            <label className="mb-1 block text-xs font-semibold uppercase text-gray-500">Speech bubbles (JSON array)</label>
            <textarea value={panelDialogues} onChange={e => setPanelDialogues(e.target.value)} className="h-40 w-full rounded-md border border-gray-300 p-3 font-mono text-xs" />
            <p className="mb-4 text-xs text-gray-500">Only the page compositor runs; the panel image is not regenerated.</p>
          </>}
          <div className="mt-4 flex justify-end gap-2"><button onClick={() => setEditingPanel(null)} className="rounded-md border px-4 py-2 text-sm">Cancel</button><button onClick={regeneratePanel} disabled={panelRegenerating} className="flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"><RotateCcw className="h-4 w-4" />{panelRegenerating ? (panelEditMode === 'panel' ? 'Regenerating image...' : 'Updating bubbles...') : (panelEditMode === 'panel' ? 'Regenerate image' : 'Update bubbles')}</button></div>
        </div>
      </div>}

      {/* 4. Far Right History Sidebar */}
      <div className="w-32 bg-white border-l border-gray-200 flex flex-col z-10 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-100 bg-gray-50 flex items-center gap-2 justify-center">
          <History className="w-4 h-4 text-gray-500" />
          <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">History</span>
        </div>
        
        <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-gray-50/30">
          {history.length === 0 ? (
            <div className="text-center text-[10px] text-gray-400 mt-4 px-2">
              No comic history yet.
            </div>
          ) : (
            history.map((url, i) => (
              <button 
                key={i} 
              onClick={() => { void openPageFromHistory(url) }}
                className={`w-full relative group aspect-[2/3] rounded-md overflow-hidden border-2 transition-all ${resultImages.includes(url) ? 'border-gray-900 shadow-sm' : 'border-gray-200 hover:border-gray-400'}`}
                title={`Comic Page ${history.length - i}`}
              >
                <img 
                  src={url} 
                  alt={`History item ${i}`}
                  className="w-full h-full object-cover group-hover:opacity-90 transition-opacity" 
                />
              </button>
            ))
          )}
        </div>
      </div>

    </div>
  )
}
