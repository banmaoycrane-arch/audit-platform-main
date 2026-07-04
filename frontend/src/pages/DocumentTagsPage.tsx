import { useState, useEffect } from 'react';
import {
  Table,
  Tag,
  Button,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Space,
  message,
  Card,
  Statistic,
  Row,
  Col,
  Popconfirm,
  DatePicker,
  Tabs,
  Badge,
} from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
  ReloadOutlined,
  HistoryOutlined,
  CheckOutlined,
  CloseOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { api, DocumentTag, LlmTagSuggestion, LlmResolutionStatistics } from '../api/client';

const { TabPane } = Tabs;

const TAG_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  business: { label: '业务', color: 'blue' },
  risk: { label: '风险', color: 'red' },
  relation: { label: '关联方', color: 'purple' },
  time: { label: '时间', color: 'orange' },
  amount: { label: '金额', color: 'green' },
  status: { label: '状态', color: 'gray' },
};

const SOURCE_CONFIG: Record<string, { label: string; color: string }> = {
  rule: { label: '规则引擎', color: 'default' },
  ai: { label: 'AI生成', color: 'processing' },
  manual: { label: '人工录入', color: 'success' },
};

const TAG_CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  customer: { label: '客户', color: 'blue' },
  supplier: { label: '供应商', color: 'green' },
  product: { label: '产品', color: 'purple' },
  material: { label: '材料', color: 'purple' },
  department: { label: '部门', color: 'orange' },
  project: { label: '项目', color: 'pink' },
  region: { label: '区域', color: 'cyan' },
  expense_type: { label: '费用类型', color: 'gold' },
  cost_element: { label: '成本要素', color: 'geekblue' },
};

const TagTypeSelect: React.FC<{ value?: string; onChange?: (value: string) => void }> = ({
  value,
  onChange,
}) => (
  <Select
    value={value}
    onChange={onChange}
    options={Object.entries(TAG_TYPE_CONFIG).map(([key, config]) => ({
      value: key,
      label: config.label,
    }))}
    placeholder="选择标签类型"
    style={{ width: '100%' }}
  />
);

const SourceSelect: React.FC<{ value?: string; onChange?: (value: string) => void }> = ({
  value,
  onChange,
}) => (
  <Select
    value={value}
    onChange={onChange}
    options={Object.entries(SOURCE_CONFIG).map(([key, config]) => ({
      value: key,
      label: config.label,
    }))}
    placeholder="选择来源"
    style={{ width: '100%' }}
  />
);

interface TagFilters {
  document_type: string;
  tag_type: string;
  source: string;
  vector_stored: '' | 'true' | 'false';
  created_from: string;
  created_to: string;
}

const emptyFilters: TagFilters = {
  document_type: '',
  tag_type: '',
  source: '',
  vector_stored: '',
  created_from: '',
  created_to: '',
};

