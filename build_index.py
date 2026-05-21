"""
构建预编译 BM25 索引（docs.json）
"""
import os
import json
import re
import jieba
from rank_bm25 import BM25Okapi

jieba.setLogLevel(jieba.logging.INFO)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "docs.json")

def tokenize(text):
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]", " ", text)
    return [w.strip() for w in jieba.cut(text) if w.strip() and len(w.strip()) > 1]

docs = []
for f in os.listdir(DATA_DIR):
    if not f.endswith(".md"):
        continue
    path = os.path.join(DATA_DIR, f)
    with open(path, "r", encoding="utf-8") as fp:
        content = fp.read()
    lines = content.split("\n")
    title = lines[0].strip().lstrip("#").strip() if lines else f.replace(".md", "")
    docs.append({"title": title, "content": content, "source": f})
    print(f"  加载: {f}")

tokenized = [tokenize(d["content"]) for d in docs]
print(f"共 {len(tokenized)} 篇文档")

bm25 = BM25Okapi(tokenized)

# 保存
index_data = {"docs": docs, "tokenized": tokenized}
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(index_data, f, ensure_ascii=False)

print(f"\n索引构建完成：{len(docs)} 篇文档 → {OUTPUT_FILE}")
