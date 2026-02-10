"""
内容安全过滤模块
提供输入/输出双重过滤机制，防止违规内容
"""

import re
import json
import os
from typing import Tuple, List, Dict
from enum import Enum

# 尝试导入 Sensitive-lexicon 加载器
try:
    from sensitive_lexicon_loader import SensitiveLexiconLoader
    LEXICON_AVAILABLE = True
except ImportError:
    LEXICON_AVAILABLE = False
    print("警告: Sensitive-lexicon 加载器不可用，将使用默认关键词库")


class FilterLevel(Enum):
    """过滤级别"""
    LOW = 1      # 低风险
    MEDIUM = 2   # 中风险
    HIGH = 3     # 高风险
    BLOCKED = 4  # 直接拦截


class ContentFilter:
    """内容安全过滤器"""

    def __init__(self, config_file: str = "filter_config.json", use_lexicon: bool = True):
        """
        初始化过滤器

        Args:
            config_file: 过滤配置文件路径
            use_lexicon: 是否使用 Sensitive-lexicon 词库
        """
        self.config_file = config_file
        self.use_lexicon = use_lexicon and LEXICON_AVAILABLE
        self.keywords = self._load_keywords()

    def _load_keywords(self) -> Dict[str, List[str]]:
        """
        加载关键词库
        参考腾讯云天御和 OpenAI Moderation API 的分类标准
        """
        # 默认关键词库
        default_keywords = {
            # 1. 色情内容 (Sexual Content)
            "sexual": [
                # 中文
                "色情", "黄色", "裸体", "性交", "做爱", "淫秽", "性爱", "情色",
                "脱衣", "露点", "三级片", "成人片", "AV", "毛片", "黄片",
                "性器官", "生殖器", "私处", "下体", "胸部", "乳房",
                "性服务", "援交", "卖淫", "嫖娼", "性交易", "包养",
                "一夜情", "约炮", "开房", "419", "磁力链接",
                # English
                "porn", "pornography", "sex", "sexual", "nude", "naked", "xxx",
                "adult", "erotic", "nsfw", "hentai", "explicit",
                "prostitution", "escort", "hookup", "onlyfans"
            ],

            # 2. 暴力内容 (Violence)
            "violence": [
                # 中文
                "暴力", "杀人", "谋杀", "屠杀", "血腥", "虐待", "酷刑",
                "砍头", "斩首", "枪击", "爆炸", "恐怖袭击", "恐怖分子",
                "绑架", "劫持", "人质", "枪支", "炸弹", "武器",
                "打架", "斗殴", "殴打", "伤害", "残害", "折磨",
                # English
                "murder", "kill", "killing", "violence", "violent", "terror",
                "terrorist", "bomb", "explosion", "gun", "weapon", "torture",
                "abuse", "assault", "attack", "bloody", "gore"
            ],

            # 3. 自残/自杀 (Self-harm)
            "self_harm": [
                # 中文
                "自杀", "自残", "自我伤害", "割腕", "跳楼", "上吊",
                "服毒", "轻生", "寻死", "想死", "不想活", "活不下去",
                "厌世", "抑郁", "绝望", "了结生命",
                # English
                "suicide", "self-harm", "self harm", "cut myself", "kill myself",
                "end my life", "want to die", "suicidal", "depressed"
            ],

            # 4. 仇恨言论 (Hate Speech)
            "hate": [
                # 中文
                "歧视", "种族歧视", "性别歧视", "地域歧视",
                "仇恨", "仇视", "排斥", "侮辱", "辱骂", "诽谤",
                "贬低", "嘲笑", "讽刺", "攻击", "人身攻击",
                # English
                "hate", "hatred", "racist", "racism", "discrimination",
                "sexist", "homophobic", "xenophobic", "bigot", "slur"
            ],

            # 5. 骚扰/威胁 (Harassment)
            "harassment": [
                # 中文
                "骚扰", "威胁", "恐吓", "勒索", "敲诈", "报复",
                "人肉搜索", "曝光隐私", "泄露信息", "网络暴力",
                "跟踪", "尾随", "偷拍", "偷窥",
                # English
                "harassment", "harass", "threaten", "threat", "blackmail",
                "dox", "doxxing", "stalk", "stalking", "bully", "bullying"
            ],

            # 6. 违法犯罪 (Illegal Activities)
            "illegal": [
                # 中文
                "毒品", "吸毒", "贩毒", "大麻", "海洛因", "冰毒", "摇头丸",
                "赌博", "赌场", "赌博网站", "博彩", "六合彩",
                "诈骗", "骗钱", "传销", "非法集资", "庞氏骗局",
                "洗钱", "走私", "贩卖", "黑市", "地下交易",
                "盗窃", "抢劫", "偷窃", "盗版", "侵权",
                "假证", "假币", "伪造", "造假", "假货",
                # English
                "drug", "drugs", "cocaine", "heroin", "marijuana", "meth",
                "gambling", "casino", "bet", "lottery", "illegal",
                "fraud", "scam", "ponzi", "pyramid scheme",
                "money laundering", "smuggling", "counterfeit", "fake"
            ],

            # 7. 政治敏感 (Political Sensitive)
            "political": [
                # 注意：此类别需要根据部署地区的法律法规进行配置
                # 以下仅为框架示例，实际使用时需要替换为符合当地法规的内容

                # 政治相关
                "政治敏感", "政治话题", "政治立场", "政治观点",
                "政府批评", "政权", "体制", "制度批评",

                # 宗教相关
                "宗教冲突", "宗教极端", "邪教", "异端",

                # 社会敏感话题
                "社会动荡", "游行", "示威", "抗议", "罢工",
                "革命", "起义", "暴动", "叛乱",

                # English
                "political", "politics", "government criticism",
                "regime", "revolution", "protest", "demonstration"
            ],

            # 8. 儿童安全 (Child Safety)
            "child_safety": [
                # 中文
                "儿童色情", "恋童", "未成年", "幼女", "萝莉",
                "儿童性侵", "儿童虐待", "拐卖儿童",
                # English
                "child porn", "child abuse", "pedophile", "underage",
                "loli", "lolita", "child exploitation"
            ],

            # 9. 欺诈/诱导 (Fraud/Deception)
            "fraud": [
                # 中文
                "刷单", "刷信誉", "刷好评", "虚假宣传",
                "钓鱼网站", "钓鱼链接", "木马", "病毒",
                "诱导点击", "诱导下载", "诱导支付", "诱导转账",
                "免费领取", "中奖", "抽奖", "返利", "高额回报",
                # English
                "phishing", "malware", "virus", "trojan", "scam",
                "fake", "fraud", "deception", "misleading"
            ],

            # 10. 垃圾信息 (Spam)
            "spam": [
                # 中文
                "广告", "推广", "加微信", "加QQ", "联系方式",
                "代办", "代理", "招聘", "兼职", "刷单",
                "贷款", "信用卡", "办证", "发票",
                # English
                "spam", "advertisement", "promotion", "contact me"
            ]
        }

        # 如果启用 Sensitive-lexicon，加载词库
        if self.use_lexicon:
            try:
                loader = SensitiveLexiconLoader()
                lexicon_keywords = loader.load_all()

                # 合并 Sensitive-lexicon 词库
                for category, words in lexicon_keywords.items():
                    if category in default_keywords:
                        default_keywords[category].extend(words)
                    else:
                        default_keywords[category] = words

                print(f"[OK] 已加载 Sensitive-lexicon 词库")
            except Exception as e:
                print(f"加载 Sensitive-lexicon 失败: {e}")

        # 尝试从配置文件加载
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    custom_keywords = json.load(f)
                    # 合并自定义关键词
                    for category, words in custom_keywords.items():
                        if category in default_keywords:
                            default_keywords[category].extend(words)
                        else:
                            default_keywords[category] = words
            except Exception as e:
                print(f"加载自定义关键词失败: {e}")

        return default_keywords

    def filter_input(self, text: str) -> Tuple[bool, str, List[str]]:
        """
        输入端过滤：检查用户输入是否包含违规内容

        Args:
            text: 用户输入文本

        Returns:
            (是否通过, 过滤后的文本, 命中的关键词列表)
        """
        if not text:
            return True, text, []

        text_lower = text.lower()
        matched_keywords = []
        blocked_categories = []

        # 检查每个类别的关键词
        for category, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    matched_keywords.append(keyword)
                    if category not in blocked_categories:
                        blocked_categories.append(category)

        # 如果命中高风险类别，直接拦截
        high_risk_categories = [
            "sexual",        # 色情
            "violence",      # 暴力
            "self_harm",     # 自残/自杀
            "illegal",       # 违法犯罪
            "child_safety"   # 儿童安全
        ]
        if any(cat in blocked_categories for cat in high_risk_categories):
            # 记录违规日志
            self.log_violation(text, matched_keywords, "input")
            return False, "", matched_keywords

        # 如果命中中低风险类别，记录但不拦截
        if matched_keywords:
            self.log_violation(text, matched_keywords, "input_warning")

        # 通过检查
        return True, text, matched_keywords

    def filter_output(self, text: str) -> Tuple[bool, str]:
        """
        输出端过滤：检查 AI 输出是否包含违规内容

        Args:
            text: AI 输出文本

        Returns:
            (是否通过, 过滤后的文本)
        """
        if not text:
            return True, text

        passed, _, _ = self.filter_input(text)

        if not passed:
            # 返回安全的默认回复
            return False, "抱歉，我无法回答这个问题。让我们聊点别的吧。"

        return True, text

    def get_system_prompt(self) -> str:
        """
        获取用于约束 LLM 行为的 System Prompt

        Returns:
            System Prompt 文本
        """
        return """你是一个友好、安全、负责任的 AI 助手。请严格遵守以下规则：

1. 内容安全规则：
   - 禁止生成任何色情、淫秽、暴力、血腥内容
   - 禁止生成涉及政治敏感话题的内容
   - 禁止生成涉及毒品、赌博、诈骗等违法内容
   - 禁止生成可能引发恐慌、仇恨、歧视的内容

2. 行为准则：
   - 拒绝回答任何违规问题，礼貌地引导用户转换话题
   - 不要试图绕过安全限制或提供规避方法
   - 保持积极、正面、健康的对话氛围
   - 如果用户多次尝试违规提问，温和地提醒用户遵守规则

3. 回复风格：
   - 友好、自然、有温度
   - 简洁明了，避免冗长
   - 适当使用表情符号增加亲和力

当遇到违规问题时，使用类似以下的回复：
- "抱歉，我无法回答这个问题。我们聊点别的吧！"
- "这个话题不太合适，换个话题怎么样？"
- "让我们聊些更有意义的事情吧！"
"""

    def log_violation(self, text: str, matched_keywords: List[str], source: str = "input"):
        """
        记录违规日志

        Args:
            text: 违规文本
            matched_keywords: 命中的关键词
            source: 来源（input/output）
        """
        log_entry = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "source": source,
            "matched_keywords": matched_keywords,
            "text_preview": text[:50] + "..." if len(text) > 50 else text
        }

        # 写入日志文件（使用绝对路径）
        log_file = os.path.join(os.path.dirname(__file__), "content_filter.log")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"写入日志失败: {e}")

