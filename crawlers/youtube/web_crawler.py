import asyncio
import os
import re
import subprocess
import tempfile

import yaml

from crawlers.utils.logger import logger

# 配置文件路径
path = os.path.abspath(os.path.dirname(__file__))

# 读取配置文件
with open(f"{path}/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class YouTubeWebCrawler:

    # 从配置文件读取 YouTube 请求头
    async def get_youtube_headers(self):
        yt_config = config['TokenManager']['youtube']
        kwargs = {
            "headers": {
                "user-agent": yt_config["headers"]["user-agent"],
                "cookie": yt_config["headers"]["cookie"],
            },
            "proxies": {"http://": yt_config["proxies"]["http"], "https://": yt_config["proxies"]["https"]},
        }
        return kwargs

    def extract_video_id(self, url: str) -> str:
        """从各种 YouTube URL 格式中提取 video ID"""
        patterns = [
            r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:youtube\.com/(?:watch\?.*v=|shorts/|embed/|live/))([a-zA-Z0-9_-]{11})',
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        raise ValueError(f"Cannot extract video ID from URL: {url}")

    async def fetch_transcript(self, video_id: str) -> str | None:
        """获取字幕文本。先试 youtube-transcript-api，失败则用 yt-dlp --write-subs"""
        # 策略 A: youtube-transcript-api（免认证，但可能被 IP ban）
        text = await self._fetch_transcript_api(video_id)
        if text:
            return text
        # 策略 B: yt-dlp --write-subs（需要 cookies）
        text = await self._fetch_transcript_ytdlp(video_id)
        return text

    async def _fetch_transcript_api(self, video_id: str) -> str | None:
        """用 youtube-transcript-api 获取字幕"""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            ytt_api = YouTubeTranscriptApi()
            transcript = ytt_api.fetch(video_id, languages=['zh-Hans', 'zh', 'en', 'zh-Hant'])
            text = " ".join(snippet.text for snippet in transcript)
            if text.strip():
                logger.info(f"YouTube 字幕获取成功 (transcript-api): {video_id}, 长度: {len(text)}")
                return text
            return None
        except Exception as e:
            logger.warning(f"youtube-transcript-api 失败 ({video_id}): {type(e).__name__}")
            return None

    async def _fetch_transcript_ytdlp(self, video_id: str) -> str | None:
        """用 yt-dlp --write-subs 获取字幕"""
        cookie_path = self._get_cookie_file_path()
        if not cookie_path:
            logger.warning(f"yt-dlp 字幕获取跳过 ({video_id}): 无 cookies")
            return None

        import glob
        import json
        work_dir = tempfile.mkdtemp(prefix="yt_subs_")
        cmd = [
            "yt-dlp",
            "--cookies", cookie_path,
            "--write-subs", "--write-auto-subs",
            "--sub-langs", "zh-Hans,zh,en,zh-Hant",
            "--skip-download",
            "--no-warnings",
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "-o", os.path.join(work_dir, "%(id)s"),
            f"https://www.youtube.com/watch?v={video_id}",
        ]

        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd,
                capture_output=True, text=True, timeout=120
            )
            # 即使 returncode != 0，字幕文件可能已下载成功（format 错误不影响字幕）
            if result.returncode != 0:
                logger.warning(f"yt-dlp --write-subs 退出码 {result.returncode} ({video_id}): {result.stderr[:200]}")

            # 查找下载的字幕文件
            sub_files = glob.glob(os.path.join(work_dir, f"{video_id}.*"))
            if not sub_files:
                logger.warning(f"yt-dlp 未下载到字幕文件 ({video_id})")
                return None

            # 优先选择 json3，其次 vtt
            sub_files.sort(key=lambda f: (0 if f.endswith('.json3') else 1))
            sub_file = sub_files[0]
            content = open(sub_file, 'r', encoding='utf-8', errors='replace').read()

            if sub_file.endswith('.json3'):
                data = json.loads(content)
                segments = data.get("events", [])
                texts = []
                for seg in segments:
                    for s in seg.get("segs", []):
                        t = s.get("utf8", "").strip()
                        if t and t != "\n":
                            texts.append(t)
                text = " ".join(texts)
            else:
                # VTT 格式：去掉时间戳行
                lines = content.splitlines()
                text_lines = []
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
                        continue
                    if re.match(r'^[\d:.,\-\s>]+$', line) or re.match(r'^\d+$', line):
                        continue
                    line = re.sub(r'<[^>]+>', '', line)
                    if line:
                        text_lines.append(line)
                # 去重连续重复行（自动字幕常见）
                deduped = []
                for line in text_lines:
                    if not deduped or line != deduped[-1]:
                        deduped.append(line)
                text = " ".join(deduped)

            if text.strip():
                logger.info(f"YouTube 字幕获取成功 (yt-dlp): {video_id}, 长度: {len(text)}")
                return text
            return None
        except Exception as e:
            logger.error(f"yt-dlp 字幕获取异常 ({video_id}): {e}")
            return None

    async def fetch_video_info(self, video_id: str) -> dict:
        """用 yt-dlp --dump-json 获取视频元数据（标题、时长等）"""
        cookie_path = self._get_cookie_file_path()
        cmd = ["yt-dlp", "--dump-json", "--no-warnings", "--skip-download", "--js-runtimes", "node", "--remote-components", "ejs:github"]
        if cookie_path:
            cmd.extend(["--cookies", cookie_path])
        cmd.append(f"https://www.youtube.com/watch?v={video_id}")

        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd,
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                logger.warning(f"yt-dlp --dump-json 失败 ({video_id}): {result.stderr[:200]}")
        except Exception as e:
            logger.warning(f"yt-dlp --dump-json 异常 ({video_id}): {e}")
        return {}

    async def download_audio(self, video_id: str, output_dir: str) -> str | None:
        """用 yt-dlp 下载音频，返回文件路径"""
        cookie_path = self._get_cookie_file_path()
        output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
        cmd = [
            "yt-dlp",
            "-f", "ba",
            "-x", "--audio-format", "mp3",
            "--no-warnings",
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "-o", output_template,
        ]
        if cookie_path:
            cmd.extend(["--cookies", cookie_path])
        cmd.append(f"https://www.youtube.com/watch?v={video_id}")

        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd,
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                logger.error(f"yt-dlp 音频下载失败 ({video_id}): {result.stderr[:300]}")
                return None

            # 查找生成的文件
            for f in os.listdir(output_dir):
                if f.startswith(video_id):
                    return os.path.join(output_dir, f)
            return None
        except Exception as e:
            logger.error(f"yt-dlp 音频下载异常 ({video_id}): {e}")
            return None

    async def update_cookie(self, cookie: str):
        """更新 YouTube cookies。支持两种格式：
        - Netscape cookies.txt（以 '# Netscape' 开头）→ 直接写入文件
        - 扁平字符串 'key=value; key=value' → 写入 config.yaml（向后兼容）
        """
        cookies_dir = os.path.join(path, "cookies")
        os.makedirs(cookies_dir, exist_ok=True)
        cookie_file = os.path.join(cookies_dir, "youtube.txt")

        if cookie.startswith("# Netscape"):
            # 完整 Netscape 格式，直接写入
            with open(cookie_file, 'w', encoding='utf-8') as f:
                f.write(cookie)
            count = sum(1 for line in cookie.splitlines() if line and not line.startswith("#"))
            logger.info(f"YouTube cookies.txt 已更新 (Netscape): {count} 条 → {cookie_file}")
        else:
            # 扁平字符串，写入 config.yaml（向后兼容）
            global config
            config["TokenManager"]["youtube"]["headers"]["cookie"] = cookie
            config_path = f"{path}/config.yaml"
            with open(config_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, default_flow_style=False, allow_unicode=True, indent=2)
            logger.info(f"YouTube cookie 已更新 (config.yaml)")

    def _get_cookie_file_path(self) -> str | None:
        """获取 Netscape cookies.txt 路径（如果存在）"""
        cookie_file = os.path.join(path, "cookies", "youtube.txt")
        if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 50:
            return cookie_file
        return None
