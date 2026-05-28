from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable


# ===== User Config =====
# 直接改这里最方便；如果想改用 .env，可以把字符串留空、列表改成 None、布尔改成 None。
BOT_NAME = "AzureVmBot"  # 机器人显示名称，只影响控制台提示。
COMMAND_PREFIX = "/"  # 命令前缀，默认是 / ，所以命令是 /status /start /stop。
ALLOWED_USER_IDS = ["10001"]  # 允许控制服务器的聊天用户 ID，不是 Azure 账号 ID；本地 mock 里 u:10001 就填 "10001"。

AZURE_VM_ENABLED = False  # 配置完整并准备真实调用 Azure 后改成 True；只演示路由时保持 False。
AZURE_VM_TENANT_ID = ""  # Azure 门户 -> Microsoft Entra ID -> 概览 -> 租户 ID(Tenant ID)。
AZURE_VM_CLIENT_ID = ""  # Azure 门户 -> Microsoft Entra ID -> 应用注册 -> 你的应用 -> 应用程序(客户端) ID。
AZURE_VM_CLIENT_SECRET = ""  # Azure 门户 -> 应用注册 -> 证书和密码 -> 客户端密码的 Value，不是 Secret ID。
AZURE_VM_SUBSCRIPTION_ID = ""  # Azure 门户 -> 订阅 -> 目标订阅 -> 概览 -> 订阅 ID。
AZURE_VM_RESOURCE_GROUP = ""  # Azure 门户 -> 虚拟机 -> 你的 VM -> 概览 -> 资源组(Resource group)。
AZURE_VM_NAME = ""  # Azure 门户 -> 虚拟机 -> 你的 VM -> 概览 -> 资源名称，不是公网 IP。
AZURE_VM_API_VERSION = "2023-09-01"  # Azure Compute REST API 版本，一般保持默认即可。


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def pick_str(config_value: str, env_name: str, default: str = "") -> str:
    value = config_value.strip()
    if value:
        return value
    return os.getenv(env_name, default).strip() or default


def pick_bool(config_value: bool | None, env_name: str, default: bool) -> bool:
    if config_value is not None:
        return bool(config_value)
    return parse_bool(os.getenv(env_name), default)


def pick_list(config_value: list[str] | None, env_name: str) -> list[str]:
    if config_value is not None:
        return [str(item).strip() for item in config_value if str(item).strip()]
    return parse_csv(os.getenv(env_name))


@dataclass(slots=True)
class AzureVMSettings:
    enabled: bool = False
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    subscription_id: str = ""
    resource_group: str = ""
    vm_name: str = ""
    api_version: str = "2023-09-01"

    def missing_fields(self) -> list[str]:
        return [
            name
            for name in [
                "tenant_id",
                "client_id",
                "client_secret",
                "subscription_id",
                "resource_group",
                "vm_name",
            ]
            if not getattr(self, name, "").strip()
        ]


@dataclass(slots=True)
class BotSettings:
    bot_name: str = "AzureVmBot"
    command_prefix: str = "/"
    allowed_user_ids: list[str] = field(default_factory=list)
    azure_vm: AzureVMSettings = field(default_factory=AzureVMSettings)

    def normalized_allowed_user_ids(self) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in self.allowed_user_ids:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized


def load_settings() -> BotSettings:
    return BotSettings(
        bot_name=pick_str(BOT_NAME, "AZURE_BOT_NAME", "AzureVmBot"),
        command_prefix=pick_str(COMMAND_PREFIX, "AZURE_BOT_COMMAND_PREFIX", "/"),
        allowed_user_ids=pick_list(ALLOWED_USER_IDS, "AZURE_BOT_ALLOWED_USERS"),
        azure_vm=AzureVMSettings(
            enabled=pick_bool(AZURE_VM_ENABLED, "AZURE_VM_ENABLED", False),
            tenant_id=pick_str(AZURE_VM_TENANT_ID, "AZURE_VM_TENANT_ID"),
            client_id=pick_str(AZURE_VM_CLIENT_ID, "AZURE_VM_CLIENT_ID"),
            client_secret=pick_str(AZURE_VM_CLIENT_SECRET, "AZURE_VM_CLIENT_SECRET"),
            subscription_id=pick_str(AZURE_VM_SUBSCRIPTION_ID, "AZURE_VM_SUBSCRIPTION_ID"),
            resource_group=pick_str(AZURE_VM_RESOURCE_GROUP, "AZURE_VM_RESOURCE_GROUP"),
            vm_name=pick_str(AZURE_VM_NAME, "AZURE_VM_NAME"),
            api_version=pick_str(AZURE_VM_API_VERSION, "AZURE_VM_API_VERSION", "2023-09-01"),
        ),
    )


