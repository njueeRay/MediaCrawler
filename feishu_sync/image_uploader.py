"""
飞书图片上传器（官方SDK）
"""

import io
import json
import mimetypes
import os
import urllib.request
from typing import Optional
import lark_oapi as lark
from lark_oapi.api.drive.v1 import UploadAllMediaRequest, UploadAllMediaRequestBody


class FeishuImageUploader:
    def __init__(self, client: lark.Client, app_token: str, parent_type: Optional[str] = None):
        self.client = client
        self.app_token = app_token
        self.parent_type = parent_type

    @staticmethod
    def _infer_parent_type(mime_type: Optional[str]) -> str:
        if mime_type and mime_type.startswith("image/"):
            return "bitable_image"
        return "bitable_file"

    def upload_image(self, file_path: str) -> Optional[str]:
        if not os.path.isfile(file_path):
            return None

        if not self.app_token:
            raise ValueError("app_token 不能为空，无法上传图片")

        file_name = os.path.basename(file_path)
        size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        parent_type = self.parent_type or self._infer_parent_type(mime_type)
        extra = json.dumps({"drive_route_token": self.app_token}, ensure_ascii=False)

        with open(file_path, "rb") as file_obj:
            request = UploadAllMediaRequest.builder() \
                .request_body(
                    UploadAllMediaRequestBody.builder()
                    .file_name(file_name)
                    .parent_type(parent_type)
                    .parent_node(self.app_token)
                    .size(size)
                    .extra(extra)
                    .file(file_obj)
                    .build()
                ) \
                .build()

            response = self.client.drive.v1.media.upload_all(request)

        if not response.success():
            raise Exception(f"上传图片失败: {response.code} {response.msg}")

        return response.data.file_token

    def upload_image_from_url(self, url: str, file_name: Optional[str] = None) -> Optional[str]:
        """从 URL 下载图片后上传到飞书，返回 file_token。"""
        if not url or not url.startswith("http"):
            return None
        if not self.app_token:
            raise ValueError("app_token 不能为空，无法上传图片")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "")
        except Exception as exc:
            raise Exception(f"图片下载失败: {url} - {exc}") from exc

        if not file_name:
            path_part = url.split("?")[0].rstrip("/")
            file_name = path_part.split("/")[-1] or "image.jpg"
            if "." not in file_name:
                file_name += ".jpg"

        mime_type = content_type.split(";")[0].strip() or mimetypes.guess_type(file_name)[0] or "image/jpeg"
        parent_type = self.parent_type or self._infer_parent_type(mime_type)
        extra = json.dumps({"drive_route_token": self.app_token}, ensure_ascii=False)
        size = len(data)

        file_obj = io.BytesIO(data)
        request = UploadAllMediaRequest.builder() \
            .request_body(
                UploadAllMediaRequestBody.builder()
                .file_name(file_name)
                .parent_type(parent_type)
                .parent_node(self.app_token)
                .size(size)
                .extra(extra)
                .file(file_obj)
                .build()
            ) \
            .build()

        response = self.client.drive.v1.media.upload_all(request)
        if not response.success():
            raise Exception(f"上传图片失败: {response.code} {response.msg}")

        return response.data.file_token