// ==================== 文档标签管理标签页 ====================
function DocumentTagTab() {
  const [tags, setTags] = useState<DocumentTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<{
    total_tags: number;
    total_documents: number;
    by_tag_type: Array<{ tag_type: string; count: number; avg_confidence: number }>;
  } | null>(null);
  const [selectedTag, setSelectedTag] = useState<DocumentTag | null>(null);
  const [form] = Form.useForm();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [filters, setFilters] = useState<TagFilters>(emptyFilters);
  const [searchText, setSearchText] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([]);

  const [batchModalVisible, setBatchModalVisible] = useState(false);
  const [batchForm] = Form.useForm();

  const [historyModalVisible, setHistoryModalVisible] = useState(false);
  const [historyRecords, setHistoryRecords] = useState<Array<Record<string, unknown>>>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    fetchTags();
    fetchStats();
  }, [filters]);

  const buildApiFilters = () => {
    const apiFilters: Parameters<typeof api.listDocumentTags>[0] = {};
    if (filters.document_type) apiFilters.document_type = filters.document_type;
    if (filters.tag_type) apiFilters.tag_type = filters.tag_type;
    if (filters.source) apiFilters.source = filters.source;
    if (filters.vector_stored) {
      apiFilters.vector_stored = filters.vector_stored === 'true';
    }
    if (filters.created_from) apiFilters.created_from = filters.created_from;
    if (filters.created_to) apiFilters.created_to = filters.created_to;
    return apiFilters;
  };

  const fetchTags = async () => {
    setLoading(true);
    try {
      const result = await api.listDocumentTags(buildApiFilters());
      setTags(result);
      setSelectedRowKeys([]);
    } catch (error) {
      message.error('获取标签列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const result = await api.getDocumentTagStats();
      setStats(result);
    } catch (error) {
      console.error('获取统计信息失败', error);
    }
  };

  const handleRefresh = () => {
    fetchTags();
    fetchStats();
    message.info('已刷新');
  };

  const handleResetFilters = () => {
    setFilters(emptyFilters);
    setSearchText('');
  };

  const handleAdd = () => {
    form.resetFields();
    setSelectedTag(null);
    setIsEditMode(false);
    setIsModalVisible(true);
  };

  const handleEdit = (tag: DocumentTag) => {
    setSelectedTag(tag);
    form.setFieldsValue({
      tag: tag.tag,
      tag_type: tag.tag_type,
      confidence: tag.confidence,
      source: tag.source,
    });
    setIsEditMode(true);
    setIsModalVisible(true);
  };

  const handleDelete = async (tagId: number) => {
    try {
      await api.deleteDocumentTag(tagId);
      message.success('删除成功');
      fetchTags();
      fetchStats();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (isEditMode && selectedTag) {
        await api.updateDocumentTag(selectedTag.id, values);
        message.success('更新成功');
      } else {
        await api.createDocumentTag({
          document_id: 0,
          document_type: filters.document_type || 'general',
          ...values,
        });
        message.success('创建成功');
      }
      setIsModalVisible(false);
      fetchTags();
      fetchStats();
    } catch (error) {
      console.error('提交失败', error);
    }
  };

  const handleSearch = async () => {
    if (!searchText.trim()) {
      fetchTags();
      return;
    }
    try {
      const results = await api.searchDocumentTags({
        query_text: searchText,
        document_type: filters.document_type || undefined,
        tag_type: filters.tag_type || undefined,
        limit: 50,
      });
      setTags(results.map((r) => r.metadata));
      setSelectedRowKeys([]);
    } catch (error) {
      message.error('搜索失败');
    }
  };

  const handleBatchSync = async () => {
    try {
      const result = await api.syncDocumentTagVectors();
      message.success(`已同步 ${result.synced_count} 个标签`);
      fetchTags();
    } catch (error) {
      message.error('同步失败');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    try {
      const result = await api.batchDeleteDocumentTags({ tag_ids: selectedRowKeys });
      message.success(`已批量删除 ${result.deleted_count} 个标签`);
      fetchTags();
      fetchStats();
    } catch (error) {
      message.error('批量删除失败');
    }
  };

  const handleOpenBatchUpdate = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择标签');
      return;
    }
    batchForm.resetFields();
    setBatchModalVisible(true);
  };

  const handleBatchUpdateSubmit = async () => {
    try {
      const values = await batchForm.validateFields();
      const updates: Record<string, string | number> = {};
      if (values.tag_type) updates.tag_type = values.tag_type;
      if (values.source) updates.source = values.source;
      if (values.confidence != null) updates.confidence = values.confidence;
      if (Object.keys(updates).length === 0) {
        message.warning('请至少设置一项更新内容');
        return;
      }
      const result = await api.batchUpdateDocumentTags({
        tag_ids: selectedRowKeys,
        updates,
      });
      message.success(`已批量更新 ${result.updated_count} 个标签`);
      setBatchModalVisible(false);
      fetchTags();
      fetchStats();
    } catch (error) {
      console.error('批量更新失败', error);
    }
  };

  const handleViewHistory = async (tag: DocumentTag) => {
    setSelectedTag(tag);
    setHistoryModalVisible(true);
    setHistoryLoading(true);
    try {
      const records = await api.listDocumentTagHistory({ document_tag_id: tag.id, limit: 50 });
      setHistoryRecords(records as Array<Record<string, unknown>>);
    } catch (error) {
      message.error('获取历史记录失败');
      setHistoryRecords([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleCreatedFromChange = (date: Dayjs | null) => {
    setFilters((prev) => ({
      ...prev,
      created_from: date ? date.startOf('day').format('YYYY-MM-DDTHH:mm:ss') : '',
    }));
  };

  const handleCreatedToChange = (date: Dayjs | null) => {
    setFilters((prev) => ({
      ...prev,
      created_to: date ? date.endOf('day').format('YYYY-MM-DDTHH:mm:ss') : '',
    }));
  };

  const columns = [
    {
      title: '标签',
      dataIndex: 'tag',
      key: 'tag',
      ellipsis: true,
      width: 220,
    },
    {
      title: '标签类型',
      dataIndex: 'tag_type',
      key: 'tag_type',
      width: 100,
      render: (tag_type: string) => (
        <Tag color={TAG_TYPE_CONFIG[tag_type]?.color || 'default'}>
          {TAG_TYPE_CONFIG[tag_type]?.label || tag_type}
        </Tag>
      ),
    },
    {
      title: '文档类型',
      dataIndex: 'document_type',
      key: 'document_type',
      width: 120,
      render: (type: string) => <Tag color="cyan">{type}</Tag>,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (source: string) => (
        <Tag color={SOURCE_CONFIG[source]?.color || 'default'}>
          {SOURCE_CONFIG[source]?.label || source}
        </Tag>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 90,
      render: (confidence: number) => <span>{(confidence * 100).toFixed(0)}%</span>,
    },
    {
      title: '向量状态',
      dataIndex: 'vector_stored',
      key: 'vector_stored',
      width: 100,
      render: (stored: boolean) => (
        <Tag color={stored ? 'green' : 'red'}>{stored ? '已同步' : '待同步'}</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: DocumentTag) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Button type="link" icon={<HistoryOutlined />} onClick={() => handleViewHistory(record)}>
            历史
          </Button>
          <Popconfirm title="确定删除该标签？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const documentTypeOptions = [
    { value: '', label: '全部' },
    { value: 'invoice', label: '发票' },
    { value: 'contract', label: '合同' },
    { value: 'bank_statement', label: '银行流水' },
    { value: 'receipt', label: '收据' },
    { value: 'inventory_receipt', label: '入库单' },
    { value: 'salary_table', label: '工资表' },
    { value: 'expense_document', label: '费用报销' },
  ];

  return (
    <>
      {stats && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic title="标签总数" value={stats.total_tags} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="关联文档" value={stats.total_documents} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="标签类型" value={stats.by_tag_type.length} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Button type="primary" block icon={<ReloadOutlined />} onClick={handleBatchSync}>
                同步向量索引
              </Button>
            </Card>
          </Col>
        </Row>
      )}

      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={16}>
            <Col span={4}>
              <Select
                placeholder="文档类型"
                value={filters.document_type}
                onChange={(value) => setFilters({ ...filters, document_type: value })}
                options={documentTypeOptions}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={4}>
              <Select
                placeholder="标签类型"
                value={filters.tag_type}
                onChange={(value) => setFilters({ ...filters, tag_type: value })}
                options={[
                  { value: '', label: '全部' },
                  ...Object.entries(TAG_TYPE_CONFIG).map(([key, config]) => ({
                    value: key,
                    label: config.label,
                  })),
                ]}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={4}>
              <Select
                placeholder="来源"
                value={filters.source}
                onChange={(value) => setFilters({ ...filters, source: value })}
                options={[
                  { value: '', label: '全部' },
                  ...Object.entries(SOURCE_CONFIG).map(([key, config]) => ({
                    value: key,
                    label: config.label,
                  })),
                ]}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={4}>
              <Select
                placeholder="向量状态"
                value={filters.vector_stored}
                onChange={(value) => setFilters({ ...filters, vector_stored: value })}
                options={[
                  { value: '', label: '全部' },
                  { value: 'true', label: '已同步' },
                  { value: 'false', label: '待同步' },
                ]}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={4}>
              <DatePicker
                placeholder="创建开始"
                value={filters.created_from ? dayjs(filters.created_from) : null}
                onChange={handleCreatedFromChange}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={4}>
              <DatePicker
                placeholder="创建结束"
                value={filters.created_to ? dayjs(filters.created_to) : null}
                onChange={handleCreatedToChange}
                style={{ width: '100%' }}
              />
            </Col>
          </Row>
          <Row gutter={16} align="middle">
            <Col span={12}>
              <Space>
                <Input
                  placeholder="语义搜索"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  prefix={<SearchOutlined />}
                  onPressEnter={handleSearch}
                  style={{ width: 320 }}
                />
                <Button icon={<SearchOutlined />} onClick={handleSearch}>
                  搜索
                </Button>
              </Space>
            </Col>
            <Col span={12} style={{ textAlign: 'right' }}>
              <Button onClick={handleResetFilters}>重置筛选</Button>
            </Col>
          </Row>
        </Space>
      </Card>

      {selectedRowKeys.length > 0 && (
        <Card style={{ marginBottom: 16, background: '#f6ffed' }}>
          <Space>
            <span>已选择 {selectedRowKeys.length} 个标签</span>
            <Button type="primary" onClick={handleOpenBatchUpdate}>
              批量更新属性
            </Button>
            <Popconfirm title="确定批量删除选中的标签？" onConfirm={handleBatchDelete}>
              <Button danger>批量删除</Button>
            </Popconfirm>
          </Space>
        </Card>
      )}

      <Table
        columns={columns}
        dataSource={tags}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1200 }}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys as number[]),
        }}
      />

      <Modal
        title={isEditMode ? '编辑标签' : '添加标签'}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onOk={handleSubmit}
        width={500}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="tag"
            label="标签内容"
            rules={[{ required: true, message: '请输入标签内容' }]}
          >
            <Input placeholder="例如：发票类型:增值税专用发票" />
          </Form.Item>
          <Form.Item
            name="tag_type"
            label="标签类型"
            rules={[{ required: true, message: '请选择标签类型' }]}
          >
            <TagTypeSelect />
          </Form.Item>
          <Form.Item
            name="confidence"
            label="置信度"
            rules={[{ required: true, message: '请输入置信度' }]}
            initialValue={0.8}
          >
            <InputNumber
              min={0}
              max={1}
              step={0.05}
              style={{ width: '100%' }}
              formatter={(value) => `${(value || 0) * 100}%`}
              parser={(value) => {
                const parsed = parseFloat(value?.replace('%', '') || '0') / 100;
                return Math.min(Math.max(parsed, 0), 1) as 0 | 1;
              }}
            />
          </Form.Item>
          <Form.Item
            name="source"
            label="来源"
            rules={[{ required: true, message: '请选择来源' }]}
            initialValue="manual"
          >
            <SourceSelect />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="批量更新标签属性"
        open={batchModalVisible}
        onCancel={() => setBatchModalVisible(false)}
        onOk={handleBatchUpdateSubmit}
        width={500}
      >
        <Form form={batchForm} layout="vertical">
          <Form.Item name="tag_type" label="标签类型">
            <TagTypeSelect />
          </Form.Item>
          <Form.Item name="source" label="来源">
            <SourceSelect />
          </Form.Item>
          <Form.Item name="confidence" label="置信度">
            <InputNumber
              min={0}
              max={1}
              step={0.05}
              style={{ width: '100%' }}
              formatter={(value) => `${(value || 0) * 100}%`}
              parser={(value) => {
                const parsed = parseFloat(value?.replace('%', '') || '0') / 100;
                return Math.min(Math.max(parsed, 0), 1) as 0 | 1;
              }}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={selectedTag ? `标签历史记录：${selectedTag.tag}` : '标签历史记录'}
        open={historyModalVisible}
        onCancel={() => setHistoryModalVisible(false)}
        footer={null}
        width={720}
      >
        <Table
          dataSource={historyRecords}
          rowKey="id"
          loading={historyLoading}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: '操作', dataIndex: 'action', key: 'action', width: 80 },
            {
              title: '变更前',
              key: 'before',
              render: (_: unknown, record: Record<string, unknown>) =>
                `${record.before_tag || '-'} / ${record.before_tag_type || '-'}`,
            },
            {
              title: '变更后',
              key: 'after',
              render: (_: unknown, record: Record<string, unknown>) =>
                `${record.after_tag || '-'} / ${record.after_tag_type || '-'}`,
            },
            {
              title: '时间',
              dataIndex: 'created_at',
              key: 'created_at',
              render: (date: string) => new Date(date).toLocaleString('zh-CN'),
            },
          ]}
        />
      </Modal>
    </>
  );
}

