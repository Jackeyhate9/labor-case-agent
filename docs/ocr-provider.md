# OCR Provider

路由按文件类型选择：TXT/CSV 直接解析，DOCX 读取段落与表格，PDF 先提取文本并按页保存，图片交给 RapidOCR。所有输出保存页码、区域、engine、原文和置信度。

图片 OCR 依赖首次安装/模型初始化可能较慢。失败时证据状态保留为 failed，API 返回具体原因，用户可人工录入原文。Mock OCR 只允许测试环境使用，端到端样例截图必须调用真实 OCR provider。

