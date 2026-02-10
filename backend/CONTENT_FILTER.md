# 内容安全过滤系统文档

## 📋 概述

本系统实现了 Input/Output 双重过滤机制，确保数字人对话系统的内容安全。

### 核心功能

1. **输入端过滤** - 检测用户输入的违规内容
2. **输出端过滤** - 检测 AI 输出的违规内容
3. **System Prompt 约束** - 通过提示词约束 LLM 行为
4. **违规日志记录** - 记录所有违规尝试
5. **多模式支持** - 支持文字聊天、语音识别、Phone 实时对话三种模式

---

## 🏗️ 系统架构

### 双重过滤机制

```
用户输入 → 输入端过滤 → LLM 处理 → 输出端过滤 → 返回结果
    ↓              ↓                          ↓
 关键词检测    System Prompt            关键词检测
    ↓              ↓                          ↓
 违规拦截      行为约束                  违规拦截
```

### 过滤级别

- **LOW (低风险)** - 记录但不拦截
- **MEDIUM (中风险)** - 警告并记录
- **HIGH (高风险)** - 拦截并记录
- **BLOCKED (直接拦截)** - 立即拦截

---

## 📁 文件结构

```
backend/
├── content_filter.py              # 内容过滤核心模块
├── sensitive_lexicon_loader.py    # Sensitive-lexicon 词库加载器
├── Sensitive-lexicon/             # 敏感词库（需克隆）
│   └── Vocabulary/                # 词库文件目录
├── filter_config.json.example     # 配置文件示例
├── filter_config.json             # 实际配置（需自行创建）
├── content_filter.log             # 违规日志（自动生成）
└── llm.py                         # 已集成过滤器
```

---

## 🚀 快速开始

### 1. 克隆 Sensitive-lexicon 词库（推荐）

