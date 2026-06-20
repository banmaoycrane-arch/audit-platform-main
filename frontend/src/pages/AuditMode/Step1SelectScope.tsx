import { Card, Radio, Button, Steps, Typography, Select, Space } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { FlowNav } from '../../components/FlowNav'

const { Title } = Typography

export function Step1SelectScope() {
  const navigate = useNavigate()
  const [scopeType, setScopeType] = useState<string | undefined>(undefined)
  const currentStep = 0

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

      <FlowNav next="/audit/step/2" style={{ marginBottom: '16px' }} />

      <Title level={4}>选择审计范围</Title>

      <Card style={{ marginBottom: '24px' }}>
        <Radio.Group
          value={scopeType}
          onChange={e => setScopeType(e.target.value)}
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
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Select placeholder="选择科目" style={{ width: '100%' }}>
                      <Select.Option value="cash">库存现金</Select.Option>
                      <Select.Option value="bank">银行存款</Select.Option>
                      <Select.Option value="receivable">应收账款</Select.Option>
                      <Select.Option value="payable">应付账款</Select.Option>
                      <Select.Option value="inventory">存货</Select.Option>
                      <Select.Option value="fixed_asset">固定资产</Select.Option>
                    </Select>
                  </Space>
                </div>
              )}
            </Card>
          </Radio>
          <Radio value="by_period">
            <Card size="small" style={{ marginLeft: '8px' }}>
              <strong>按期间审计</strong> - 选择特定会计期间进行审计
              {scopeType === 'by_period' && (
                <div style={{ marginTop: '12px', padding: '12px', background: '#f5f5f5', borderRadius: '8px' }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Select placeholder="选择年度" style={{ width: '100%' }}>
                      <Select.Option value="2024">2024年</Select.Option>
                      <Select.Option value="2023">2023年</Select.Option>
                      <Select.Option value="2022">2022年</Select.Option>
                    </Select>
                  </Space>
                </div>
              )}
            </Card>
          </Radio>
        </Radio.Group>
      </Card>

      <Button
        type="primary"
        onClick={() => navigate('/audit/step/2')}
        disabled={!scopeType}
      >
        下一步
      </Button>
    </div>
  )
}
