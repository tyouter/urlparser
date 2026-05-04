"""
图片下载器

从 Markdown 中提取图片 URL，下载到本地或转换为 Base64
"""

import re
import base64
import hashlib
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from urllib.parse import urlparse, unquote
import requests
from PIL import Image
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

# Markdown 图片匹配模式：![alt](url)
IMG_PATTERN = re.compile(r'!\[([^\]]*)\]\((https?://[^\)]+)\)')


class ImageDownloader:
    """图片下载器"""

    def __init__(self, config: Optional['ImageDownloadConfig'] = None):
        from .config import ImageDownloadConfig
        self.config = config or ImageDownloadConfig()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.user_agent,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        })
        self.downloaded_images: List[Dict] = []

    def process_markdown(
        self, 
        markdown: str, 
        output_dir: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Tuple[str, List[Dict]]:
        """
        处理 Markdown，下载图片并替换路径

        Args:
            markdown: 原始 Markdown 内容
            output_dir: 图片保存目录
            base_url: 用于转换相对链接的基准 URL

        Returns:
            (处理后的 Markdown, 下载信息列表)
        """
        self.downloaded_images = []
        result_markdown = markdown

        if not self.config.enabled:
            return result_markdown, []

        # 确定输出目录
        if output_dir:
            save_dir = Path(output_dir)
        elif self.config.image_dir:
            save_dir = Path(self.config.image_dir)
        else:
            save_dir = Path("images")
        
        if self.config.mode == "local":
            save_dir.mkdir(parents=True, exist_ok=True)

        # 查找所有图片
        matches = list(IMG_PATTERN.finditer(markdown))
        logger.info(f"找到 {len(matches)} 张图片")

        # 反向替换，避免位置偏移问题
        for match in reversed(matches):
            alt_text = match.group(1) or ""
            img_url = match.group(2)

            # 处理 URL
            img_url = self._normalize_url(img_url, base_url)
            
            # 下载或转换
            replacement = self._process_image(img_url, alt_text, save_dir)
            
            if replacement:
                result_markdown = (
                    result_markdown[:match.start()] + 
                    replacement + 
                    result_markdown[match.end():]
                )

        return result_markdown, self.downloaded_images

    def _normalize_url(self, url: str, base_url: Optional[str]) -> str:
        """规范化 URL，处理相对路径"""
        if url.startswith("http"):
            return url
        
        # 尝试从 base_url 构建绝对 URL
        if base_url:
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        
        return url

    def _process_image(self, url: str, alt: str, save_dir: Path) -> Optional[str]:
        """处理单张图片"""
        try:
            # 下载图片
            img_data = self._download_image(url)
            if not img_data:
                return None

            # 处理图片
            if self.config.mode == "local":
                return self._save_as_local(url, alt, img_data, save_dir)
            elif self.config.mode == "base64":
                return self._convert_to_base64(url, alt, img_data)
            else:
                return None

        except Exception as e:
            logger.error(f"处理图片失败 {url}: {e}")
            return None

    def _download_image(self, url: str) -> Optional[bytes]:
        """下载图片"""
        try:
            response = self.session.get(url, timeout=self.config.timeout, stream=True)
            response.raise_for_status()
            
            # 检查大小
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > self.config.max_size:
                    logger.warning(f"图片过大 {size_mb:.1f}MB > {self.config.max_size}MB: {url}")
                    return None
            
            return response.content
        except Exception as e:
            logger.error(f"下载失败 {url}: {e}")
            return None

    def _save_as_local(self, url: str, alt: str, img_data: bytes, save_dir: Path) -> Optional[str]:
        """保存为本地文件"""
        # 生成文件名
        filename = self._generate_filename(url)
        filepath = save_dir / filename
        
        try:
            # 保存文件
            with open(filepath, "wb") as f:
                f.write(img_data)
            
            # 构建 Markdown 路径
            relative_path = self.config.image_prefix + filename
            img_tag = f"![{alt}]({relative_path})"
            
            # 记录下载信息
            self.downloaded_images.append({
                'url': url,
                'alt': alt,
                'local_path': str(filepath),
                'success': True,
            })
            
            logger.info(f"图片已保存: {filepath}")
            return img_tag
            
        except Exception as e:
            logger.error(f"保存图片失败 {url}: {e}")
            return None

    def _convert_to_base64(self, url: str, alt: str, img_data: bytes) -> Optional[str]:
        """转换为 Base64"""
        try:
            # 检测 MIME 类型
            img = Image.open(BytesIO(img_data))
            mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"
            img.close()
            
            # 编码为 Base64
            b64_data = base64.b64encode(img_data).decode('utf-8')
            img_tag = f"![{alt}](data:{mime_type};base64,{b64_data})"
            
            self.downloaded_images.append({
                'url': url,
                'alt': alt,
                'mode': 'base64',
                'success': True,
            })
            
            logger.info(f"图片已转换为 Base64: {url}")
            return img_tag
            
        except Exception as e:
            logger.error(f"Base64 转换失败 {url}: {e}")
            return None

    def _generate_filename(self, url: str) -> str:
        """生成文件名，避免冲突"""
        # 提取原始文件名
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path)
            original_name = Path(path).name or "image"
            
            # 提取扩展名
            ext = Path(original_name).suffix or ".jpg"
            stem = Path(original_name).stem
            
            # 截断过长的文件名
            stem = stem[:100]
            
            # 生成短哈希避免冲突
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
            
            return f"{stem}_{url_hash}{ext}"
        except Exception:
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
            return f"image_{url_hash}.jpg"

    def cleanup(self):
        """清理资源"""
        self.session.close()
