import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Card, Col, Row, Space, Statistic, Typography } from 'antd'
import {
  ApartmentOutlined,
  PartitionOutlined,
  UnorderedListOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api, type DimensionPendingQueueResponse, type DimensionRegistryResponse } from '../../api/client'
import {
  DIMENSION_STAT_HINTS,
  buildPendingAlertDescription,
  buildPendingAlertTitle,
  humanizeRegistryWarning,
} from '../dimensions/dimensionReminderCopy'
import { persistImportJobContext } from '../../utils/importJobContext'

const { Paragraph, Text } = Typography

type Step4DimensionReviewPanelProps = {
  jobId: number
  onContinue: () => void
}

export function Step4DimensionReviewPanel({ jobId, onContinue }: Step4DimensionReviewPanelProps) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [pendingQueue, setPendingQueue] = useState<DimensionPendingQueueResponse | null>(null)
  const [registrySummary, setRegistrySummary] = useState<Pick<
    DimensionRegistryResponse,
    'dimension_count' | 'warnings'
  > | null>(null)

  const loadSummary = useCallback(async () => {
    if (!jobId) return
    setLoading(true)
    try {
      const [queue, registry] = await Promise.all([
        api.getDimensionPendingQueue(jobId),
        api.getDimensionRegistry(jobId),
      ])
      setPendingQueue(queue)
      setRegistrySummary({
        dimension_count: registry.dimension_count,
        warnings: registry.warnings,
      })
    } catch (error) {
      console.error('加载维度复核摘要失败', error)
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  const pendingTotal = pendingQueue?.summary.total ?? 0
  const dimensionCount = registrySummary?.dimension_count ?? 0
  const warningCount = registrySummary?.warnings.length ?? 0

  const openDimensions = (tab: string, extra?: Record<string, string>) => {
    const params = new URLSearchParams({ tab, jobId: String(jobId), ...extra })
    const path = `/ledger/dimensions?${params.toString()}`
    persistImportJobContext(jobId, `/ledger/vouchers/step/4?jobId=${jobId}&reviewPhase=dimensions&inputMode=day_book_import`)
    navigate(path)
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="先对一下：科目和辅助核算有没有解析对"
        description="序时簿导入后，会把科目下级段变成「维度 Tag」（比如银行户名、费用类型）。这里只看摘要；具体补全请去「账簿维度中心」的待处理队列，避免本页卡死。"
      />

      <Row gutter={16}>
        <Col xs={24} sm={8}>
          <Card size="small" loading={loading}>
            <Statistic title="识别到的维度种类" value={dimensionCount} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {DIMENSION_STAT_HINTS.dimensionCount}
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" loading={loading}>
            <Statistic
              title="建议入账前处理"
              value={pendingTotal}
              valueStyle={{ color: pendingTotal > 0 ? '#cf1322' : '#3f8600' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {DIMENSION_STAT_HINTS.pendingTotal}
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" loading={loading}>
            <Statistic title="额外提醒" value={warningCount} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {DIMENSION_STAT_HINTS.warningCount}
            </Text>
          </Card>
        </Col>
      </Row>

      {pendingQueue && pendingTotal > 0 && (
        <Alert
          type="warning"
          showIcon
          message={buildPendingAlertTitle(pendingQueue.summary)}
          description={buildPendingAlertDescription(pendingQueue.summary)}
        />
      )}

      {registrySummary?.warnings.map((warning) => {
        const copy = humanizeRegistryWarning(warning)
        return (
          <Alert
            key={`${warning.code}-${warning.message}`}
            type={warning.severity === 'warning' ? 'warning' : 'info'}
            showIcon
            message={copy.message}
            description={copy.description}
          />
        )
      })}

      <Card title="推荐操作" size="small" loading={loading}>
        <Space wrap>
          <Button icon={<PartitionOutlined />} onClick={() => openDimensions('parse-mapping')}>
            检查解析映射规则
          </Button>
          <Button icon={<ApartmentOutlined />} onClick={() => openDimensions('master-values')}>
            维护维度值主数据
          </Button>
          <Button icon={<UnorderedListOutlined />} onClick={() => openDimensions('pending')}>
            待处理队列
            {pendingTotal > 0 ? ` (${pendingTotal})` : ''}
          </Button>
          <Button icon={<ApartmentOutlined />} onClick={() => openDimensions('compare')}>
            三层对照
          </Button>
          {(pendingQueue?.summary.requires_llm || 0) > 0 && (
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={() => openDimensions('pending')}
            >
              批量 LLM 识别
            </Button>
          )}
        </Space>
        <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          批量改户名、费用类型等规范全称，请到「账簿维度中心 → 待处理队列」，本页只显示数量摘要。
        </Paragraph>
      </Card>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
        <Button onClick={() => void loadSummary()} loading={loading}>
          刷新摘要
        </Button>
        <Button type="primary" onClick={onContinue}>
          {pendingTotal > 0 ? '先审凭证，待处理项稍后再补' : '维度已对好，进入凭证复核'}
        </Button>
      </div>
    </Space>
  )
}
