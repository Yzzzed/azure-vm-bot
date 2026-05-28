# Azure VM Hermes 快速使用指南

## 📋 可用命令

### 1. 查询 VM 状态
```bash
python3 azure_vm_hermes.py status
```
输出示例：
```
📊 服务器状态
目标: sub2api_group/sub2api
状态: ✅ 正在运行
```

### 2. 启动 VM
```bash
python3 azure_vm_hermes.py start
```

### 3. 关闭 VM
```bash
python3 azure_vm_hermes.py stop
```

### 4. 自动守护（检查并自动启动）
```bash
python3 azure_vm_hermes.py autostart
```
这个命令会：
- 检查 VM 状态
- 如果 VM 未运行，自动发送启动命令
- 如果 VM 已运行，只报告状态

## 🤖 在 Hermes 中使用

### 方式 1: 手动执行命令

在 Hermes 中直接发送命令：
```
/exec python3 /path/to/azure-vm-bot/azure_vm_hermes.py status
```

### 方式 2: 设置定时任务

如果 Hermes 支持定时任务，可以设置每 5 分钟自动检查：
```bash
# 每 5 分钟执行一次守护检查
*/5 * * * * cd /path/to/azure-vm-bot && python3 azure_vm_hermes.py autostart
```

或者使用系统 crontab：
```bash
# 编辑 crontab
crontab -e

# 添加以下行（每 5 分钟检查一次）
*/5 * * * * cd /path/to/azure-vm-bot && python3 azure_vm_hermes.py autostart >> /tmp/azure-vm-autostart.log 2>&1
```

## 📝 配置信息

- **配置文件**: `.env.azure`
- **权限要求**: Azure 应用需要"虚拟机参与者"角色

## 🔧 故障排查

### SSL 连接错误
如果遇到 SSL 错误，重试一次通常可以解决。这是网络临时问题。

### 权限错误
如果看到 403 错误，检查：
1. Azure 门户 → 资源组 → 访问控制 (IAM)
2. 确认 AzureVmBot 有"虚拟机参与者"角色

### 配置错误
如果提示"Azure VM 控制功能未启用"：
1. 检查 `.env.azure` 文件
2. 确保 `AZURE_VM_ENABLED=true`

## 🎯 下一步

1. **测试所有命令**：确保 start/stop/status 都能正常工作
2. **设置定时任务**：让 VM 保持自动运行
3. **集成到 Hermes**：根据你的 Hermes 配置方式集成命令

## 📚 相关文档

- 完整使用说明：`HERMES_USAGE.md`
- 部署文档：`AZURE_BOT_DEPLOY.md`
- 项目 README：`README.md`
