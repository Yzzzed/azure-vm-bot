# Azure VM 自动开机机器人部署教程

## 功能说明

这是一个可以通过聊天工具（QQ机器人等）控制 Azure 虚拟机开关机的脚本，支持：

- `/status` - 查看服务器状态
- `/start` - 启动服务器
- `/stop` - 关闭服务器
- `/autostart` - 开启守护模式，每5分钟检查一次，发现服务器关机就自动开机
- `/help` - 查看帮助

## 部署位置选择

**重要：不要部署在你的 Azure VM 上！**

推荐部署位置：

1. **本地电脑**（适合测试）
   - 优点：方便调试
   - 缺点：电脑关机后机器人停止工作

2. **另一台常开的服务器**（推荐生产环境）
   - 优点：24小时运行，守护模式才有意义
   - 缺点：需要额外的服务器
   - 可以用：腾讯云轻量服务器、阿里云ECS、家里的NAS等

## 部署步骤

### 1. 安装 Python

确保安装了 Python 3.10 或更高版本：

```bash
python3 --version
```

### 2. 准备文件

将以下文件放在同一个目录：
- `azure_vm_bot.py` - 主程序
- `.env.azure` - 配置文件模板

### 3. 配置 Azure 应用注册

在 Azure 门户创建应用注册并授权：

#### 3.1 创建应用注册

