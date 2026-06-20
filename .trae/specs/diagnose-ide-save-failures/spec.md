# IDE 文件保存失败排查 Spec

## Why
近期多次出现 Trae/VS Code 提示“无法写入文件 UNKNOWN”，涉及 `main.py`、`Step2ImportSource.tsx`、`Step3ImportEntries.tsx` 等真实项目文件，并曾生成 `ide临时文件`。这会影响开发稳定性，容易导致真实代码与临时副本混淆。

## What Changes
- 从整体排查保存失败原因：文件权限、只读属性、路径/文件名、目录写权限、Git 状态、运行进程占用、临时目录残留、IDE 临时副本混淆。
- 确认 `ide临时文件` 不再参与项目运行路径。
- 对最近报错文件执行非破坏性读写能力检查。
- 给出最小修复动作：清理临时目录、确认真实文件可写、避免误编辑临时副本。
- 如发现真实文件损坏或保存失败由项目结构引起，按最小改动修复。

## Impact
- Affected specs: 当前所有开发任务的稳定性
- Affected code: 不预期修改业务代码；仅在确认必要时调整配置或清理未跟踪临时文件

## ADDED Requirements
### Requirement: 真实路径识别
系统 SHALL 明确区分真实项目文件和 IDE 临时副本，后续开发只使用真实项目路径。

#### Scenario: 检测到 `ide临时文件`
- **WHEN** 工作区存在 `ide临时文件`
- **THEN** 系统确认该目录是否被项目引用
- **AND** 未被引用时应清理或提示关闭误打开标签

### Requirement: 文件写入能力检查
系统 SHALL 对频繁保存失败的文件执行非破坏性写入检查。

#### Scenario: 真实文件可读但 IDE 保存失败
- **WHEN** 文件可读取且同目录可创建临时文件
- **THEN** 判断问题更可能在 IDE 缓冲区、文件锁、杀毒/同步软件或编辑器临时副本层面

### Requirement: 开发进度恢复
系统 SHALL 在确认真实项目文件可写后恢复正常开发进度，不再使用临时目录路径。

#### Scenario: 排查完成
- **WHEN** 临时路径清理完成且真实路径验证通过
- **THEN** 继续以真实路径进行后续任务

## MODIFIED Requirements
### Requirement: 文件引用说明
后续回答涉及 `main.py`、`Step2ImportSource.tsx`、`Step3ImportEntries.tsx` 等文件时 SHALL 使用真实项目路径，不再引用 `ide临时文件`。

## REMOVED Requirements
无。
