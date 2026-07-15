import { Alert } from 'antd'
import { Link, useLocation } from 'react-router-dom'

const UNDEVELOPED_MODULE_PREFIXES: Array<{ prefix: string; name: string }> = [
  { prefix: '/bank', name: '银行模块' },
  { prefix: '/inventory', name: '进销存模块' },
  { prefix: '/fixed-assets', name: '固定资产模块' },
]

function resolveUndevelopedModule(pathname: string) {
  return UNDEVELOPED_MODULE_PREFIXES.find((item) => pathname === item.prefix || pathname.startsWith(`${item.prefix}/`))
}

function isTaxModulePath(pathname: string) {
  return pathname === '/tax' || pathname.startsWith('/tax/')
}

export function UndevelopedModuleNotice({ moduleName }: { moduleName: string }) {
  return (
    <Alert
      type="warning"
      showIcon
      title={`${moduleName}尚未开发`}
      description="当前入口仅作产品规划占位，暂无正式业务数据与流程。请优先使用「财务总账」完成记账闭环，或「审计系统」完成审计验收路径。"
      style={{ marginBottom: 16 }}
    />
  )
}

/** 税务模块：记账不依赖税局登录，直连为可选增值 */
export function TaxModuleNotice() {
  return (
    <Alert
      type="info"
      showIcon
      title="记账无需开通税局直连"
      description={(
        <span>
          代账「只做记账、客户只给文件」请走
          <Link to="/ledger/vouchers/step/1"> 财务总账 · 序时簿导入 </Link>
          （Excel/PDF/OFD 等），无需配置 IP 或登录电子税务局。
          「税局直连（代开票/取票）」为<strong>可选增值</strong>，仅当客户明确要求代操作税局时再启用
          <Link to="/tax/connections"> 税务连接 </Link>
          ；大客户自动化开票请单独立项乐企/航天百旺，不与记账 MVP 绑定。
        </span>
      )}
      style={{ marginBottom: 16 }}
    />
  )
}

/** 在 MainShell 内容区顶部展示模块提示 */
export function ModuleStatusNotices() {
  const { pathname } = useLocation()
  if (isTaxModulePath(pathname)) {
    return <TaxModuleNotice />
  }
  const module = resolveUndevelopedModule(pathname)
  if (!module) {
    return null
  }
  return <UndevelopedModuleNotice moduleName={module.name} />
}

export function ExperimentalAgentNotice() {
  return (
    <Alert
      type="warning"
      showIcon
      title="实验功能"
      description="Agent 助手处于 Wizard of Oz 验证阶段，能力以规则导航与只读查询为主，不替代 Step1–5 记账向导。结果仅供参考，重要操作请在对应业务页面完成。"
      style={{ marginBottom: 16 }}
    />
  )
}
