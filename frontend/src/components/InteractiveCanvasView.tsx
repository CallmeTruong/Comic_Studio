import { useState, useEffect, useRef } from 'react'
import { RefreshCw } from 'lucide-react'

interface Panel {
  id: string;
  description_en: string;
  panel_prompt_en: string;
  dialogues: Array<{
    character: string;
    text: string;
    emotion?: string;
  }>;
}

interface InteractiveCanvasProps {
  seriesId: string;
  chapterId: string;
  pageName: string;
  onGenerate: (prompt: string) => void;
  onResume: () => void;
  loading: boolean;
  isWaitingApproval?: boolean;
  setIsWaitingApproval?: (val: boolean) => void;
  setLogs?: (val: any) => void;
  draftSchema?: any;
}

export function InteractiveCanvasView({ seriesId, chapterId, pageName, onGenerate, onResume, loading, isWaitingApproval, setIsWaitingApproval, setLogs, draftSchema }: InteractiveCanvasProps) {
  const [schema, setSchema] = useState<{panels: Panel[], layout?: any} | null>(null)
  const [prompt, setPrompt] = useState("Anna khám phá một hang động băng tuyết bí ẩn.")
  const [hasCharacters, setHasCharacters] = useState<boolean | null>(null)

  useEffect(() => {
    if (seriesId) {
      fetch(`http://localhost:8000/api/database/characters?series_id=${seriesId}`)
        .then(res => res.json())
        .then(data => {
          setHasCharacters(data.characters && data.characters.length > 0)
        })
    }
  }, [seriesId, chapterId])

  const fetchSchema = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/schema?series_id=${seriesId}&chapter_id=${chapterId}&page_name=${pageName}`)
      const data = await res.json()
      setSchema(data)
    } catch (e) {
      console.error(e)
    }
  }

  if (hasCharacters === false) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-stone-50 h-full p-8">
         <div className="bg-white p-10 rounded-2xl shadow-xl border border-red-200 text-center max-w-md">
           <h3 className="text-2xl font-bold text-red-600 mb-4">Vũ trụ trống rỗng!</h3>
           <p className="text-stone-600 mb-6">Bạn chưa tạo nhân vật nào trong Lorebook. Bạn cần tạo ít nhất 1 nhân vật để AI có thể hiểu bối cảnh và viết kịch bản chính xác.</p>
           <p className="text-stone-500 text-sm font-medium">👉 Hãy sang tab "Quản Lý Dữ Liệu" ở thanh bên trái để bắt đầu!</p>
         </div>
      </div>
    )
  }

  useEffect(() => {
    if (isWaitingApproval && draftSchema) {
      setSchema(draftSchema)
    } else if (seriesId && chapterId) {
      fetchSchema()
    } else {
      setSchema(null)
    }
  }, [seriesId, chapterId, pageName, loading, isWaitingApproval, draftSchema])

  const handleRenderPage = async () => {
    if (!schema || !setIsWaitingApproval || !setLogs) return
    setIsWaitingApproval(false)
    setLogs((prev: any) => [...prev, "[STUDIO] Bắt đầu quá trình vẽ trang..."])
    
    try {
      const response = await fetch('http://localhost:8000/api/render_page', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          series_id: seriesId, 
          chapter_id: chapterId, 
          panels: schema.panels 
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
              // done
            } else if (msg.startsWith('[SCHEMA_READY]')) {
              setIsWaitingApproval(true)
              setLogs((prev: any) => [...prev, "✅ Đã tạo xong kịch bản trang tiếp theo, vui lòng xác nhận!"])
            } else {
              setLogs((prev: any) => [...prev, msg])
            }
          }
        }
      }
    } catch (e) {
      console.error(e)
      setLogs((prev: any) => [...prev, "❌ Error rendering comic"])
    }
  }

  const handleRegeneratePanel = async (panelId: string, newPrompt: string) => {
    const confirmed = window.confirm(`Bạn có chắc muốn vẽ lại Panel: ${panelId} không?`)
    if (!confirmed) return
    
    await fetch('http://localhost:8000/api/regenerate_panel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panel_id: panelId, new_prompt: newPrompt, series_id: seriesId, chapter_id: chapterId, page_name: pageName })
    })
    
    alert(`Đã vẽ lại panel ${panelId}!`)
    fetchSchema()
  }

  const containerRef = useRef<HTMLDivElement>(null)

  return (
    <div className="flex h-full">
      {/* Editor Sidebar */}
      <div className="w-96 bg-stone-50 border-r border-stone-200 p-6 flex flex-col shrink-0">
        <h3 className="font-bold text-stone-800 uppercase tracking-wide text-sm mb-4">Mô tả cốt truyện</h3>
        <textarea 
          className="w-full h-40 p-4 border border-stone-300 rounded-lg resize-none focus:outline-none focus:border-stone-500 focus:ring-1 focus:ring-stone-500 transition-all text-stone-700 bg-white shadow-sm"
          placeholder="Nhập ý tưởng..."
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
        />
        <div className="mt-4 flex flex-col gap-2">
          <div className="flex gap-2">
            <button 
              onClick={() => onGenerate(prompt)}
              disabled={loading || !seriesId || !chapterId}
              className="flex-1 bg-stone-800 hover:bg-stone-900 text-white font-medium py-3 px-4 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Đang tạo...' : 'Tạo Truyện Mới'}
            </button>
            <button 
              onClick={() => onResume()}
              disabled={loading || !seriesId || !chapterId}
              className="flex-1 bg-amber-600 hover:bg-amber-700 text-white font-medium py-3 px-4 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Tiếp Tục (Resume)
            </button>
          </div>
          
          {loading && (
            <button
              onClick={async () => {
                await fetch('http://localhost:8000/api/cancel', { method: 'POST' })
              }}
              className="w-full bg-red-500 hover:bg-red-600 text-white font-medium py-3 px-4 rounded-lg shadow-md transition-colors"
            >
              Dừng khẩn cấp
            </button>
          )}
        </div>

        {schema?.panels && (
          <div className="mt-8 flex-1 overflow-y-auto">
            <h3 className="font-bold text-stone-800 uppercase tracking-wide text-sm mb-4">Các khung hình (Panels)</h3>
            <div className="flex flex-col gap-4">
              {schema.panels.map((p, idx) => (
                <div key={idx} className="bg-white p-4 rounded-lg border border-stone-200 shadow-sm">
                  <div className="font-bold text-stone-800 mb-1">{p.id}</div>
                  <div className="text-xs text-stone-500 mb-2">{p.description_en}</div>
                  
                  <div className="mt-3">
                    <div className="text-xs font-semibold text-stone-400 uppercase mb-1">Prompt vẽ:</div>
                    <textarea 
                      className="w-full p-2 border border-stone-200 rounded text-xs bg-stone-50 focus:outline-none focus:border-stone-400 focus:bg-white transition-colors"
                      value={p.panel_prompt_en}
                      onChange={e => {
                        const newPanels = [...schema.panels]
                        newPanels[idx].panel_prompt_en = e.target.value
                        setSchema({...schema, panels: newPanels})
                      }}
                      rows={3}
                    />
                  </div>
                  
                  {p.dialogues && p.dialogues.length > 0 && (
                    <div className="mt-3">
                      <div className="text-xs font-semibold text-stone-400 uppercase mb-1">Lời thoại:</div>
                      {p.dialogues.map((d, dIdx) => (
                        <div key={dIdx} className="mb-2">
                          <span className="text-xs font-bold text-stone-600">{d.character}:</span>
                          <textarea 
                            className="w-full p-2 border border-stone-200 rounded text-xs bg-stone-50 focus:outline-none focus:border-stone-400 focus:bg-white transition-colors mt-1"
                            value={d.text}
                            onChange={e => {
                              const newPanels = [...schema.panels]
                              newPanels[idx].dialogues[dIdx].text = e.target.value
                              setSchema({...schema, panels: newPanels})
                            }}
                            rows={2}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 overflow-y-auto p-8 relative flex flex-col items-center bg-stone-100">
        <div className="w-full max-w-4xl flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-light tracking-tight text-stone-800">Studio Workspace</h2>
            {seriesId && chapterId && (
              <div className="text-stone-500 text-sm mt-1">
                Project: <span className="font-medium text-stone-700">{seriesId}</span> / <span className="font-medium text-stone-700">{chapterId}</span>
              </div>
            )}
          </div>
        </div>
        
        {(!seriesId || !chapterId) ? (
          <div className="m-auto text-stone-400 text-lg flex flex-col items-center gap-4 mt-20">
            <RefreshCw size={48} className="opacity-20" />
            Vui lòng chọn Bộ Truyện và Chapter trong thư viện.
          </div>
        ) : isWaitingApproval ? (
          <div className="m-auto flex flex-col items-center justify-center bg-white p-8 rounded-xl shadow-lg border border-stone-200 max-w-lg text-center mt-20">
            <h3 className="text-xl font-bold text-stone-800 mb-2">Đã tạo xong kịch bản trang</h3>
            <p className="text-stone-600 mb-6 text-sm">
              Hãy kiểm tra và chỉnh sửa lại Prompt vẽ cùng với Lời thoại ở cột bên trái cho phù hợp.
              Khi đã ưng ý, hãy bấm Xác nhận để hệ thống bắt đầu vẽ ảnh cho trang này.
            </p>
            <button 
              onClick={handleRenderPage}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-lg shadow-md transition-colors w-full"
            >
              Xác nhận & Vẽ ảnh
            </button>
          </div>
        ) : schema?.panels && schema.panels.length > 0 ? (
          <div ref={containerRef} className="relative w-full max-w-4xl bg-white border border-stone-300 rounded shadow-lg overflow-hidden shrink-0">
            <img 
              src={`http://localhost:8000/outputs/series/${seriesId}/${chapterId}/${pageName}?t=${new Date().getTime()}`} 
              alt="Comic Page" 
              className="w-full block" 
            />
            
            {/* Overlay for Regenerating Panels with Corner Icons */}
            <div className="absolute inset-0 pointer-events-none">
              {schema.layout && schema.layout.panels && schema.layout.panels.map((rect: number[], idx: number) => {
                const [x, y, w, h] = rect;
                const panel = schema.panels[idx];
                if (!panel) return null;
                
                const leftPct = (x / schema.layout.page_width) * 100;
                const topPct = (y / schema.layout.page_height) * 100;
                const widthPct = (w / schema.layout.page_width) * 100;
                const heightPct = (h / schema.layout.page_height) * 100;
                
                return (
                  <div 
                    key={idx} 
                    className="absolute group pointer-events-auto z-10"
                    style={{
                      left: `${leftPct}%`,
                      top: `${topPct}%`,
                      width: `${widthPct}%`,
                      height: `${heightPct}%`
                    }}
                  >
                    <button 
                      onClick={() => handleRegeneratePanel(panel.id, panel.panel_prompt_en)}
                      className="absolute bottom-2 right-2 opacity-30 hover:opacity-100 bg-stone-800 text-white p-2 rounded-full shadow-md transition-all flex items-center justify-center"
                      title={`Vẽ lại ${panel.id}`}
                    >
                      <RefreshCw size={18} />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="m-auto text-stone-400 mt-20">Chưa có dữ liệu trang truyện. Hãy bấm "Tạo Truyện".</div>
        )}
      </div>
    </div>
  )
}
