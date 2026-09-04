import { Terminal, X, ChevronUp, ChevronDown, Loader2 } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

interface GlobalTerminalProps {
  logs: string[];
  loading: boolean;
}

export function GlobalTerminal({ logs, loading }: GlobalTerminalProps) {
  const [expanded, setExpanded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  // If not loading and no logs, maybe keep it collapsed or minimal.
  // Actually, always show a small bar if there are logs, or if loading.
  if (!loading && logs.length === 0) return null;

  return (
    <div className={`fixed bottom-0 left-0 right-0 bg-stone-900 border-t border-stone-800 text-stone-300 font-mono text-sm shadow-2xl transition-all duration-300 z-50 ${expanded ? 'h-64' : 'h-10'}`}>
      <div 
        className="flex items-center justify-between px-4 h-10 cursor-pointer bg-stone-800 hover:bg-stone-700 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {loading ? <Loader2 size={16} className="animate-spin text-blue-400" /> : <Terminal size={16} className="text-stone-400" />}
          <span className="font-bold tracking-wider uppercase text-xs">
            {loading ? 'System Processing...' : 'System Idle'}
          </span>
          {!expanded && logs.length > 0 && (
            <span className="text-stone-500 truncate max-w-xl">
              {logs[logs.length - 1]}
            </span>
          )}
        </div>
        <div>
          {expanded ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </div>
      </div>
      
      {expanded && (
        <div 
          ref={scrollRef}
          className="p-4 h-[calc(100%-2.5rem)] overflow-y-auto flex flex-col gap-1"
        >
          {logs.map((log, i) => (
            <div key={i} className="opacity-90">{log}</div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 mt-2 text-blue-400">
              <span className="animate-pulse">_</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
