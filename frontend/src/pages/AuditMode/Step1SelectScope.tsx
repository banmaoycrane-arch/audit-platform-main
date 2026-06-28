import { Card, Radio, Button, Steps, Typography, Select, Space, message, Spin, Alert } from 'antd'
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
  const { currentLedgerId, authContext } = useAuthStore()
  const canUseLedgerWithoutProject = Boolean(authContext?.can_use_ledger_without_project)
  const existingJobId = Number(searchParams.get('jobId') || 0) || null

  const [scopeType, setScopeType] = useState<ScopeType | undefined>(undefined)
  const [projectId, setProjectId] = useState<number | undefined>(undefined)
  const [selectedAccountCodes, setSelectedAccountCodes] = useState<string[]>([])
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | undefined>(undefined)
  const [projects, setProjects] = useState<Project[]>([])
  const [projectLedgers, setProjectLedgers] = useState<Record<number, number[]>>({})
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
        const ledgerPairs = await Promise.all(
          projectList
            .filter(project => project.type === 'audit' && project.status === 'active')
            .map(async project => [project.id, (await api.listProjectLedgers(project.id)).map(ledger => ledger.id)] as const)
        )
        if (cancelled) return
        const ledgerMap = Object.fromEntries(ledgerPairs) as Record<number, number[]>
        setProjectLedgers(ledgerMap)
        setProjectId(current => {
          if (current) return current
          const defaultProject = projectList.find(project =>
            project.type === 'audit' &&
            project.status === 'active' &&
            currentLedgerId != null &&
            ledgerMap[project.id]?.includes(currentLedgerId)
          )
          return defaultProject?.id
        })
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

  const auditProjectOptions = projects.filter(project =>
    project.type === 'audit' &&
    project.status === 'active' &&
    currentLedgerId != null &&
    projectLedgers[project.id]?.includes(currentLedgerId)
  )

  const buildScopePayload = (): AuditScopePayload | null => {
    if (!canUseLedgerWithoutProject && !projectId) return null
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
      message.warning(canUseLedgerWithoutProject ? '请完整选择审计范围' : '请先选择已绑定当前账簿的审计项目，并完整选择审计范围')
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
    (!canUseLedgerWithoutProject && !projectId) ||
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
            <Typography.Text type="secondary">
              {canUseLedgerWithoutProject ? '关联项目（可选，企业会计可直接按当前账簿归集资料）' : '关联项目（必选，且项目必须已绑定当前账簿）'}
            </Typography.Text>
            {canUseLedgerWithoutProject && (
              <Alert
                type="info"
                showIcon
                message="企业内部会计模式"
                description="当前用户可直接基于账簿处理财务总账和企业内部审计资料；如属于专项审计项目，也可以选择已绑定项目。"
              />
            )}
            {currentLedgerId == null && (
              <Alert
                type="warning"
                showIcon
                message="请先选择账簿"
                description="审计项目实施前必须有明确账簿。请到用户设置申请账簿访问，或到账簿管理选择/创建账簿。"
                action={(
                  <Space wrap>
                    <Button size="small" type="primary" onClick={() => navigate('/user-settings?focus=binding')}>申请账簿绑定</Button>
                    <Button size="small" onClick={() => navigate('/ledger-management')}>账簿管理</Button>
                  </Space>
                )}
              />
            )}
            {currentLedgerId != null && !canUseLedgerWithoutProject && !projectId && (
              <Alert
                type="warning"
                showIcon
                message="未关联项目时请注意资料不可外泄"
                description="当前资料会暂按账簿归集，不进入项目底稿范围；涉及客户、项目组或外部服务资料时，请先绑定项目，避免资料外泄或串项目使用。"
                action={(
                  <Space wrap>
                    <Button size="small" type="primary" onClick={() => navigate('/user-settings?focus=binding')}>申请项目绑定</Button>
                    <Button size="small" onClick={() => navigate('/projects')}>项目管理</Button>
                  </Space>
                )}
              />
            )}
            {currentLedgerId != null && !canUseLedgerWithoutProject && auditProjectOptions.length === 0 && (
              <Alert
                type="warning"
                showIcon
                message="当前账簿尚未绑定可实施的审计项目"
                description="请先在用户设置申请参与项目，或到项目管理创建/维护项目并完成项目-账簿绑定。"
                action={(
                  <Space wrap>
                    <Button size="small" type="primary" onClick={() => navigate('/user-settings?focus=binding')}>申请项目绑定</Button>
                    <Button size="small" onClick={() => navigate('/projects')}>项目管理</Button>
                  </Space>
                )}
              />
            )}
            <Select
              allowClear
              placeholder={canUseLedgerWithoutProject ? '可选：选择已绑定当前账簿的审计项目' : '建议选择已绑定当前账簿的审计项目'}
              style={{ width: '100%' }}
              value={projectId}
              onChange={value => setProjectId(value)}
              options={auditProjectOptions.map(project => ({
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
