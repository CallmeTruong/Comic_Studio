import { useState, useRef, useEffect } from 'react'
import { Pencil, Settings2, LayoutTemplate, SlidersHorizontal, Image as ImageIcon, History } from 'lucide-react'

export default function App() {
  const [activeTab, setActiveTab] = useState<'prompt' | 'models' | 'layout'>('prompt')
  
  // Generation State
  const [prompt, setPrompt] = useState("")
  const [loading, setLoading] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [resultImage, setResultImage] = useState<string | null>(null)
  const [history, setHistory] = useState<string[]>([])
  
  // Settings State (UI Demo)
  const [steps, setSteps] = useState(20)
  const [guidance, setGuidance] = useState(7.5)
  const [lora, setLora] = useState("ghibli")
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
    fetch('http://127.0.0.1:8000/api/history')
      .then(res => res.json())
      .then(data => {
        if (data.history && data.history.length > 0) {
          const fullUrls = data.history.map((url: string) => `http://127.0.0.1:8000${url}`)
          setHistory(fullUrls)
        }
      })
      .catch(err => console.error("Could not load history", err))
  }, [])

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setActiveTab('prompt') // Switch back to prompt tab to see logs
    setLogs(["[SYSTEM] Đang gửi yêu cầu..."])
    setResultImage(null)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/generate', {
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
          seed
        })
      })
      
      if (!response.body) return
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        const text = decoder.decode(value)
        const lines = text.split('\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const msg = line.substring(6)
            if (msg === '[DONE]') {
              setLoading(false)
            } else if (msg.startsWith('[RESULT]')) {
              const url = msg.substring(9).trim()
              const fullUrl = `http://127.0.0.1:8000${url}`
              setResultImage(fullUrl)
              setHistory(prev => {
                // Prepend to history, avoid exact duplicates if immediately retried
                if (prev[0] !== fullUrl) {
                  return [fullUrl, ...prev]
                }
                return prev
              })
            } else {
              setLogs(prev => [...prev, msg])
            }
          }
        }
      }
    } catch (err) {
      console.error(err)
      setLogs(prev => [...prev, "[ERROR] Không thể kết nối với server."])
      setLoading(false)
    }
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
          title="Kịch bản & Terminal"
        >
          <Pencil className="w-5 h-5" />
        </button>

        <button 
          onClick={() => setActiveTab('models')}
          className={`p-3 rounded-xl transition-all ${activeTab === 'models' ? 'bg-gray-100 text-gray-900 shadow-sm' : 'text-gray-400 hover:bg-gray-50 hover:text-gray-600'}`}
          title="Cấu hình AI Model"
        >
          <Settings2 className="w-5 h-5" />
        </button>

        <button 
          onClick={() => setActiveTab('layout')}
          className={`p-3 rounded-xl transition-all ${activeTab === 'layout' ? 'bg-gray-100 text-gray-900 shadow-sm' : 'text-gray-400 hover:bg-gray-50 hover:text-gray-600'}`}
          title="Bố cục & Layout"
        >
          <LayoutTemplate className="w-5 h-5" />
        </button>
      </div>

      {/* 2. Secondary Left Sidebar (Settings/Prompt Panel) */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col z-10 shadow-sm">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-lg font-semibold tracking-tight">
            {activeTab === 'prompt' && 'Kịch Bản'}
            {activeTab === 'models' && 'Cấu Hình Model'}
            {activeTab === 'layout' && 'Tùy Chỉnh Bố Cục'}
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {/* TAB: PROMPT */}
          {activeTab === 'prompt' && (
            <div className="flex flex-col h-full space-y-6">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Ý tưởng của bạn</label>
                <textarea
                  className="w-full h-40 p-3 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900 focus:border-gray-900 transition-all resize-none"
                  placeholder="Ví dụ: Một phi hành gia đi dạo trên sao hỏa..."
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
                {loading ? "Đang Vẽ..." : "Bắt Đầu Vẽ"}
              </button>

              <div className="flex-1 flex flex-col min-h-0 bg-gray-900 rounded-md overflow-hidden mt-4">
                <div className="bg-black/50 px-3 py-2 text-[10px] font-medium text-gray-400 uppercase tracking-widest border-b border-gray-800 flex justify-between items-center">
                  <span>Terminal</span>
                  <SlidersHorizontal className="w-3 h-3" />
                </div>
                <div className="p-3 flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed text-gray-300">
                  {logs.length === 0 ? (
                    <div className="text-gray-500 italic">Chờ lệnh...</div>
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
                <select 
                  value={lora}
                  onChange={(e) => setLora(e.target.value)}
                  className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                >
                  <option value="ghibli">Ghibli Style (Anime)</option>
                  <option value="mjmanga">MjManga (Manga Style)</option>
                  <option value="ukiyo">Ukiyo-e (Nhật Bản Cổ)</option>
                  <option value="vintage">1950s Vintage Art</option>
                  <option value="cartoony">Cartoony (Hoạt Hình Tây)</option>
                </select>
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
                <p className="text-[11px] text-gray-400">Số bước chạy SD (Max: 100), cao hơn sẽ nét hơn nhưng chậm.</p>
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
                <p className="text-[11px] text-gray-400">Mức độ bám sát mô tả (Max: 30). Chuẩn là 7.0 - 8.0.</p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Negative Prompt</label>
                <textarea
                  className="w-full h-20 p-2.5 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900 focus:border-gray-900 transition-all resize-none"
                  placeholder="Ví dụ: text, watermark, bad anatomy, deformed..."
                  value={negativePrompt}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Seed (Để trống nếu muốn Random)</label>
                <input
                  type="text"
                  className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                  placeholder="Ví dụ: 123456"
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
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Kiểu chia khung (Grid)</label>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => setLayoutStyle('auto')} className={`p-3 border rounded-md text-sm font-medium flex flex-col items-center gap-2 ${layoutStyle === 'auto' ? 'border-gray-900 bg-gray-50 text-gray-900' : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}>
                    <div className="flex flex-wrap gap-1 w-8 h-8 justify-center">
                      <div className="w-full h-3 bg-current rounded-sm"></div>
                      <div className="w-3.5 h-3.5 bg-current rounded-sm"></div>
                      <div className="w-3 h-3.5 bg-current rounded-sm"></div>
                    </div>
                    Tự động (AI)
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
                  <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">Chọn Layout Chi Tiết</label>
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
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tùy chọn Bong Bóng Thoại</label>
                <label className="flex items-center gap-2 mt-2">
                  <input type="checkbox" defaultChecked className="rounded border-gray-300 text-gray-900 focus:ring-gray-900" />
                  <span className="text-sm text-gray-700">Tự động gắn bong bóng thoại</span>
                </label>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Main Content - Result Display */}
      <div className="flex-1 relative flex items-center justify-center p-8 overflow-y-auto bg-gray-50/50">
        {resultImage ? (
          <div className="relative max-h-full">
            <img 
              src={resultImage} 
              alt="Generated Comic" 
              className="max-w-full max-h-[90vh] object-contain rounded-sm shadow-lg border border-gray-200 bg-white" 
            />
          </div>
        ) : (
          <div className="text-center space-y-4 text-gray-400 max-w-sm">
            <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <ImageIcon className="w-8 h-8 text-gray-300" />
            </div>
            <h3 className="text-gray-900 font-medium">Bản Vẽ Trống</h3>
            <p className="text-sm">Hãy chọn tab Kịch bản bên trái, nhập nội dung bạn muốn và nhấn nút Bắt Đầu Vẽ.</p>
          </div>
        )}
      </div>

      {/* 4. Far Right History Sidebar */}
      <div className="w-32 bg-white border-l border-gray-200 flex flex-col z-10 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-100 bg-gray-50 flex items-center gap-2 justify-center">
          <History className="w-4 h-4 text-gray-500" />
          <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">History</span>
        </div>
        
        <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-gray-50/30">
          {history.length === 0 ? (
            <div className="text-center text-[10px] text-gray-400 mt-4 px-2">
              Chưa có lịch sử tạo truyện.
            </div>
          ) : (
            history.map((url, i) => (
              <button 
                key={i} 
                onClick={() => setResultImage(url)}
                className={`w-full relative group aspect-[2/3] rounded-md overflow-hidden border-2 transition-all ${resultImage === url ? 'border-gray-900 shadow-sm' : 'border-gray-200 hover:border-gray-400'}`}
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
