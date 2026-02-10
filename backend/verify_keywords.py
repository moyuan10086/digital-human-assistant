"""
验证关键词加载数量
"""

from content_filter import ContentFilter
import sys
from io import StringIO

# 捕获所有打印输出
old_stdout = sys.stdout
sys.stdout = StringIO()

# 初始化过滤器
filter = ContentFilter(use_lexicon=True)

# 恢复输出
captured_output = sys.stdout.getvalue()
sys.stdout = old_stdout

# 显示实际加载的关键词数量
print("=" * 60)
print("关键词加载验证")
print("=" * 60)

total = 0
for category, keywords in filter.keywords.items():
    count = len(keywords)
    total += count
    print(f"{category:15s}: {count:>7,} 个关键词")

print("-" * 60)
print(f"{'总计':15s}: {total:>7,} 个关键词")
print("=" * 60)
