"""
🌐 翻译工具

提供文本翻译能力。支持多种语言互译。
使用离线词典 + 规则引擎实现基础翻译演示；
可替换为真实翻译 API（如 DeepL、Google Translate、百度翻译等）。
"""

import json
import urllib.parse
import urllib.request
from typing import Optional


# 简易离线词典（演示用）
_OFFLINE_DICT = {
    # 中 → 英
    "你好": "Hello",
    "谢谢": "Thank you",
    "再见": "Goodbye",
    "早上好": "Good morning",
    "晚上好": "Good evening",
    "今天": "today",
    "明天": "tomorrow",
    "昨天": "yesterday",
    "天气": "weather",
    "吃饭": "eat",
    "喝水": "drink water",
    "喜欢": "like",
    "帮助": "help",
    "朋友": "friend",
    "工作": "work",
    "学习": "study",
    "开心": "happy",
    "难过": "sad",
    "美丽": "beautiful",
    "大": "big",
    "小": "small",
    "好": "good",
    "坏": "bad",
    "热": "hot",
    "冷": "cold",
    "是": "yes",
    "不是": "no",
    "可能": "maybe",
    "请": "please",
    "对不起": "sorry",
    "没关系": "it's okay",
    "多少钱": "How much",
    "在哪里": "Where is",
    "什么时候": "When",
    "为什么": "Why",
    "谁": "Who",
    # 英 → 中
    "hello": "你好",
    "world": "世界",
    "thank you": "谢谢",
    "goodbye": "再见",
    "please": "请",
    "sorry": "对不起",
    "help": "帮助",
    "friend": "朋友",
    "beautiful": "美丽",
    "love": "爱",
    "time": "时间",
    "people": "人们",
    "family": "家庭",
    "money": "钱",
    "food": "食物",
    "water": "水",
    "sun": "太阳",
    "moon": "月亮",
    "star": "星星",
    "book": "书",
    "computer": "电脑",
    "music": "音乐",
    "happy": "快乐",
    "sad": "悲伤",
    "big": "大",
    "small": "小",
    "good": "好",
    "bad": "坏",
    "hot": "热",
    "cold": "冷",
    "yes": "是",
    "no": "不是",
}


# 语言代码映射
_LANG_CODES = {
    "中文": "zh",
    "英语": "en",
    "英文": "en",
    "日语": "ja",
    "日文": "ja",
    "韩语": "ko",
    "韩文": "ko",
    "法语": "fr",
    "法文": "fr",
    "德语": "de",
    "德文": "de",
    "西班牙语": "es",
    "西语": "es",
    "俄语": "ru",
    "葡萄牙语": "pt",
    "意大利语": "it",
    "阿拉伯语": "ar",
    "zh": "zh",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "ru": "ru",
    "pt": "pt",
    "it": "it",
    "ar": "ar",
}

# 语言代码 → 中文名称
_LANG_NAMES = {
    "zh": "中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "ru": "俄语",
    "pt": "葡萄牙语",
    "it": "意大利语",
    "ar": "阿拉伯语",
}


def _normalize_lang(lang: str) -> str:
    """将语言名称标准化为代码。"""
    return _LANG_CODES.get(lang.strip().lower(), lang.strip().lower())


def _offline_translate(text: str, source: str, target: str) -> Optional[str]:
    """
    使用离线词典翻译。
    对短语级翻译有用，长文本效果有限。
    """
    # 查词典
    if text.lower() in _OFFLINE_DICT:
        return _OFFLINE_DICT[text.lower()]
    
    # 逐词翻译（英文 → 中文）
    if source == "en" and target == "zh":
        words = text.split()
        translated_words = []
        for word in words:
            clean = word.strip(".,!?;:'\"()[]{}")
            punct_before = word[:len(word) - len(clean)] if clean != word else ""
            punct_after = word[len(clean):] if clean != word else ""
            if clean.lower() in _OFFLINE_DICT:
                translated_words.append(punct_before + _OFFLINE_DICT[clean.lower()] + punct_after)
            else:
                translated_words.append(word)
        return " ".join(translated_words)
    
    return None


