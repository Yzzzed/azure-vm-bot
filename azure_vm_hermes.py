#!/usr/bin/env python3
"""
Azure VM Controller for Hermes
支持手动命令和定时任务
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """加载 .env 文件"""
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
    """解析布尔值"""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AzureVMSettings:
    """Azure VM 配置"""
    enabled: bool = False
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    subscription_id: str = ""
    resource_group: str = ""
    vm_name: str = ""
    api_version: str = "2023-09-01"

    def missing_fields(self) -> list[str]:
        """检查缺失的配置项"""
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

    @classmethod
    def from_env(cls) -> AzureVMSettings:
        """从环境变量加载配置"""
        return cls(
            enabled=parse_bool(os.getenv("AZURE_VM_ENABLED"), False),
            tenant_id=os.getenv("AZURE_VM_TENANT_ID", "").strip(),
            client_id=os.getenv("AZURE_VM_CLIENT_ID", "").strip(),
            client_secret=os.getenv("AZURE_VM_CLIENT_SECRET", "").strip(),
            subscription_id=os.getenv("AZURE_VM_SUBSCRIPTION_ID", "").strip(),
            resource_group=os.getenv("AZURE_VM_RESOURCE_GROUP", "").strip(),
            vm_name=os.getenv("AZURE_VM_NAME", "").strip(),
            api_version=os.getenv("AZURE_VM_API_VERSION", "2023-09-01").strip(),
        )


class AzureVMController:
    """Azure VM 控制器"""

    def __init__(self, settings: AzureVMSettings) -> None:
        self.settings = settings
        self._access_token = ""
        self._token_expire_at = 0.0

    def target_label(self) -> str:
        """获取目标服务器标签"""
        parts = [self.settings.resource_group.strip(), self.settings.vm_name.strip()]
        return "/".join(part for part in parts if part) or "Azure VM"

    @staticmethod
    def humanize_status(code: str) -> str:
        """人性化状态描述"""
        mapping = {
            "PowerState/running": "✅ 正在运行",
            "PowerState/starting": "🔄 正在启动中",
            "PowerState/stopping": "🔄 正在关机中",
            "PowerState/stopped": "⛔ 已关机",
            "PowerState/deallocating": "🔄 正在释放资源",
            "PowerState/deallocated": "⛔ 已关机（资源已释放）",
        }
        return mapping.get(code, f"❓ {code}")

    def get_vm_status(self) -> tuple[bool, str, str]:
        """
        获取 VM 状态
        返回: (成功?, 状态码, 错误信息)
        """
        missing = self.settings.missing_fields()
        if missing:
            return False, "", f"缺少配置: {', '.join(missing)}"

        try:
            token = self._ensure_access_token()
            url = (
                "https://management.azure.com/subscriptions/"
                f"{self.settings.subscription_id}/resourceGroups/{self.settings.resource_group}/"
                "providers/Microsoft.Compute/virtualMachines/"
                f"{self.settings.vm_name}/instanceView?api-version={self.settings.api_version}"
            )
            body = self._get_json(url, {"Authorization": f"Bearer {token}"})
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

    def start_vm(self) -> tuple[bool, str]:
        """
        启动 VM
        返回: (成功?, 错误信息)
        """
        return self._post_action("start")

    def stop_vm(self) -> tuple[bool, str]:
        """
        关闭 VM
        返回: (成功?, 错误信息)
        """
        return self._post_action("powerOff")

    def _post_action(self, action: str) -> tuple[bool, str]:
        """执行 VM 操作"""
        missing = self.settings.missing_fields()
        if missing:
            return False, f"缺少配置: {', '.join(missing)}"

        try:
            token = self._ensure_access_token()
            url = (
                "https://management.azure.com/subscriptions/"
                f"{self.settings.subscription_id}/resourceGroups/{self.settings.resource_group}/"
                "providers/Microsoft.Compute/virtualMachines/"
                f"{self.settings.vm_name}/{action}?api-version={self.settings.api_version}"
            )
            status_code, _ = self._post_empty(url, {"Authorization": f"Bearer {token}"}, action)
        except Exception as exc:
            return False, str(exc)

        if status_code in {200, 202, 204}:
            return True, "操作成功"
        return False, f"HTTP {status_code}"

    def _ensure_access_token(self) -> str:
        """确保有有效的访问令牌"""
        now = time.time()
        if self._access_token and now < self._token_expire_at:
            return self._access_token

        token_url = f"https://login.microsoftonline.com/{self.settings.tenant_id}/oauth2/v2.0/token"
        status_code, body = self._post_form(
            token_url,
            {
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "grant_type": "client_credentials",
                "scope": "https://management.azure.com/.default",
            },
        )

        if status_code not in {200, 201}:
            raise RuntimeError(f"获取 Azure 令牌失败: HTTP {status_code}")

        token = str(body.get("access_token", "")).strip()
        expires_in = int(body.get("expires_in", 3600))
        if not token:
            raise RuntimeError("Azure 令牌响应缺少 access_token")

        self._access_token = token
        self._token_expire_at = time.time() + max(60, expires_in - 120)
        return token

    @staticmethod
    def _post_form(url: str, form: dict[str, str]) -> tuple[int, dict[str, object]]:
        """发送表单 POST 请求"""
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
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"连接失败: {exc}") from exc

        if not raw:
            return code, {}

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("响应不是有效的 JSON") from exc

        if isinstance(parsed, dict):
            return code, parsed
        raise RuntimeError("响应格式异常")

    @staticmethod
    def _post_empty(url: str, headers: dict[str, str], action: str) -> tuple[int, bytes]:
        """发送空 POST 请求"""
        req = urllib.request.Request(url=url, data=b"", headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return int(response.getcode() or 0), response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"连接失败: {exc}") from exc

    @staticmethod
    def _get_json(url: str, headers: dict[str, str]) -> dict[str, object]:
        """发送 GET 请求并解析 JSON"""
        req = urllib.request.Request(url=url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"连接失败: {exc}") from exc

        if not raw:
            return {}

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("响应不是有效的 JSON") from exc

        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError("响应格式异常")


def cmd_status() -> str:
    """查询 VM 状态"""
    settings = AzureVMSettings.from_env()

    if not settings.enabled:
        return "❌ Azure VM 控制功能未启用\n请在 .env.azure 中设置 AZURE_VM_ENABLED=true"

    controller = AzureVMController(settings)
    ok, code, detail = controller.get_vm_status()

    if not ok:
        return f"❌ 查询失败\n{detail}"

    return (
        f"📊 服务器状态\n"
        f"目标: {controller.target_label()}\n"
        f"状态: {controller.humanize_status(code)}"
    )


def cmd_start() -> str:
    """启动 VM"""
    settings = AzureVMSettings.from_env()

    if not settings.enabled:
        return "❌ Azure VM 控制功能未启用"

    controller = AzureVMController(settings)
    ok, detail = controller.start_vm()

    if not ok:
        return f"❌ 启动失败\n{detail}"

    return (
        f"✅ 已发送启动命令\n"
        f"目标: {controller.target_label()}\n"
        f"提示: 服务器需要一点时间启动，请稍后使用 /status 查看"
    )


def cmd_stop() -> str:
    """关闭 VM"""
    settings = AzureVMSettings.from_env()

    if not settings.enabled:
        return "❌ Azure VM 控制功能未启用"

    controller = AzureVMController(settings)
    ok, detail = controller.stop_vm()

    if not ok:
        return f"❌ 关机失败\n{detail}"

    return (
        f"✅ 已发送关机命令\n"
        f"目标: {controller.target_label()}\n"
        f"提示: 服务器需要一点时间关闭，请稍后使用 /status 确认"
    )


def cmd_autostart() -> str:
    """自动启动检查（用于定时任务）"""
    settings = AzureVMSettings.from_env()

    if not settings.enabled:
        return "❌ Azure VM 控制功能未启用"

    controller = AzureVMController(settings)

    # 检查状态
    ok, code, detail = controller.get_vm_status()
    if not ok:
        return f"⚠️ 守护检查失败\n{detail}"

    # 如果已经在运行，不需要操作
    if code in {"PowerState/running", "PowerState/starting"}:
        return f"✅ 守护检查: 服务器运行正常\n状态: {controller.humanize_status(code)}"

    # 尝试启动
    start_ok, start_detail = controller.start_vm()
    if start_ok:
        return (
            f"🔄 守护模式: 检测到服务器未启动，已自动发送开机命令\n"
            f"目标: {controller.target_label()}\n"
            f"之前状态: {controller.humanize_status(code)}"
        )

    return (
        f"❌ 守护模式: 检测到服务器未启动，但自动开机失败\n"
        f"目标: {controller.target_label()}\n"
        f"状态: {controller.humanize_status(code)}\n"
        f"失败原因: {start_detail}"
    )


def main() -> None:
    """主函数 - 用于命令行调用"""
    import sys

    # 加载环境变量
    env_file = Path(__file__).with_name(".env.azure")
    load_dotenv(env_file)

    if len(sys.argv) < 2:
        print("用法: python azure_vm_hermes.py <command>")
        print("可用命令:")
        print("  status     - 查询 VM 状态")
        print("  start      - 启动 VM")
        print("  stop       - 关闭 VM")
        print("  autostart  - 自动启动检查（守护模式）")
        sys.exit(1)

    command = sys.argv[1].lower()

    commands = {
        "status": cmd_status,
        "start": cmd_start,
        "stop": cmd_stop,
        "autostart": cmd_autostart,
    }

    if command not in commands:
        print(f"❌ 未知命令: {command}")
        print(f"可用命令: {', '.join(commands.keys())}")
        sys.exit(1)

    result = commands[command]()
    print(result)


if __name__ == "__main__":
    main()
