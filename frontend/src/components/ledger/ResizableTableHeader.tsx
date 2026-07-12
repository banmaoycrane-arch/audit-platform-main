import type { CSSProperties, ThHTMLAttributes } from 'react'
import type { MouseEvent } from 'react'

import { clampColumnWidth } from '../../utils/subsidiaryLedgerColumnWidths'

type ResizeHeaderCellProps = ThHTMLAttributes<HTMLTableCellElement> & {
  width?: number
  onResize?: (width: number) => void
}

export function ResizableTableHeaderCell({
  width = 120,
  onResize,
  style,
  children,
  ...rest
}: ResizeHeaderCellProps) {
  if (!width || !onResize) {
    return (
      <th {...rest} style={style}>
        {children}
      </th>
    )
  }

  const handleMouseDown = (event: MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    const startX = event.clientX
    const startWidth = width

    const onMouseMove = (moveEvent: MouseEvent) => {
      onResize(clampColumnWidth(startWidth + moveEvent.clientX - startX))
    }

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }

  const mergedStyle: CSSProperties = {
    ...style,
    position: 'relative',
    width,
    minWidth: width,
  }

  return (
    <th {...rest} style={mergedStyle}>
      {children}
      <span
        role="separator"
        aria-orientation="vertical"
        title="拖动调整列宽"
        onMouseDown={handleMouseDown}
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          width: 8,
          height: '100%',
          cursor: 'col-resize',
          zIndex: 1,
        }}
      />
    </th>
  )
}
