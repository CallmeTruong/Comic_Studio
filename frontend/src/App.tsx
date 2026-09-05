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
  const [activePage, setActivePage] = useState('comic_page_1.png')

  // Global Generation State
  const [loading, setLoading] = useState(false)
  const [isWaitingApproval, setIsWaitingApproval] = useState(false)
  const [draftSchema, setDraftSchema] = useState<any>(null)
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
              // Only clear loading if we are not waiting for approval
              setLoading(false)
            } else if (msg.startsWith('[SCHEMA_READY]')) {
              const schemaStr = msg.substring(14).trim()
              try {
                setDraftSchema(JSON.parse(schemaStr))
              } catch(e) {
                console.error("Failed to parse schema", e)
              }
              setIsWaitingApproval(true)
              setLoading(false)
              setLogs(prev => [...prev, "✅ Đã tạo xong kịch bản, vui lòng xác nhận!"])
            } else if (msg.startsWith('[CANCELLED]')) {
              setLoading(false)
              setLogs(prev => [...prev, msg])
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

  const handleResume = async () => {
    if (!activeSeries || !activeChapter) return
    setLoading(true)
    setLogs(["[SYSTEM] Khôi phục kết nối với AI..."])
    
    try {
      const response = await fetch('http://localhost:8000/api/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ series_id: activeSeries, chapter_id: activeChapter })
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
            } else if (msg.startsWith('[SCHEMA_READY]')) {
              const schemaStr = msg.substring(14).trim()
              try {
                setDraftSchema(JSON.parse(schemaStr))
              } catch(e) {
                console.error("Failed to parse schema", e)
              }
              setIsWaitingApproval(true)
              setLoading(false)
              setLogs(prev => [...prev, "✅ Đã tạo xong kịch bản, vui lòng xác nhận!"])
            } else if (msg.startsWith('[CANCELLED]')) {
              setLoading(false)
              setLogs(prev => [...prev, msg])
            } else {
              setLogs(prev => [...prev, msg])
            }
          }
        }
      }
    } catch (e) {
      console.error(e)
      setLogs(prev => [...prev, "❌ Error resuming comic"])
      setLoading(false)
    }
  }

  return (
    <div className="h-screen w-screen flex bg-stone-50 overflow-hidden font-sans text-stone-900 pb-10">
      <Sidebar activeTab={activeTab} onChangeTab={setActiveTab} isLocked={!activeSeries || !activeChapter} />
      
      <div className="flex-1 bg-white overflow-hidden relative">
        {activeTab === 'library' && (
          <LibraryView 
            activeSeries={activeSeries} 
            activeChapter={activeChapter} 
            onSelect={handleSelectChapter} 
            onNextStep={() => setActiveTab('database')}
            onEditPage={(pageName) => {
              setActivePage(pageName);
              setActiveTab('canvas');
            }}
          />
        )}
        {activeTab === 'canvas' && (
          <InteractiveCanvasView 
            seriesId={activeSeries} 
            chapterId={activeChapter} 
            pageName={activePage}
            onGenerate={handleGenerate}
            onResume={handleResume}
            loading={loading}
            isWaitingApproval={isWaitingApproval}
            setIsWaitingApproval={setIsWaitingApproval}
            setLogs={setLogs}
            draftSchema={draftSchema}
          />
        )}
        {activeTab === 'settings' && <SettingsView />}
        {activeTab === 'database' && (
          <DatabaseView 
            activeSeries={activeSeries} 
            onNextStep={() => setActiveTab('canvas')} 
          />
        )}
      </div>
      
      <GlobalTerminal logs={logs} loading={loading} />
    </div>
  )
}

export default App
