import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from typing import Annotated
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolArg

from model.loadenv_utils import get_llm_config
from rag.rag_service import build_rag_chain, load_vectorstore

# 初始化 RAG chain（模块加载时执行一次）
vectors = load_vectorstore()
rag_chain = build_rag_chain(vectors)

config = get_llm_config()
gaode_api_key = config["gaode_api_key"]

DB_PATH = Path(__file__).parent.parent.parent / "data" / "user_records.db"

def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT    NOT NULL,
            month       TEXT    NOT NULL,
            action_type TEXT    NOT NULL,
            summary     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

_init_db()


@tool(description=(
    "从向量知识库中精准检索扫地/扫拖机器人相关资料，涵盖常用问答、专业使用建议、"
    "故障处理、环境适配、选购指南、维护保养等内容。"
    "入参 query 为检索词（字符串），出参为检索到的相关资料摘要（字符串）。"
    "当用户提问涉及机器人使用、故障、保养、选购等专业问题时，优先调用此工具。"
))
def use_rag_service(query: str) -> str:
    """从向量知识库检索扫地/扫拖机器人相关资料并返回摘要。"""
    return rag_chain.invoke(query)


@tool(description=(
    "获取指定城市的实时天气、空气湿度、降雨概率等核心环境信息，以字符串形式返回。"
    "使用场景：判断指定城市的环境是否适合使用扫地/扫拖机器人，或用户问题涉及天气、"
    "湿度对机器人使用的影响时调用。"
    "调用规则：必须传入纯文本字符串类型的 city 参数，值为标准城市名称（如北京、上海）。"
))
def get_weather(city: str) -> str:
    """调用高德 API 获取指定城市的实时天气环境信息。"""
    # 第一步：城市名 → adcode
    geo_url = "https://restapi.amap.com/v3/geocode/geo"
    geo_resp = requests.get(
        geo_url,
        params={"address": city, "key": gaode_api_key},
        timeout=10,
    )
    geo_data = geo_resp.json()
    if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
        return f"无法获取城市 {city} 的地理编码，请确认城市名称是否正确。"

    adcode = geo_data["geocodes"][0]["adcode"]

    # 第二步：adcode → 实时天气（extensions=base）
    weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
    weather_resp = requests.get(
        weather_url,
        params={"city": adcode, "key": gaode_api_key, "extensions": "base"},
        timeout=10,
    )
    w = weather_resp.json()
    if w.get("status") != "1" or not w.get("lives"):
        return f"无法获取城市 {city} 的天气数据，请稍后重试。"

    live = w["lives"][0]
    weather     = live.get("weather", "未知")
    temperature = live.get("temperature", "未知")
    humidity    = live.get("humidity", "未知")
    winddirection = live.get("winddirection", "未知")
    windpower   = live.get("windpower", "未知")
    reporttime  = live.get("reporttime", "未知")

    # 第三步：adcode → 天气预报（extensions=all）获取降雨概率
    forecast_resp = requests.get(
        weather_url,
        params={"city": adcode, "key": gaode_api_key, "extensions": "all"},
        timeout=10,
    )
    f_data = forecast_resp.json()
    rain_prob = "未知"
    if f_data.get("status") == "1" and f_data.get("forecasts"):
        casts = f_data["forecasts"][0].get("casts", [])
        if casts:
            # 取今日白天降雨描述作为概率参考
            day_weather = casts[0].get("dayweather", "")
            rain_prob = day_weather if day_weather else "未知"

    return (
        f"城市：{city} | 天气：{weather} | 气温：{temperature}℃ | "
        f"空气湿度：{humidity}% | 风向：{winddirection} | 风力：{windpower}级 | "
        f"今日天气预报：{rain_prob} | 数据更新时间：{reporttime}"
    )


@tool(description=(
    "获取当前发起请求的用户所处的城市名称，无需任何入参，直接返回字符串类型的标准城市名。"
    "使用场景：当需要获取用户地理位置以配套调用 get_weather 等需城市参数的工具，"
    "或回答与用户所在城市相关的机器人使用问题时调用。"
))
def get_user_location() -> str:
    """通过高德 IP 定位接口获取用户当前所在城市名称。"""
    try:
        resp = requests.get(
            "https://restapi.amap.com/v3/ip",
            params={"key": gaode_api_key},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "1":
            return "未知"
        city = data.get("city") or data.get("province") or "未知"
        return city
    except Exception:
        return "未知"


@tool(description=(
    "获取系统当前月份，格式固定为 YYYY-MM（如 '2025-06'），无需任何入参。"
    "使用场景：当用户未明确指定月份，且需要基于当前月份检索用户记录、"
    "生成个性化使用报告或数据统计时调用。"
))
def get_current_time() -> str:
    """返回当前系统月份，格式为 YYYY-MM。"""
    return datetime.now().strftime("%Y-%m")


@tool(description=(
    "将用户本次交互记录持久化写入本地数据库，入参为 user_id（用户标识）、month（YYYY-MM格式月份）、"
    "action_type（行为类型，限：使用咨询/故障处理/维护保养/选购建议）、summary（对话核心结论，100字以内）。"
    "使用场景：用户完成一次有实质内容的对话后主动调用，用于后续生成个性化使用报告。"
    "month 未知时须先调用 get_current_time 获取；user_id 未知时填 default。"
))
def save_user_record(user_id: str, month: str, action_type: str, summary: str) -> str:
    """将用户对话记录写入 SQLite，返回写入结果。"""
    valid_types = {"使用咨询", "故障处理", "维护保养", "选购建议"}
    if action_type not in valid_types:
        return f"写入失败：action_type 须为以下之一：{'、'.join(valid_types)}"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO user_records (user_id, month, action_type, summary, created_at) VALUES (?,?,?,?,?)",
            (user_id, month, action_type, summary, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()
        return "记录已保存"
    except Exception as e:
        return f"写入失败：{e}"


@tool(description=(
    "获取当前发起请求的用户唯一标识（ID字符串），无需任何入参。"
    "使用场景：当需要基于当前用户ID检索其专属使用记录或生成个性化使用报告时，"
    "若未知用户ID，先调用此工具获取，再进行后续操作。"
))
def get_user_id(config: Annotated[RunnableConfig, InjectedToolArg]) -> str:
    """从请求上下文中获取后端注入的用户ID，不存在时返回 default。"""
    return str(config.get("configurable", {}).get("user_id", "default"))


@tool(description=(
    "查询当前用户的历史对话摘要记录，无需任何入参，返回该用户过去所有存档的对话摘要列表（字符串）。"
    "使用场景：当用户提到「上次」「之前」「我记得」等涉及历史对话的表述，"
    "或需要了解用户过去咨询/故障/保养/选购情况以提供个性化建议时，优先调用此工具。"
))
def get_user_history(config: Annotated[RunnableConfig, InjectedToolArg]) -> str:
    """从数据库读取当前用户的历史对话摘要，按时间倒序返回最近20条。"""
    user_id = str(config.get("configurable", {}).get("user_id", "default"))
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT month, action_type, summary, created_at "
            "FROM user_records WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
        conn.close()
        if not rows:
            return "暂无历史记录。"
        lines = [f"[{r[3]}] 类型：{r[1]}（{r[0]}）— {r[2]}" for r in rows]
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败：{e}"

