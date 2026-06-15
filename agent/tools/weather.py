"""
🌤 天气查询工具

模拟查询天气信息。在实际生产环境中，可替换为真实天气 API（如和风天气、OpenWeatherMap 等）。
"""

import random
import time


# 模拟城市天气数据库
_CITY_WEATHER = {
    "北京": {"temp": 28, "condition": "晴", "humidity": 45, "wind": "3级", "aqi": 85},
    "上海": {"temp": 32, "condition": "多云", "humidity": 70, "wind": "4级", "aqi": 95},
    "广州": {"temp": 35, "condition": "阵雨", "humidity": 85, "wind": "3级", "aqi": 60},
    "深圳": {"temp": 33, "condition": "多云转阴", "humidity": 78, "wind": "3级", "aqi": 55},
    "杭州": {"temp": 30, "condition": "阴", "humidity": 72, "wind": "2级", "aqi": 72},
    "成都": {"temp": 27, "condition": "小雨", "humidity": 80, "wind": "2级", "aqi": 90},
    "武汉": {"temp": 34, "condition": "晴", "humidity": 65, "wind": "3级", "aqi": 88},
    "南京": {"temp": 31, "condition": "多云", "humidity": 68, "wind": "3级", "aqi": 78},
    "重庆": {"temp": 36, "condition": "晴", "humidity": 60, "wind": "2级", "aqi": 82},
    "西安": {"temp": 29, "condition": "阴", "humidity": 55, "wind": "3级", "aqi": 100},
    "London": {"temp": 18, "condition": "Cloudy", "humidity": 65, "wind": "4级", "aqi": 40},
    "New York": {"temp": 25, "condition": "Sunny", "humidity": 55, "wind": "3级", "aqi": 45},
    "Tokyo": {"temp": 26, "condition": "Rainy", "humidity": 80, "wind": "3级", "aqi": 35},
    "Paris": {"temp": 22, "condition": "Partly Cloudy", "humidity": 60, "wind": "3级", "aqi": 42},
    "Sydney": {"temp": 16, "condition": "Clear", "humidity": 50, "wind": "4级", "aqi": 30},
}


def register_weather_tools(registry) -> None:
    """
    注册天气相关工具。
    
    Args:
        registry: ToolRegistry 实例。
    """

    @registry.register(
        name="get_weather",
        description="查询指定城市的实时天气信息，包括温度、天气状况、湿度、风力等",
        metadata={"category": "weather", "version": "1.0"},
    )
    def get_weather(city: str) -> str:
        """
        查询天气。
        
        :param city: 城市名称，支持中文（如"北京"）或英文（如"London"）。
        :returns: 格式化的天气报告。
        """
        # 模拟网络延迟
        time.sleep(0.3)

        city_normalized = city.strip()

        # 优先精确匹配
        if city_normalized in _CITY_WEATHER:
            data = _CITY_WEATHER[city_normalized]
        else:
            # 模糊匹配
            matched = None
            for known_city in _CITY_WEATHER:
                if city_normalized.lower() in known_city.lower():
                    matched = known_city
                    break
                if known_city.lower() in city_normalized.lower():
                    matched = known_city
                    break

            if matched:
                data = _CITY_WEATHER[matched]
                city_normalized = matched
            else:
                # 随机生成一个天气（城市未收录时）
                data = {
                    "temp": random.randint(-5, 40),
                    "condition": random.choice(["晴", "多云", "阴", "小雨", "大风"]),
                    "humidity": random.randint(20, 95),
                    "wind": f"{random.randint(1, 6)}级",
                    "aqi": random.randint(20, 200),
                }

        def _aqi_label(aqi: int) -> str:
            if aqi <= 50: return "优"
            if aqi <= 100: return "良"
            if aqi <= 150: return "轻度污染"
            if aqi <= 200: return "中度污染"
            return "重度污染"

        return (
            f"🌤 {city_normalized} 天气\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🌡 温度：{data['temp']}°C\n"
            f"☁️ 状况：{data['condition']}\n"
            f"💧 湿度：{data['humidity']}%\n"
            f"🌬 风力：{data['wind']}\n"
            f"🍃 AQI：{data['aqi']}（{_aqi_label(data['aqi'])}）"
        )

    @registry.register(
        name="get_weather_forecast",
        description="查询指定城市未来几天的天气预报",
        metadata={"category": "weather", "version": "1.0"},
    )
    def get_weather_forecast(city: str, days: int = 3) -> str:
        """
        查询未来天气预报。
        
        :param city: 城市名称。
        :param days: 预报天数（1-7），默认为3天。
        :returns: 多日天气预报。
        """
        time.sleep(0.3)
        days = max(1, min(7, days))

        conditions = ["晴", "多云", "阴", "小雨", "晴转多云", "多云转阴"]
        lines = [f"📅 {city} 未来 {days} 天预报", "━" * 30]

        for i in range(days):
            day_cond = random.choice(conditions)
            day_temp_high = random.randint(20, 38)
            day_temp_low = day_temp_high - random.randint(5, 12)
            lines.append(
                f"  第{i+1}天: {day_cond}  "
                f"{day_temp_low}~{day_temp_high}°C"
            )

        return "\n".join(lines)
