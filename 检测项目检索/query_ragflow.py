import requests
import json

# 定义 API URL 和请求头
url = "http://42.121.223.225/v1/chunk/retrieval_test"  #  Ragflow API 的实际 URL

# 在 headers 中加入 API 密钥或令牌
headers = {
"Authorization": "ImM0ODVjOGY0ZjljNDExZjA5OGZiMDI0MmFjMTIwMDA2Ig.aXXPCw.ZDvgy2CvLU8hApl6RlBpj3JsEfs",    # 实际的 API 密钥
    "Content-Type": "application/json"
}

data = {
    "kb_id": "4793322ff5f611f0a2d30242ac120006",  # 实际的知识库 ID
    "question": "婴儿配方食品检验项目"  # 输入你要查询的问题
}

# 发起 POST 请求
try:
    # 显式禁用代理，这样即使开启梯子，请求也会直接走本地网络访问国内服务器
    proxies = {
        "http": None,
        "https": None,
    }
    response = requests.post(url, json=data, headers=headers, proxies=proxies)
    
    # 打印响应状态码和原始内容
    print(f"状态码: {response.status_code}")
    print(f"响应头: {response.headers}")
    print(f"原始响应内容（前500字符）: {response.text[:500]}")
    print("=" * 80)
    
    # 检查 HTTP 状态码
    if response.status_code != 200:
        print(f"\n❌ 请求失败！")
        print(f"状态码: {response.status_code}")
        if response.status_code == 502:
            print("错误类型: Bad Gateway - 服务器暂时无法访问")
            print("可能的原因:")
            print("  1. Ragflow 服务器可能正在维护或重启")
            print("  2. 网络连接问题")
            print("  3. API 端点配置错误")
            print("\n建议: 请稍后重试或检查 API 服务器状态")
        elif response.status_code == 401:
            print("错误类型: Unauthorized - 授权失败")
            print("建议: 请检查 API 密钥是否正确")
        elif response.status_code == 404:
            print("错误类型: Not Found - 端点不存在")
            print("建议: 请检查 API URL 是否正确")
        print(f"\n完整响应内容:\n{response.text}")
        exit(1)
    
    # 尝试解析 JSON
    result = response.json()
    
    # 检查响应结构
    if 'data' in result and 'chunks' in result['data']:
        chunks = result['data']['chunks']
        print(f"\n✅ 成功获取 {len(chunks)} 个数据片段")
        print("=" * 80)
        
        # 获取前5个数据片段并对第一个 HTML 表格进行标记
        for i, chunk in enumerate(chunks[:5]):  # 获取前5个片段
            print(f"\n【Chunk {i + 1}】")
            print(f"ID: {chunk['chunk_id']}")
            content = chunk['content_with_weight']

            # 查找第一个 <table> 标签，并在其之前添加标记
            if "<table>" in content:
                content = content.replace("<table>", "\n**📋 标记: 第一个 HTML 表格开始**\n<table>", 1)

            print(f"内容:\n{content}")
            print("-" * 80)
    else:
        print("\n⚠️ 响应格式不符合预期")
        print("错误: 响应中没有预期的 'data' 或 'chunks' 字段")
        print(f"完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
except requests.exceptions.JSONDecodeError as e:
    print(f"\n❌ JSON 解码错误: {e}")
    print(f"响应文本: {response.text}")
except requests.exceptions.RequestException as e:
    print(f"\n❌ 请求异常: {e}")
except Exception as e:
    print(f"\n❌ 发生未知错误: {type(e).__name__}: {e}")
