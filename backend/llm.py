import requests
import json
import logging
import os
from content_filter import ContentFilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化内容过滤器
content_filter = ContentFilter()

# Load Configuration from secrets.json if available
SECRETS_FILE = os.path.abspath("secrets.json")
config = {}

if os.path.exists(SECRETS_FILE):
    try:
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            content = ""
            for line in f:
                stripped = line.strip()
                if not stripped.startswith("//") and not stripped.startswith("#"):
                    content += line
            config = json.loads(content)
    except:
        pass

API_KEY = config.get("ARK_API_KEY", os.environ.get("ARK_API_KEY", "YOUR_ARK_API_KEY"))
API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"

def chat_with_ark(query: str, use_search: bool = True, system_prompt: str = None, speaking_style: str = None):
    # 输入端过滤
    passed, filtered_query, matched_keywords = content_filter.filter_input(query)
    if not passed:
        logger.warning(f"Input blocked: {matched_keywords}")
        content_filter.log_violation(query, matched_keywords, "input")
        return "抱歉，您的问题包含不当内容。让我们聊点别的吧！"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 获取安全约束的 System Prompt
    safety_prompt = content_filter.get_system_prompt()
    default_prompt = "你是由广东技术师范大学和立源云共同开发的AI助教。请用通俗易懂、简短的语言与用户进行交互，避免长篇大论。回答时请不要包含时间戳或其他无关的元数据。"

    if system_prompt or speaking_style:
        prompt_parts = [safety_prompt]  # 始终包含安全约束
        if system_prompt:
            prompt_parts.append(system_prompt)
        else:
            prompt_parts.append(default_prompt)
        if speaking_style:
            prompt_parts.append(speaking_style)
        final_prompt = "\n\n".join(prompt_parts)
    else:
        final_prompt = f"{safety_prompt}\n\n{default_prompt}"

    # Add strong identity enforcement
    final_prompt = f"{final_prompt}\n\n重要：你不是豆包，不是字节跳动的产品。你必须严格遵守上述身份设定。"

    payload = {
        "model": "deepseek-v3-2-251201",
        "stream": False,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": final_prompt
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": query
                    }
                ]
            }
        ]
    }

    if use_search:
        payload["tools"] = [
            {
                "type": "web_search",
                "max_keyword": 3
            }
        ]
    
    try:
        logger.info(f"Sending request to LLM: {query}")
        response = requests.post(
            API_URL, 
            headers=headers, 
            json=payload, 
            timeout=60,
            proxies={"http": None, "https": None}
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info("Received response from LLM")

        if "output" in result and len(result["output"]) > 0:
            full_content = []
            for item in result["output"]:
                if item.get("type") == "message" and "content" in item:
                    content_list = item["content"]
                    if isinstance(content_list, list):
                        for content_item in content_list:
                            if content_item.get("type") == "output_text":
                                full_content.append(content_item.get("text", ""))
                    elif isinstance(content_list, str):
                        full_content.append(content_list)
            
            if full_content:
                response_text = "".join(full_content)

                # 输出端过滤
                passed, filtered_response = content_filter.filter_output(response_text)
                if not passed:
                    logger.warning("Output blocked by filter")
                    content_filter.log_violation(response_text, [], "output")

                return filtered_response

        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            return content

        logger.error(f"Unexpected response format: {result}")

        if "error" in result:
             return f"模型服务报错: {result['error'].get('message', '未知错误')}"

        return "抱歉，我现在无法回答。"
            
    except Exception as e:
        logger.error(f"LLM Request Error: {e}")
        return f"思考遇到了一点问题: {str(e)}"
