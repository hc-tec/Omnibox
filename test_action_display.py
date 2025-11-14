"""测试动作显示名称"""
from services.subscription.action_registry import ActionRegistry

registry = ActionRegistry()

# 测试 bilibili user 的所有动作
actions = registry.get_supported_actions('bilibili', 'user')
print(f"bilibili/user 支持的动作: {actions}\n")

# 检查 videos 动作
action_def = registry.get_action('bilibili', 'user', 'videos')
if action_def:
    print(f"videos 动作定义:")
    print(f"  action_name: {action_def.action_name}")
    print(f"  display_name: {action_def.display_name}")
    print(f"  path_template: {action_def.path_template}")
else:
    print("未找到 videos 动作定义")

# 测试动作映射
print("\n动作映射表:")
action_map = {}
for action in actions[:10]:  # 只测试前10个
    action_def = registry.get_action('bilibili', 'user', action)
    if action_def:
        action_map[action_def.display_name.lower()] = action
        print(f"  '{action_def.display_name}' -> '{action}'")

# 测试匹配
test_action = "投稿视频"
print(f"\n测试匹配: '{test_action}'")
if test_action.lower() in action_map:
    print(f"  精确匹配: {action_map[test_action.lower()]}")
else:
    print("  精确匹配失败")
    # 包含匹配
    for display_name, action_name in action_map.items():
        if test_action.lower() in display_name or display_name in test_action.lower():
            print(f"  包含匹配: '{display_name}' -> '{action_name}'")
            break
    else:
        print("  包含匹配也失败")
