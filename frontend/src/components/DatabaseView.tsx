import { useState, useEffect } from 'react'
import { Database, User, Plus, RefreshCw, X, Trash2, Edit } from 'lucide-react'

interface DatabaseViewProps {
  activeSeries: string;
  onNextStep?: () => void;
}

export function DatabaseView({ activeSeries, onNextStep }: DatabaseViewProps) {
  const [characters, setCharacters] = useState<any[]>([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    id: '', name: '', age: '', personality: '', base_prompt_en: '', seed: 42, inventory: ''
  })

  const fetchCharacters = async () => {
    if (!activeSeries) {
      setCharacters([]);
      return;
    }
    const res = await fetch(`http://localhost:8000/api/database/characters?series_id=${activeSeries}`)
    const data = await res.json()
    setCharacters(data.characters)
  }

  const handleDelete = async (charId: string) => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa nhân vật này?")) return;
    try {
      await fetch(`http://localhost:8000/api/database/characters/${charId}?series_id=${activeSeries}`, {
        method: 'DELETE'
      })
      fetchCharacters()
    } catch (e) {
      console.error(e)
    }
  }

  const handleEdit = (char: any) => {
    setForm({
      id: char.id,
      name: char.name,
      age: char.age,
      personality: char.personality,
      base_prompt_en: char.base_prompt_en,
      seed: char.seed || 42,
      inventory: char.inventory ? char.inventory.join(', ') : ''
    })
    setShowForm(true)
  }

  useEffect(() => {
    fetchCharacters()
  }, [activeSeries])

  const handleCreate = async () => {
    if (!form.id || !form.name || !form.base_prompt_en) {
      alert("Vui lòng nhập đủ ID, Name và Prompt!")
      return
    }

    const inventoryList = form.inventory ? form.inventory.split(',').map(i => i.trim()) : []
    
    await fetch('http://localhost:8000/api/database/characters/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        series_id: activeSeries,
        ...form,
        inventory: inventoryList
      })
    })

    setShowForm(false)
    setForm({ id: '', name: '', age: '', personality: '', base_prompt_en: '', seed: 42, inventory: '' })
    fetchCharacters()
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
      <div className="flex justify-between items-center mb-8 border-b border-stone-200 pb-4 shrink-0">
        <div>
          <h2 className="text-2xl font-light tracking-tight text-stone-900 flex items-center gap-3">
          <Database size={28} className="text-stone-500" />
          Lorebook <span className="text-stone-400">|</span> <span className="text-stone-500 font-medium text-lg">{activeSeries || 'Chưa chọn truyện'}</span>
        </h2>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchCharacters}
            className="p-2 text-stone-500 hover:text-stone-900 hover:bg-stone-200 rounded-lg transition-colors"
            title="Làm mới"
          >
            <RefreshCw size={20} />
          </button>
          <button 
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 bg-stone-900 hover:bg-stone-800 text-white font-medium py-2 px-4 rounded-lg shadow-sm transition-colors"
          >
            <Plus size={18} />
            Thêm Nhân Vật
          </button>
          {onNextStep && (
            <button 
              onClick={onNextStep}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg shadow-sm transition-colors ml-2"
            >
              Tiếp tục: Mở Studio
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {characters.length === 0 ? (
          <div className="text-center p-12 text-stone-400 font-medium mt-12 flex flex-col items-center gap-4">
            <User size={48} className="opacity-20" />
            Vũ trụ truyện này chưa có nhân vật nào. Hãy bắt đầu sáng tạo!
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {characters.map(char => {
              let inventory = []
              try {
                if (typeof char.inventory === 'string') {
                  inventory = JSON.parse(char.inventory)
                } else if (Array.isArray(char.inventory)) {
                  inventory = char.inventory
                }
              } catch(e) {
                inventory = []
              }

              return (
                <div key={char.id} className="group bg-white p-6 rounded-xl border border-stone-200 shadow-sm hover:shadow-md transition-shadow flex gap-6 relative">
                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                    <button onClick={() => handleEdit(char)} className="p-1.5 bg-white text-stone-600 rounded-lg hover:bg-stone-100 shadow-sm border border-stone-200" title="Chỉnh sửa">
                      <Edit size={16} />
                    </button>
                    <button onClick={() => handleDelete(char.id)} className="p-1.5 bg-white text-red-500 rounded-lg hover:bg-red-50 shadow-sm border border-stone-200" title="Xóa">
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <div className="w-24 h-24 rounded-full bg-stone-100 border border-stone-200 flex items-center justify-center shrink-0">
                    <User size={40} className="text-stone-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="text-xl font-bold text-stone-900 truncate">{char.name}</h3>
                      <span className="bg-stone-100 text-stone-600 text-xs px-2 py-1 rounded font-medium border border-stone-200">Seed: {char.seed}</span>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-y-2 gap-x-4 mb-4 text-sm">
                      <div className="col-span-1 text-stone-500">ID:</div>
                      <div className="col-span-2 text-stone-900 font-mono font-medium truncate">{char.id}</div>
                      
                      <div className="col-span-1 text-stone-500">Tuổi:</div>
                      <div className="col-span-2 text-stone-900">{char.age || 'N/A'}</div>
                      
                      <div className="col-span-1 text-stone-500">Tính cách:</div>
                      <div className="col-span-2 text-stone-900 truncate" title={char.personality}>{char.personality || 'N/A'}</div>

                      <div className="col-span-1 text-stone-500">Prompt:</div>
                      <div className="col-span-2 text-stone-700 italic text-xs line-clamp-3">{char.base_prompt_en}</div>
                    </div>

                    {inventory.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {inventory.map((item: string, idx: number) => (
                          <span key={idx} className="bg-stone-100 border border-stone-200 text-stone-600 text-xs px-3 py-1 rounded-full">
                            {item}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* CREATE MODAL */}
      {showForm && (
        <div className="absolute inset-0 bg-stone-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col max-h-full overflow-hidden border border-stone-200">
            <div className="p-6 border-b border-stone-100 flex justify-between items-center bg-stone-50">
              <h3 className="text-xl font-bold text-stone-800">Thêm nhân vật mới</h3>
              <button onClick={() => setShowForm(false)} className="text-stone-400 hover:text-stone-600 bg-white rounded p-1 border border-stone-200 shadow-sm"><X size={20} /></button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1 flex flex-col gap-5">
              <div className="grid grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-semibold text-stone-700 mb-1">ID Nhân vật (VD: char_bob)</label>
                  <input type="text" value={form.id} onChange={e => setForm({...form, id: e.target.value})} className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg focus:ring-1 focus:ring-stone-500 outline-none text-sm" placeholder="ID viết liền không dấu..." />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-stone-700 mb-1">Tên hiển thị (Name)</label>
                  <input type="text" value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg focus:ring-1 focus:ring-stone-500 outline-none text-sm" placeholder="VD: Bob" />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-stone-700 mb-1">Tuổi (Age)</label>
                  <input type="text" value={form.age} onChange={e => setForm({...form, age: e.target.value})} className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg focus:ring-1 focus:ring-stone-500 outline-none text-sm" placeholder="VD: 30" />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-stone-700 mb-1">Cố định Seed (Random: -1)</label>
                  <input type="number" value={form.seed} onChange={e => setForm({...form, seed: parseInt(e.target.value) || 0})} className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg focus:ring-1 focus:ring-stone-500 outline-none text-sm" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-stone-700 mb-1">Ngoại hình (Base Prompt EN)</label>
                <textarea rows={3} value={form.base_prompt_en} onChange={e => setForm({...form, base_prompt_en: e.target.value})} className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg focus:ring-1 focus:ring-stone-500 outline-none text-sm resize-none" placeholder="a young man, messy hair, wearing a white shirt... (Prompt tiếng Anh)" />
              </div>

              <div>
                <label className="block text-sm font-semibold text-stone-700 mb-1">Tính cách (Personality)</label>
                <textarea rows={2} value={form.personality} onChange={e => setForm({...form, personality: e.target.value})} className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg focus:ring-1 focus:ring-stone-500 outline-none text-sm resize-none" placeholder="Vui vẻ, hòa đồng..." />
              </div>

              <div>
                <label className="block text-sm font-semibold text-stone-700 mb-1">Hành trang / Sở hữu (Cách nhau bằng dấu phẩy)</label>
                <input type="text" value={form.inventory} onChange={e => setForm({...form, inventory: e.target.value})} className="w-full p-2.5 bg-stone-50 border border-stone-300 rounded-lg focus:ring-1 focus:ring-stone-500 outline-none text-sm" placeholder="Kiếm, áo giáp, sách phép..." />
              </div>
            </div>

            <div className="p-6 border-t border-stone-100 flex justify-end gap-3 bg-stone-50">
              <button onClick={() => setShowForm(false)} className="px-6 py-2.5 rounded-lg border border-stone-300 text-stone-600 font-medium hover:bg-stone-100 transition-colors">Hủy</button>
              <button onClick={handleCreate} className="px-6 py-2.5 rounded-lg bg-stone-900 text-white font-medium hover:bg-stone-800 transition-colors shadow-md">Lưu Nhân Vật</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
