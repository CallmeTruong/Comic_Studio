import { useState, useEffect, useRef } from 'react'
import { Bubble } from './Bubble'
import { RefreshCw, Save } from 'lucide-react'

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
  onGenerate: (prompt: string) => void;
  loading: boolean;
}

export function InteractiveCanvasView({ seriesId, chapterId, onGenerate, loading }: InteractiveCanvasProps) {
  const [schema, setSchema] = useState<{panels: Panel[], layout?: any} | null>(null)
  const [prompt, setPrompt] = useState("Anna khám phá một hang động băng tuyết bí ẩn.")
  const [bubbles, setBubbles] = useState<any[]>([])

  const fetchSchema = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/schema?series_id=${seriesId}&chapter_id=${chapterId}`)
      const data = await res.json()
      setSchema(data)
      
      if (data && data.panels && data.layout && data.layout.panels) {
        const newBubbles: any[] = []
        data.panels.forEach((p: Panel, pIdx: number) => {
          const rect = data.layout.panels[pIdx]
          if (rect) {
            const [px, py, pw, ph] = rect
            p.dialogues.forEach((d, dIdx) => {
              newBubbles.push({
                id: `${p.id}_bubble_${dIdx}`,
                panelId: p.id,
                text: d.text,
                x: (px / data.layout.page_width) * 100 + 5, // 5% offset
                y: (py / data.layout.page_height) * 100 + 5 + (dIdx * 10), // offset by index
                width: 150, 
                height: 80 
              })
            })
          }
        })
        setBubbles(newBubbles)
      } else {
        setBubbles([])
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    if (seriesId && chapterId) {
      fetchSchema()
    } else {
      setSchema(null)
      setBubbles([])
    }
  }, [seriesId, chapterId, loading]) // Re-fetch schema when loading turns false

  const handleUpdateBubbleText = (id: string, newText: string) => {
    setBubbles(prev => prev.map(b => b.id === id ? { ...b, text: newText } : b))
  }

  const handleSaveAndRender = async () => {
    if (!schema) return
    const newSchema = { ...schema }
    newSchema.panels = newSchema.panels.map(p => {
      const pBubbles = bubbles.filter(b => b.panelId === p.id)
      const newDialogues = pBubbles.map(b => ({
        character: p.dialogues.find(d => d.text === b.text)?.character || 'unknown',
        text: b.text
      }))
      return { ...p, dialogues: newDialogues }
    })
    
    await fetch('http://localhost:8000/api/update_bubbles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panels: newSchema.panels, series_id: seriesId, chapter_id: chapterId })
    })
    
    alert("Đã lưu và render lại Text! Bạn có thể xem ảnh mới.")
    fetchSchema()
  }

  const handleRegeneratePanel = async (panelId: string, newPrompt: string) => {
    const confirmed = window.confirm(`Bạn có chắc muốn vẽ lại Panel: ${panelId} không?`)
    if (!confirmed) return
    
    await fetch('http://localhost:8000/api/regenerate_panel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panel_id: panelId, new_prompt: newPrompt, series_id: seriesId, chapter_id: chapterId })
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
        <button 
          onClick={() => onGenerate(prompt)}
          disabled={loading || !seriesId || !chapterId}
          className="mt-4 bg-stone-800 hover:bg-stone-900 text-white font-medium py-3 px-4 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Đang tạo truyện...' : 'Tạo Truyện'}
        </button>

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
          {schema?.panels && (
            <button 
              onClick={handleSaveAndRender}
              className="flex items-center gap-2 bg-white hover:bg-stone-50 text-stone-800 font-medium py-2 px-4 rounded-lg border border-stone-300 shadow-sm transition-all active:bg-stone-100"
            >
              <Save size={18} /> Lưu Text
            </button>
          )}
        </div>
        
        {(!seriesId || !chapterId) ? (
          <div className="m-auto text-stone-400 text-lg flex flex-col items-center gap-4 mt-20">
            <RefreshCw size={48} className="opacity-20" />
            Vui lòng chọn Bộ Truyện và Chapter trong thư viện.
          </div>
        ) : schema?.panels && schema.panels.length > 0 ? (
          <div ref={containerRef} className="relative w-full max-w-4xl bg-white border border-stone-300 rounded shadow-lg overflow-hidden shrink-0">
            <img 
              src={`http://localhost:8000/outputs/series/${seriesId}/${chapterId}/comic_page_1.png?t=${new Date().getTime()}`} 
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

            {/* Bubbles on Top Layer */}
            <div className="absolute inset-0 pointer-events-none z-20">
              {bubbles.map(bubble => (
                <Bubble 
                  key={bubble.id} 
                  text={bubble.text}
                  x={bubble.x}
                  y={bubble.y}
                  width={bubble.width}
                  height={bubble.height}
                  parentRef={containerRef}
                  onChange={(newText) => handleUpdateBubbleText(bubble.id, newText)} 
                  onDragStop={(x, y) => {
                    setBubbles(prev => prev.map(b => b.id === bubble.id ? { ...b, x, y } : b))
                  }}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="m-auto text-stone-400 mt-20">Chưa có dữ liệu trang truyện. Hãy bấm "Tạo Truyện".</div>
        )}
      </div>
    </div>
  )
}
