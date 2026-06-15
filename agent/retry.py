"""
🔄 智能错误重试机制 (RetryHandler)

提供工具调用失败后的自动重试能力，支持：
  1. 指数退避（Exponential Backoff）
  2. 最大重试次数限制
  3. 特定异常类型的重试策略
  4. 重试回调钩子（日志、告警等）
  5. 退避抖动（Jitter）防止惊群效应
"""

import time
import random
import logging
from typing import Any, Callable, Optional, Tuple, Type, Union

logger = logging.getLogger("agent.retry")


class RetryConfig:
    """
    重试配置。
    
    Attributes:
        max_retries: 最大重试次数。
        base_delay: 初始退避延迟（秒）。
        max_delay: 最大退避延迟（秒）。
        backoff_factor: 退避乘数（每次重试延迟 *= factor）。
        jitter: 是否添加随机抖动 ±50%。
        retryable_exceptions: 可重试的异常类型列表。为空则所有异常均可重试。
        on_retry_callback: 每次重试前的回调函数。
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[list] = None,
        on_retry_callback: Optional[Callable[[int, Exception, float], None]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or []
        self.on_retry_callback = on_retry_callback

    def __repr__(self) -> str:
        return (
            f"RetryConfig(max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}s, "
            f"backoff={self.backoff_factor})"
        )


class RetryHandler:
    """
    重试处理器。
    
    封装函数执行和自动重试逻辑。
    
    使用示例:
        handler = RetryHandler(max_retries=3)
        success, result, error = handler.execute(my_func)
    """

    DEFAULT_CONFIG = RetryConfig()

    def __init__(
        self,
        max_retries: int = 3,
        config: Optional[RetryConfig] = None,
    ):
        """
        初始化重试处理器。
        
        Args:
            max_retries: 最大重试次数（当不提供 config 时有效）。
            config: 详细重试配置（优先级高于 max_retries）。
        """
        if config:
            self.config = config
        else:
            self.config = RetryConfig(max_retries=max_retries)

        self.attempt_count = 0
        self.total_delay = 0.0
        self.retry_history: list[dict] = []

    # ── 核心执行方法 ──────────────────────────────────────────────────────────

    def execute(
        self,
        func: Callable[[], Any],
        context: Optional[dict] = None,
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        执行函数并自动重试。
        
        Args:
            func: 需要执行的零参数函数（已通过闭包绑定参数）。
            context: 可选上下文信息（用于日志/回调）。
        
        Returns:
            (success: bool, result: Any, error: Optional[str])
                - success=True: result 为函数返回值，error 为 None
                - success=False: result 为 None，error 为错误信息
        """
        self.attempt_count = 0
        self.total_delay = 0.0
        self.retry_history = []

        last_exception = None

        while self.attempt_count <= self.config.max_retries:
            self.attempt_count += 1

            try:
                result = func()
                # 成功
                if self.attempt_count > 1:
                    logger.info(
                        f"第 {self.attempt_count} 次尝试成功 "
                        f"（共重试 {self.attempt_count - 1} 次）"
                    )
                return True, result, None

            except Exception as e:
                last_exception = e

                # 检查是否属于可重试异常
                if not self._is_retryable(e):
                    logger.warning(f"不可重试的异常: {type(e).__name__}: {e}")
                    return False, None, self._format_error(e)

                # 记录重试历史
                history_entry = {
                    "attempt": self.attempt_count,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }

                # 判断是否还有重试次数
                if self.attempt_count > self.config.max_retries:
                    history_entry["action"] = "达到最大重试次数，放弃"
                    self.retry_history.append(history_entry)
                    break

                # 计算退避延迟
                delay = self._calculate_delay()

                history_entry["action"] = f"等待 {delay:.2f}s 后重试"
                history_entry["delay"] = delay
                self.retry_history.append(history_entry)

                # 调用回调
                if self.config.on_retry_callback:
                    try:
                        self.config.on_retry_callback(
                            self.attempt_count, e, delay
                        )
                    except Exception:
                        pass

                logger.warning(
                    f"工具调用失败（第 {self.attempt_count} 次）: {e}. "
                    f"{delay:.1f}s 后重试..."
                )

                # 等待
                time.sleep(delay)
                self.total_delay += delay

        # 所有重试均失败
        error_msg = self._format_error(last_exception)
        logger.error(
            f"工具调用在 {self.config.max_retries} 次重试后全部失败: "
            f"{error_msg}"
        )
        return False, None, error_msg

    # ── 辅助方法 ─────────────────────────────────────────────────────────────

    def _is_retryable(self, exception: Exception) -> bool:
        """判断异常是否可重试。"""
        if not self.config.retryable_exceptions:
            # 默认所有异常均可重试（但 ValueError 等逻辑错误通常不重试）
            # 只对特定"可恢复"异常重试
            return isinstance(exception, (
                ConnectionError,
                TimeoutError,
                OSError,
                IOError,
            )) or "timeout" in str(exception).lower()
        
        return any(
            isinstance(exception, exc_type)
            for exc_type in self.config.retryable_exceptions
        )

    def _calculate_delay(self) -> float:
        """
        使用指数退避 + 抖动计算等待时间。
        
        公式: delay = min(base * factor^(attempt-1), max_delay) * jitter
        """
        delay = self.config.base_delay * (
            self.config.backoff_factor ** (self.attempt_count - 1)
        )
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            # ±50% 随机抖动
            jitter_factor = 1 + (random.random() - 0.5)
            delay *= jitter_factor

        return round(delay, 3)

    @staticmethod
    def _format_error(exception: Exception) -> str:
        """格式化错误信息。"""
        import traceback
        tb = traceback.format_exception_only(type(exception), exception)
        return "".join(tb).strip()

    # ── 信息查询 ─────────────────────────────────────────────────────────────

    def get_retry_summary(self) -> str:
        """获取重试执行摘要。"""
        if not self.retry_history:
            return "无需重试，一次执行成功。"

        lines = [
            "🔄 重试执行摘要",
            "=" * 40,
            f"总尝试次数: {self.attempt_count}",
            f"重试次数: {len(self.retry_history)}",
            f"总等待时间: {self.total_delay:.2f}s",
            "",
            "重试历史:",
        ]

        for entry in self.retry_history:
            attempt = entry["attempt"]
            error = entry["error"][:80]
            action = entry["action"]
            lines.append(f"  #{attempt}: {error}")
            lines.append(f"          → {action}")

        return "\n".join(lines)

    def reset(self) -> None:
        """重置重试状态。"""
        self.attempt_count = 0
        self.total_delay = 0.0
        self.retry_history = []


# ── 便捷装饰器 ───────────────────────────────────────────────────────────────

def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: Optional[list] = None,
):
    """
    函数重试装饰器。
    
    使用示例:
        @with_retry(max_retries=2)
        def unstable_api_call():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            handler = RetryHandler(
                config=RetryConfig(
                    max_retries=max_retries,
                    base_delay=base_delay,
                    retryable_exceptions=retryable_exceptions,
                )
            )
            success, result, error = handler.execute(
                lambda: func(*args, **kwargs)
            )
            if not success:
                raise RuntimeError(error)
            return result
        return wrapper
    return decorator
