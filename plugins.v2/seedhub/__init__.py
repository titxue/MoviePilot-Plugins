from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.types import EventType
from fastapi import Body

from .models import SeedHubConfig, SeedHubLinksRequest, SeedHubSearchRequest
from .services import SeedHubService


class SeedHub(_PluginBase):
    # 插件名称
    plugin_name = "SeedHub 搜索"
    # 插件描述
    plugin_desc = "搜索 SeedHub 影视资源并提取夸克等下载链接。"
    # 插件图标
    plugin_icon = "search.png"
    # 插件版本
    plugin_version = "1.2.6"
    # 插件作者
    plugin_author = "Claude"
    # 作者主页
    author_url = "https://github.com/anthropics/claude-code"
    # 插件配置项ID前缀
    plugin_config_prefix = "seedhub_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    _config: SeedHubConfig = SeedHubConfig()
    _service: SeedHubService | None = None
    _scheduler: BackgroundScheduler | None = None

    def init_plugin(self, config: dict = None):
        self.stop_service()
        if config:
            self._config = SeedHubConfig.model_validate(config)
        else:
            self._config = SeedHubConfig()

        self._update_config()
        self._service = SeedHubService(self._config)

        if self._config.onlyonce and self._config.enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(
                self._run_once,
                "date",
                run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
            )
            self._config.onlyonce = False
            self._update_config()
            if self._scheduler.get_jobs():
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._config.enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/seedhub_search",
                "event": EventType.PluginAction,
                "desc": "搜索 SeedHub 资源",
                "category": "工具",
                "data": {"action": "seedhub_search"},
            },
            {
                "cmd": "/seedhub_links",
                "event": EventType.PluginAction,
                "desc": "获取 SeedHub 链接",
                "category": "工具",
                "data": {"action": "seedhub_links"},
            },
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "summary": "获取 SeedHub 插件状态",
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["POST"],
                "summary": "搜索 SeedHub 资源",
            },
            {
                "path": "/links",
                "endpoint": self.api_links,
                "methods": ["POST"],
                "summary": "获取 SeedHub 下载链接",
            },
            {
                "path": "/clear_history",
                "endpoint": self.api_clear_history,
                "methods": ["POST"],
                "summary": "清除 SeedHub 查询历史",
            },
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "enabled", "label": "启用插件"}
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "proxy", "label": "使用代理服务器"}
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "notify", "label": "发送通知"}
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "onlyonce", "label": "立即测试一次"}
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {"model": "search_limit", "label": "默认搜索结果数", "type": "number"}
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {"model": "quark_limit", "label": "默认夸克解析数", "type": "number"}
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VTextField",
                                    "props": {"model": "timeout", "label": "请求超时（秒）", "type": "number"}
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "show_magnet", "label": "显示磁力链接"}
                                }],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{
                                    "component": "VSwitch",
                                    "props": {"model": "show_non_quark_links", "label": "显示非夸克链接信息"}
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{
                                    "component": "VAlert",
                                    "props": {
                                        "type": "info",
                                        "variant": "tonal",
                                        "text": "本插件适合作为 MoviePilot V2 的外部补源工具，支持搜索 SeedHub 资源并查看夸克等下载链接。"
                                    }
                                }],
                            }
                        ],
                    },
                ],
            }
        ], self._config.model_dump()

    def get_page(self) -> List[dict]:
        history = self.get_data("history") or []

        # 统计数据
        total_count = len(history)
        search_count = sum(1 for item in history if item.get("action") == "search")
        links_count = sum(1 for item in history if item.get("action") == "links")
        latest_time = history[-1].get("time", "") if history else ""

        page_content = []

        # 统计卡片行
        page_content.append({
            "component": "VRow",
            "props": {"class": "mb-4"},
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 3},
                    "content": [{
                        "component": "VCard",
                        "props": {"class": "text-center pa-3"},
                        "content": [
                            {"component": "div", "text": "总查询次数", "props": {"class": "text-caption text-grey mb-1"}},
                            {"component": "div", "text": str(total_count), "props": {"class": "text-h6 font-bold"}},
                        ],
                    }],
                },
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 3},
                    "content": [{
                        "component": "VCard",
                        "props": {"class": "text-center pa-3"},
                        "content": [
                            {"component": "div", "text": "搜索次数", "props": {"class": "text-caption text-grey mb-1"}},
                            {"component": "div", "text": str(search_count), "props": {"class": "text-h6 font-bold text-primary"}},
                        ],
                    }],
                },
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 3},
                    "content": [{
                        "component": "VCard",
                        "props": {"class": "text-center pa-3"},
                        "content": [
                            {"component": "div", "text": "取链次数", "props": {"class": "text-caption text-grey mb-1"}},
                            {"component": "div", "text": str(links_count), "props": {"class": "text-h6 font-bold text-success"}},
                        ],
                    }],
                },
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 3},
                    "content": [{
                        "component": "VCard",
                        "props": {"class": "text-center pa-3"},
                        "content": [
                            {"component": "div", "text": "最近操作", "props": {"class": "text-caption text-grey mb-1"}},
                            {"component": "div", "text": latest_time, "props": {"class": "text-sm"}},
                        ],
                    }],
                },
            ],
        })

        # 搜索表单区域
        page_content.append({
            "component": "VCard",
            "props": {"class": "mb-4 pa-4"},
            "content": [
                {
                    "component": "VRow",
                    "props": {"align": "center"},
                    "content": [
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 8},
                            "content": [{
                                "component": "VTextField",
                                "props": {
                                    "model": "searchKeyword",
                                    "label": "🔍 搜索关键词",
                                    "placeholder": "请输入要搜索的影视名称",
                                    "variant": "outlined",
                                    "density": "comfortable"
                                }
                            }],
                        },
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 2},
                            "content": [{
                                "component": "VTextField",
                                "props": {
                                    "model": "searchLimit",
                                    "label": "结果数量",
                                    "type": "number",
                                    "min": 1,
                                    "max": 50,
                                    "value": self._config.search_limit,
                                    "variant": "outlined",
                                    "density": "comfortable"
                                }
                            }],
                        },
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 2},
                            "content": [{
                                "component": "VBtn",
                                "props": {
                                    "color": "primary",
                                    "size": "large",
                                    "block": True
                                },
                                "text": "立即搜索",
                                "events": {
                                    "click": {
                                        "api": f"plugin/SeedHub/search?apikey={settings.API_TOKEN}",
                                        "method": "post",
                                        "params": {
                                            "keyword": "$searchKeyword",
                                            "limit": "$searchLimit"
                                        },
                                        "success": {
                                            "message": "搜索成功，找到 {{result.data.length}} 个结果，已复制到剪贴板",
                                            "action": "copy",
                                            "data": "{{JSON.stringify(result.data, null, 2)}}"
                                        },
                                        "error": {
                                            "message": "搜索失败：{{result.message}}"
                                        }
                                    }
                                }
                            }],
                        },
                    ],
                }
            ],
        })

        # 取链表单区域
        page_content.append({
            "component": "VCard",
            "props": {"class": "mb-4 pa-4"},
            "content": [
                {
                    "component": "VRow",
                    "props": {"align": "center"},
                    "content": [
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 8},
                            "content": [{
                                "component": "VTextField",
                                "props": {
                                    "model": "linkMovieId",
                                    "label": "🔗 资源条目ID",
                                    "placeholder": "请输入资源条目ID",
                                    "variant": "outlined",
                                    "density": "comfortable"
                                }
                            }],
                        },
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 2},
                            "content": [{
                                "component": "VTextField",
                                "props": {
                                    "model": "linkQuarkLimit",
                                    "label": "解析数量",
                                    "type": "number",
                                    "min": 1,
                                    "max": 20,
                                    "value": self._config.quark_limit,
                                    "variant": "outlined",
                                    "density": "comfortable"
                                }
                            }],
                        },
                        {
                            "component": "VCol",
                            "props": {"cols": 12, "md": 2},
                            "content": [{
                                "component": "VBtn",
                                "props": {
                                    "color": "success",
                                    "size": "large",
                                    "block": True
                                },
                                "text": "获取链接",
                                "events": {
                                    "click": {
                                        "api": f"plugin/SeedHub/links?apikey={settings.API_TOKEN}",
                                        "method": "post",
                                        "params": {
                                            "movie_id": "$linkMovieId",
                                            "quark_limit": "$linkQuarkLimit"
                                        },
                                        "success": {
                                            "message": "链接解析成功，已复制到剪贴板",
                                            "action": "copy",
                                            "data": "{{JSON.stringify(result.data, null, 2)}}"
                                        },
                                        "error": {
                                            "message": "获取链接失败：{{result.message}}"
                                        }
                                    }
                                }
                            }],
                        },
                    ],
                }
            ],
        })

        # 帮助提示
        page_content.append({
            "component": "VAlert",
            "props": {
                "type": "info",
                "variant": "tonal",
                "border": "start",
                "class": "mb-4"
            },
            "text": "💡 使用说明：输入关键词点击「立即搜索」，成功后结果会自动复制到剪贴板；粘贴资源ID点击「获取链接」，解析结果也会自动复制。所有操作自动记录到历史列表。"
        })

        # 历史记录区域
        if history:
            items = []
            for item in reversed(history[:50]):
                items.append({
                    "time": item.get("time", ""),
                    "action": item.get("action", ""),
                    "keyword": item.get("keyword", ""),
                    "target": item.get("target", ""),
                    "summary": item.get("summary", ""),
                })

            page_content.append({
                "component": "VRow",
                "content": [{
                    "component": "VCol",
                    "props": {"cols": 12},
                    "content": [{
                        "component": "VDataTableVirtual",
                        "props": {
                            "headers": [
                                {"title": "时间", "key": "time", "sortable": True},
                                {"title": "动作", "key": "action", "sortable": True},
                                {"title": "关键词/ID", "key": "target", "sortable": False},
                                {"title": "摘要", "key": "summary", "sortable": False},
                            ],
                            "items": items,
                            "height": "30rem",
                            "density": "compact",
                            "fixed-header": True,
                            "hide-no-data": True,
                            "hover": True,
                        },
                    }],
                }],
            })
        else:
            page_content.append({
                "component": "div",
                "text": "暂无查询记录",
                "props": {"class": "text-center mt-4"},
            })

        return page_content

    def api_status(self) -> schemas.Response:
        return schemas.Response(success=True, data=self._config.model_dump())

    def api_search(self, item: SeedHubSearchRequest = Body(...)) -> schemas.Response:
        if not self._config.enabled:
            return schemas.Response(success=False, message="插件未启用")
        try:
            results = self._service.search(item.keyword, item.limit)
            self._append_history(
                action="search",
                target=item.keyword,
                summary=f"找到 {len(results)} 个结果",
                keyword=item.keyword,
            )
            return schemas.Response(success=True, data=[result.model_dump() for result in results])
        except Exception as err:
            logger.error(f"SeedHub search failed: {err}")
            return schemas.Response(success=False, message=str(err))

    def api_links(self, item: SeedHubLinksRequest = Body(...)) -> schemas.Response:
        if not self._config.enabled:
            return schemas.Response(success=False, message="插件未启用")
        try:
            result = self._service.get_links(item.movie_id, item.quark_limit)
            self._append_history(
                action="links",
                target=item.movie_id,
                summary=f"夸克 {len(result.quark_resolved)} 条，磁力 {len(result.magnet)} 条",
            )
            return schemas.Response(success=True, data=result.model_dump())
        except Exception as err:
            logger.error(f"SeedHub links failed: {err}")
            return schemas.Response(success=False, message=str(err))

    def api_clear_history(self) -> schemas.Response:
        self.save_data("history", [])
        logger.info("SeedHub 查询历史已清空")
        return schemas.Response(success=True, message="历史已清空")

    @eventmanager.register(EventType.PluginAction)
    def handle_search_action(self, event: Event):
        if not self._config.enabled:
            return
        if not event:
            return
        event_data = event.event_data
        if not event_data or event_data.get("action") != "seedhub_search":
            return
        keyword = event_data.get("args") or event_data.get("keyword") or event_data.get("text") or event_data.get("form_data", {}).get("keyword")
        if not keyword:
            self.post_message(
                title=f"【{self.plugin_name}】",
                mtype=NotificationType.Plugin,
                text="请提供搜索关键词",
                channel=event_data.get("channel"),
                userid=event_data.get("user"),
            )
            return
        try:
            results = self._service.search(keyword)
            if not results:
                text = "未找到相关结果"
            else:
                lines = []
                for index, item in enumerate(results[:10], 1):
                    lines.append(f"{index}. {item.title}")
                    lines.append(f"ID: {item.id} | 评分: {item.rating}")
                text = "\n".join(lines)
            self.post_message(
                title=f"【{self.plugin_name}】搜索结果",
                mtype=NotificationType.Plugin,
                text=text,
                channel=event_data.get("channel"),
                userid=event_data.get("user"),
            )
            self._append_history(action="search", target=keyword, summary=f"找到 {len(results)} 个结果", keyword=keyword)
        except Exception as err:
            logger.error(f"SeedHub action search failed: {err}")

    @eventmanager.register(EventType.PluginAction)
    def handle_links_action(self, event: Event):
        if not self._config.enabled:
            return
        if not event:
            return
        event_data = event.event_data
        if not event_data or event_data.get("action") != "seedhub_links":
            return
        movie_id = event_data.get("args") or event_data.get("movie_id") or event_data.get("text") or event_data.get("form_data", {}).get("movie_id")
        if not movie_id:
            self.post_message(
                title=f"【{self.plugin_name}】",
                mtype=NotificationType.Plugin,
                text="请提供 SeedHub 条目 ID",
                channel=event_data.get("channel"),
                userid=event_data.get("user"),
            )
            return
        try:
            result = self._service.get_links(movie_id)
            lines = [result.title]
            if result.quark_resolved:
                lines.append("夸克链接：")
                for item in result.quark_resolved[:5]:
                    lines.append(item.url or "")
            elif result.magnet and self._config.show_magnet:
                lines.append("磁力链接：")
                lines.extend(result.magnet[:5])
            else:
                lines.append("未找到可展示的链接")
            self.post_message(
                title=f"【{self.plugin_name}】链接结果",
                mtype=NotificationType.Plugin,
                text="\n".join([line for line in lines if line]),
                channel=event_data.get("channel"),
                userid=event_data.get("user"),
            )
            self._append_history(
                action="links",
                target=movie_id,
                summary=f"夸克 {len(result.quark_resolved)} 条，磁力 {len(result.magnet)} 条",
            )
        except Exception as err:
            logger.error(f"SeedHub action links failed: {err}")

    def _run_once(self):
        try:
            results = self._service.search("电影")
            logger.info(f"SeedHub run once success: {len(results)} results")
        except Exception as err:
            logger.error(f"SeedHub run once failed: {err}")

    def _append_history(self, action: str, target: str, summary: str, keyword: str = ""):
        history = self.get_data("history") or []
        history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "keyword": keyword,
            "target": target,
            "summary": summary,
        })
        self.save_data("history", history[-100:])

    def _update_config(self):
        self.update_config(self._config.model_dump())

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as err:
            logger.error(f"退出插件失败：{err}")