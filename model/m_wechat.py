# -*- coding: utf-8 -*-
# @Desc : 微信公众号数据模型

from typing import Optional

from pydantic import BaseModel, Field


class WeChatAccountInfo(BaseModel):
    """公众号账号信息"""
    fakeid: str = Field(description="公众号唯一标识")
    nickname: str = Field(default="", description="公众号名称")
    alias: str = Field(default="", description="微信号")
    round_head_img: str = Field(default="", description="头像 URL")
    service_type: int = Field(default=0, description="服务类型")
    signature: str = Field(default="", description="简介/签名")
    verify_status: int = Field(default=0, description="认证状态")


class WeChatArticleInfo(BaseModel):
    """公众号文章信息"""
    aid: str = Field(default="", description="文章ID")
    title: str = Field(default="", description="文章标题")
    cover: str = Field(default="", description="封面图 URL")
    link: str = Field(default="", description="文章链接")
    digest: str = Field(default="", description="摘要")
    update_time: int = Field(default=0, description="更新时间戳")
    create_time: int = Field(default=0, description="创建时间戳")
    author_name: str = Field(default="", description="作者名")
    appmsgid: int = Field(default=0, description="消息ID")
    itemidx: int = Field(default=1, description="消息中的位置索引")
    copyright_type: int = Field(default=0, description="版权类型")
    is_deleted: bool = Field(default=False, description="是否已删除")


class WeChatAuthorInfo(BaseModel):
    """公众号主体信息（authorinfo 接口）"""
    identity_name: str = Field(default="", description="主体名称")
    is_verify: int = Field(default=0, description="认证状态")
    original_article_count: int = Field(default=0, description="原创文章数")


class WeChatAboutBizInfo(BaseModel):
    """公众号详细信息（aboutbiz 接口）"""
    intro: str = Field(default="", description="公众号简介")
    wechat: str = Field(default="", description="微信号")
    type: str = Field(default="", description="账号类型")
    org: str = Field(default="", description="主体名称")
    ip_wording: Optional[dict] = Field(default=None, description="IP 属地信息")


class WeChatCreatorInfo(BaseModel):
    """创作者完整信息（聚合 account + authorinfo + aboutbiz）"""
    fakeid: str = Field(description="公众号唯一标识")
    nickname: str = Field(default="", description="公众号名称")
    alias: str = Field(default="", description="微信号")
    round_head_img: str = Field(default="", description="头像 URL")
    signature: str = Field(default="", description="简介/签名")
    service_type: int = Field(default=0, description="服务类型")
    verify_status: int = Field(default=0, description="认证状态")
    # authorinfo
    identity_name: str = Field(default="", description="主体名称")
    original_article_count: int = Field(default=0, description="原创文章数")
    # aboutbiz
    intro: str = Field(default="", description="公众号简介")
    org: str = Field(default="", description="认证主体")
    account_type: str = Field(default="", description="账号类型")
    ip_location: str = Field(default="", description="IP 属地")
