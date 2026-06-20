import { Button, Space } from 'antd'
import type { CSSProperties } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

interface FlowNavProps {
  prev?: string
  next?: string
  nextLabel?: string
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

export function FlowNav({ prev, next, nextLabel = '下一步', style }: FlowNavProps) {
  const navigate = useNavigate()
  const location = useLocation()

  const goStep = (path: string) => navigate(withSearch(resolveStepPath(path, location.pathname), location.search))

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
      {next && (
        <Button type="primary" onClick={() => goStep(next)}>
          {nextLabel}
        </Button>
      )}
    </Space>
  )
}
