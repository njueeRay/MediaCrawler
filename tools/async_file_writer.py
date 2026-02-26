# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/async_file_writer.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import csv
import io
import json
import os
import pathlib
from typing import Dict, List, Optional, Tuple
import aiofiles
import config
from tools.utils import utils
from var import source_keyword_var
from tools.words import AsyncWordCloudGenerator

class AsyncFileWriter:
    def __init__(self, platform: str, crawler_type: str):
        self.lock = asyncio.Lock()
        self.platform = platform
        self.crawler_type = crawler_type
        self.wordcloud_generator = AsyncWordCloudGenerator() if config.ENABLE_GET_WORDCLOUD else None

    def _get_file_path(self, file_type: str, item_type: str) -> str:
        base_path = f"data/{self.platform}/{file_type}"
        pathlib.Path(base_path).mkdir(parents=True, exist_ok=True)
        keyword = self._sanitize_filename_part(source_keyword_var.get(""))
        crawler_type = self._sanitize_filename_part(self.crawler_type)
        item_type = self._sanitize_filename_part(item_type)
        file_name = f"{utils.get_current_date()}_{keyword}_{crawler_type}_{item_type}.{file_type}"
        return f"{base_path}/{file_name}"

    @staticmethod
    def _sanitize_filename_part(value: str) -> str:
        if not value:
            return "all"
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            value = value.replace(char, "_")
        value = value.strip().replace(" ", "_")
        return value[:80] if value else "all"

    async def write_to_csv(self, item: Dict, item_type: str):
        file_path = self._get_file_path('csv', item_type)
        async with self.lock:
            file_exists = os.path.exists(file_path)
            async with aiofiles.open(file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=item.keys())
                if not file_exists or await f.tell() == 0:
                    await writer.writeheader()
                await writer.writerow(item)

    async def write_to_csv_with_dedup(
        self,
        item: Dict,
        item_type: str,
        dedup_key: Optional[str] = None,
        replace_on_dup: bool = False,
    ) -> None:
        """写入 CSV，并在指定 key 上做覆盖写（replace）。"""
        if not dedup_key or not replace_on_dup:
            await self.write_to_csv(item=item, item_type=item_type)
            return

        file_path = self._get_file_path('csv', item_type)

        async with self.lock:
            rows, fieldnames = await self._read_csv_rows(file_path)

            dedup_value = str(item.get(dedup_key, ""))
            replaced = False
            if dedup_value:
                for idx, row in enumerate(rows):
                    if str(row.get(dedup_key, "")) == dedup_value:
                        rows[idx] = item
                        replaced = True
                        break

            if not replaced:
                rows.append(item)

            fieldnames = self._merge_fieldnames(fieldnames, list(item.keys()))
            await self._write_csv_rows(file_path, rows, fieldnames)

    async def dedup_latest_csv(self, item_type: str, dedup_key: str) -> None:
        """对当前日期/关键词生成的 CSV 做一次去重覆盖（保留最新）。"""
        file_path = self._get_file_path('csv', item_type)
        await self._dedup_csv_file(file_path, dedup_key)

    async def _read_csv_rows(self, file_path: str) -> Tuple[List[Dict], List[str]]:
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return [], []

        async with aiofiles.open(file_path, 'r', encoding='utf-8-sig') as f:
            content = await f.read()
        if not content:
            return [], []

        buffer = io.StringIO(content)
        reader = csv.DictReader(buffer)
        rows = [row for row in reader]
        fieldnames = reader.fieldnames or []
        return rows, fieldnames

    async def _write_csv_rows(self, file_path: str, rows: List[Dict], fieldnames: List[str]) -> None:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        async with aiofiles.open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            await f.write(buffer.getvalue())

    @staticmethod
    def _merge_fieldnames(existing: List[str], incoming: List[str]) -> List[str]:
        merged = list(existing or [])
        for name in incoming:
            if name not in merged:
                merged.append(name)
        return merged

    async def _dedup_csv_file(self, file_path: str, dedup_key: str) -> None:
        if not dedup_key:
            return

        rows, fieldnames = await self._read_csv_rows(file_path)
        if not rows:
            return

        last_index: Dict[str, int] = {}
        for idx, row in enumerate(rows):
            last_index[str(row.get(dedup_key, ""))] = idx

        deduped = []
        for idx, row in enumerate(rows):
            if last_index.get(str(row.get(dedup_key, ""))) == idx:
                deduped.append(row)

        if len(deduped) == len(rows):
            return

        await self._write_csv_rows(file_path, deduped, fieldnames)

    async def write_single_item_to_json(self, item: Dict, item_type: str):
        file_path = self._get_file_path('json', item_type)
        async with self.lock:
            existing_data = []
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        content = await f.read()
                        if content:
                            existing_data = json.loads(content)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                    except json.JSONDecodeError:
                        existing_data = []

            existing_data.append(item)

            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(existing_data, ensure_ascii=False, indent=4))

    async def generate_wordcloud_from_comments(self):
        """
        Generate wordcloud from comments data
        Only works when ENABLE_GET_WORDCLOUD and ENABLE_GET_COMMENTS are True
        """
        if not config.ENABLE_GET_WORDCLOUD or not config.ENABLE_GET_COMMENTS:
            return

        if not self.wordcloud_generator:
            return

        try:
            # Read comments from JSON file
            comments_file_path = self._get_file_path('json', 'comments')
            if not os.path.exists(comments_file_path) or os.path.getsize(comments_file_path) == 0:
                utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] No comments file found at {comments_file_path}")
                return

            async with aiofiles.open(comments_file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                if not content:
                    utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Comments file is empty")
                    return

                comments_data = json.loads(content)
                if not isinstance(comments_data, list):
                    comments_data = [comments_data]

            # Filter comments data to only include 'content' field
            # Handle different comment data structures across platforms
            filtered_data = []
            for comment in comments_data:
                if isinstance(comment, dict):
                    # Try different possible content field names
                    content_text = comment.get('content') or comment.get('comment_text') or comment.get('text') or ''
                    if content_text:
                        filtered_data.append({'content': content_text})

            if not filtered_data:
                utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] No valid comment content found")
                return

            # Generate wordcloud
            words_base_path = f"data/{self.platform}/words"
            pathlib.Path(words_base_path).mkdir(parents=True, exist_ok=True)
            words_file_prefix = f"{words_base_path}/{self.crawler_type}_comments_{utils.get_current_date()}"

            utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Generating wordcloud from {len(filtered_data)} comments")
            await self.wordcloud_generator.generate_word_frequency_and_cloud(filtered_data, words_file_prefix)
            utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Wordcloud generated successfully at {words_file_prefix}")

        except Exception as e:
            utils.logger.error(f"[AsyncFileWriter.generate_wordcloud_from_comments] Error generating wordcloud: {e}")