@dataclass(slots=True)
class MessageEvent:
    user_id: str
    message: str
    group_id: str | None = None
    raw_event: dict[str, Any] = field(default_factory=dict)


CommandHandler = Callable[[MessageEvent, list[str], "Bot"], Awaitable[None]]


class CommandRouter:
    def __init__(self, prefix: str = "/") -> None:
        self.prefix = prefix
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, command: str, handler: CommandHandler) -> None:
        self._handlers[command.lower()] = handler

    def command(self, command: str) -> Callable[[CommandHandler], CommandHandler]:
        def decorator(func: CommandHandler) -> CommandHandler:
            self.register(command, func)
            return func

        return decorator

    @property
    def command_names(self) -> list[str]:
        return sorted(self._handlers.keys())

    async def dispatch(self, event: MessageEvent, bot: "Bot") -> bool:
        text = event.message.strip()
        if not text or not text.startswith(self.prefix):
            return False

        payload = text[len(self.prefix) :].strip()
        if not payload:
            return False

        parts = payload.split()
        command = parts[0].lower()
        args = parts[1:]
        handler = self._handlers.get(command)
        if handler is None:
            await bot.reply(event, f"没有这个命令：/{command}\n发送 /help 查看可用命令。")
            return False

        await handler(event, args, bot)
        return True


class BaseBotClient(ABC):
    @property
    def supports_recv_events(self) -> bool:
        return True

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def recv_event(self) -> MessageEvent:
        pass

    @abstractmethod
    async def send_private_message(self, user_id: str, message: str) -> None:
        pass

    @abstractmethod
    async def send_group_message(self, group_id: str, message: str) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


class MockConsoleClient(BaseBotClient):
    async def connect(self) -> None:
        print("[MockConsoleClient] connected. type 'quit' to stop.")
        print("[MockConsoleClient] private: u:<user_id> <message>")
        print("[MockConsoleClient] group:   g:<group_id>:<user_id> <message>")

    async def recv_event(self) -> MessageEvent:
        line = await asyncio.to_thread(input, "> ")
        text = line.strip()
        if not text:
            return MessageEvent(user_id="0", message="")

        if text.lower() in {"quit", "exit"}:
            raise EOFError("stop requested")

        if text.startswith("u:"):
            header, _, message = text.partition(" ")
            user_id = header[2:].strip() or "10001"
            return MessageEvent(user_id=user_id, message=message)

        if text.startswith("g:"):
            header, _, message = text.partition(" ")
            try:
                _, group_id, user_id = header.split(":", maxsplit=2)
            except ValueError:
                group_id = "20001"
                user_id = "10001"
            return MessageEvent(
                user_id=user_id.strip() or "10001",
                group_id=group_id.strip() or "20001",
                message=message,
            )

        return MessageEvent(user_id="10001", message=text)

    async def send_private_message(self, user_id: str, message: str) -> None:
        print(f"[send-private] to {user_id}: {message}")

    async def send_group_message(self, group_id: str, message: str) -> None:
        print(f"[send-group] to {group_id}: {message}")

    async def close(self) -> None:
        print("[MockConsoleClient] disconnected")


