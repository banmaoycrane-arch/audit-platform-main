import { Card, Button, Steps, Typography, Select, Space, message, Alert, Radio } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { DownloadOutlined, FileTextOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { api } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { withJobQuery } from '../../utils/navigation'

const { Title, Text } = Typography

type ExportFormat = 'xlsx' | 'json'

export function Step6ExportReport() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const jobId = Number(searchParams.get('jobId') || 0)
  const [exportFormat, setExportFormat] = useState<ExportFormat>('xlsx')
  const [reportType, setReportType] = useState('standard')
  const [exporting, setExporting] = useState(false)
  const [exported, setExported] = useState(false)
  const currentStep = 5

  const handleExport = async () => {
    if (!jobId) {
      message.warning('缺少导入任务编号，无法导出')
      return
    }
    setExporting(true)
    try {
      const blob = await api.exportAuditReport(jobId, exportFormat)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `audit_report_${jobId}.${exportFormat}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      message.success('审计报告导出成功！')
      setExported(true)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`导出失败：${detail}`)
      console.error('Audit export error:', detail, error)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择范围' },
          { title: '导入资料' },
          { title: '导入分录' },
          { title: '执行测试' },
          { title: '复核发现' },
          { title: '导出报告' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav prev={withJobQuery('/audit/step/5', jobId)} style={{ marginBottom: '16px' }} />

      <Title level={4}>生成审计报告</Title>

      {!jobId && (
        <Alert
          title="尚未找到可导出的审计报告数据"
          description="请从「复核发现」步骤重新进入，否则无法导出审计报告。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {exported && (
        <Alert
          title="导出成功"
          description="审计报告已生成并下载，请检查您的下载文件夹。"
          type="success"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
              报告类型
            </label>
            <Radio.Group
              value={reportType}
              onChange={e => setReportType(e.target.value)}
              style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}
            >
              <Radio value="standard">
                <Card size="small" style={{ marginLeft: '8px' }}>
                  <Text strong>标准审计报告</Text>
                  <Text type="secondary" style={{ display: 'block' }}>
                    包含审计范围、方法、发现及建议的完整报告
                  </Text>
                </Card>
              </Radio>
              <Radio value="executive">
                <Card size="small" style={{ marginLeft: '8px' }}>
                  <Text strong>管理层报告</Text>
                  <Text type="secondary" style={{ display: 'block' }}>
                    简化的执行摘要，适合管理层阅读
                  </Text>
                </Card>
              </Radio>
              <Radio value="detailed">
                <Card size="small" style={{ marginLeft: '8px' }}>
                  <Text strong>详细工作底稿</Text>
                  <Text type="secondary" style={{ display: 'block' }}>
                    包含所有测试细节和取证的工作底稿
                  </Text>
                </Card>
              </Radio>
            </Radio.Group>
            <Text type="secondary" style={{ marginTop: '4px', display: 'block' }}>
              说明：当前版本报告类型仅用于前端展示，导出内容以审计发现 + 测试结论为主。
            </Text>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
              导出格式
            </label>
            <Select
              value={exportFormat}
              onChange={(val: ExportFormat) => setExportFormat(val)}
              style={{ width: 200 }}
            >
              <Select.Option value="xlsx">Excel 格式 (.xlsx)</Select.Option>
              <Select.Option value="json">系统对接格式 (.json)</Select.Option>
            </Select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
              报告内容
            </label>
            <div style={{ color: '#666' }}>
              <p>✓ 审计概述与范围</p>
              <p>✓ 审计方法与程序</p>
              <p>✓ 审计发现汇总</p>
              <p>✓ 风险分布统计</p>
              <p>✓ 改进建议</p>
            </div>
          </div>

          <div style={{ padding: '16px', background: '#f5f5f5', borderRadius: '8px' }}>
            <FileTextOutlined style={{ marginRight: '8px' }} />
            <Text type="secondary">
              报告将包含审计标识、日期、被审计单位信息等标准要素
            </Text>
          </div>

          <Button
            type="primary"
            icon={<DownloadOutlined />}
            size="large"
            loading={exporting}
            onClick={handleExport}
            disabled={!jobId}
          >
            {exporting ? '正在导出...' : '导出审计报告'}
          </Button>
        </Space>
      </Card>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(jobId ? `/audit/step/5?jobId=${jobId}` : '/audit/step/5')}>
          上一步
        </Button>
        <Button onClick={() => navigate('/')}>
          返回首页
        </Button>
      </div>
    </div>
  )
}
