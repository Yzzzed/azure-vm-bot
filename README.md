# Azure VM Bot

一个用于管理 Azure 虚拟机的 Telegram 机器人。

## 功能

- 启动/停止 Azure 虚拟机
- 查询虚拟机状态
- 通过 Telegram 进行远程管理

## 部署

详细的部署说明请参考 [AZURE_BOT_DEPLOY.md](AZURE_BOT_DEPLOY.md)

## 配置

### 1. 复制环境变量配置文件

```bash
cp .env.example .env.azure
```

### 2. 编辑 `.env.azure` 并填写你的配置

需要配置以下环境变量：

**机器人配置：**
- `AZURE_BOT_NAME`: 机器人名称（默认：AzureVmBot）
- `AZURE_BOT_COMMAND_PREFIX`: 命令前缀（默认：/）
- `AZURE_BOT_ALLOWED_USERS`: 允许使用机器人的用户 ID 列表（逗号分隔）

**Azure 配置：**
- `AZURE_VM_ENABLED`: 是否启用真实 Azure API 调用（true/false）
- `AZURE_VM_TENANT_ID`: Azure 租户 ID
- `AZURE_VM_CLIENT_ID`: Azure 应用程序（客户端）ID
- `AZURE_VM_CLIENT_SECRET`: Azure 客户端密钥
- `AZURE_VM_SUBSCRIPTION_ID`: Azure 订阅 ID
- `AZURE_VM_RESOURCE_GROUP`: Azure 资源组名称
- `AZURE_VM_NAME`: Azure 虚拟机名称

详细的获取方式请查看 `.env.example` 文件中的注释。

## 使用

1. 克隆仓库
   ```bash
   git clone https://github.com/Yzzzed/azure-vm-bot.git
   cd azure-vm-bot
   ```

2. 配置环境变量（参考上面的配置章节）

3. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

4. 运行机器人
   ```bash
   python azure_vm_bot.py
   ```