class Bot:
    def __init__(self, settings: BotSettings, client: BaseBotClient) -> None:
        self.settings = settings
        self.client = client
        self.router = CommandRouter(prefix=settings.command_prefix)
        self._running = False
        self._background_tasks: set[asyncio.Task[None]] = set()

    @property
    def is_running(self) -> bool:
        return self._running

    def command(self, name: str) -> Callable[[CommandHandler], CommandHandler]:
        return self.router.command(name)

    def create_background_task(self, coro: Awaitable[None], name: str) -> asyncio.Task[None]:
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def reply(self, event: MessageEvent, message: str) -> None:
        if event.group_id is not None:
            await self.client.send_group_message(event.group_id, message)
            return
        await self.client.send_private_message(event.user_id, message)

    async def run_event_loop(self) -> None:
        while self._running:
            event = await self.client.recv_event()
            if not event.message.strip():
                continue
            await self.router.dispatch(event, self)

    async def start(self) -> None:
        self._running = True
        await self.client.connect()
        print(f"[{self.settings.bot_name}] started")

        try:
            await self.run_event_loop()
        except EOFError:
            print(f"[{self.settings.bot_name}] stop requested")
        finally:
            await self.stop()

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False

        for task in list(self._background_tasks):
            task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        await self.client.close()
        print(f"[{self.settings.bot_name}] stopped")


