# Azure VM Hermes 使用指南

这是一个适配 Hermes 的 Azure VM 控制脚本，支持手动命令和定时任务。

## 功能

- ✅ 查询 VM 状态
- ✅ 启动/关闭 VM
- ✅ 自动守护模式（定时检查并自动启动）

## 配置

1. 复制环境变量配置文件：
```bash
cp .env.example .env.azure
```

2. 编辑 `.env.azure` 并填写你的 Azure 配置

3. 确保 `AZURE_VM_ENABLED=true`

## 在 Hermes 中使用

### 方式 1: 手动命令

在 Hermes 中发送以下命令：

```bash
# 查询 VM 状态
python3 /path/to/azure_vm_hermes.py status

# 启动 VM
python3 /path/to/azure_vm_hermes.py start

# 关闭 VM
python3 /path/to/azure_vm_hermes.py stop

# 守护检查（检查状态，如果未启动则自动启动）
python3 /path/to/azure_vm_hermes.py autostart
```

### 方式 2: 设置定时任务

在 Hermes 中设置定时任务，每 5 分钟自动检查并启动 VM：

```bash
# 添加到 crontab
*/5 * * * * cd /path/to/azure-vm-bot && python3 azure_vm_hermes.py autostart
```

或者使用 Hermes 的定时任务功能（如果支持）。

## 命令说明

| 命令 | 说明 | 适用场景 |
|------|------|----------|
| `status` | 查询 VM 当前状态 | 手动查看服务器状态 |
| `start` | 发送启动命令 | 手动启动服务器 |
| `stop` | 发送关机命令 | 手动关闭服务器 |
| `autostart` | 守护检查，如果未启动则自动启动 | 定时任务，保持服务器始终运行 |

## 输出示例

### 查询状态
```
📊 服务器状态
目标: my-resource-group/my-vm
状态: ✅ 正在运行
```

### 启动服务器
```
✅ 已发送启动命令
目标: my-resource-group/my-vm
提示: 服务器需要一点时间启动，请稍后使用 /status 查看
```

### 守护模式
```
🔄 守护模式: 检测到服务器未启动，已自动发送开机命令
目标: my-resource-group/my-vm
之前状态: ⛔ 已关机
```

## 故障排查

### 1. 命令执行失败
- 检查 `.env.azure` 文件是否存在且配置正确
- 确保 `AZURE_VM_ENABLED=true`
- 检查 Azure 凭证是否有效

### 2. 权限问题
- 确保 Azure 应用注册有足够的权限（Virtual Machine Contributor）
- 检查订阅 ID、资源组、VM 名称是否正确

### 3. 网络问题
- 确保可以访问 Azure API（`management.azure.com`）
- 检查防火墙设置

## 与原版的区别

| 特性 | 原版 (azure_vm_bot.py) | Hermes 版 (azure_vm_hermes.py) |
|------|------------------------|--------------------------------|
| 运行方式 | 长期运行的机器人进程 | 单次执行的命令行工具 |
| 交互方式 | QQ/控制台交互 | 命令行参数 |
| 守护模式 | 内置后台任务 | 通过外部定时任务（cron） |
| 依赖 | 无 | 无 |
| 适用场景 | QQ 机器人 | Hermes / 命令行 / 定时任务 |
