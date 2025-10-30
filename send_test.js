// 我们不再需要 'rsshub' 包，因为它似乎存在导入问题。
// 我们将使用 Node.js 内置的 'fetch' API 来直接调用 RSSHub 实例。

const instanceUrl = 'http://localhost:1200/';
const route = 'bilibili/user/followings/475310928/475310928';

// 关键：我们直接向 RSSHub 实例请求 JSON 格式的数据
// 通过添加 ?format=json 查询参数
const url = `${instanceUrl}${route}?format=json`;

console.log(`正在从 ${url} 请求数据...`);

// 使用 fetch (Node.js v18+ 已内置) 来发起请求
fetch(url)
  .then((response) => {
    // 检查请求是否成功
    if (!response.ok) {
      throw new Error(`HTTP 错误! 状态: ${response.status}`);
    }
    // 将响应解析为 JSON
    return response.json();
  })
  .then((data) => {
    // 请求成功！
    console.log("✅ 数据获取成功!");
    
    // 打印订阅源的标题 (JSON 格式的字段)
    console.log(`   订阅源标题: ${data.title}`);
    
    // 打印最新一条内容的标题
    // 注意：RSSHub 的 JSON 格式使用 'items' 数组
    if (data.items && data.items.length > 0) { 
      console.log(data.items);
    } else {
      console.log("   (订阅源中暂时没有内容)");
    }
  })
  .catch((e) => {
    // 请求失败
    console.error("❌ 请求失败: ", e.message);
  });

