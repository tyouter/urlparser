"""
依赖安装器

自动检查并安装缺失的依赖，避免重复安装
"""

import subprocess
import os
import sys
import importlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class DependencyType(Enum):
    """依赖类型"""
    PYTHON_PACKAGE = "python_package"
    EXTERNAL_TOOL = "external_tool"


@dataclass
class Dependency:
    """依赖定义"""
    name: str                          # 依赖名称
    type: DependencyType               # 依赖类型
    pip_name: Optional[str] = None     # pip 安装名称（Python包）
    description: str = ""              # 描述
    extra_deps: Optional[List[str]] = None  # 附加依赖


# 预定义的依赖列表
DEPENDENCIES = {
    # 核心依赖
    "yt-dlp": Dependency(
        name="yt-dlp",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="yt-dlp",
        description="视频下载工具",
    ),
    "playwright": Dependency(
        name="playwright",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="playwright",
        description="浏览器自动化",
        extra_deps=["playwright install"],  # 需要额外运行 playwright install
    ),

    # 转录依赖
    "ffmpeg": Dependency(
        name="ffmpeg",
        type=DependencyType.EXTERNAL_TOOL,
        description="音视频处理工具",
    ),
    "funasr": Dependency(
        name="funasr",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="funasr",
        description="阿里 FunASR 中文转录引擎",
        extra_deps=["modelscope"],  # 需要附加安装
    ),
    "faster-whisper": Dependency(
        name="faster-whisper",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="faster-whisper",
        description="高效 Whisper 转录引擎",
    ),

    # 理解依赖
    "openvino": Dependency(
        name="openvino",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="openvino",
        description="Intel OpenVINO 推理引擎",
    ),
    "openvino_genai": Dependency(
        name="openvino_genai",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="openvino-genai",
        description="OpenVINO 生成式 AI 扩展",
    ),
    "llama_cpp": Dependency(
        name="llama_cpp",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="llama-cpp-python",
        description="llama.cpp Python 绑定",
    ),
    "PIL": Dependency(
        name="PIL",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="pillow",
        description="图像处理库",
    ),
    "psutil": Dependency(
        name="psutil",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="psutil",
        description="系统进程/资源监控",
    ),

    # 可选依赖
    "browser-use": Dependency(
        name="browser-use",
        type=DependencyType.PYTHON_PACKAGE,
        pip_name="browser-use",
        description="智能浏览器操作",
    ),
}


def is_package_installed(package_name: str) -> Tuple[bool, Optional[str]]:
    """
    检查 Python 包是否已安装

    Args:
        package_name: 包名称

    Returns:
        (是否已安装, 版本号)
    """
    try:
        # 尝试导入
        importlib.import_module(package_name.replace("-", "_"))
        # 获取版本
        try:
            import importlib.metadata as metadata
            version = metadata.version(package_name)
        except Exception:
            version = None
        return True, version
    except ImportError:
        return False, None


