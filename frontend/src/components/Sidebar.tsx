import { Settings, Database, Paintbrush, Library, Lock } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SidebarProps {
  activeTab: string;
  onChangeTab: (tab: string) => void;
  isLocked: boolean;
}

export function Sidebar({ activeTab, onChangeTab, isLocked }: SidebarProps) {
  const tabs = [
    { id: 'library', icon: <Library size={24} />, label: 'Bước 1: Dự án', locked: false },
    { id: 'database', icon: <Database size={24} />, label: 'Bước 2: Nhân vật', locked: isLocked },
    { id: 'canvas', icon: <Paintbrush size={24} />, label: 'Bước 3: Studio', locked: isLocked },
  ]

  return (
    <div className="w-20 lg:w-64 bg-stone-900 border-r border-stone-800 flex flex-col items-center lg:items-stretch py-8 shrink-0 shadow-xl z-10">
      <div className="mb-10 px-4 lg:px-8 text-center lg:text-left">
        <h1 className="text-white font-light text-2xl tracking-tight hidden lg:block">Comic<span className="font-bold">Studio</span></h1>
        <div className="text-white font-bold text-2xl block lg:hidden">CS</div>
      </div>
      
      <div className="flex flex-col gap-2 px-3 lg:px-4 flex-1 mt-6">
        {tabs.map(tab => {
          const isActive = activeTab === tab.id
          const isLocked = tab.locked
          return (
            <button
              key={tab.id}
              onClick={() => !isLocked && onChangeTab(tab.id)}
              className={cn(
                "group flex items-center justify-center lg:justify-start gap-4 p-3 lg:px-4 rounded-lg transition-all relative overflow-hidden",
                isActive 
                  ? "text-white bg-stone-800 shadow-inner" 
                  : isLocked
                    ? "text-stone-600 cursor-not-allowed opacity-50"
                    : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50"
              )}
              title={tab.label}
              disabled={isLocked}
            >
              <div className="relative z-10">{isLocked ? <Lock size={24} className="opacity-50" /> : tab.icon}</div>
              <span className="font-medium text-sm hidden lg:block relative z-10">{tab.label}</span>
              {isActive && (
                <div className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-blue-500 rounded-r-md"></div>
              )}
            </button>
          )
        })}
      </div>

      {/* Settings at the bottom */}
      <div className="px-3 lg:px-4 mb-4 mt-auto">
        <button
          onClick={() => onChangeTab('settings')}
          className={cn(
            "w-full group flex items-center justify-center lg:justify-start gap-4 p-3 lg:px-4 rounded-lg transition-all relative overflow-hidden",
            activeTab === 'settings'
              ? "text-white bg-stone-800 shadow-inner" 
              : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50"
          )}
          title="Cài đặt"
        >
          <div className="relative z-10"><Settings size={24} /></div>
          <span className="font-medium text-sm hidden lg:block relative z-10">Cài đặt</span>
        </button>
      </div>
    </div>
  )
}