1. 登录 [Azure 门户](https://portal.azure.com)
2. 搜索并进入 **Microsoft Entra ID**（旧称 Azure Active Directory）
3. 左侧菜单选择 **应用注册** → **新注册**
4. 填写信息：
   - 名称：`AzureVmBot`（随意）
   - 支持的账户类型：选择 **仅此组织目录中的账户**
   - 重定向 URI：留空
5. 点击 **注册**

#### 3.2 获取认证信息

注册完成后，在应用概览页面：

1. **应用程序(客户端) ID** - 复制保存
2. **目录(租户) ID** - 复制保存
3. 左侧菜单选择 **证书和密码** → **新客户端密码**
   - 说明：`bot-secret`（随意）
   - 过期时间：选择 **24个月**
   - 点击 **添加**
   - **立即复制 Value 值**（只显示一次！）

#### 3.3 授予权限

1. 回到 Azure 门户首页
2. 搜索并进入 **订阅**
3. 选择你的订阅 → 左侧菜单选择 **访问控制(IAM)**
4. 点击 **添加** → **添加角色分配**
5. 选择角色：**虚拟机参与者**（Virtual Machine Contributor）
6. 下一步，选择成员：搜索你刚创建的应用 `AzureVmBot`
7. 点击 **审阅 + 分配**

### 4. 配置机器人

复制配置文件并填写信息：

```bash
cp .env.azure .env
nano .env  # 或用其他编辑器
```

填写以下信息：

```bash
# 改为 true 启用真实 Azure API
AZURE_VM_ENABLED=true

# 从 Azure 门户获取的信息
AZURE_VM_TENANT_ID=你的租户ID
AZURE_VM_CLIENT_ID=你的应用程序ID
AZURE_VM_CLIENT_SECRET=你的客户端密码
AZURE_VM_SUBSCRIPTION_ID=你的订阅ID
AZURE_VM_RESOURCE_GROUP=你的资源组名称
AZURE_VM_NAME=你的VM名称

# 允许控制的用户ID（根据你的聊天平台修改）
AZURE_BOT_ALLOWED_USERS=10001
```

**获取 Azure 信息的位置：**

- **订阅ID**：Azure 门户 → 订阅 → 你的订阅 → 概览 → 订阅 ID
- **资源组**：Azure 门户 → 虚拟机 → 你的 VM → 概览 → 资源组
- **VM名称**：Azure 门户 → 虚拟机 → 你的 VM → 概览 → 名称（不是公网IP！）

### 5. 测试运行

先用控制台模式测试：

```bash
python3 azure_vm_bot.py
```

测试命令格式：

```
> /help              # 查看帮助
> /status            # 查看状态
> /start             # 启动服务器
> /stop              # 关闭服务器
> /autostart         # 开启守护模式
> quit               # 退出
```

如果一切正常，你会看到类似输出：

```
[MockConsoleClient] connected. type 'quit' to stop.
[AzureVmBot] started
> /status
[send-private] to 10001: 服务器状态：已关机
目标服务器：your-resource-group/your-vm-name
```

### 6. 集成到聊天平台（可选）

当前脚本使用的是 `MockConsoleClient`，只能在控制台测试。

要接入真实的聊天平台（QQ、微信、Telegram等），需要：

1. 替换 `BaseBotClient` 的实现
2. 实现对应平台的消息接收和发送
3. 修改 `ALLOWED_USER_IDS` 为真实的用户ID

常见平台：
- **QQ机器人**：使用 go-cqhttp、NoneBot2 等框架
- **Telegram**：使用 python-telegram-bot
- **微信**：使用 itchat、wechaty 等

### 7. 后台运行（生产环境）

使用 systemd 服务（Linux）：

创建服务文件 `/etc/systemd/system/azure-vm-bot.service`：

```ini
[Unit]
Description=Azure VM Auto Start Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 /path/to/bot/azure_vm_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable azure-vm-bot
sudo systemctl start azure-vm-bot
sudo systemctl status azure-vm-bot
```

查看日志：

```bash
sudo journalctl -u azure-vm-bot -f
```

## 安全建议

1. **保护 .env 文件**：包含敏感信息，不要提交到 Git
   ```bash
   echo ".env" >> .gitignore
   ```

2. **限制用户权限**：只在 `ALLOWED_USER_IDS` 中添加信任的用户

3. **最小权限原则**：Azure 应用只授予 "虚拟机参与者" 角色，不要给更高权限

4. **定期轮换密钥**：定期更新 Azure 客户端密码

## 故障排查

### 问题1：提示 "missing azure settings"

**原因**：配置文件未正确填写

**解决**：检查 `.env` 文件，确保所有 `AZURE_VM_*` 字段都已填写

### 问题2：提示 "azure token request failed"

**原因**：Azure 认证信息错误

**解决**：
1. 检查 `TENANT_ID`、`CLIENT_ID`、`CLIENT_SECRET` 是否正确
2. 确认客户端密码没有过期
3. 在 Azure 门户重新生成客户端密码

### 问题3：提示 "HTTP 403" 或权限错误

**原因**：应用没有权限操作虚拟机

**解决**：
1. 检查应用是否被授予 "虚拟机参与者" 角色
2. 确认角色分配在正确的订阅/资源组上
3. 等待几分钟让权限生效

### 问题4：守护模式不工作

**原因**：机器人进程停止或网络问题

**解决**：
1. 确保机器人进程持续运行（使用 systemd 或 screen）
2. 检查网络连接
3. 查看日志排查具体错误

## 常见问题

**Q: 可以同时控制多台 VM 吗？**

A: 当前版本只支持一台。如需控制多台，可以修改代码添加 VM 选择功能。

**Q: 守护模式会一直开机吗？**

A: 是的，只要检测到关机就会自动开机。如果不需要，发送 `/autostart` 关闭守护模式。

**Q: 会产生额外费用吗？**

A: Azure API 调用本身免费，但 VM 运行时间会计费。守护模式会让 VM 保持开机状态。

**Q: 可以定时开关机吗？**

A: 当前版本不支持。可以结合 cron 定时任务实现，或修改代码添加定时功能。

## 进阶功能

如果你想扩展功能，可以修改代码添加：

1. **多VM支持**：修改配置支持多个 VM，命令中指定 VM 名称
2. **定时任务**：添加定时开关机功能
3. **状态通知**：VM 状态变化时主动推送通知
4. **成本监控**：集成 Azure Cost Management API 查看费用
5. **日志记录**：记录所有操作到文件

## 参考资料

- [Azure REST API 文档](https://learn.microsoft.com/zh-cn/rest/api/compute/virtual-machines)
- [Azure 应用注册文档](https://learn.microsoft.com/zh-cn/entra/identity-platform/quickstart-register-app)
- [Azure RBAC 角色](https://learn.microsoft.com/zh-cn/azure/role-based-access-control/built-in-roles)
