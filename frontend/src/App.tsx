import { useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { InteractiveCanvasView } from './components/InteractiveCanvasView'
import { SettingsView } from './components/SettingsView'
import { DatabaseView } from './components/DatabaseView'
import { LibraryView } from './components/LibraryView'
import { GlobalTerminal } from './components/GlobalTerminal'

function App() {
  const [activeTab, setActiveTab] = useState('library')
  const [activeSeries, setActiveSeries] = useState('')
  const [activeChapter, setActiveChapter] = useState('')

  // Global Generation State
  const [loading, setLoading] = useState(false)
  const [logs, setLogs] = useState<string[]>([])

  const handleSelectChapter = (series: string, chapter: string) => {
    setActiveSeries(series)
    setActiveChapter(chapter)
  }

  const handleGenerate = async (prompt: string) => {
    if (!activeSeries || !activeChapter) {
      alert("Vui lòng chọn Bộ Truyện và Chapter trong Library trước!");
      return;
    }
    setLoading(true)
    setLogs(["[STUDIO] Khởi tạo hệ thống..."])
    try {
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, series_id: activeSeries, chapter_id: activeChapter })
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
              // Trigger a schema refetch by a small hack or passing a callback
              // For now, InteractiveCanvasView will fetch if we pass a refresh trigger, 
              // but we can just let InteractiveCanvasView poll or we pass an onComplete prop.
            } else {
              setLogs(prev => [...prev, msg])
            }
          }
        }
      }
    } catch (e) {
      console.error(e)
      setLogs(prev => [...prev, "❌ Error generating comic"])
      setLoading(false)
    }
  }

  return (
    <div className="h-screen w-screen flex bg-stone-50 overflow-hidden font-sans text-stone-900 pb-10">
      <Sidebar activeTab={activeTab} onChangeTab={setActiveTab} />
      
      <div className="flex-1 bg-white overflow-hidden relative">
        {activeTab === 'library' && (
          <LibraryView 
            activeSeries={activeSeries} 
            activeChapter={activeChapter} 
            onSelect={handleSelectChapter} 
            onNavigateToStudio={() => setActiveTab('canvas')}
          />
        )}
        {activeTab === 'canvas' && (
          <InteractiveCanvasView 
            seriesId={activeSeries} 
            chapterId={activeChapter} 
            onGenerate={handleGenerate}
            loading={loading}
          />
        )}
        {activeTab === 'settings' && <SettingsView />}
        {activeTab === 'database' && <DatabaseView activeSeries={activeSeries} />}
      </div>
      
      <GlobalTerminal logs={logs} loading={loading} />
    </div>
  )
}

export default App