本系统已集成 [Sensitive-lexicon](https://github.com/konsheng/Sensitive-lexicon) 敏感词库，提供 **70,000+ 敏感词**，覆盖政治、色情、暴力等领域。

```bash
cd backend
git clone https://github.com/konsheng/Sensitive-lexicon.git
```

**词库统计**：
- 政治敏感: 7,500+ 关键词
- 色情内容: 600+ 关键词
- 暴力恐怖: 650+ 关键词
- 违法犯罪: 14,600+ 关键词
- 其他类别: 50,000+ 关键词

### 2. 创建配置文件

复制示例配置文件：

```bash
cd backend
cp filter_config.json.example filter_config.json
```

### 2. 创建配置文件

复制示例配置文件：

```bash
cd backend
cp filter_config.json.example filter_config.json
```

### 3. 配置关键词库

编辑 `filter_config.json`，添加需要过滤的关键词：

```json
{
  "sexual": ["敏感词1", "敏感词2"],
  "violence": ["暴力词1", "暴力词2"],
  "political": ["政治敏感词"],
  "illegal": ["违法词1", "违法词2"]
}
```

**注意**：如果已克隆 Sensitive-lexicon，系统会自动加载词库，无需手动配置大量关键词。

### 4. 系统自动启用

过滤系统已集成到以下模块，无需额外配置即可使用：
- **文字聊天** - `llm.py` 模块
- **语音识别对话** - ASR 模式
- **Phone 实时对话** - `main.py` WebSocket 处理

---

## 🔧 使用方法

### 基本使用

过滤器已自动集成到 LLM 模块，调用 `chat_with_ark()` 时自动启用：

```python
from llm import chat_with_ark

# 正常调用，自动过滤
response = chat_with_ark("用户问题")
```

### 独立使用过滤器

如需在其他模块使用过滤器：

```python
from content_filter import ContentFilter

# 初始化过滤器（默认启用 Sensitive-lexicon）
filter = ContentFilter(use_lexicon=True)

# 或者禁用 Sensitive-lexicon，仅使用默认词库
# filter = ContentFilter(use_lexicon=False)

# 输入过滤
passed, filtered_text, keywords = filter.filter_input("用户输入")
if not passed:
    print(f"输入被拦截，命中关键词: {keywords}")

# 输出过滤
passed, filtered_text = filter.filter_output("AI输出")
if not passed:
    print("输出被拦截")

# 获取 System Prompt
system_prompt = filter.get_system_prompt()
```

---

## 📝 配置说明

### 关键词分类

参考腾讯云天御和 OpenAI Moderation API 的分类标准，系统包含 10 大类别：

#### 默认词库（内置）

| 分类 | 说明 | 关键词数量 | 风险级别 |
|------|------|-----------|----------|
| `sexual` | 色情、淫秽内容 | 50+ | HIGH |
| `violence` | 暴力、血腥、恐怖内容 | 30+ | HIGH |
| `self_harm` | 自残、自杀相关内容 | 20+ | HIGH |
| `hate` | 仇恨言论、歧视内容 | 20+ | MEDIUM |
| `harassment` | 骚扰、威胁、恐吓 | 20+ | MEDIUM |
| `illegal` | 违法犯罪活动 | 40+ | HIGH |
| `political` | 政治敏感话题 | 框架示例 | MEDIUM |
| `child_safety` | 儿童安全相关 | 15+ | HIGH |
| `fraud` | 欺诈、诱导行为 | 20+ | MEDIUM |
| `spam` | 垃圾信息、广告 | 15+ | LOW |

**默认词库总计**: 250+ 关键词，中英文双语支持

#### Sensitive-lexicon 词库（可选）

如果克隆了 Sensitive-lexicon 仓库，系统会自动加载以下词库：

| 分类 | 说明 | 关键词数量 | 来源文件 |
|------|------|-----------|----------|
| `political` | 政治敏感话题 | 7,500+ | 政治类型.txt, 反动词库.txt, GFW补充词库.txt 等 |
| `sexual` | 色情内容 | 600+ | 色情词库.txt, 色情类型.txt |
| `violence` | 暴力恐怖 | 650+ | 暴恐词库.txt, 涉枪涉爆.txt |
| `illegal` | 违法犯罪 | 14,600+ | 非法网址.txt |
| `spam` | 垃圾信息 | 120+ | 广告类型.txt |
| `other` | 其他类别 | 50,000+ | 补充词库.txt, 网易前端过滤敏感词库.txt 等 |

**Sensitive-lexicon 总计**: 73,000+ 关键词

### 过滤策略详解

系统采用**分级过滤策略**，根据风险等级采取不同的处理方式。

#### 1️⃣ 高风险类别（直接拦截）

以下类别命中后会**立即拦截**，不允许通过：

| 类别 | 说明 | 处理方式 |
|------|------|---------|
| `sexual` | 色情、淫秽内容 | 直接拦截 + 记录日志 |
| `violence` | 暴力、血腥、恐怖内容 | 直接拦截 + 记录日志 |
| `self_harm` | 自残、自杀相关内容 | 直接拦截 + 记录日志 |
| `illegal` | 违法犯罪活动 | 直接拦截 + 记录日志 |
| `child_safety` | 儿童安全相关 | 直接拦截 + 记录日志 |

**拦截效果**：
- 输入端：返回 `(False, "", matched_keywords)`，用户输入被拒绝
- 输出端：返回 `(False, "抱歉，我无法回答这个问题。让我们聊点别的吧。")`

#### 2️⃣ 中低风险类别（仅记录，不拦截）

以下类别命中后**不会拦截**，但会记录到日志供人工审核：

| 类别 | 说明 | 处理方式 |
|------|------|---------|
| `political` | 政治敏感话题 | 通过 + 记录日志 |
| `hate` | 仇恨言论、歧视内容 | 通过 + 记录日志 |
| `harassment` | 骚扰、威胁、恐吓 | 通过 + 记录日志 |
| `fraud` | 欺诈、诱导行为 | 通过 + 记录日志 |
| `spam` | 垃圾信息、广告 | 通过 + 记录日志 |

**通过效果**：
- 输入端：返回 `(True, text, matched_keywords)`，允许继续处理
- 输出端：返回 `(True, text)`，正常输出内容

#### 3️⃣ 为什么这样设计？

**避免过度拦截**：
- 政治敏感词如果全部拦截，会导致正常新闻讨论、历史学习、政治学科内容无法进行
- 用户体验会极差，系统可用性大幅下降

**分级管理的优势**：
- **高风险**：色情、暴力、违法 → 零容忍，直接拦截
- **中风险**：政治、仇恨言论 → 记录日志，人工审核
- **低风险**：垃圾信息 → 仅记录，不影响使用

**实际案例**：

| 输入内容 | 命中类别 | 是否拦截 | 原因 |
|---------|---------|---------|------|
| "你好，今天天气怎么样？" | 无 | ❌ 不拦截 | 正常对话 |
| "习近平" | `political` | ❌ 不拦截 | 中风险，仅记录 |
| "色情内容" | `sexual` | ✅ 拦截 | 高风险，直接拦截 |
| "暴力恐怖" | `violence` | ✅ 拦截 | 高风险，直接拦截 |
| "法轮功" | `political` | ❌ 不拦截 | 中风险，仅记录 |
| "赌博网站" | `illegal` | ✅ 拦截 | 高风险，直接拦截 |

### System Prompt 约束

系统会自动在每次 LLM 调用时添加安全约束提示词，包括：

1. **内容安全规则** - 禁止生成违规内容
2. **行为准则** - 拒绝违规问题并引导话题
3. **回复风格** - 友好、正面、健康

---

## 🔍 工作原理

### 文字聊天模式过滤流程

```python
def filter_input(text: str) -> Tuple[bool, str, List[str]]:
    1. 将文本转为小写
    2. 遍历所有关键词库
    3. 检测是否命中关键词
    4. 判断风险级别
    5. 返回过滤结果
```

### Phone 实时对话模式过滤流程

```
用户语音 → ASR识别 → 输入过滤 → 实时对话API → 输出过滤 → 返回结果
              ↓           ↓                           ↓
          文本结果    关键词检测                  关键词检测
              ↓           ↓                           ↓
                     违规拦截                    违规拦截
```

**Phone 模式特点**：
- 在 ASR 识别结果处进行输入过滤
- 在 AI 响应保存前进行输出过滤
- 违规内容不会进入对话历史
- 所有违规尝试记录到日志（source: `phone_input` / `phone_output`）

### 输出端过滤流程

```python
def filter_output(text: str) -> Tuple[bool, str]:
    1. 调用输入过滤逻辑
    2. 如果命中违规词，返回安全回复
    3. 否则返回原始内容
```

---

## 📊 日志记录

### 日志格式

违规日志保存在 `content_filter.log`，每行一条 JSON 记录：

```json
{
  "timestamp": "2026-02-10T15:30:00",
  "source": "input",
  "matched_keywords": ["敏感词1", "敏感词2"],
  "text_preview": "违规文本前50字..."
}
```

### 日志字段说明

- `timestamp` - 时间戳
- `source` - 来源
  - `input` - 文字聊天输入
  - `output` - 文字聊天输出
  - `phone_input` - Phone 模式用户语音输入
  - `phone_output` - Phone 模式 AI 响应输出
- `matched_keywords` - 命中的关键词列表
- `text_preview` - 文本预览（最多50字）

---

## ⚠️ 注意事项

### 1. 配置文件安全

- `filter_config.json` 已添加到 `.gitignore`
- 不要将敏感关键词提交到公开仓库
- 定期更新关键词库

### 2. 性能考虑

- 关键词数量建议控制在 1000 个以内
- 过多关键词会影响响应速度
- 可考虑使用正则表达式优化匹配

### 3. 误判处理

- 定期检查日志，识别误判情况
- 调整关键词库，减少误判
- 可添加白名单机制（未来功能）

---

## 🛠️ 高级配置

### 自定义过滤级别

可以扩展 `ContentFilter` 类，实现自定义过滤逻辑：

```python
class CustomFilter(ContentFilter):
    def filter_input(self, text: str):
        # 自定义逻辑
        passed, filtered, keywords = super().filter_input(text)
        # 添加额外检查
        return passed, filtered, keywords
```

### 集成第三方服务

可以集成第三方内容审核 API：

```python
# 示例：集成阿里云内容安全
def check_with_aliyun(text: str):
    # 调用阿里云 API
    pass
```

---

## 📈 未来优化

### 计划功能

1. **机器学习模型** - 使用 ML 模型提升检测准确率
2. **白名单机制** - 允许特定上下文的敏感词
3. **动态更新** - 支持热更新关键词库
4. **多语言支持** - 支持英文、日文等多语言过滤
5. **风险评分** - 为每条内容计算风险分数


