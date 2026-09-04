import { useState, useEffect } from 'react'
import { Save, Settings } from 'lucide-react'

interface SettingsData {
  models: string[];
  current_model: string;
  lora_path: string;
  lora_scale: number;
  guidance_scale: number;
  quality_mode: string;
  layout: string;
  available_loras?: string[];
}

export function SettingsView() {
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('http://localhost:8000/api/config')
      .then(res => res.json())
      .then(data => setSettings(data))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    await fetch('http://localhost:8000/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lora_path: settings?.lora_path,
        lora_scale: settings?.lora_scale,
        guidance_scale: settings?.guidance_scale,
        quality_mode: settings?.quality_mode,
        layout: settings?.layout
      })
    })
    setSaving(false)
    alert("Đã lưu cấu hình!")
  }

  if (!settings) return <div className="p-8 text-stone-500 font-medium">Loading config...</div>

  return (
    <div className="p-8 h-full bg-stone-50 flex flex-col">
      <div className="flex justify-between items-center mb-8 border-b border-stone-200 pb-4">
        <h2 className="text-2xl font-light tracking-tight text-stone-900 flex items-center gap-3">
          <Settings size={28} className="text-stone-500" />
          System Settings
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

      <div className="flex-1 overflow-y-auto max-w-2xl">
        <div className="bg-white border border-stone-200 p-6 rounded-xl shadow-sm flex flex-col gap-6">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-2">Base Model</label>
            <select 
              value={settings.current_model}
              onChange={(e) => setSettings({...settings, current_model: e.target.value})}
              className="w-full p-2.5 border border-stone-300 rounded-lg text-sm focus:border-stone-500 focus:ring-1 focus:ring-stone-500 outline-none bg-stone-50 transition-colors"
            >
              {settings.models.map((m: string) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-2">LoRA Style</label>
            <select
              value={settings.lora_path || ""}
              onChange={(e) => setSettings({...settings, lora_path: e.target.value})}
              className="w-full p-2.5 border border-stone-300 rounded-lg text-sm focus:border-stone-500 focus:ring-1 focus:ring-stone-500 outline-none bg-stone-50 transition-colors"
            >
              <option value="">Không dùng LoRA</option>
              {settings.available_loras?.map(lora => (
                <option key={lora} value={lora}>{lora.split('/').pop()}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-2 flex justify-between">
                <span>Độ mạnh LoRA (Scale)</span>
                <span className="text-stone-500">{settings.lora_scale}</span>
              </label>
              <input 
                type="range" min="0" max="1" step="0.05"
                value={settings.lora_scale}
                onChange={(e) => setSettings({...settings, lora_scale: parseFloat(e.target.value)})}
                className="w-full"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-2 flex justify-between">
                <span>Guidance Scale (CFG)</span>
                <span className="text-stone-500">{settings.guidance_scale}</span>
              </label>
              <input 
                type="range" min="1" max="20" step="0.5"
                value={settings.guidance_scale}
                onChange={(e) => setSettings({...settings, guidance_scale: parseFloat(e.target.value)})}
                className="w-full"
              />
            </div>
          </div>

          <hr className="border-stone-100 my-2" />

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-2">Chất lượng Render (Quality Mode)</label>
            <div className="flex gap-4">
              {['fast', 'balanced', 'high'].map(mode => (
                <label key={mode} className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="radio" 
                    name="quality_mode" 
                    value={mode}
                    checked={settings.quality_mode === mode}
                    onChange={(e) => setSettings({...settings, quality_mode: e.target.value})}
                    className="accent-stone-800"
                  />
                  <span className="text-sm text-stone-700 capitalize">{mode}</span>
                </label>
              ))}
            </div>
            <p className="text-xs text-stone-400 mt-2">
              Fast: ~20 steps (Render nhanh nhất). Balanced: ~40 steps (Được khuyên dùng). High: ~60 steps (Đẹp nhưng mất thời gian).
            </p>
          </div>

        </div>
      </div>
    </div>
  )
}
