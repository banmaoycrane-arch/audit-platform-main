import { Button, Space } from 'antd'
import type { CSSProperties } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

interface FlowNavProps {
  prev?: string
  next?: string
  nextLabel?: string
  nextDisabled?: boolean
  onNext?: () => void
  style?: CSSProperties
}

function resolveStepPath(path: string, pathname: string) {
  if (pathname.startsWith('/ledger/vouchers/step/') && path.startsWith('/accounting/step/')) {
    return path.replace('/accounting/step/', '/ledger/vouchers/step/')
  }
  return path
}

function withSearch(path: string, search: string) {
  return `${path}${search}`
}

export function FlowNav({ prev, next, nextLabel = '下一步', nextDisabled = false, onNext, style }: FlowNavProps) {
  const navigate = useNavigate()
  const location = useLocation()

  const goStep = (path: string) => navigate(withSearch(resolveStepPath(path, location.pathname), location.search))

  const handleNext = () => {
    if (nextDisabled) return
    if (onNext) {
      onNext()
      return
    }
    if (next) {
      goStep(next)
    }
  }

  return (
    <Space style={style} wrap>
      <Button onClick={() => navigate(`/workspace${location.search}`)}>
        返回工作台
      </Button>
      {prev && (
        <Button onClick={() => goStep(prev)}>
          上一步
        </Button>
      )}
      {(next || onNext) && (
        <Button type="primary" disabled={nextDisabled} onClick={handleNext}>
          {nextLabel}
        </Button>
      )}
    </Space>
  )
}
