"""
研究服务常量定义

定义研究任务相关的所有常量、枚举和错误类型，避免魔法字符串。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Callable


class TaskStatus(str, Enum):
    """研究任务状态"""

    PENDING = "pending"  # 等待创建
    RUNNING = "running"  # 运行中
    PROCESSING = "processing"  # 处理用户输入后继续运行
    HUMAN_IN_LOOP = "human_in_loop"  # 等待人工输入
    COMPLETED = "completed"  # 已完成
    ERROR = "error"  # 错误
    CANCELLED = "cancelled"  # 已取消


class StreamEventType(str, Enum):
    """流式事件类型"""

    STEP = "step"  # 步骤更新
    HUMAN_IN_LOOP = "human_in_loop"  # 请求人工输入
    HUMAN_RESPONSE_ACK = "human_response_ack"  # 确认收到人工输入
    COMPLETE = "complete"  # 任务完成
    ERROR = "error"  # 错误事件
    CANCELLED = "cancelled"  # 取消事件


class StepStatus(str, Enum):
    """研究步骤状态"""

    SUCCESS = "success"
    ERROR = "error"
    IN_PROGRESS = "in_progress"


class NodeName(str, Enum):
    """LangGraph 节点名称"""

    ROUTER = "router"  # 路由节点
    PLANNER = "planner"  # 规划节点
    TOOL_EXECUTOR = "tool_executor"  # 工具执行节点
    REFLECTOR = "reflector"  # 反思节点
    SYNTHESIZER = "synthesizer"  # 综合节点
    WAIT_FOR_HUMAN = "wait_for_human"  # 等待人工输入节点


# 异常消息常量
class ErrorMessages:
    """错误消息常量"""

    TASK_NOT_FOUND = "任务 {task_id} 不存在"
    TASK_CANCELLED = "research_task_cancelled"
    TASK_RESUME_FAILED = "任务恢复失败: {reason}"
    CONTEXT_NOT_FOUND = "无法续写研究任务 {task_id}：上下文不存在"
    MAX_STEPS_REACHED = "达到最大步数 {max_steps}，停止研究"


# 配置默认值
class DefaultConfig:
    """默认配置常量"""

    MAX_STEPS = 20  # 最大步骤数
    TASK_WAIT_TIMEOUT = 10.0  # 任务等待超时（秒）
    THREAD_POOL_SIZE = 5  # 线程池大小
    HISTORY_LIMIT = 200  # 事件历史限制


@dataclass
class ResearchConfig:
    """
    研究任务配置对象。

    用于简化 ResearchService.research() 方法的参数传递。
    """

    # 必需参数
    user_query: str

    # 可选参数
    filter_datasource: Optional[str] = None
    max_steps: int = DefaultConfig.MAX_STEPS
    task_id: Optional[str] = None

    # 高级参数
    callback: Optional[Callable[[Dict[str, Any]], None]] = None
    initial_state: Optional[Dict[str, Any]] = None
    reuse_task: bool = False

    def __post_init__(self):
        """验证配置参数"""
        # 验证 user_query
        if not self.user_query or not self.user_query.strip():
            raise ValueError("user_query 不能为空")

        if len(self.user_query) > 5000:
            raise ValueError(f"user_query 长度不能超过 5000 字符，当前长度：{len(self.user_query)}")

        # 验证 max_steps
        if self.max_steps <= 0:
            raise ValueError(f"max_steps 必须大于 0，当前值：{self.max_steps}")

        if self.max_steps > 100:
            raise ValueError(f"max_steps 不能超过 100，当前值：{self.max_steps}")

        # 验证 task_id
        if self.task_id is not None:
            if not isinstance(self.task_id, str) or not self.task_id.strip():
                raise ValueError("task_id 必须是非空字符串")
            if len(self.task_id) > 128:
                raise ValueError(f"task_id 长度不能超过 128 字符，当前长度：{len(self.task_id)}")

        # 验证 filter_datasource
        if self.filter_datasource is not None:
            if not isinstance(self.filter_datasource, str) or not self.filter_datasource.strip():
                raise ValueError("filter_datasource 必须是非空字符串")

        # 验证 initial_state
        if self.initial_state is not None:
            if not isinstance(self.initial_state, dict):
                raise ValueError("initial_state 必须是字典类型")

        # 验证 callback
        if self.callback is not None:
            if not callable(self.callback):
                raise ValueError("callback 必须是可调用对象")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchConfig":
        """从字典创建配置对象"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
