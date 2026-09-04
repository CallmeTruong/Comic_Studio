import { useState, useEffect } from 'react'
import { Save, Settings, Layers, Sliders, Image as ImageIcon, FileText } from 'lucide-react'

export function SettingsView() {
  const [config, setConfig] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('models')

  useEffect(() => {
    fetch('http://localhost:8000/api/config')
      .then(res => res.json())
      .then(data => setConfig(data))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    await fetch('http://localhost:8000/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    setSaving(false)
    alert("Đã lưu cấu hình thành công!")
  }

  const updateConfig = (section: string, key: string, value: any) => {
    setConfig((prev: any) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }))
  }

  if (!config) return <div className="p-8 text-stone-500 font-medium">Loading config...</div>

  const tabs = [
    { id: 'models', label: 'Models & ControlNet', icon: <Layers size={18} /> },
    { id: 'quality', label: 'Quality & Steps', icon: <Sliders size={18} /> },
    { id: 'page', label: 'Page & Panel Layout', icon: <ImageIcon size={18} /> },
    { id: 'story', label: 'Story & Agents', icon: <FileText size={18} /> },
  ]

  return (
    <div className="p-8 h-full bg-stone-50 flex flex-col">
      <div className="flex justify-between items-center mb-8 border-b border-stone-200 pb-4">
        <h2 className="text-2xl font-light tracking-tight text-stone-900 flex items-center gap-3">
          <Settings size={28} className="text-stone-500" />
          Advanced Settings
        </h2>
        <button 
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-stone-900 hover:bg-stone-800 text-white font-medium py-2 px-6 rounded-lg shadow-sm transition-all disabled:opacity-50"
        >
          <Save size={18} />
          {saving ? 'Đang lưu...' : 'Lưu Cài Đặt'}
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden gap-6">
        {/* Tabs sidebar */}
        <div className="w-64 flex flex-col gap-2 shrink-0">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-3 p-3 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.id 
                  ? 'bg-stone-800 text-white' 
                  : 'text-stone-600 hover:bg-stone-200'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto bg-white border border-stone-200 rounded-xl p-8 shadow-sm">
          
          {activeTab === 'models' && (
            <div className="flex flex-col gap-6 max-w-2xl">
              <h3 className="text-lg font-bold border-b border-stone-100 pb-2">Models & Generation</h3>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">Base Model Path</label>
                <input 
                  type="text" 
                  value={config.models.base_model}
                  onChange={(e) => updateConfig('models', 'base_model', e.target.value)}
                  className="w-full p-2 border border-stone-300 rounded text-sm bg-stone-50"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">LoRA Path</label>
                  <input 
                    type="text" 
                    value={config.models.lora_path}
                    onChange={(e) => updateConfig('models', 'lora_path', e.target.value)}
                    className="w-full p-2 border border-stone-300 rounded text-sm bg-stone-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1 flex justify-between">
                    <span>LoRA Scale</span>
                    <span>{config.models.lora_scale}</span>
                  </label>
                  <input 
                    type="range" min="0" max="1" step="0.05"
                    value={config.models.lora_scale}
                    onChange={(e) => updateConfig('models', 'lora_scale', parseFloat(e.target.value))}
                    className="w-full mt-2"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1 flex justify-between">
                  <span>Guidance Scale (CFG)</span>
                  <span>{config.models.guidance_scale}</span>
                </label>
                <input 
                  type="range" min="1" max="15" step="0.5"
                  value={config.models.guidance_scale}
                  onChange={(e) => updateConfig('models', 'guidance_scale', parseFloat(e.target.value))}
                  className="w-full mt-2"
                />
              </div>
              
              <h3 className="text-lg font-bold border-b border-stone-100 pb-2 mt-4">ControlNet Options</h3>
              <div className="flex items-center gap-3">
                <input 
                  type="checkbox"
                  checked={config.models.use_controlnet}
                  onChange={(e) => updateConfig('models', 'use_controlnet', e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm font-medium">Bật ControlNet (Tăng độ chính xác nhân vật)</span>
              </div>
            </div>
          )}

          {activeTab === 'quality' && (
            <div className="flex flex-col gap-6 max-w-2xl">
              <h3 className="text-lg font-bold border-b border-stone-100 pb-2">Quality Settings</h3>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-2">Quality Mode</label>
                <div className="flex gap-4">
                  {['fast', 'balanced', 'high'].map(mode => (
                    <label key={mode} className="flex items-center gap-2 cursor-pointer">
                      <input 
                        type="radio" name="quality_mode" value={mode}
                        checked={config.quality.mode === mode}
                        onChange={(e) => updateConfig('quality', 'mode', e.target.value)}
                        className="accent-stone-800"
                      />
                      <span className="text-sm capitalize">{mode}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Base Steps</label>
                  <input 
                    type="number" 
                    value={config.quality.base_steps}
                    onChange={(e) => updateConfig('quality', 'base_steps', parseInt(e.target.value))}
                    className="w-full p-2 border border-stone-300 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Panel Steps</label>
                  <input 
                    type="number" 
                    value={config.quality.panel_steps}
                    onChange={(e) => updateConfig('quality', 'panel_steps', parseInt(e.target.value))}
                    className="w-full p-2 border border-stone-300 rounded text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Max Render Width</label>
                  <input 
                    type="number" 
                    value={config.quality.max_render_width}
                    onChange={(e) => updateConfig('quality', 'max_render_width', parseInt(e.target.value))}
                    className="w-full p-2 border border-stone-300 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Max Render Height</label>
                  <input 
                    type="number" 
                    value={config.quality.max_render_height}
                    onChange={(e) => updateConfig('quality', 'max_render_height', parseInt(e.target.value))}
                    className="w-full p-2 border border-stone-300 rounded text-sm"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'page' && (
            <div className="flex flex-col gap-6 max-w-2xl">
              <h3 className="text-lg font-bold border-b border-stone-100 pb-2">Page Properties</h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Page Width (px)</label>
                  <input type="number" value={config.page.width} onChange={(e) => updateConfig('page', 'width', parseInt(e.target.value))} className="w-full p-2 border border-stone-300 rounded text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Page Height (px)</label>
                  <input type="number" value={config.page.height} onChange={(e) => updateConfig('page', 'height', parseInt(e.target.value))} className="w-full p-2 border border-stone-300 rounded text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Margin (px)</label>
                  <input type="number" value={config.page.margin} onChange={(e) => updateConfig('page', 'margin', parseInt(e.target.value))} className="w-full p-2 border border-stone-300 rounded text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Gutter (Khoảng cách Panel)</label>
                  <input type="number" value={config.page.gutter} onChange={(e) => updateConfig('page', 'gutter', parseInt(e.target.value))} className="w-full p-2 border border-stone-300 rounded text-sm" />
                </div>
              </div>

              <h3 className="text-lg font-bold border-b border-stone-100 pb-2 mt-4">Panel Resolution</h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Panel Width (Render)</label>
                  <input type="number" value={config.panel.width} onChange={(e) => updateConfig('panel', 'width', parseInt(e.target.value))} className="w-full p-2 border border-stone-300 rounded text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">Panel Height (Render)</label>
                  <input type="number" value={config.panel.height} onChange={(e) => updateConfig('panel', 'height', parseInt(e.target.value))} className="w-full p-2 border border-stone-300 rounded text-sm" />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'story' && (
            <div className="flex flex-col gap-6 max-w-2xl">
              <h3 className="text-lg font-bold border-b border-stone-100 pb-2">Agent & Graph Settings</h3>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">Max Retries (Validator)</label>
                <input 
                  type="number" 
                  value={config.story.max_retries}
                  onChange={(e) => updateConfig('story', 'max_retries', parseInt(e.target.value))}
                  className="w-full p-2 border border-stone-300 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">Timeout (Seconds)</label>
                <input 
                  type="number" 
                  value={config.story.timeout}
                  onChange={(e) => updateConfig('story', 'timeout', parseInt(e.target.value))}
                  className="w-full p-2 border border-stone-300 rounded text-sm"
                />
              </div>
              <div className="flex items-center gap-3">
                <input 
                  type="checkbox"
                  checked={config.story.force_regenerate_schema}
                  onChange={(e) => updateConfig('story', 'force_regenerate_schema', e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm font-medium">Bắt buộc render lại Schema mới (khi Tạo truyện mới)</span>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
