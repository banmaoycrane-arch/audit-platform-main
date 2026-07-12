import { useEffect, useMemo, useState } from 'react'
import { Alert, Card, Col, Pagination, Row, Statistic, Table, Typography, message } from 'antd'
import dayjs from 'dayjs'
import {
  api,
  type VoucherCard,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'

export { SubsidiaryLedgerPage } from './SubsidiaryLedgerPage'
export { GeneralLedgerPage } from './GeneralLedgerPage'

const { Title, Paragraph } = Typography

export function LedgerBooksPage() {
  const { currentLedgerId } = useAuthStore()
  const [vouchers, setVouchers] = useState<VoucherCard[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const currentMonth = dayjs().format('YYYY-MM')

  useEffect(() => {
    if (!currentLedgerId) {
      setVouchers([])
      setTotal(0)
      return
    }
    setLoading(true)
    api
      .queryVouchers({
        ledger_id: currentLedgerId,
        month: currentMonth,
        limit: 50,
        offset: (page - 1) * 50,
        include_lines: false,
      })
      .then((resp) => {
        setVouchers(resp.items)
        setTotal(resp.total)
      })
      .catch((error) => message.error(`加载凭证序时簿失败：${error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [currentLedgerId, page, currentMonth])

  const voucherRows = useMemo(
    () =>
      vouchers.map((voucher) => ({
        key: `${voucher.voucher_no ?? ''}||${voucher.voucher_date ?? ''}`,
        voucher_no: voucher.voucher_no || '无凭证号',
        voucher_date: voucher.voucher_date || '-',
        summary: voucher.summary_preview || '-',
        line_count: voucher.line_count,
        debit_total: voucher.debit_total,
        credit_total: voucher.credit_total,
      })),
    [vouchers],
  )
  const debitTotal = voucherRows.reduce((sum, row) => sum + row.debit_total, 0)
  const creditTotal = voucherRows.reduce((sum, row) => sum + row.credit_total, 0)

  return (
    <div>
      <Title level={3}>账簿管理</Title>
      <Paragraph type="secondary">
        凭证序时簿默认展示本月凭证（{currentMonth}），分页加载，避免一次拉取全账簿。
      </Paragraph>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Card><Statistic title="本月凭证张数" value={total} /></Card></Col>
        <Col span={8}><Card><Statistic title="本页借方合计" value={debitTotal} prefix="¥" /></Card></Col>
        <Col span={8}><Card><Statistic title="本页贷方合计" value={creditTotal} prefix="¥" /></Card></Col>
      </Row>
      {Math.round((debitTotal - creditTotal) * 100) !== 0 && (
        <Alert type="warning" showIcon title="本页凭证借贷合计不平衡（可能因分页仅展示部分凭证）" style={{ marginBottom: 16 }} />
      )}
      <Card title="凭证序时簿">
        <Table
          rowKey="key"
          loading={loading}
          dataSource={voucherRows}
          size="small"
          pagination={false}
          columns={[
            { title: '日期', dataIndex: 'voucher_date', key: 'voucher_date', width: 120 },
            { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no', width: 150 },
            { title: '摘要', dataIndex: 'summary', key: 'summary' },
            { title: '分录行数', dataIndex: 'line_count', key: 'line_count', width: 90 },
            { title: '借方合计', dataIndex: 'debit_total', key: 'debit_total', width: 120, render: (v: number) => formatAmount(v) },
            { title: '贷方合计', dataIndex: 'credit_total', key: 'credit_total', width: 120, render: (v: number) => formatAmount(v) },
          ]}
        />
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Pagination
            current={page}
            pageSize={50}
            total={total}
            showSizeChanger={false}
            showTotal={(t) => `共 ${t} 张凭证`}
            onChange={setPage}
          />
        </div>
      </Card>
    </div>
  )
}
