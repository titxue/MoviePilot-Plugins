from typing import List, Optional

from pydantic import BaseModel, Field


class SeedHubConfig(BaseModel):
    enabled: bool = False
    proxy: bool = False
    notify: bool = False
    onlyonce: bool = False
    search_limit: int = 10
    quark_limit: int = 5
    timeout: int = 30
    show_magnet: bool = True
    show_non_quark_links: bool = True


class SeedHubSearchItem(BaseModel):
    id: str
    title: str
    info: str = ""
    rating: str = "?"
    url: str


class SeedHubLinkItem(BaseModel):
    path: Optional[str] = None
    desc: str = ""
    url: Optional[str] = None


class SeedHubSearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    limit: Optional[int] = Field(default=None, ge=1, le=50)


class SeedHubLinksRequest(BaseModel):
    movie_id: str = Field(..., min_length=1)
    quark_limit: Optional[int] = Field(default=None, ge=1, le=50)


class SeedHubLinksResult(BaseModel):
    title: str = "未知标题"
    quark: List[SeedHubLinkItem] = Field(default_factory=list)
    quark_resolved: List[SeedHubLinkItem] = Field(default_factory=list)
    baidu: List[SeedHubLinkItem] = Field(default_factory=list)
    aliyun: List[SeedHubLinkItem] = Field(default_factory=list)
    uc: List[SeedHubLinkItem] = Field(default_factory=list)
    xunlei: List[SeedHubLinkItem] = Field(default_factory=list)
    magnet: List[str] = Field(default_factory=list)
    thunder: List[str] = Field(default_factory=list)
    ed2k: List[str] = Field(default_factory=list)
