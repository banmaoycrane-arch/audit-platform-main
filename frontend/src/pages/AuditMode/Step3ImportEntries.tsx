import { Card, Upload, Button, Steps, Typography, message, Table, Space, Tag, Alert, Tabs, Statistic, List } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { api, type AccountingEntry, type DayBookReport } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { withJobQuery } from '../../utils/navigation'
import { useAuthStore } from '../../stores/authStore'

const { Dragger } = Upload
const { Title } = Typography

type ImportKind = 'voucher' | 'audit_day_book'

export function Step3ImportEntries() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentLedgerId } = useAuthStore()
  const urlJobId = Number(searchParams.get('jobId') || 0)
  const currentStep = 2
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [activeKind, setActiveKind] = useState<ImportKind>('voucher')
  const [dayBookReport, setDayBookReport] = useState<DayBookReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [jobId, setJobId] = useState<number>(urlJobId)
  const [jobSourceType, setJobSourceType] = useState<string | null>(null)

  const refreshEntries = async () => {
    if (!jobId) return
    setLoading(true)
    try {
      const list = await api.listEntries(jobId)
      setEntries(list)
    } catch (error) {
      console.error('获取分录失败', error)
      message.error('获取分录失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchDayBookReport = async () => {
    if (!jobId) return
    setReportLoading(true)
    try {
      const report = await api.getDayBookReport(jobId)
      setDayBookReport(report)
    } catch (error) {
      console.error('获取序时簿检测报告失败', error)
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    if (urlJobId) {
      setJobId(urlJobId)
    }
  }, [urlJobId])

  useEffect(() => {
    if (!jobId) {
      setJobSourceType(null)
      return
    }
    api.getImportJob(jobId)
      .then((job) => setJobSourceType(job.source_type))
      .catch(() => setJobSourceType(null))
  }, [jobId])

  useEffect(() => {
    refreshEntries()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  const handleUpload = async (file: File, kind: ImportKind) => {
    let currentJobId = jobId
    if (kind === 'audit_day_book' && jobSourceType !== 'audit_day_book') {
      currentJobId = 0
    }
    if (!currentJobId) {
      if (kind === 'audit_day_book') {
        try {
          const job = await api.createImportJob('审计项目', 'audit_day_book', currentLedgerId)
          currentJobId = job.id
          setJobId(currentJobId)
          setJobSourceType(job.source_type)
          setEntries([])
          setDayBookReport(null)
        } catch (error) {
          console.error('创建导入任务失败', error)
          message.error('创建导入任务失败')
          return
        }
      } else {
        message.warning('请先从上一步导入审计资料，再上传凭证分录')
        return
      }
    }
    setUploading(true)
    try {
      await api.uploadFile(currentJobId, file)
      const kindLabel = kind === 'audit_day_book' ? '序时簿' : '凭证'
      message.success(`${file.name}（${kindLabel}）上传成功，开始解析`)
      await api.processImportJobSync(currentJobId)
      message.success('解析完成')
      await refreshEntries()
      if (kind === 'audit_day_book') {
        await fetchDayBookReport()
      }
    } catch (error) {
      console.error('导入分录失败', error)
      message.error(`${file.name} 导入或解析失败`)
    } finally {
      setUploading(false)
    }
  }

  const columns: ColumnsType<AccountingEntry> = [
    {
      title: '凭证号',
      dataIndex: 'voucher_no',
      key: 'voucher_no',
      render: (val: string | null) => val || '-'
    },
    {
      title: '行号',
      dataIndex: 'entry_line_no',
      key: 'entry_line_no'
    },
    {
      title: '日期',
      dataIndex: 'voucher_date',
      key: 'voucher_date',
      render: (val: string | null) => val || '-'
    },
    {
      title: '科目代码',
      dataIndex: 'account_code',
      key: 'account_code',
      render: (val: string | null) => val || '-'
    },
    {
      title: '科目名称',
      dataIndex: 'account_name',
      key: 'account_name',
      render: (val: string | null) => val || '-'
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      render: (val: string | null) => val || '-'
    },
    {
      title: '借方金额',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      render: (val: number) => (val > 0 ? `¥${Number(val).toLocaleString()}` : '-')
    },
    {
      title: '贷方金额',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      render: (val: number) => (val > 0 ? `¥${Number(val).toLocaleString()}` : '-')
    }
  ]

  const renderDragger = (kind: ImportKind) => {
    const isDayBook = kind === 'audit_day_book'
    return (
      <Dragger
        name="files"
        multiple={false}
        disabled={uploading}
        beforeUpload={(file) => {
          handleUpload(file, kind)
          return false
        }}
        accept=".xlsx,.xls,.csv"
        style={{ padding: '40px' }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">
          {isDayBook ? '点击或拖拽文件上传被审计单位序时簿' : '点击或拖拽文件上传被审计单位凭证'}
        </p>
        <p className="ant-upload-hint">
          {isDayBook
            ? '序时簿：按日期顺序、连续登记的全部凭证流水。请保留凭证号、日期、借贷金额、对方单位等列，用于完整性 / 截止性 / 跳号检测。'
            : '支持 Excel 或 CSV 格式，包含凭证号、日期、科目、金额等信息。'}
        </p>
      </Dragger>
    )
  }

  const renderDayBookReport = () => {
    if (!dayBookReport) return null
    const hasIssues = dayBookReport.skip_count > 0 || dayBookReport.unbalanced_count > 0 || dayBookReport.missing_voucher_nos.length > 0
    return (
      <Card
        title="序时簿检测报告"
        loading={reportLoading}
        style={{ marginTop: '24px' }}
      >
        <Space size="large" wrap>
          <Statistic title="凭证总数" value={dayBookReport.total_vouchers} />
          <Statistic title="跳号数量" value={dayBookReport.skip_count} valueStyle={{ color: dayBookReport.skip_count > 0 ? '#cf1322' : undefined }} />
          <Statistic title="不平衡凭证数量" value={dayBookReport.unbalanced_count} valueStyle={{ color: dayBookReport.unbalanced_count > 0 ? '#cf1322' : undefined }} />
          <Statistic title="完整性评分" value={dayBookReport.completeness_score} suffix="%" valueStyle={{ color: dayBookReport.completeness_score < 100 ? '#cf1322' : '#3f8600' }} />
        </Space>

        {hasIssues && (
          <Alert
            title="检测到序时簿异常"
            type="warning"
            showIcon
            style={{ marginTop: '16px' }}
          />
        )}

        {dayBookReport.missing_voucher_nos.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <Title level={5} style={{ marginBottom: '8px' }}>缺失凭证号列表</Title>
            <List
              size="small"
              bordered
              dataSource={dayBookReport.missing_voucher_nos}
              renderItem={(item) => (
                <List.Item>
                  <Tag color="red">{item}</Tag>
                </List.Item>
              )}
            />
          </div>
        )}

        {dayBookReport.unbalanced_vouchers.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <Title level={5} style={{ marginBottom: '8px' }}>不平衡凭证列表</Title>
            <List
              size="small"
              bordered
              dataSource={dayBookReport.unbalanced_vouchers}
              renderItem={(item) => (
                <List.Item>
                  <Space wrap>
                    <Tag color="red">{item.voucher_no}</Tag>
                    <span>借方合计：{item.debit_total}</span>
                    <span>贷方合计：{item.credit_total}</span>
                    <span>差额：{item.difference}</span>
                  </Space>
                </List.Item>
              )}
            />
          </div>
        )}
      </Card>
    )
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
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

      <FlowNav
        prev={withJobQuery('/audit/step/2', jobId)}
        next={withJobQuery('/audit/step/4', jobId)}
        nextDisabled={!jobId || entries.length === 0}
        style={{ marginBottom: '16px' }}
      />

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>导入被审计单位分录</Title>
        <Tag color="blue">共 {entries.length} 条</Tag>
      </Space>

      {!jobId && (
        <Alert
          title="尚未找到导入资料"
          description="请从导入资料步骤重新进入；如本次要直接导入序时簿，可在序时簿导入页签上传文件，系统会自动创建序时簿任务。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {activeKind === 'audit_day_book' && jobId > 0 && jobSourceType !== 'audit_day_book' && (
        <Alert
          title="序时簿将作为单独的审计资料处理"
          description="当前已有任务不是序时簿任务。上传序时簿时，系统会自动新建序时簿任务，用于跳号、完整性和借贷平衡检测。"
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card style={{ marginBottom: '24px' }}>
        <Tabs
          activeKey={activeKind}
          onChange={(key) => setActiveKind(key as ImportKind)}
          items={[
            {
              key: 'voucher',
              label: '凭证导入',
              children: renderDragger('voucher')
            },
            {
              key: 'audit_day_book',
              label: '序时簿导入',
              children: renderDragger('audit_day_book')
            }
          ]}
        />
      </Card>

      <Card title="已导入的分录" loading={loading}>
        <Table
          columns={columns}
          dataSource={entries}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          size="small"
          locale={{ emptyText: jobId ? '暂无分录，请上传被审计单位凭证或序时簿' : '请先上传或选择审计资料' }}
        />
      </Card>

      {activeKind === 'audit_day_book' && dayBookReport && renderDayBookReport()}

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(jobId ? `/audit/step/2?jobId=${jobId}` : '/audit/step/2')}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={() => navigate(jobId ? `/audit/step/4?jobId=${jobId}` : '/audit/step/4')}
          disabled={!jobId || entries.length === 0}
        >
          下一步执行测试
        </Button>
      </div>
    </div>
  )
}