// ==================== LLM 标签建议审批标签页 ====================
function LlmTagReviewTab() {
  const [suggestions, setSuggestions] = useState<LlmTagSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<LlmResolutionStatistics | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([]);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchSuggestions = async (page: number = 1, pageSize: number = 20) => {
    setLoading(true);
    try {
      const result = await api.llmGetPendingSuggestions({
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setSuggestions(result.items);
      setPagination((prev) => ({ ...prev, current: page, pageSize, total: result.total }));
      setSelectedRowKeys([]);
    } catch (error) {
      message.error('获取LLM标签建议失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const result = await api.llmGetStatistics();
      setStats(result);
    } catch (error) {
      console.error('获取统计信息失败', error);
    }
  };

  useEffect(() => {
    fetchSuggestions();
    fetchStats();
  }, []);

  const handleRefresh = () => {
    fetchSuggestions(pagination.current, pagination.pageSize);
    fetchStats();
    message.info('已刷新');
  };

  const handleApprove = async (ids: number[]) => {
    if (ids.length === 0) return;
    try {
      const result = await api.llmApproveSuggestions(ids);
      message.success(`已审批通过 ${result.approved_count} 个标签建议`);
      fetchSuggestions(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error) {
      message.error('审批失败');
    }
  };

  const handleReject = async (ids: number[]) => {
    if (ids.length === 0) return;
    try {
      const result = await api.llmRejectSuggestions(ids);
      message.success(`已驳回 ${result.rejected_count} 个标签建议`);
      fetchSuggestions(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error) {
      message.error('驳回失败');
    }
  };

  const handleBatchApprove = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择标签建议');
      return;
    }
    handleApprove(selectedRowKeys);
  };

  const handleBatchReject = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择标签建议');
      return;
    }
    handleReject(selectedRowKeys);
  };

  const filteredSuggestions = suggestions.filter((item) => {
    const matchCategory = !categoryFilter || item.category_code === categoryFilter;
    const matchSearch =
      !searchText.trim() ||
      item.display_name.includes(searchText.trim()) ||
      item.tag_value.includes(searchText.trim()) ||
      String(item.entry_id).includes(searchText.trim());
    return matchCategory && matchSearch;
  });

  const columns = [
    {
      title: '分录ID',
      dataIndex: 'entry_id',
      key: 'entry_id',
      width: 90,
    },
    {
      title: '标签值',
      dataIndex: 'display_name',
      key: 'display_name',
      ellipsis: true,
      render: (display_name: string, record: LlmTagSuggestion) => (
        <Space>
          <span>{display_name || record.tag_value}</span>
          <Tag color="processing">{record.tag_source}</Tag>
        </Space>
      ),
    },
    {
      title: '维度类别',
      dataIndex: 'category_code',
      key: 'category_code',
      width: 120,
      render: (category_code: string) => {
        const config = TAG_CATEGORY_CONFIG[category_code] || { label: category_code, color: 'default' };
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 100,
      render: (confidence: number) => (
        <Badge
          color={confidence >= 0.8 ? 'green' : confidence >= 0.6 ? 'orange' : 'red'}
          text={`${(confidence * 100).toFixed(0)}%`}
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => (date ? new Date(date).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: unknown, record: LlmTagSuggestion) => (
        <Space>
          <Button
            type="link"
            icon={<CheckOutlined />}
            onClick={() => handleApprove([record.id])}
          >
            通过
          </Button>
          <Button
            type="link"
            danger
            icon={<CloseOutlined />}
            onClick={() => handleReject([record.id])}
          >
            驳回
          </Button>
        </Space>
      ),
    },
  ];

  const categoryOptions = [
    { value: '', label: '全部类别' },
    ...Object.entries(TAG_CATEGORY_CONFIG).map(([key, config]) => ({
      value: key,
      label: config.label,
    })),
  ];

  return (
    <>
      {stats && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={8}>
            <Card>
              <Statistic
                title="待LLM解析分录"
                value={stats.pending_llm_resolution}
                valueStyle={{ color: '#faad14' }}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="待审批标签"
                value={stats.pending_review}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="已审批标签"
                value={stats.reviewed}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={16} align="middle">
            <Col span={6}>
              <Select
                placeholder="维度类别"
                value={categoryFilter}
                onChange={(value) => setCategoryFilter(value)}
                options={categoryOptions}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={12}>
              <Space>
                <Input
                  placeholder="搜索标签值、原始值或分录ID"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  prefix={<SearchOutlined />}
                  style={{ width: 320 }}
                />
                <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
                  刷新
                </Button>
              </Space>
            </Col>
          </Row>
        </Space>
      </Card>

      {selectedRowKeys.length > 0 && (
        <Card style={{ marginBottom: 16, background: '#f6ffed' }}>
          <Space>
            <span>已选择 {selectedRowKeys.length} 个标签建议</span>
            <Button type="primary" icon={<CheckOutlined />} onClick={handleBatchApprove}>
              批量通过
            </Button>
            <Button danger icon={<CloseOutlined />} onClick={handleBatchReject}>
              批量驳回
            </Button>
          </Space>
        </Card>
      )}

      <Table
        columns={columns}
        dataSource={filteredSuggestions}
        rowKey="id"
        loading={loading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchSuggestions(page, pageSize || 20),
        }}
        scroll={{ x: 900 }}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys as number[]),
        }}
        locale={{ emptyText: '暂无待审批的LLM标签建议' }}
      />
    </>
  );
}

// ==================== 入口页面 ====================
export default function DocumentTagsPage() {
  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <RobotOutlined />
            <span>标签管理</span>
          </Space>
        }
      >
        <Tabs defaultActiveKey="document">
          <TabPane tab="文档标签管理" key="document">
            <DocumentTagTab />
          </TabPane>
          <TabPane tab="LLM标签建议审批" key="llm-review">
            <LlmTagReviewTab />
          </TabPane>
        </Tabs>
      </Card>
    </div>
  );
}
