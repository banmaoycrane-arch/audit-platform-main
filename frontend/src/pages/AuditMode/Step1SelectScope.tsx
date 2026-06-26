import { Card, Radio, Button, Steps, Typography, Select, Space, message, Spin } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { FlowNav } from '../../components/FlowNav'
import { api, type AccountingPeriod, type AuditScopePayload, type ChartOfAccount, type Project } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { withJobQuery } from '../../utils/navigation'

const { Title } = Typography

type ScopeType = AuditScopePayload['audit_scope_type']

export function Step1SelectScope() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentLedgerId } = useAuthStore()
  const existingJobId = Number(searchParams.get('jobId') || 0) || null

  const [scopeType, setScopeType] = useState<ScopeType | undefined>(undefined)
  const [projectId, setProjectId] = useState<number | undefined>(undefined)
  const [selectedAccountCodes, setSelectedAccountCodes] = useState<string[]>([])
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | undefined>(undefined)
  const [projects, setProjects] = useState<Project[]>([])
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [accounts, setAccounts] = useState<ChartOfAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const currentStep = 0

  useEffect(() => {
    let cancelled = false
    const loadOptions = async () => {
      setLoading(true)
      try {
        const [projectList, periodList, accountList] = await Promise.all([
          api.listProjects(),
          api.listAccountingPeriods(undefined, currentLedgerId ?? undefined),
          api.listChartOfAccounts(),
        ])
        if (cancelled) return
        setProjects(projectList)
        setPeriods(periodList)
        setAccounts(accountList.filter(item => item.is_terminal && item.status === 'active'))
      } catch (error) {
        if (!cancelled) {
          message.error('加载审计范围选项失败')
          console.error(error)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void loadOptions()
    return () => {
      cancelled = true
    }
  }, [currentLedgerId])

  const buildScopePayload = (): AuditScopePayload | null => {
    if (!scopeType) return null
    if (scopeType === 'by_account' && selectedAccountCodes.length === 0) return null
    if (scopeType === 'by_period' && !selectedPeriodId) return null
    return {
      audit_scope_type: scopeType,
      audit_period_id: scopeType === 'by_period' ? selectedPeriodId : null,
      audit_account_codes: scopeType === 'by_account' ? selectedAccountCodes : null,
      project_id: projectId ?? null,
    }
  }

  const handleNext = async () => {
    const scopePayload = buildScopePayload()
    if (!scopePayload) {
      message.warning('请完整选择审计范围')
      return
    }

    setSaving(true)
    try {
      let jobId = existingJobId
      if (jobId) {
        await api.updateImportJobAuditScope(jobId, scopePayload)
      } else {
        const job = await api.createImportJob('审计项目', 'voucher_import', currentLedgerId, scopePayload)
        jobId = job.id
      }
      navigate(withJobQuery('/audit/step/2', jobId))
    } catch (error) {
      message.error('保存审计范围失败')
      console.error(error)
    } finally {
      setSaving(false)
    }
  }

  const nextDisabled =
    !scopeType ||
    (scopeType === 'by_account' && selectedAccountCodes.length === 0) ||
    (scopeType === 'by_period' && !selectedPeriodId)

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

      <FlowNav
        next={existingJobId ? withJobQuery('/audit/step/2', existingJobId) : undefined}
        onNext={handleNext}
        nextDisabled={nextDisabled || saving}
        style={{ marginBottom: '16px' }}
      />

      <Title level={4}>选择审计范围</Title>

      <Spin spinning={loading}>
        <Card style={{ marginBottom: '24px' }}>
          <Space direction="vertical" style={{ width: '100%', marginBottom: '16px' }}>
            <Typography.Text type="secondary">关联项目（可选）</Typography.Text>
            <Select
              allowClear
              placeholder="选择审计项目"
              style={{ width: '100%' }}
              value={projectId}
              onChange={value => setProjectId(value)}
              options={projects.map(project => ({
                value: project.id,
                label: project.name,
              }))}
            />
          </Space>

          <Radio.Group
            value={scopeType}
            onChange={e => setScopeType(e.target.value as ScopeType)}
            style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <Radio value="all">
              <Card size="small" style={{ marginLeft: '8px' }}>
                <strong>全量审计</strong> - 对所有科目和期间进行全面审计
              </Card>
            </Radio>
            <Radio value="by_account">
              <Card size="small" style={{ marginLeft: '8px' }}>
                <strong>按科目审计</strong> - 选择特定科目进行审计
                {scopeType === 'by_account' && (
                  <div style={{ marginTop: '12px', padding: '12px', background: '#f5f5f5', borderRadius: '8px' }}>
                    <Select
                      mode="multiple"
                      placeholder="选择科目"
                      style={{ width: '100%' }}
                      value={selectedAccountCodes}
                      onChange={setSelectedAccountCodes}
                      options={accounts.map(account => ({
                        value: account.code,
                        label: `${account.code} ${account.name}`,
                      }))}
                    />
                  </div>
                )}
              </Card>
            </Radio>
            <Radio value="by_period">
              <Card size="small" style={{ marginLeft: '8px' }}>
                <strong>按期间审计</strong> - 选择特定会计期间进行审计
                {scopeType === 'by_period' && (
                  <div style={{ marginTop: '12px', padding: '12px', background: '#f5f5f5', borderRadius: '8px' }}>
                    <Select
                      placeholder="选择会计期间"
                      style={{ width: '100%' }}
                      value={selectedPeriodId}
                      onChange={setSelectedPeriodId}
                      options={periods.map(period => ({
                        value: period.id,
                        label: `${period.period_code} (${period.start_date} ~ ${period.end_date})`,
                      }))}
                    />
                  </div>
                )}
              </Card>
            </Radio>
          </Radio.Group>
        </Card>
      </Spin>

      <Button
        type="primary"
        onClick={handleNext}
        disabled={nextDisabled || saving}
        loading={saving}
      >
        下一步
      </Button>
    </div>
  )
}