class AzureVMController:
    def __init__(self) -> None:
        self._access_token = ""
        self._token_expire_at = 0.0
        self._token_lock = asyncio.Lock()

    @staticmethod
    def target_label(settings: AzureVMSettings) -> str:
        parts = [settings.resource_group.strip(), settings.vm_name.strip()]
        return "/".join(part for part in parts if part) or "Azure VM"

    @staticmethod
    def humanize_status(code: str) -> str:
        mapping = {
            "PowerState/running": "正在运行，服务器已经开机",
            "PowerState/starting": "正在启动中",
            "PowerState/stopping": "正在关机中",
            "PowerState/stopped": "已关机",
            "PowerState/deallocating": "正在释放资源并关机",
            "PowerState/deallocated": "已关机，并且 Azure 计算资源已经释放",
        }
        return mapping.get(code, f"当前状态：{code}")

    async def start_vm(self, settings: AzureVMSettings) -> tuple[bool, str]:
        return await self.post_action(settings, "start")

    async def stop_vm(self, settings: AzureVMSettings) -> tuple[bool, str]:
        return await self.post_action(settings, "powerOff")

    async def get_vm_status(self, settings: AzureVMSettings) -> tuple[bool, str, str]:
        missing = settings.missing_fields()
        if missing:
            return False, "", f"missing azure settings: {', '.join(missing)}"

        try:
            token = await self.ensure_access_token(settings)
            url = (
                "https://management.azure.com/subscriptions/"
                f"{settings.subscription_id}/resourceGroups/{settings.resource_group}/"
                "providers/Microsoft.Compute/virtualMachines/"
                f"{settings.vm_name}/instanceView?api-version={settings.api_version}"
            )
            body = await asyncio.to_thread(
                self.get_json,
                url,
                {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        except Exception as exc:
            return False, "", str(exc)

        statuses = body.get("statuses") if isinstance(body, dict) else None
        if not isinstance(statuses, list):
            return False, "", "Azure 返回的数据里没有状态信息"

        for item in statuses:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            if code.startswith("PowerState/"):
                return True, code, ""

        return False, "", "没有找到电源状态"

    async def post_action(self, settings: AzureVMSettings, action: str) -> tuple[bool, str]:
        missing = settings.missing_fields()
        if missing:
            return False, f"missing azure settings: {', '.join(missing)}"

        try:
            token = await self.ensure_access_token(settings)
            url = (
                "https://management.azure.com/subscriptions/"
                f"{settings.subscription_id}/resourceGroups/{settings.resource_group}/"
                "providers/Microsoft.Compute/virtualMachines/"
                f"{settings.vm_name}/{action}?api-version={settings.api_version}"
            )
            status_code, _ = await asyncio.to_thread(
                self.post_empty,
                url,
                {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                action,
            )
        except Exception as exc:
            return False, str(exc)

        if status_code in {200, 202, 204}:
            return True, "ok"
        return False, f"unexpected status {status_code}"

    async def ensure_access_token(self, settings: AzureVMSettings) -> str:
        now = time.time()
        if self._access_token and now < self._token_expire_at:
            return self._access_token

        async with self._token_lock:
            now = time.time()
            if self._access_token and now < self._token_expire_at:
                return self._access_token

            token_url = f"https://login.microsoftonline.com/{settings.tenant_id}/oauth2/v2.0/token"
            status_code, body = await asyncio.to_thread(
                self.post_form,
                token_url,
                {
                    "client_id": settings.client_id,
                    "client_secret": settings.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "https://management.azure.com/.default",
                },
            )
            if status_code not in {200, 201}:
                raise RuntimeError(f"azure token request failed: HTTP {status_code}")

            token = str(body.get("access_token", "")).strip()
            expires_in = int(body.get("expires_in", 3600))
            if not token:
                raise RuntimeError("azure token response missing access_token")

            self._access_token = token
            self._token_expire_at = time.time() + max(60, expires_in - 120)
            return token

    @staticmethod
    def post_form(url: str, form: dict[str, str]) -> tuple[int, dict[str, object]]:
        encoded = urllib.parse.urlencode(form).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read()
                code = int(response.getcode() or 0)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"azure token HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"azure token connection failed: {exc}") from exc

        if not raw:
            return code, {}

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("azure token response is not JSON") from exc

        if isinstance(parsed, dict):
            return code, parsed
        raise RuntimeError("azure token response has unexpected structure")

    @staticmethod
    def post_empty(url: str, headers: dict[str, str], action: str) -> tuple[int, bytes]:
        req = urllib.request.Request(url=url, data=b"", headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return int(response.getcode() or 0), response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"azure {action} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"azure {action} connection failed: {exc}") from exc

    @staticmethod
    def get_json(url: str, headers: dict[str, str]) -> dict[str, object]:
        req = urllib.request.Request(url=url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"azure status HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"azure status connection failed: {exc}") from exc

        if not raw:
            return {}

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("azure status response is not JSON") from exc

        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError("azure status response has unexpected structure")


def ensure_allowed(bot: Bot, user_id: str) -> None:
    allowed = set(bot.settings.normalized_allowed_user_ids())
    if allowed and str(user_id).strip() not in allowed:
        raise PermissionError("only configured users can use this command")


def azure_disabled_text() -> str:
    return "当前没有开启 Azure 服务器控制功能。"


def register_commands(bot: Bot) -> None:
    controller = AzureVMController()
    monitor_interval_seconds = 300
    monitor_active = False
    monitor_task: asyncio.Task[None] | None = None
    monitor_target: MessageEvent | None = None

    def clone_message_target(event: MessageEvent) -> MessageEvent:
        return MessageEvent(user_id=event.user_id, group_id=event.group_id, message="")

    async def send_monitor_message(bot_instance: Bot, message: str) -> None:
        if monitor_target is None:
            print(f"[autostart] {message}")
            return
        try:
            await bot_instance.reply(monitor_target, message)
        except Exception as exc:
            print(f"[autostart] notify failed: {exc}")

    async def monitor_once(bot_instance: Bot) -> None:
        azure = bot_instance.settings.azure_vm
        ok, code, detail = await controller.get_vm_status(azure)
        if not ok:
            print(f"[autostart] status check failed: {detail}")
            return

        if code in {"PowerState/running", "PowerState/starting"}:
            print(f"[autostart] status ok: {code}")
            return

        start_ok, start_detail = await controller.start_vm(azure)
        label = controller.target_label(azure)
        status_text = controller.humanize_status(code)
        if start_ok:
            await send_monitor_message(
                bot_instance,
                "守护模式检测到服务器未启动，已自动发送开机命令。\n"
                f"目标服务器：{label}\n"
                f"检测到的状态：{status_text}",
            )
            return

        await send_monitor_message(
            bot_instance,
            "守护模式检测到服务器未启动，但自动开机失败。\n"
            f"目标服务器：{label}\n"
            f"检测到的状态：{status_text}\n"
            f"失败原因：{start_detail}",
        )

    async def monitor_loop(bot_instance: Bot) -> None:
        while bot_instance.is_running and monitor_active:
            await monitor_once(bot_instance)
            await asyncio.sleep(monitor_interval_seconds)

    @bot.command("help")
    async def help_cmd(event: MessageEvent, args: list[str], bot_instance: Bot) -> None:
        commands = "、".join(f"/{name}" for name in bot_instance.router.command_names)
        await bot_instance.reply(
            event,
            "可用命令如下：\n"
            f"{commands}\n"
            "/status：查看 Azure VM 当前状态\n"
            "/start：启动 Azure VM\n"
            "/stop：关闭 Azure VM\n"
            "/autostart：开启或关闭守护模式，每 5 分钟检查一次，发现服务器没开就自动开机\n"
            "/help：查看这份说明",
        )

    @bot.command("status")
    async def status_cmd(event: MessageEvent, args: list[str], bot_instance: Bot) -> None:
        try:
            ensure_allowed(bot_instance, event.user_id)
        except PermissionError:
            await bot_instance.reply(event, "你没有权限查看服务器状态。")
            return

        azure = bot_instance.settings.azure_vm
        if not azure.enabled:
            await bot_instance.reply(event, azure_disabled_text())
            return

        ok, code, detail = await controller.get_vm_status(azure)
        if not ok:
            await bot_instance.reply(event, f"查询服务器状态失败：{detail}")
            return

        await bot_instance.reply(
            event,
            f"服务器状态：{controller.humanize_status(code)}\n"
            f"目标服务器：{controller.target_label(azure)}",
        )

    @bot.command("start")
    async def start_cmd(event: MessageEvent, args: list[str], bot_instance: Bot) -> None:
        try:
            ensure_allowed(bot_instance, event.user_id)
        except PermissionError:
            await bot_instance.reply(event, "你没有权限执行开机命令。")
            return

        azure = bot_instance.settings.azure_vm
        if not azure.enabled:
            await bot_instance.reply(event, azure_disabled_text())
            return

        ok, detail = await controller.start_vm(azure)
        if not ok:
            await bot_instance.reply(event, f"开机失败：{detail}")
            return

        await bot_instance.reply(
            event,
            "已发送开机命令。\n"
            f"目标服务器：{controller.target_label(azure)}\n"
            "服务器需要一点时间启动，请稍后再发 /status 查看结果。",
        )

    @bot.command("stop")
    async def stop_cmd(event: MessageEvent, args: list[str], bot_instance: Bot) -> None:
        try:
            ensure_allowed(bot_instance, event.user_id)
        except PermissionError:
            await bot_instance.reply(event, "你没有权限执行关机命令。")
            return

        azure = bot_instance.settings.azure_vm
        if not azure.enabled:
            await bot_instance.reply(event, azure_disabled_text())
            return

        ok, detail = await controller.stop_vm(azure)
        if not ok:
            await bot_instance.reply(event, f"关机失败：{detail}")
            return

        await bot_instance.reply(
            event,
            "已发送关机命令。\n"
            f"目标服务器：{controller.target_label(azure)}\n"
            "服务器需要一点时间关闭，请稍后再发 /status 确认。",
        )

    @bot.command("autostart")
    async def autostart_cmd(event: MessageEvent, args: list[str], bot_instance: Bot) -> None:
        nonlocal monitor_active, monitor_task, monitor_target

        try:
            ensure_allowed(bot_instance, event.user_id)
        except PermissionError:
            await bot_instance.reply(event, "你没有权限修改守护模式。")
            return

        azure = bot_instance.settings.azure_vm
        if not azure.enabled:
            await bot_instance.reply(event, azure_disabled_text())
            return

        if monitor_active:
            monitor_active = False
            if monitor_task is not None:
                monitor_task.cancel()
                await asyncio.gather(monitor_task, return_exceptions=True)
                monitor_task = None
            monitor_target = None
            await bot_instance.reply(
                event,
                "守护模式已关闭。\n"
                "之后不会再每 5 分钟自动检查服务器状态，也不会自动开机。",
            )
            return

        monitor_active = True
        monitor_target = clone_message_target(event)
        monitor_task = bot_instance.create_background_task(
            monitor_loop(bot_instance),
            name="azure-vm-autostart-monitor",
        )
        await bot_instance.reply(
            event,
            "守护模式已开启。\n"
            "我会先立即检查一次服务器状态，之后每 5 分钟再检查一次。\n"
            "如果发现服务器未启动，就会自动发送开机命令。\n"
            "再次发送 /autostart 可以关闭这个模式。",
        )


async def run() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    settings = load_settings()
    bot = Bot(settings=settings, client=MockConsoleClient())
    register_commands(bot)
    await bot.start()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
