import { Form, Input, Modal } from 'antd'

export type ReportSignatureForm = {
  preparer_name: string
  reviewer_name: string
  approver_name: string
}

type ReportSignatureModalProps = {
  open: boolean
  title?: string
  loading?: boolean
  onCancel: () => void
  onConfirm: (values: ReportSignatureForm) => void
}

export function ReportSignatureModal({
  open,
  title = '填写签章信息（正式 PDF / 报表包）',
  loading = false,
  onCancel,
  onConfirm,
}: ReportSignatureModalProps) {
  const [form] = Form.useForm<ReportSignatureForm>()

  return (
    <Modal
      open={open}
      title={title}
      okText="确认导出"
      cancelText="取消"
      confirmLoading={loading}
      onCancel={onCancel}
      onOk={() => {
        void form.validateFields().then((values) => onConfirm(values))
      }}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
        <Form.Item name="preparer_name" label="编制人" rules={[{ required: true, message: '请填写编制人' }]}>
          <Input placeholder="会计 / 制单人" />
        </Form.Item>
        <Form.Item name="reviewer_name" label="复核人" rules={[{ required: true, message: '请填写复核人' }]}>
          <Input placeholder="交叉复核人" />
        </Form.Item>
        <Form.Item name="approver_name" label="审核人" rules={[{ required: true, message: '请填写审核人' }]}>
          <Input placeholder="主管 / 财务负责人" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