def is_ffmpeg_installed() -> Tuple[bool, Optional[str]]:
    """
    检查 ffmpeg 是否已安装

    Returns:
        (是否已安装, 版本号)
    """
    try:
        from .utils.ffmpeg_utils import find_ffmpeg, find_ffprobe

        ffmpeg_cmd = find_ffmpeg()
        ffprobe_cmd = find_ffprobe()

        # 检查 ffmpeg
        result = subprocess.run(
            [ffmpeg_cmd, '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, None

        # 检查 ffprobe
        result2 = subprocess.run(
            [ffprobe_cmd, '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result2.returncode != 0:
            return False, None

        # 提取版本号
        version_line = result.stdout.split('\n')[0]
        if 'version' in version_line:
            parts = version_line.split()
            for i, p in enumerate(parts):
                if p == 'version' and i + 1 < len(parts):
                    return True, parts[i + 1]

        return True, None

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False, None


def install_pip_package(package_name: str, extra_packages: Optional[List[str]] = None) -> bool:
    """
    使用 pip 安装 Python 包

    Args:
        package_name: 包名称
        extra_packages: 附加包列表

    Returns:
        是否成功
    """
    packages = [package_name]
    if extra_packages:
        packages.extend(extra_packages)

    logger.info("正在安装: %s", ', '.join(packages))

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", *packages, "--quiet"],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        if result.returncode == 0:
            logger.info("安装成功: %s", package_name)
            return True
        else:
            logger.error("安装失败: %s", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("安装超时: %s", package_name)
        return False
    except Exception as e:
        logger.error("安装异常: %s", e)
        return False


def run_post_install_command(command: str) -> bool:
    """
    运行安装后命令

    Args:
        command: 命令字符串

    Returns:
        是否成功
    """
    logger.info("正在执行: %s", command)
    try:
        parts = command.split()
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            logger.info("执行成功: %s", command)
            return True
        else:
            logger.error("执行失败: %s", result.stderr)
            return False
    except Exception as e:
        logger.error("执行异常: %s", e)
        return False


def install_ffmpeg_imageio() -> bool:
    """
    使用 imageio-ffmpeg 安装 ffmpeg（仅适用于简单场景）

    Returns:
        是否成功
    """
    try:
        # 先安装 imageio-ffmpeg
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "--quiet"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            return False

        # 获取 ffmpeg 路径
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

        logger.info("ffmpeg 已通过 imageio-ffmpeg 安装: %s", ffmpeg_path)

        # 在 Windows 下，复制到 C:/ffmpeg/bin 以便项目使用
        if os.name == 'nt':
            target_dir = Path('C:/ffmpeg/bin')
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)

            target_ffmpeg = target_dir / 'ffmpeg.exe'
            target_ffprobe = target_dir / 'ffprobe.exe'

            # 复制 ffmpeg
            import shutil
            shutil.copy2(ffmpeg_path, target_ffmpeg)

            # imageio-ffmpeg 不包含 ffprobe，需要单独下载
            logger.info("ffmpeg 已复制到: %s", target_ffmpeg)
            logger.warning("注意: imageio-ffmpeg 不包含 ffprobe，部分功能可能受限")

        return True
    except Exception as e:
        logger.error("imageio-ffmpeg 安装失败: %s", e)
        return False


def ensure_dependency(name: str, auto_install: bool = True) -> Tuple[bool, Optional[str]]:
    """
    确保依赖已安装，如果未安装则自动安装

    Args:
        name: 依赖名称
        auto_install: 是否自动安装

    Returns:
        (是否已安装/安装成功, 版本号)
    """
    dep = DEPENDENCIES.get(name)
    if not dep:
        raise ValueError(f"未知的依赖: {name}")

    # 检查是否已安装
    if dep.type == DependencyType.PYTHON_PACKAGE:
        installed, version = is_package_installed(name)
    elif dep.type == DependencyType.EXTERNAL_TOOL:
        if name == "ffmpeg":
            installed, version = is_ffmpeg_installed()
        else:
            installed, version = False, None
    else:
        installed, version = False, None

    if installed:
        logger.info("[OK] %s 已安装 (v%s)", name, version or '未知')
        return True, version

    # 未安装
    if not auto_install:
        logger.warning("[MISSING] %s 未安装", name)
        return False, None

    logger.info("[INSTALL] %s 未安装，正在安装...", name)

    # 安装
    if dep.type == DependencyType.PYTHON_PACKAGE:
        # 处理附加依赖
        extra_packages = None
        if dep.extra_deps:
            # 过滤出 pip 包（非命令，不含空格）
            extra_packages = [p for p in dep.extra_deps if " " not in p]

        success = install_pip_package(dep.pip_name or name, extra_packages)

        if success and dep.extra_deps:
            # 运行安装后命令
            for extra in dep.extra_deps:
                if " " in extra:  # 是命令而非包名
                    run_post_install_command(extra)

        if success:
            # 再次检查版本
            _, version = is_package_installed(name)
            return True, version
        return False, None

    elif dep.type == DependencyType.EXTERNAL_TOOL and name == "ffmpeg":
        # ffmpeg 需要特殊处理
        logger.info("ffmpeg 是外部工具，正在尝试通过 imageio-ffmpeg 安装...")
        success = install_ffmpeg_imageio()
        if success:
            return True, "imageio-ffmpeg"
        return False, None

    return False, None


def ensure_all_dependencies(
    categories: Optional[List[str]] = None,
    auto_install: bool = True
) -> dict:
    """
    确保所有依赖已安装

    Args:
        categories: 依赖分类，可选 ['core', 'transcribe', 'browser']
        auto_install: 是否自动安装

    Returns:
        安装结果字典
    """
    # 分类映射
    category_deps = {
        'core': ['yt-dlp', 'playwright'],
        'transcribe': ['ffmpeg', 'funasr', 'faster-whisper'],
        'browser': ['browser-use'],
    }

    # 确定要检查的依赖
    if categories:
        deps_to_check = []
        for cat in categories:
            deps_to_check.extend(category_deps.get(cat, []))
    else:
        deps_to_check = list(DEPENDENCIES.keys())

    results = {}
    for name in deps_to_check:
        installed, version = ensure_dependency(name, auto_install)
        results[name] = {
            'installed': installed,
            'version': version,
        }

    return results


def ensure_transcribe_dependencies(auto_install: bool = True) -> bool:
    """
    确保转录依赖已安装（唯一入口）

    策略:
    1. ffmpeg（必须）
    2. FunASR（首选，中英文均优先）→ 安装失败才尝试 Whisper
    3. faster-whisper（备选）→ FunASR 不可用时使用

    Args:
        auto_install: 是否自动安装

    Returns:
        是否所有必要依赖都已安装
    """
    logger.info("\n检查转录依赖...")

    ffmpeg_ok, _ = ensure_dependency("ffmpeg", auto_install)

    funasr_ok, _ = ensure_dependency("funasr", auto_install)

    if funasr_ok:
        if ffmpeg_ok:
            logger.info("转录依赖检查完成: ffmpeg + FunASR")
            return True
        else:
            logger.warning("转录依赖检查完成: FunASR 可用但 ffmpeg 缺失")
            return False

    whisper_ok, _ = ensure_dependency("faster-whisper", auto_install)

    if whisper_ok:
        if ffmpeg_ok:
            logger.info("转录依赖检查完成: ffmpeg + Whisper (FunASR 不可用)")
            return True
        else:
            logger.warning("转录依赖检查完成: Whisper 可用但 ffmpeg 缺失")
            return False

    logger.warning("转录依赖检查完成: 无可用引擎 (FunASR 和 Whisper 均安装失败)")
    return False


def ensure_core_dependencies(auto_install: bool = True) -> bool:
    """
    确保核心依赖已安装

    Args:
        auto_install: 是否自动安装

    Returns:
        是否所有核心依赖都已安装
    """
    logger.info("\n检查核心依赖...")

    results = ensure_all_dependencies(categories=['core'], auto_install=auto_install)

    all_ok = all(r['installed'] for r in results.values())

    if all_ok:
        logger.info("核心依赖检查完成")
    else:
        logger.warning("核心依赖检查完成，部分依赖缺失")

    return all_ok


def ensure_comprehension_dependencies(auto_install: bool = True) -> bool:
    """
    确保视频理解依赖已安装

    Args:
        auto_install: 是否自动安装

    Returns:
        是否所有必要依赖都已安装
    """
    logger.info("\n检查视频理解依赖...")

    deps = ["psutil", "PIL", "openvino", "openvino_genai", "llama_cpp"]
    results = {}

    for name in deps:
        installed, version = ensure_dependency(name, auto_install)
        results[name] = installed

    # 至少需要 openvino 或 llama_cpp 之一
    has_engine = results.get("openvino", False) or results.get("llama_cpp", False)

    all_ok = results.get("psutil", False) and results.get("PIL", False) and has_engine

    if all_ok:
        logger.info("视频理解依赖检查完成，功能可用")
    else:
        logger.warning("视频理解依赖检查完成，部分依赖缺失")
        if not results.get("psutil", False):
            logger.warning("  - psutil 缺失")
        if not results.get("PIL", False):
            logger.warning("  - Pillow 缺失")
        if not has_engine:
            logger.warning("  - 推理引擎缺失 (openvino 或 llama-cpp-python)")

    return all_ok


# CLI 命令
def cmd_install_deps(args):
    """CLI 命令: 安装依赖"""
    if args.transcribe:
        ensure_transcribe_dependencies(auto_install=True)
    elif args.core:
        ensure_core_dependencies(auto_install=True)
    else:
        ensure_all_dependencies(auto_install=True)


if __name__ == '__main__':
    # 独立运行时安装所有依赖
    print("=" * 60)
    print("依赖安装器")
    print("=" * 60)

    ensure_all_dependencies()