# Azure VM Bot

一个用于管理 Azure 虚拟机的 Telegram 机器人。

## 功能

- 启动/停止 Azure 虚拟机
- 查询虚拟机状态
- 通过 Telegram 进行远程管理

## 部署

详细的部署说明请参考 [AZURE_BOT_DEPLOY.md](AZURE_BOT_DEPLOY.md)

## 环境变量

需要配置以下环境变量：

- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token
- `AZURE_SUBSCRIPTION_ID`: Azure 订阅 ID
- `AZURE_TENANT_ID`: Azure 租户 ID
- `AZURE_CLIENT_ID`: Azure 客户端 ID
- `AZURE_CLIENT_SECRET`: Azure 客户端密钥
- `AZURE_RESOURCE_GROUP`: Azure 资源组名称
- `AZURE_VM_NAME`: Azure 虚拟机名称

## 使用

1. 克隆仓库
2. 配置环境变量
3. 运行 `python azure_vm_bot.py`
