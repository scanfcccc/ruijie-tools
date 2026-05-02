# bookstack-importer.py — BookStack HTML 批量导入

将 HTML 文档批量上传到 BookStack 知识库。支持自动创建/匹配书本和页面，带重试和日志。

## 功能

- 自动创建或匹配已存在的 BookStack 书本
- 递归扫描 HTML 文件
- 按目录结构自动创建章节和页面
- 失败自动重试（最多 3 次）

## 用法

```bash
pip install requests beautifulsoup4 chardet
python bookstack-importer.py
```

## 配置

脚本顶部可修改：API 地址、令牌、目标书本名、源文件目录。

## 依赖

- `requests` — API 调用
- `beautifulsoup4` — HTML 解析
- `chardet` — 编码检测