def _try_online_translate(text: str, source: str, target: str) -> Optional[str]:
    """
    尝试调用在线翻译 API。
    默认使用 mymemory API（免费，无需 key）。
    """
    try:
        url = (
            f"https://api.mymemory.translated.net/get?"
            f"q={urllib.parse.quote(text)}&"
            f"langpair={source}|{target}"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("responseStatus") == 200:
                translated = data["responseData"]["translatedText"]
                if translated and translated != text:
                    return translated
    except Exception:
        pass
    return None


def register_translation_tools(registry) -> None:
    """
    注册翻译相关工具。
    
    Args:
        registry: ToolRegistry 实例。
    """

    @registry.register(
        name="translate",
        description="将文本从一种语言翻译为另一种语言。支持中文、英语、日语、韩语、法语、德语、西班牙语等",
        metadata={"category": "translation", "version": "1.0"},
    )
    def translate(text: str, source_lang: str = "", target_lang: str = "中文") -> str:
        """
        翻译文本。
        
        :param text: 待翻译的文本。
        :param source_lang: 源语言（可选，为空时自动检测）。
        :param target_lang: 目标语言，默认"中文"。
        :returns: 翻译结果。
        """
        source = _normalize_lang(source_lang) if source_lang else ""
        target = _normalize_lang(target_lang)

        if not target:
            raise ValueError(f"不支持的目标语言: {target_lang}")

        # 自动检测源语言
        if not source:
            # 去除语言指令词汇后再检测
            clean_text = text
            for word in ["翻译", "翻译成", "用中文说", "用英文说", "成中文", "成英文",
                         "translate", "translation", "to Chinese", "to English"]:
                clean_text = clean_text.replace(word, "")
            clean_text = clean_text.strip()
            # 如果清理后为空，用原文
            if not clean_text:
                clean_text = text
            # 简单检测：含中文则为中文
            has_chinese = any("\u4e00" <= c <= "\u9fff" for c in clean_text)
            source = "zh" if has_chinese else "en"

        # 如果源语言 == 目标语言
        if source == target:
            return f"源语言和目标语言相同，无需翻译：\n{text}"

        # 先尝试离线词典
        result = _offline_translate(text, source, target)
        if result:
            note = "（离线词典翻译）" if len(text) < 50 else ""
            return (
                f"🌐 翻译结果 {note}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"源语言 ({_LANG_NAMES.get(source, source)}): {text}\n"
                f"目标语言 ({_LANG_NAMES.get(target, target)}): {result}"
            )

        # 尝试在线翻译
        result = _try_online_translate(text, source, target)
        if result:
            return (
                f"🌐 翻译结果\n"
                f"━━━━━━━━━━━━━━━\n"
                f"源语言 ({_LANG_NAMES.get(source, source)}): {text}\n"
                f"目标语言 ({_LANG_NAMES.get(target, target)}): {result}"
            )

        # 回退
        return (
            f"🌐 翻译结果（离线模式 - 逐词翻译）\n"
            f"━━━━━━━━━━━━━━━\n"
            f"源语言 ({_LANG_NAMES.get(source, source)}): {text}\n"
            f"目标语言 ({_LANG_NAMES.get(target, target)}): "
            f"[无法翻译完整句子，建议配置在线翻译 API]"
        )

    @registry.register(
        name="detect_language",
        description="检测文本的语言种类",
        metadata={"category": "translation", "version": "1.0"},
    )
    def detect_language(text: str) -> str:
        """
        检测文本语言。
        
        :param text: 待检测的文本。
        :returns: 语言检测结果及置信度。
        """
        # 简单检测逻辑
        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in text)
        has_japanese = any("\u3040" <= c <= "\u309f" or "\u30a0" <= c <= "\u30ff" for c in text)
        has_korean = any("\uac00" <= c <= "\ud7af" for c in text)
        has_russian = any("\u0400" <= c <= "\u04ff" for c in text)
        has_arabic = any("\u0600" <= c <= "\u06ff" for c in text)

        # 计算英文字母比例
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in text if c.isalpha())
        english_ratio = english_chars / total_chars if total_chars > 0 else 0

        if has_chinese:
            lang = "中文"
            confidence = "高"
        elif has_japanese:
            lang = "日语"
            confidence = "中"
        elif has_korean:
            lang = "韩语"
            confidence = "中"
        elif has_russian:
            lang = "俄语"
            confidence = "中"
        elif has_arabic:
            lang = "阿拉伯语"
            confidence = "中"
        elif english_ratio > 0.8:
            lang = "英语"
            confidence = "高"
        else:
            lang = "未知/混合语言"
            confidence = "低"

        return (
            f"🔍 语言检测结果\n"
            f"━━━━━━━━━━━━━\n"
            f"文本: {text[:50]}{'...' if len(text) > 50 else ''}\n"
            f"检测结果: {lang}\n"
            f"置信度: {confidence}"
        )
