"""Session 模块

提供 Workspace 会话管理功能：
- SessionState: 会话运行时状态
- Session: 会话持久化模型
- SessionStore: 存储层
- SessionRuntimeManager: Runtime 管理器（Phase 6.2）
- StepRecorder: 步骤记录器（Phase 6.3）
- WorkflowExtractor: 工作流提取器（Phase 6.5）

使用示例：

```python
# 创建 Session
from services.session import get_session_store, SessionState

store = get_session_store()
session = store.create_session(workspace_id="ws-123")

# 获取状态
state = session.get_state()

# 更新状态
state.add_to_chat_history("user", "获取B站热点")
state.touch()
store.update_state(session.session_id, state)

# 关闭 Session
store.close_session(session.session_id)
```
"""

from .config import (
    SessionConfig,
    get_session_config,
    reset_session_config,
)
from .models import (
    SessionStatus,
    RecordedStep,
    SessionState,
    Session,
)
from .store import (
    SessionStore,
    get_session_store,
    reset_session_store,
)
from .runtime_manager import (
    SessionRuntimeManager,
    get_session_runtime_manager,
    reset_session_runtime_manager,
)
from .workflow_extractor import (
    WorkflowExtractor,
    get_workflow_extractor,
    reset_workflow_extractor,
)

__all__ = [
    # 配置
    "SessionConfig",
    "get_session_config",
    "reset_session_config",
    # 模型
    "SessionStatus",
    "RecordedStep",
    "SessionState",
    "Session",
    # 存储
    "SessionStore",
    "get_session_store",
    "reset_session_store",
    # Runtime 管理器
    "SessionRuntimeManager",
    "get_session_runtime_manager",
    "reset_session_runtime_manager",
    # 工作流提取器
    "WorkflowExtractor",
    "get_workflow_extractor",
    "reset_workflow_extractor",
]
