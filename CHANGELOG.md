# Changelog

All notable changes to Spark will be documented in this file.

## [0.3.0] - 2026-06-07

### Added
- **知识图谱引擎**：被动自动建图（点段落→解释→提取关联概念→写入DB）+ 手动搜索分析
- **知识图谱 GUI**：搜索框 + QTreeWidget 关系树 + QTextBrowser 详情面板，嵌入阅读器右侧面板
- **高亮标注**：选中文本右键高亮，支持关联到知识图谱概念
- **书签系统**：PDF 页码书签 / 文本行号书签，右键添加
- **结构化总结**：对当前章节或选中文本生成三层总结（核心论点/论证结构/关联知识点）
- **概念链接**：问答 Tab 中 AI 回答里的概念名自动变为可点击链接
- **右键菜单**：高亮选中、添加书签、总结选中内容、关联到概念
- **后台概念提取**：点段落后自动检测核心概念并提取关联，静默写入缓存
- **SQLite knowledge.db**：概念图/高亮/书签/总结独立数据库，thread-local 连接
- **极简呼吸主题**：暖蓝灰背景 #111820 + 柔和珊瑚色 #e07050 + 宽间距 + hover 过渡
- **PDF 渲染提升**：DPI 从 144 提升到 216（3x），翻页保持用户缩放比
- **动态搜索框提示**：解释视图显示"点击段落自动分析..."，图谱视图显示"搜索概念..."

### Fixed
- SQLite "database is locked" 错误：单例连接改为 thread-local 连接
- 点击"总结本章"崩溃：动态内部类 Signal 注册失败，Worker 提到模块级
- 翻页缩放丢失：goto_page 保存/恢复用户 zoom
- 概念链线程阻塞主线程：bg_thread 与 _thread 分离，非阻塞守卫
- 概念搜索无结果显示：概念链完成后自动展示关系树
- extract_concepts 返回值不一致：统一返回 DB 格式
- Chat 概念链接从未创建：_load_messages 中为已知概念名包裹链接
- JSON fallback 无保护：嵌套 json.loads 加 try/except
- CSS transition 警告：Qt 不支持，全部删除
- 内联颜色与主题不一致：Python 文件颜色同步更新

### Changed
- 主题从"革命红"（#c0392b）改为"极简呼吸"（#e07050）
- 按钮样式从实心填充改为半透明边框
- 滚动条从 8px 改为 6px（hover 时 8px）
- 分割线从明显灰色改为几乎隐形
- Tab 指示器从 3px 改为 2px

---

## [0.2.0] - 2026-06-06

### Added
- PDF 图片渲染器（QGraphicsView，高 DPI）
- 三栏阅读布局（目录 | 内容 | AI 分析）
- 目录导航（PDF 书签树 + 文本标题提取）
- 革命红深色主题
- 空状态引导
- 工具栏分组 + 状态栏信息分组
- 大文件分批导入
- 对话历史 SQLite 持久化
- RAG 增强问答模式

---

## [0.1.0] - 2026-06-05

### Added
- 初始 MVP：Ollama + ChromaDB 后端
- PySide6 GUI 四标签框架
- 问答 Tab（RAG/上下文/直接三模式）
- 文档库 Tab（拖拽导入）
- 设置 Tab
- 剪贴板监控
- 预检启动检查
