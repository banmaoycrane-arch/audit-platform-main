import { Card, Button, Steps, Typography, Select, Space, message, Alert } from 'antd'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { DownloadOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { api } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'

const { Title } = Typography

type ExportFormat = 'xlsx' | 'csv' | 'json'

export function Step5Export() {
  const navigate = useNavigate()
  const location = useLocation()
  const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
  const [searchParams] = useSearchParams()
  const jobId = Number(searchParams.get('jobId') || 0)
  const periodId = Number(searchParams.get('periodId') || 0)
  const [exportFormat, setExportFormat] = useState<ExportFormat>('xlsx')
  const [exporting, setExporting] = useState(false)
  const [exported, setExported] = useState(false)
  const currentStep = 4

  const prevParams = new URLSearchParams()
  if (jobId) prevParams.set('jobId', String(jobId))
  if (periodId) prevParams.set('periodId', String(periodId))
  const prevQuery = prevParams.toString()

  const handleExport = async () => {
    if (!jobId) {
      message.warning('请先完成草稿生成和复核，再确认入账与导出')
      return
    }
    setExporting(true)
    try {
      await api.postImportJobEntries(jobId)
      const blob = await api.exportImportJob(jobId, exportFormat)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `job_${jobId}_entries.${exportFormat}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      message.success('确认入账与账套导出成功')
      setExported(true)
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

      <FlowNav prev="/accounting/step/4" style={{ marginBottom: '16px' }} />

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
          description="已复核凭证文件已生成并下载，请检查您的下载文件夹。"
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
            {exporting ? '正在确认入账并导出...' : '确认入账并导出账套'}
          </Button>
        </Space>
      </Card>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(prevQuery ? `${stepPath(4)}?${prevQuery}` : stepPath(4))}>
          上一步
        </Button>
        <Button onClick={() => navigate('/')}>
          返回首页
        </Button>
      </div>
    </div>
  )
}
