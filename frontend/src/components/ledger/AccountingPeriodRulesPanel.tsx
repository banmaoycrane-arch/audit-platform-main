import { Alert, Card, Collapse, Table, Typography } from 'antd'

const { Paragraph, Text, Title } = Typography

const STATUS_FLOW = [
  { status: 'open', label: '开放', meaning: '可录入、修改、删除本分录；报表按「实时重算」口径（期初 + 本期发生 → 期末）。' },
  { status: 'pl_transferred', label: '损益已达标', meaning: '过账/校验确认损益科目已清零且报表平衡（含导入结转凭证）；尚未冻结，可结账。' },
  { status: 'closed', label: '已结账', meaning: '本分录数据冻结；固化截止期间最后一天的科目余额表唯一快照（含本期/本年发生额累计）；报表直接读快照。' },
  { status: 'reopened', label: '已反结账', meaning: '解除冻结、作废原快照；期间恢复为可编辑，需重新损益结转并再次结账。' },
]

const ROLE_COMPARE = [
  {
    key: 'trial',
    item: '科目余额表（报表查询）',
    role: '展示某一截止日的六列余额（期初借/贷、本期借/贷、期末借/贷），用于核对与编制报表。',
    timing: '开放期间：可按任意截止日「实时汇总」；已结账期间：读取结账日固化的快照口径。',
  },
  {
    key: 'close',
    item: '期间结账（本页）',
    role: '在损益结转完成且资产负债表平衡后，将期间最后一天的科目余额表「全表」固化为快照，并冻结该期间一切业务修改。',
    timing: '每个会计期间通常月末执行一次；结账后除反结账外，前端与 API 均不可再改该期间数据（直接改库除外）。',
  },
]

export function AccountingPeriodRulesPanel() {
  return (
    <Card size="small" title="期末处理规则说明" style={{ marginBottom: 16 }}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="本页定位：会计期间的「过账校验 → 结账冻结 → 余额快照」管理中心"
        description="日常只需处理「当前工作期间」；损益结转在过账/结账时自动校验。历史多月补结转请用页面下方「高级 / 补救操作」的跨期间批量功能。"
      />

      <Collapse
        defaultActiveKey={['flow', 'freeze', 'snapshot']}
        items={[
          {
            key: 'flow',
            label: '一、期间状态与操作顺序',
            children: (
              <>
                <Paragraph type="secondary" style={{ marginBottom: 12 }}>
                  推荐顺序：<Text strong>凭证过账</Text> → <Text strong>结转校验（可选）</Text> →{' '}
                  <Text strong>报表核对（科目余额表 / 资产负债表）</Text> → <Text strong>期间结账</Text>。
                  未满足损益结转条件时，结账会自动尝试生成系统结转凭证。
                </Paragraph>
                <Table
                  size="small"
                  pagination={false}
                  rowKey="status"
                  dataSource={STATUS_FLOW}
                  columns={[
                    { title: '状态', dataIndex: 'label', width: 110 },
                    { title: '含义与数据口径', dataIndex: 'meaning' },
                  ]}
                />
              </>
            ),
          },
          {
            key: 'freeze',
            label: '二、结账 = 数据冻结（不可再通过系统修改）',
            children: (
              <Paragraph style={{ marginBottom: 0 }}>
                <ul style={{ paddingLeft: 20, margin: 0 }}>
                  <li>
                    期间一旦 <Text strong>已结账</Text>，该期间内所有会计凭证、分录及相关业务数据视为
                    <Text strong>只读冻结</Text>：前端与后端 API 均拒绝新增、修改、删除（数据库直改除外）。
                  </li>
                  <li>
                    <Text strong>已结转损益</Text> 但未结账期间：系统同样限制再录入凭证，避免结账前数据被篡改。
                  </li>
                  <li>
                    需要调整时须先执行 <Text strong>反结账</Text>（作废快照、恢复开放），修正后再重新损益结转并结账。
                  </li>
                </ul>
              </Paragraph>
            ),
          },
          {
            key: 'snapshot',
            label: '三、结账快照 = 期间末日科目余额表全表（唯一版本）',
            children: (
              <>
                <Paragraph>
                  结账时，系统以该期间 <Text strong>最后一天（end_date）</Text> 为截止日，在同一数据库事务内生成与「科目余额表」一致的
                  <Text strong>全科目十列余额快照</Text>：期初借/贷、<Text strong>本期发生借/贷累计</Text>、
                  <Text strong>本年发生借/贷累计</Text>、期末借/贷，写入 <Text code>period_snapshots</Text>。
                </Paragraph>
                <Paragraph>
                  <Text strong>科目余额表没有多版本概念：</Text>每个已结账期间只保留一份固化结果（内部版本号恒为 1）。
                  反结账会清除该快照；重新结账在同一事务内覆盖生成新的唯一快照。
                </Paragraph>
                <Paragraph>
                  <Title level={5} style={{ marginTop: 0 }}>与下一期间的关系</Title>
                  下一开放期间查询期初数时，应直接承接上一 <Text strong>已结账</Text> 期间的科目余额表
                  <Text strong>期末列</Text>，作为本期期初，而无需每次从建账以来全量重算实时余额。
                  这正是「科目余额表 + 结账」的分工：
                </Paragraph>
                <Table
                  size="small"
                  pagination={false}
                  rowKey="key"
                  dataSource={ROLE_COMPARE}
                  columns={[
                    { title: '能力', dataIndex: 'item', width: 180 },
                    { title: '定位', dataIndex: 'role' },
                    { title: '使用时机', dataIndex: 'timing', width: 280 },
                  ]}
                />
              </>
            ),
          },
          {
            key: 'pl',
            label: '四、损益结转（过账/结账时自动校验，非独立必点按钮）',
            children: (
              <Paragraph style={{ marginBottom: 0 }}>
                <ul style={{ paddingLeft: 20, margin: 0 }}>
                  <li>
                    <Text strong>过账时</Text>：系统检测该期间损益类科目是否已清零、资产负债表是否平衡；
                    若导入凭证已完成结转（摘要含「结转/本年利润」等），期间自动标记为「损益已达标」。
                  </li>
                  <li>
                    <Text strong>结账时</Text>：再次校验；若已达标则直接结账；若仍有损益余额则自动生成{' '}
                    <Text code>转-期末-{'{期间编码}'}</Text> 凭证后再结账。
                  </li>
                  <li>
                    <Text strong>结转校验</Text>：结账前可手动查看是否已满足条件，无需单独点击「损益结转」。
                  </li>
                </ul>
              </Paragraph>
            ),
          },
        ]}
      />
    </Card>
  )
}
