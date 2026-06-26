import { Card, Radio, Button, Steps, Typography } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { FlowNav } from '../../components/FlowNav'

const { Title, Text } = Typography

type VoucherInputMode = 'ai_generated' | 'manual_entry' | 'day_book_import'

export function Step1AccountingSelectType() {
  const navigate = useNavigate()
  const location = useLocation()
  const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
  const [selectedInputMode, setSelectedInputMode] = useState<VoucherInputMode | undefined>(undefined)
  const currentStep = 0

  const handleNext = () => {
    if (!selectedInputMode) return
    navigate(`${stepPath(2)}?inputMode=${selectedInputMode}`)
  }

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择模式' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认导出' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav style={{ marginBottom: '16px' }} />

      <Title level={4}>选择凭证输入模式</Title>

      <Card style={{ marginBottom: '24px' }}>
        <Radio.Group
          value={selectedInputMode}
          onChange={e => setSelectedInputMode(e.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}
        >
          <Radio value="ai_generated">
            <Card size="small" style={{ marginLeft: '8px' }}>
              <strong>根据原始资料 AI 智能生成凭证</strong>
              <br />
              <Text type="secondary">上传发票、银行流水、合同等原始资料，由 AI 辅助生成待复核凭证草稿。</Text>
            </Card>
          </Radio>
          <Radio value="day_book_import">
            <Card size="small" style={{ marginLeft: '8px' }}>
              <strong>序时簿导入生成会计凭证</strong>
              <br />
              <Text type="secondary">上传 Excel/CSV 序时簿，系统按凭证号分组生成正式分录，并自动识别对应会计月份。</Text>
            </Card>
          </Radio>
          <Radio value="manual_entry">
            <Card size="small" style={{ marginLeft: '8px' }}>
              <strong>传统人工录入凭证</strong>
              <br />
              <Text type="secondary">纸质记账凭证样式：摘要、科目、借方/贷方面额分列，支持快速录入与保存并新增。</Text>
            </Card>
          </Radio>
        </Radio.Group>
      </Card>

      <Button
        type="primary"
        onClick={handleNext}
        disabled={!selectedInputMode}
      >
        下一步
      </Button>
    </div>
  )
}
