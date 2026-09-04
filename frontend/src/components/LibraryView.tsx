import { useState, useEffect } from 'react'
import { Library, Folder, BookOpen, Plus, Search, Image as ImageIcon, Trash2, Maximize2, ExternalLink, RefreshCw, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LibraryViewProps {
  activeSeries: string;
  activeChapter: string;
  onSelect: (series: string, chapter: string) => void;
  onNextStep: () => void;
  onEditPage?: (pageName: string) => void;
}

export function LibraryView({ activeSeries, activeChapter, onSelect, onNextStep, onEditPage }: LibraryViewProps) {
  const [seriesList, setSeriesList] = useState<any[]>([])
  const [showCreateSeries, setShowCreateSeries] = useState(false)
  const [showCreateChapter, setShowCreateChapter] = useState(false)
  const [newSeriesName, setNewSeriesName] = useState('')
  const [newChapterName, setNewChapterName] = useState('')
  const [targetSeriesForChapter, setTargetSeriesForChapter] = useState('')
  
  // Explorer state
  const [explorerData, setExplorerData] = useState<{pages: string[], panels: string[]} | null>(null)
  const [activeFolder, setActiveFolder] = useState<'root' | 'panels'>('root')
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchSeries = async () => {
    const res = await fetch('http://localhost:8000/api/series')
    const data = await res.json()
    setSeriesList(data.series)
  }

  const fetchExplorerData = async () => {
    if (!activeSeries || !activeChapter) return;
    setRefreshing(true);
    const res = await fetch(`http://localhost:8000/api/explorer?series_id=${activeSeries}&chapter_id=${activeChapter}`)
    const data = await res.json()
    setExplorerData(data)
    setRefreshing(false);
  }

  useEffect(() => {
    fetchSeries()
  }, [])

  useEffect(() => {
    fetchExplorerData()
  }, [activeSeries, activeChapter])

  const handleCreateSeries = async () => {
    if (!newSeriesName) return
    await fetch('http://localhost:8000/api/series/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ series_id: newSeriesName })
    })
    setShowCreateSeries(false)
    setNewSeriesName('')
    fetchSeries()
  }

  const handleCreateChapter = async () => {
    if (!newChapterName || !targetSeriesForChapter) return
    await fetch('http://localhost:8000/api/chapter/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ series_id: targetSeriesForChapter, chapter_id: newChapterName })
    })
    setShowCreateChapter(false)
    setNewChapterName('')
    fetchSeries()
  }

  const handleDeleteFile = async (filename: string, isPanel: boolean) => {
    if (!confirm(`Bạn có chắc muốn xóa ảnh ${filename}?`)) return;
    await fetch('http://localhost:8000/api/explorer/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        series_id: activeSeries, 
        chapter_id: activeChapter,
        filename,
        is_panel: isPanel
      })
    })
    fetchExplorerData();
  }

  return (
    <div className="flex h-full bg-stone-50 overflow-hidden">
      
      {/* LEFT PANE: Directory Tree */}
      <div className="w-80 bg-white border-r border-stone-200 flex flex-col shrink-0">
        <div className="p-6 border-b border-stone-100 flex justify-between items-center bg-stone-50 shrink-0">
          <h2 className="text-xl font-bold tracking-tight text-stone-900 flex items-center gap-2">
            <Library size={24} className="text-stone-500" />
            Thư viện
          </h2>
          <button 
            onClick={() => setShowCreateSeries(true)}
            className="p-2 hover:bg-stone-200 rounded-lg transition-colors text-stone-600"
            title="Tạo truyện mới"
          >
            <Plus size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="space-y-4">
            {seriesList.length === 0 ? (
              <div className="text-center text-stone-500 text-sm mt-8">Chưa có bộ truyện nào</div>
            ) : (
              seriesList.map(series => (
                <div key={series.id} className="space-y-1">
                  <div className="flex items-center gap-2 text-stone-800 font-bold px-2 py-1.5 hover:bg-stone-100 rounded cursor-pointer group">
                    <Folder size={18} className="text-stone-400 group-hover:text-stone-600" />
                    <span className="truncate">{series.name}</span>
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        setTargetSeriesForChapter(series.id);
                        setShowCreateChapter(true);
                      }}
                      className="ml-auto opacity-0 group-hover:opacity-100 p-1 hover:bg-stone-200 rounded text-stone-500 transition-opacity"
                      title="Thêm Chapter"
                    >
                      <Plus size={14} />
                    </button>
                  </div>
                  
                  <div className="pl-6 space-y-1">
                    {series.chapters.length === 0 ? (
                      <div className="text-xs text-stone-400 italic px-2 py-1">Chưa có chapter</div>
                    ) : (
                      series.chapters.map((chapter: string) => (
                        <div 
                          key={chapter}
                          onClick={() => {
                            onSelect(series.id, chapter)
                            setActiveFolder('root')
                          }}
                          className={cn(
                            "flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-sm transition-colors",
                            activeSeries === series.id && activeChapter === chapter
                              ? "bg-stone-900 text-white font-medium" 
                              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
                          )}
                        >
                          <BookOpen size={14} className={activeSeries === series.id && activeChapter === chapter ? "text-stone-300" : "text-stone-400"} />
                          <span className="truncate">{chapter}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* RIGHT PANE: File Explorer */}
      <div className="flex-1 flex flex-col min-w-0 bg-stone-50 relative">
        {!activeSeries || !activeChapter ? (
          <div className="m-auto flex flex-col items-center justify-center opacity-50">
            <Folder size={64} className="mb-4 text-stone-400" />
            <p className="text-lg font-medium text-stone-600">Chọn một Chapter để duyệt file</p>
          </div>
        ) : (
          <>
            {/* Explorer Header */}
            <div className="h-16 border-b border-stone-200 bg-white flex items-center justify-between px-6 shrink-0">
              <div className="flex items-center gap-2 text-stone-600 font-medium text-sm">
                <span className="cursor-pointer hover:text-stone-900 hover:underline" onClick={() => setActiveFolder('root')}>
                  {activeSeries} / {activeChapter}
                </span>
                {activeFolder === 'panels' && (
                  <>
                    <span className="text-stone-400">/</span>
                    <span className="text-stone-900">panels</span>
                  </>
                )}
              </div>
              
              <div className="flex gap-2">
                <button 
                  onClick={fetchExplorerData}
                  className="p-2 hover:bg-stone-100 text-stone-600 rounded-lg transition-colors flex items-center gap-2"
                >
                  <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
                  <span className="text-sm font-medium">Làm mới</span>
                </button>
                <button 
                  onClick={() => { onSelect(activeSeries, activeChapter); onNextStep() }}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-bold text-sm transition-colors flex items-center gap-2 shadow-sm"
                >
                  Tiếp tục: Cấu hình Nhân vật <ExternalLink size={16} />
                </button>
              </div>
            </div>

            {/* Explorer Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {activeFolder === 'root' ? (
                // ROOT FOLDER VIEW
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                  {/* Panels Directory Icon */}
                  <div 
                    onClick={() => setActiveFolder('panels')}
                    className="group flex flex-col items-center gap-3 p-4 rounded-xl hover:bg-stone-100 cursor-pointer transition-colors border border-transparent hover:border-stone-200"
                  >
                    <Folder size={64} className="text-amber-400 fill-amber-100 drop-shadow-sm group-hover:scale-105 transition-transform" strokeWidth={1.5} />
                    <span className="font-medium text-stone-800 text-sm">panels</span>
                  </div>

                  {/* Comic Pages */}
                  {explorerData?.pages.map(file => (
                    <div key={file} className="group relative flex flex-col items-center gap-3 p-4 rounded-xl hover:bg-white cursor-pointer transition-all border border-transparent hover:border-stone-200 hover:shadow-sm">
                      <div className="w-full aspect-[2/3] bg-stone-100 rounded-lg overflow-hidden border border-stone-200 relative">
                        <img 
                          src={`http://localhost:8000/outputs/series/${activeSeries}/${activeChapter}/${file}?t=${Date.now()}`} 
                          className="w-full h-full object-cover"
                          alt={file}
                        />
                        {/* Hover overlay actions */}
                        <div className="absolute inset-0 bg-stone-900/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                          <button onClick={(e) => { e.stopPropagation(); setPreviewImage(`http://localhost:8000/outputs/series/${activeSeries}/${activeChapter}/${file}?t=${Date.now()}`) }} className="p-2 bg-white rounded-full text-stone-900 hover:scale-110 transition-transform" title="Xem ảnh">
                            <Maximize2 size={16} />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); onSelect(activeSeries, activeChapter); if(onEditPage) onEditPage(file); else onNextStep(); }} className="p-2 bg-white rounded-full text-stone-900 hover:scale-110 transition-transform" title="Chỉnh sửa trong Studio">
                            <ExternalLink size={16} />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); handleDeleteFile(file, false) }} className="p-2 bg-red-500 rounded-full text-white hover:scale-110 transition-transform" title="Xóa ảnh">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                      <span className="font-medium text-stone-700 text-xs truncate w-full text-center" title={file}>{file}</span>
                    </div>
                  ))}
                  
                  {explorerData?.pages.length === 0 && (
                    <div className="col-span-full text-center text-stone-400 mt-12 italic">Chưa có trang truyện nào được tạo.</div>
                  )}
                </div>
              ) : (
                // PANELS FOLDER VIEW
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
                  {explorerData?.panels.map(file => (
                    <div key={file} className="group relative flex flex-col items-center gap-3 p-4 rounded-xl hover:bg-white cursor-pointer transition-all border border-transparent hover:border-stone-200 hover:shadow-sm">
                      <div className="w-full aspect-square bg-stone-100 rounded-lg overflow-hidden border border-stone-200 relative">
                        <img 
                          src={`http://localhost:8000/outputs/series/${activeSeries}/${activeChapter}/panels/${file}?t=${Date.now()}`} 
                          className="w-full h-full object-cover"
                          alt={file}
                        />
                        <div className="absolute inset-0 bg-stone-900/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                          <button onClick={(e) => { e.stopPropagation(); setPreviewImage(`http://localhost:8000/outputs/series/${activeSeries}/${activeChapter}/panels/${file}?t=${Date.now()}`) }} className="p-2 bg-white rounded-full text-stone-900 hover:scale-110 transition-transform">
                            <Maximize2 size={16} />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); handleDeleteFile(file, true) }} className="p-2 bg-red-500 rounded-full text-white hover:scale-110 transition-transform">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                      <span className="font-medium text-stone-700 text-xs truncate w-full text-center" title={file}>{file}</span>
                    </div>
                  ))}
                  
                  {explorerData?.panels.length === 0 && (
                    <div className="col-span-full text-center text-stone-400 mt-12 italic">Thư mục panels trống.</div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* LIGHTBOX PREVIEW */}
      {previewImage && (
        <div className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-sm flex items-center justify-center p-8" onClick={() => setPreviewImage(null)}>
          <button 
            className="absolute top-6 right-6 text-white/50 hover:text-white p-2"
            onClick={() => setPreviewImage(null)}
          >
            <X size={32} />
          </button>
          <img 
            src={previewImage} 
            alt="Preview" 
            className="max-w-full max-h-full object-contain drop-shadow-2xl rounded"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* CREATE SERIES MODAL */}
      {showCreateSeries && (
        <div className="fixed inset-0 bg-stone-900/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-[400px] overflow-hidden">
            <div className="p-4 border-b border-stone-100 flex justify-between items-center bg-stone-50">
              <h3 className="font-bold text-stone-800">Tạo Truyện Mới</h3>
              <button onClick={() => setShowCreateSeries(false)} className="text-stone-400 hover:text-stone-600"><X size={20} /></button>
            </div>
            <div className="p-6">
              <input 
                type="text" 
                value={newSeriesName} 
                onChange={e => setNewSeriesName(e.target.value)} 
                className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg outline-none focus:ring-1 focus:ring-stone-500" 
                placeholder="Tên bộ truyện (ví dụ: superman_v1)..." 
                autoFocus
              />
              <button onClick={handleCreateSeries} className="w-full mt-4 bg-stone-900 text-white font-medium py-2.5 rounded-lg hover:bg-stone-800">Tạo mới</button>
            </div>
          </div>
        </div>
      )}

      {/* CREATE CHAPTER MODAL */}
      {showCreateChapter && (
        <div className="fixed inset-0 bg-stone-900/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-[400px] overflow-hidden">
            <div className="p-4 border-b border-stone-100 flex justify-between items-center bg-stone-50">
              <h3 className="font-bold text-stone-800">Thêm Chapter mới</h3>
              <button onClick={() => setShowCreateChapter(false)} className="text-stone-400 hover:text-stone-600"><X size={20} /></button>
            </div>
            <div className="p-6">
              <p className="text-sm text-stone-500 mb-3">Tạo cho bộ: <span className="font-bold text-stone-800">{targetSeriesForChapter}</span></p>
              <input 
                type="text" 
                value={newChapterName} 
                onChange={e => setNewChapterName(e.target.value)} 
                className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg outline-none focus:ring-1 focus:ring-stone-500" 
                placeholder="Tên chapter (ví dụ: chap_01)..." 
                autoFocus
              />
              <button onClick={handleCreateChapter} className="w-full mt-4 bg-stone-900 text-white font-medium py-2.5 rounded-lg hover:bg-stone-800">Tạo Chapter</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
