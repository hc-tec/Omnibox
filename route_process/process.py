import json
import re
import os

def clean_description(description: str) -> str:
    """清理RSSHub描述中的Markdown标记。"""
    if not description:
        return ""
    # 移除 ::: tip ... ::: 块
    desc = re.sub(r":::\s*tip.*?:::", "", description, flags=re.DOTALL | re.IGNORECASE)
    return desc.strip().replace('\n', ' ') # 移除换行

def parse_parameters(params_dict: dict, path_template_key: str, error_context: str) -> list:
    """
    解析RSSHub的 'parameters' 对象，将其转换为 DataSourceDefinition 格式。
    """
    parsed_params = []
    if not params_dict:
        return []

    for name, desc_value in params_dict.items():
        description_str = ""
        
        try:
            if isinstance(desc_value, str):
                description_str = desc_value
            elif isinstance(desc_value, dict):
                if 'description' in desc_value and isinstance(desc_value['description'], str):
                    description_str = desc_value['description']
                elif 'desc' in desc_value and isinstance(desc_value['desc'], str):
                    description_str = desc_value['desc']
                else:
                    print(f"⚠️ 警告: {error_context} - 参数 '{name}' 值为字典，但未找到 'description' 字符串。跳过。字典: {desc_value}")
                    continue
            else:
                print(f"❌ 错误: {error_context} - 参数 '{name}' 值类型不受支持。跳过。值: {desc_value}")
                continue

            new_param = {
                "name": name,
                "type": "string",
                "description": description_str,
                "required": False,
                "default_value": None,
                "options": []
            }

            is_required = f":{name}" in path_template_key and f":{name}?" not in path_template_key
            new_param["required"] = is_required

            option_matches = re.findall(r"[`'](.*?)['`]\s*即\s*([^,，\s或]+)", description_str)
            options_map = {}
            for value, desc in option_matches:
                new_param["options"].append({"value": value, "description": desc})
                options_map[desc] = value
            
            default_match = re.search(r"[，,]?\s*默认为(.*?)(?:[，,]|$)", description_str)
            if default_match:
                default_text = default_match.group(1).strip()
                # --- 新增：清理包裹的引号或反引号 ---
                default_text = default_text.strip("`'\"") 
                
                if options_map and default_text in options_map:
                    new_param["default_value"] = options_map[default_text]
                else:
                    new_param["default_value"] = default_text

            clean_desc = re.sub(r"[,，]?\s*可选.*$", "", description_str).strip()
            clean_desc = re.sub(r"[,，]?\s*默认为.*$", "", clean_desc).strip()
            new_param["description"] = clean_desc

            parsed_params.append(new_param)

        except Exception as e:
            print(f"❌ 严重错误: {error_context} - 处理参数 '{name}' 时发生未知错误。")
            print(f"   错误详情: {e}")
            continue
            
    return parsed_params

def transform_rsshub_data(source_data: dict) -> list:
    """
    将原始RSSHub路由元数据字典转换为 DataSourceDefinition 列表。
    """
    all_providers = []
    
    for provider_id, provider_data in source_data.items():
        
        # --- 更新：提取 Provider 级别的详细信息 ---
        provider_name = provider_data.get("name", provider_id.capitalize())
        provider_desc_raw = provider_data.get("description")
        
        # 如果描述为空或不存在，则使用默认值
        if not provider_desc_raw:
             provider_desc = f"来自 {provider_name} 的数据源。"
        else:
             provider_desc = clean_description(provider_desc_raw)

        new_provider = {
            "provider_id": provider_id,
            "provider_name": provider_name,
            "provider_description": provider_desc,
            "provider_url": provider_data.get("url"), # 新增
            "provider_categories": provider_data.get("categories", []), # 新增
            "provider_lang": provider_data.get("lang"), # 新增
            "routes": []
        }
        # --- Provider 级别信息提取完毕 ---
        
        source_routes = provider_data.get("routes", {})
        routes_by_location = {}
        
        for path_key, route_data in source_routes.items():
            
            error_context = f"[Provider: {provider_id}, Route: {path_key}]"

            location = route_data.get("location")
            if not location:
                location = path_key 
            
            if location not in routes_by_location:
                path_field = route_data.get("path")
                paths = []
                if isinstance(path_field, list):
                    paths.extend(path_field)
                elif path_field:
                    paths.append(path_field)
                else:
                    paths.append(path_key)
                
                # --- 更新：提取 Route 级别的详细信息 ---
                routes_by_location[location] = {
                    "route_id": f"{provider_id}_{location.replace('.ts', '').replace('/', '_')}",
                    "path_template": paths,
                    "name": route_data.get("name"),
                    "description": clean_description(route_data.get("description", "")),
                    "categories": route_data.get("categories", []),
                    "example_path": route_data.get("example"),
                    "route_url": route_data.get("url"), # 新增
                    "features": route_data.get("features", {}), # 新增
                    "parameters": parse_parameters(
                        route_data.get("parameters", {}), 
                        path_key,
                        error_context
                    )
                }
            else:
                pass
        
        for route_def in routes_by_location.values():
            new_provider["routes"].append(route_def)
            
        all_providers.append(new_provider)
        
    return all_providers

# --- 主执行逻辑 ---
if __name__ == "__main__":
    
        # 1. 输入数据：您提供的 RSSHub 元数据示例
    with open("./routes.json", 'r', encoding='utf-8') as f:
        rsshub_data = json.load(f)

    # 2. 执行转换
    print("正在转换 RSSHub 元数据...")
    transformed_data = transform_rsshub_data(rsshub_data)
    
    # 3. 定义输出文件名
    output_filename = "datasource_definitions.json"
    
    # 4. 保存到文件
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(transformed_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 成功！转换后的数据已保存到: {os.path.abspath(output_filename)}")
        
        # 5. (可选) 打印 '81' 提供商的结果以供检查
        # print("\n--- '81' 提供商转换结果预览 ---")
        # for provider in transformed_data:
        #     if provider["provider_id"] == "81":
        #         print(json.dumps(provider, ensure_ascii=False, indent=2))
        
    except IOError as e:
        print(f"❌ 错误：无法写入文件 {output_filename}. {e}")
    except Exception as e:
        print(f"❌ 转换过程中发生未知错误: {e}")