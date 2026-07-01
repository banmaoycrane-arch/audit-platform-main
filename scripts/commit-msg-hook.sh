#!/bin/bash
# commit-msg hook: 校验提交信息是否符合 Conventional Commits 规范
# 安装方法：
#   cp scripts/commit-msg-hook.sh .git/hooks/commit-msg
#   chmod +x .git/hooks/commit-msg

commit_regex='^(feat|fix|docs|style|refactor|test|chore|perf|ci|revert|build)(\(.+\))?: .{1,72}'

error_msg="提交信息不符合 Conventional Commits 规范！

正确格式：<type>(<scope>): <subject>

可用 type：
  feat      新功能
  fix       Bug 修复
  docs      文档更新
  style     代码格式
  refactor  重构
  test      测试相关
  chore     构建/工具
  perf      性能优化
  ci        CI 配置
  revert    回滚提交

示例：
  feat(voucher): 添加凭证批量审核功能
  fix(report): 修复资产负债表不平衡问题
  docs(api): 更新凭证接口文档

详细规范请参考 GIT_WORKFLOW.md"

# 读取提交信息文件的第一行
first_line=$(head -1 "$1")

# 跳过 merge commit 和 revert commit
if [[ "$first_line" =~ ^Merge\  ]] || [[ "$first_line" =~ ^Revert\  ]]; then
    exit 0
fi

# 校验格式
if ! [[ "$first_line" =~ $commit_regex ]]; then
    echo "$error_msg"
    exit 1
fi

exit 0
