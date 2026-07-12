import { Card, Button, Steps, Typography, Select, Space, message, Alert } from 'antd'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { DownloadOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { api } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { clearLedgerImportResume } from '../../utils/importJobContext'
import { parseContentDispositionFilename } from '../../utils/downloadFilename'
import { useAuthStore } from '../../stores/authStore'
import { Step5CompletionGuide } from '../../components/ledger/Step5CompletionGuide'
import { trackBookkeepingStep } from '../../utils/productAnalytics'
import { useTrackBookkeepingStep } from '../../hooks/useTrackBookkeepingStep'

const { Title } = Typography

type ExportFormat = 'xlsx' | 'csv' | 'json'

export function Step5Export() {
  const navigate = useNavigate()
  const location = useLocation()
  const { currentLedgerId } = useAuthStore()
  const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
  const [searchParams] = useSearchParams()
  const jobId = Number(searchParams.get('jobId') || 0)
  useTrackBookkeepingStep('step5_post', jobId > 0 ? jobId : undefined)
  const periodId = Number(searchParams.get('periodId') || 0)
  const inputMode = searchParams.get('inputMode')
  const [exportFormat, setExportFormat] = useState<ExportFormat>('xlsx')
  const [exporting, setExporting] = useState(false)
  const [exported, setExported] = useState(false)
  const currentStep = 4

  const prevParams = new URLSearchParams()
  if (jobId) prevParams.set('jobId', String(jobId))
  if (periodId) prevParams.set('periodId', String(periodId))
  if (inputMode) prevParams.set('inputMode', inputMode)
  const prevQuery = prevParams.toString()

  const ensureImportConfirmed = async () => {
    const job = await api.getImportJob(jobId)
    if (job.status !== 'preview') return
    try {
      const result = await api.confirmImport(jobId)
      if (result.entries_created > 0) {
        message.info(`已自动确认入账 ${result.entries_created} 条分录`)
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      if (detail.includes('没有可确认的草稿分录')) {
        return
      }
      throw error
    }
  }

  const handleExport = async () => {
    if (!jobId) {
      message.warning('请先完成草稿生成和复核，再确认入账与导出')
      return
    }
    setExporting(true)
    try {
      await ensureImportConfirmed()
      await api.postImportJobEntries(jobId)
      const { blob, contentDisposition } = await api.exportImportJob(jobId, exportFormat)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = parseContentDispositionFilename(contentDisposition) || `ledger_job${jobId}_entries.${exportFormat}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      message.success('确认入账与账簿导出成功')
      setExported(true)
      if (jobId > 0) {
        trackBookkeepingStep('step5_post', jobId)
      }
      if (currentLedgerId) clearLedgerImportResume(currentLedgerId)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`导出失败：${detail}`)
      console.error('Export error:', detail, error)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择类型' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认入账与导出' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav prev={prevQuery ? `${stepPath(4)}?${prevQuery}` : stepPath(4)} style={{ marginBottom: '16px' }} />

      <Title level={4}>确认入账与导出</Title>

      {!jobId && (
        <Alert
          title="尚未找到可确认入账与导出的已复核凭证"
          description="请先完成草稿生成和复核调整，再进入确认入账与导出步骤。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {exported && (
        <Alert
          title="确认入账与导出成功"
          description="已复核凭证文件已生成并下载。请按下方引导继续月结与报表核对。"
          type="success"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Alert
        title="当前步骤用于确认入账与导出已复核凭证"
        description="凭证已完成复核，可在本步骤进行确认入账与导出。本步骤不新增完整总账过账引擎、结账或复杂审批流，底层导出功能保持不变。"
        type="info"
        showIcon
        style={{ marginBottom: '16px' }}
      />

      <Card>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
              选择导出格式
            </label>
            <Select
              value={exportFormat}
              onChange={(val: ExportFormat) => setExportFormat(val)}
              style={{ width: 200 }}
            >
              <Select.Option value="xlsx">Excel 格式 (.xlsx)</Select.Option>
              <Select.Option value="csv">CSV 格式 (.csv)</Select.Option>
              <Select.Option value="json">系统对接格式 (.json)</Select.Option>
            </Select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
              导出内容
            </label>
            <div style={{ color: '#666' }}>
              <p>• 已复核凭证清单（含凭证号、行号、日期、科目、摘要、借贷金额、对方单位）</p>
            </div>
          </div>

          <div style={{ padding: '16px', background: '#f5f5f5', borderRadius: '8px' }}>
            <strong>导出说明：</strong>
            <ul style={{ marginTop: '8px', color: '#666' }}>
              <li>Excel 格式适合财务软件直接导入</li>
              <li>CSV 格式适合数据分析和进一步处理</li>
              <li>系统对接格式适合后续与其他系统交换数据</li>
            </ul>
          </div>

          <Button
            type="primary"
            icon={<DownloadOutlined />}
            size="large"
            loading={exporting}
            onClick={handleExport}
            disabled={!jobId}
          >
            {exporting ? '正在确认入账并导出...' : '确认入账并导出账簿'}
          </Button>
        </Space>
      </Card>

      {exported && jobId > 0 && (
        <Step5CompletionGuide jobId={jobId} periodId={periodId || undefined} />
      )}

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(prevQuery ? `${stepPath(4)}?${prevQuery}` : stepPath(4))}>
          上一步
        </Button>
        {exported ? (
          <Button type="primary" onClick={() => navigate('/ledger/workspace')}>
            返回总账工作台
          </Button>
        ) : (
          <Button onClick={() => navigate('/ledger/workspace')}>
            返回总账工作台
          </Button>
        )}
      </div>
    </div>
  )
}
