import { useState, useEffect } from 'react'
import { Database, User, Plus, RefreshCw, X, Trash2, Edit, Map, BookOpen, Wand2 } from 'lucide-react'

interface DatabaseViewProps {
  activeSeries: string;
  onNextStep?: () => void;
}

export function DatabaseView({ activeSeries, onNextStep }: DatabaseViewProps) {
  const [activeSubTab, setActiveSubTab] = useState<'characters' | 'settings' | 'hooks'>('characters')
  
  // Data States
  const [characters, setCharacters] = useState<any[]>([])
  const [settings, setSettings] = useState<any[]>([])
  const [hooks, setHooks] = useState<any[]>([])
  
  // Form States
  const [showForm, setShowForm] = useState(false)
  const [formType, setFormType] = useState<'character' | 'setting' | 'hook'>('character')
  
  const [charForm, setCharForm] = useState({
    id: '', name: '', age: '', personality: '', base_prompt_en: '', seed: 42, inventory: ''
  })
  const [settingForm, setSettingForm] = useState({
    id: '', name: '', description: '', background_seed: 42
  })
  const [hookForm, setHookForm] = useState({
    description: '', chapter: 1
  })
  
  // AI Agent State
  const [aiPrompt, setAiPrompt] = useState('')
  const [generatingAi, setGeneratingAi] = useState(false)

  const fetchData = async () => {
    if (!activeSeries) return;
    try {
      const resChar = await fetch(`http://localhost:8000/api/database/characters?series_id=${activeSeries}`)
      const dataChar = await resChar.json()
      setCharacters(dataChar.characters)
      
      const resSet = await fetch(`http://localhost:8000/api/database/settings?series_id=${activeSeries}`)
      const dataSet = await resSet.json()
      setSettings(dataSet.settings)
      
      const resHook = await fetch(`http://localhost:8000/api/database/hooks?series_id=${activeSeries}`)
      const dataHook = await resHook.json()
      setHooks(dataHook.hooks)
    } catch(e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchData()
  }, [activeSeries])

  // CHARACTERS
  const handleDeleteChar = async (charId: string) => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa nhân vật này?")) return;
    await fetch(`http://localhost:8000/api/database/characters/${charId}?series_id=${activeSeries}`, { method: 'DELETE' })
    fetchData()
  }
  const handleCreateChar = async () => {
    if (!charForm.id || !charForm.name || !charForm.base_prompt_en) return alert("Thiếu thông tin bắt buộc!");
    const inventoryList = charForm.inventory ? charForm.inventory.split(',').map(i => i.trim()) : []
    await fetch('http://localhost:8000/api/database/characters/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ series_id: activeSeries, ...charForm, inventory: inventoryList })
    })
    setShowForm(false)
    fetchData()
  }

  // SETTINGS
  const handleDeleteSetting = async (setId: string) => {
    if (!window.confirm("Xóa bối cảnh này?")) return;
    await fetch(`http://localhost:8000/api/database/settings/${setId}?series_id=${activeSeries}`, { method: 'DELETE' })
    fetchData()
  }
  const handleCreateSetting = async () => {
    if (!settingForm.id || !settingForm.name) return alert("Thiếu thông tin bắt buộc!");
    await fetch('http://localhost:8000/api/database/settings/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ series_id: activeSeries, ...settingForm })
    })
    setShowForm(false)
    fetchData()
  }

  // HOOKS
  const handleDeleteHook = async (hookId: number) => {
    if (!window.confirm("Xóa cốt truyện này?")) return;
    await fetch(`http://localhost:8000/api/database/hooks/${hookId}?series_id=${activeSeries}`, { method: 'DELETE' })
    fetchData()
  }
  const handleCreateHook = async () => {
    if (!hookForm.description) return alert("Thiếu mô tả!");
    await fetch('http://localhost:8000/api/database/hooks/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ series_id: activeSeries, ...hookForm })
    })
    setShowForm(false)
    fetchData()
  }
  
  // AI AGENT
  const handleGenerateAi = async () => {
    if (!aiPrompt) return
    setGeneratingAi(true)
    try {
      const res = await fetch('http://localhost:8000/api/database/agent/character', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: aiPrompt })
      })
      const data = await res.json()
      if (data.status === 'success') {
        const char = data.character
        setCharForm({
          id: char.id || '',
          name: char.name || '',
          age: char.age || '',
          personality: char.personality || '',
          base_prompt_en: char.base_prompt_en || '',
          seed: char.seed || 42,
          inventory: ''
        })
      }
    } catch (e) {
      console.error(e)
    }
    setGeneratingAi(false)
  }

  const openForm = (type: 'character'|'setting'|'hook', item?: any) => {
    setFormType(type)
    if (type === 'character') {
      if (item) setCharForm({ ...item, inventory: item.inventory ? item.inventory.join(', ') : '' })
      else setCharForm({ id: '', name: '', age: '', personality: '', base_prompt_en: '', seed: 42, inventory: '' })
    } else if (type === 'setting') {
      if (item) setSettingForm(item)
      else setSettingForm({ id: '', name: '', description: '', background_seed: 42 })
    } else if (type === 'hook') {
      if (item) setHookForm(item)
      else setHookForm({ description: '', chapter: 1 })
    }
    setShowForm(true)
  }

  if (!activeSeries) {
    return (
      <div className="p-8 h-full bg-stone-50 flex flex-col items-center justify-center">
        <RefreshCw size={48} className="opacity-20 mb-4 text-stone-500" />
        <div className="text-stone-500 font-medium text-lg">Vui lòng chọn Bộ Truyện ở Library trước để xem Lorebook!</div>
      </div>
    )
  }

  return (
    <div className="p-8 h-full bg-stone-50 flex flex-col relative">
      <div className="flex justify-between items-center mb-6 shrink-0">
        <div>
          <h2 className="text-2xl font-light tracking-tight text-stone-900 flex items-center gap-3">
          <Database size={28} className="text-stone-500" />
          Quản Lý Dữ Liệu <span className="text-stone-400">|</span> <span className="text-stone-500 font-medium text-lg">{activeSeries}</span>
        </h2>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={fetchData} className="p-2 text-stone-500 hover:text-stone-900 hover:bg-stone-200 rounded-lg transition-colors"><RefreshCw size={20} /></button>
          {onNextStep && (
            <button onClick={onNextStep} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg shadow-sm transition-colors ml-2">
              Tiếp tục: Mở Studio
            </button>
          )}
        </div>
      </div>
      
      {/* TABS */}
      <div className="flex gap-4 border-b border-stone-200 mb-6 shrink-0">
        <button 
          className={`pb-3 px-2 font-medium flex items-center gap-2 border-b-2 transition-colors ${activeSubTab === 'characters' ? 'border-stone-900 text-stone-900' : 'border-transparent text-stone-500 hover:text-stone-700'}`}
          onClick={() => setActiveSubTab('characters')}
        >
          <User size={18} /> Nhân vật
        </button>
        <button 
          className={`pb-3 px-2 font-medium flex items-center gap-2 border-b-2 transition-colors ${activeSubTab === 'settings' ? 'border-stone-900 text-stone-900' : 'border-transparent text-stone-500 hover:text-stone-700'}`}
          onClick={() => setActiveSubTab('settings')}
        >
          <Map size={18} /> Bối cảnh
        </button>
        <button 
          className={`pb-3 px-2 font-medium flex items-center gap-2 border-b-2 transition-colors ${activeSubTab === 'hooks' ? 'border-stone-900 text-stone-900' : 'border-transparent text-stone-500 hover:text-stone-700'}`}
          onClick={() => setActiveSubTab('hooks')}
        >
          <BookOpen size={18} /> Cốt truyện
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* CHARACTERS TAB */}
        {activeSubTab === 'characters' && (
          <>
            <div className="mb-4">
              <button onClick={() => openForm('character')} className="flex items-center gap-2 bg-stone-900 hover:bg-stone-800 text-white font-medium py-2 px-4 rounded-lg shadow-sm">
                <Plus size={18} /> Thêm Nhân Vật
              </button>
            </div>
            {characters.length === 0 ? (
              <div className="text-center p-12 text-stone-400 font-medium mt-12 flex flex-col items-center gap-4">
                <User size={48} className="opacity-20" /> Chưa có nhân vật nào.
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {characters.map(char => (
                  <div key={char.id} className="group bg-white p-6 rounded-xl border border-stone-200 shadow-sm hover:shadow-md flex gap-6 relative">
                    <div className="absolute top-2 right-2 flex gap-2">
                      <button onClick={() => openForm('character', char)} className="p-1.5 bg-white text-stone-600 rounded-lg hover:bg-stone-100 border border-stone-200"><Edit size={16} /></button>
                      <button onClick={() => handleDeleteChar(char.id)} className="p-1.5 bg-white text-red-500 rounded-lg hover:bg-red-50 border border-stone-200"><Trash2 size={16} /></button>
                    </div>
                    <div className="w-24 h-24 rounded-full bg-stone-100 border border-stone-200 flex items-center justify-center shrink-0">
                      <User size={40} className="text-stone-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start mb-2">
                        <h3 className="text-xl font-bold text-stone-900 truncate">{char.name}</h3>
                        <span className="bg-stone-100 text-stone-600 text-xs px-2 py-1 rounded border border-stone-200">Seed: {char.seed}</span>
                      </div>
                      <div className="text-sm text-stone-500">ID: <span className="text-stone-900 font-mono">{char.id}</span></div>
                      <div className="text-sm text-stone-500 mt-1">Prompt: <span className="text-stone-700 italic">{char.base_prompt_en}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* SETTINGS TAB */}
        {activeSubTab === 'settings' && (
          <>
            <div className="mb-4">
              <button onClick={() => openForm('setting')} className="flex items-center gap-2 bg-stone-900 hover:bg-stone-800 text-white font-medium py-2 px-4 rounded-lg shadow-sm">
                <Plus size={18} /> Thêm Bối Cảnh
              </button>
            </div>
            {settings.length === 0 ? (
              <div className="text-center p-12 text-stone-400 font-medium flex flex-col items-center gap-4">
                <Map size={48} className="opacity-20" /> Chưa có bối cảnh nào.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {settings.map(s => (
                  <div key={s.id} className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm flex flex-col gap-2 relative">
                    <div className="absolute top-2 right-2 flex gap-2">
                      <button onClick={() => openForm('setting', s)} className="p-1 bg-white text-stone-600 rounded hover:bg-stone-100"><Edit size={16} /></button>
                      <button onClick={() => handleDeleteSetting(s.id)} className="p-1 bg-white text-red-500 rounded hover:bg-red-50"><Trash2 size={16} /></button>
                    </div>
                    <h3 className="font-bold text-lg">{s.name} <span className="text-sm font-normal text-stone-400">({s.id})</span></h3>
                    <p className="text-sm text-stone-600">{s.description}</p>
                    <div className="text-xs text-stone-400">Background Seed: {s.background_seed}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* HOOKS TAB */}
        {activeSubTab === 'hooks' && (
          <>
            <div className="mb-4">
              <button onClick={() => openForm('hook')} className="flex items-center gap-2 bg-stone-900 hover:bg-stone-800 text-white font-medium py-2 px-4 rounded-lg shadow-sm">
                <Plus size={18} /> Thêm Cốt Truyện
              </button>
            </div>
            {hooks.length === 0 ? (
              <div className="text-center p-12 text-stone-400 font-medium flex flex-col items-center gap-4">
                <BookOpen size={48} className="opacity-20" /> Chưa có cốt truyện mở nào.
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {hooks.map(h => (
                  <div key={h.id} className="bg-white p-4 rounded-lg border border-stone-200 shadow-sm flex items-center justify-between">
                    <div>
                      <p className="font-medium text-stone-800">{h.description}</p>
                      <p className="text-xs text-stone-500">Tạo ở Chapter {h.created_in_chapter}</p>
                    </div>
                    <button onClick={() => handleDeleteHook(h.id)} className="p-2 text-red-500 hover:bg-red-50 rounded-lg"><Trash2 size={18}/></button>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* MODAL FORMS */}
      {showForm && (
        <div className="absolute inset-0 bg-stone-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl flex flex-col overflow-hidden border border-stone-200">
            <div className="p-6 border-b border-stone-100 flex justify-between items-center bg-stone-50">
              <h3 className="text-xl font-bold text-stone-800">
                {formType === 'character' ? 'Thông tin Nhân Vật' : formType === 'setting' ? 'Thông tin Bối Cảnh' : 'Thông tin Cốt Truyện'}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-stone-400 hover:text-stone-600"><X size={20} /></button>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[70vh]">
              {formType === 'character' && (
                <div className="flex flex-col gap-5">
                  <div className="bg-purple-50 p-4 rounded-lg border border-purple-100 mb-2">
                    <label className="block text-sm font-bold text-purple-800 mb-2 flex items-center gap-2"><Wand2 size={16}/> Tạo bằng AI</label>
                    <div className="flex gap-2">
                      <textarea 
                        value={aiPrompt} onChange={e => setAiPrompt(e.target.value)} 
                        placeholder="VD: Cô bé phù thủy 15 tuổi, tóc hồng, mặc váy trắng..."
                        className="flex-1 p-2 border border-purple-200 rounded text-sm outline-none focus:border-purple-400"
                        rows={2}
                      />
                      <button 
                        onClick={handleGenerateAi} disabled={generatingAi}
                        className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-4 rounded font-medium transition-colors whitespace-nowrap"
                      >
                        {generatingAi ? 'Đang tạo...' : 'Tự động điền'}
                      </button>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold mb-1">ID (VD: char_anna)</label>
                      <input value={charForm.id} onChange={e => setCharForm({...charForm, id: e.target.value})} className="w-full p-2 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold mb-1">Tên hiển thị</label>
                      <input value={charForm.name} onChange={e => setCharForm({...charForm, name: e.target.value})} className="w-full p-2 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold mb-1">Tuổi</label>
                      <input value={charForm.age} onChange={e => setCharForm({...charForm, age: e.target.value})} className="w-full p-2 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold mb-1">Seed (-1 = Random)</label>
                      <input type="number" value={charForm.seed} onChange={e => setCharForm({...charForm, seed: parseInt(e.target.value) || 0})} className="w-full p-2 border rounded" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-1">Prompt tiếng Anh (Ngoại hình)</label>
                    <textarea rows={3} value={charForm.base_prompt_en} onChange={e => setCharForm({...charForm, base_prompt_en: e.target.value})} className="w-full p-2 border rounded" />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-1">Tính cách</label>
                    <input value={charForm.personality} onChange={e => setCharForm({...charForm, personality: e.target.value})} className="w-full p-2 border rounded" />
                  </div>
                </div>
              )}

              {formType === 'setting' && (
                <div className="flex flex-col gap-4">
                  <div>
                    <label className="block text-sm font-semibold mb-1">ID (VD: loc_cave)</label>
                    <input value={settingForm.id} onChange={e => setSettingForm({...settingForm, id: e.target.value})} className="w-full p-2 border rounded" />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-1">Tên Bối Cảnh</label>
                    <input value={settingForm.name} onChange={e => setSettingForm({...settingForm, name: e.target.value})} className="w-full p-2 border rounded" />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-1">Mô tả (Prompt)</label>
                    <textarea rows={3} value={settingForm.description} onChange={e => setSettingForm({...settingForm, description: e.target.value})} className="w-full p-2 border rounded" />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-1">Background Seed</label>
                    <input type="number" value={settingForm.background_seed} onChange={e => setSettingForm({...settingForm, background_seed: parseInt(e.target.value) || 0})} className="w-full p-2 border rounded" />
                  </div>
                </div>
              )}

              {formType === 'hook' && (
                <div className="flex flex-col gap-4">
                  <div>
                    <label className="block text-sm font-semibold mb-1">Mô tả cốt truyện (Unresolved Hook)</label>
                    <textarea rows={3} value={hookForm.description} onChange={e => setHookForm({...hookForm, description: e.target.value})} className="w-full p-2 border rounded" />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-1">Chapter khởi tạo</label>
                    <input type="number" value={hookForm.chapter} onChange={e => setHookForm({...hookForm, chapter: parseInt(e.target.value) || 1})} className="w-full p-2 border rounded" />
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-5 border-t border-stone-100 flex justify-end gap-3 bg-stone-50">
              <button onClick={() => setShowForm(false)} className="px-5 py-2 border rounded text-stone-600">Hủy</button>
              <button onClick={() => formType === 'character' ? handleCreateChar() : formType === 'setting' ? handleCreateSetting() : handleCreateHook()} className="px-5 py-2 bg-stone-900 text-white rounded font-medium">
                Lưu
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
