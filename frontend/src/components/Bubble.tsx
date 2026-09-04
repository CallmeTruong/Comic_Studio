import { useRef, useEffect, useState } from "react"
import _ContentEditable, { ContentEditableEvent } from "react-contenteditable"
const ContentEditable = (_ContentEditable as any).default || _ContentEditable;
import Draggable from "react-draggable"
import { cn } from "@/lib/utils"
import { Move } from "lucide-react"

interface BubbleProps {
  text: string;
  onChange: (newText: string) => void;
  onDragStop: (x: number, y: number) => void;
  x: number; // percentage
  y: number; // percentage
  width: number;
  height: number;
  parentRef: React.RefObject<HTMLDivElement>;
}

export function Bubble({ text: initialText, onChange, onDragStop, x, y, width, height, parentRef }: BubbleProps) {
  const ref = useRef<HTMLDivElement>(null)
  const textRef = useRef(`${initialText || ''}`)
  const [dragPos, setDragPos] = useState({ x: 0, y: 0 })

  const handleChange = (evt: ContentEditableEvent) => {
    textRef.current = evt.target.value
  }

  const handleBlur = () => {
    onChange(textRef.current)
  }

  const handleStop = (e: any, data: any) => {
    if (!parentRef.current) return;
    
    // Calculate new percentage based on pixel delta
    const parentWidth = parentRef.current.clientWidth;
    const parentHeight = parentRef.current.clientHeight;
    
    const deltaXPct = (data.x / parentWidth) * 100;
    const deltaYPct = (data.y / parentHeight) * 100;
    
    // Call onDragStop with new percentages
    onDragStop(x + deltaXPct, y + deltaYPct);
    
    // Reset Draggable's internal translation to 0
    setDragPos({ x: 0, y: 0 });
  }

  return (
    <div 
      className="absolute z-50 pointer-events-none" 
      style={{ left: `${x}%`, top: `${y}%` }}
    >
      <Draggable
        position={dragPos}
        onDrag={(e, data) => setDragPos({ x: data.x, y: data.y })}
        onStop={handleStop}
        handle=".drag-handle"
      >
        <div 
          className="absolute flex flex-col items-center justify-center pointer-events-auto group -translate-x-1/2 -translate-y-1/2"
          style={{ width: `${width}px`, height: `${height}px` }}
        >
          <div className="drag-handle absolute -top-8 bg-black text-white p-1 rounded-md opacity-0 group-hover:opacity-100 cursor-move transition-opacity z-50">
            <Move size={16} />
          </div>
          <div
            ref={ref}
            className={cn(
              "bg-white border-2 border-black rounded-2xl p-2 md:p-4 text-center cursor-text comic-font",
              "shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]", // Comic style shadow
              "text-xs md:text-sm font-bold text-black leading-tight"
            )}
            style={{ minWidth: "80%", minHeight: "60%" }}
          >
            <ContentEditable
              html={textRef.current}
              onChange={handleChange}
              onBlur={handleBlur}
              className="outline-none"
            />
          </div>
        </div>
      </Draggable>
    </div>
  )
}
