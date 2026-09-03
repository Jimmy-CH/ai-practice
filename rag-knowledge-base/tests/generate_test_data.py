# tests/generate_test_data.py
"""生成集成测试所需的测试数据文件"""
import os
import struct

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


def ensure_dir():
    os.makedirs(TEST_DATA_DIR, exist_ok=True)


# ==================== TXT 测试文档 ====================

HR_POLICY_TXT = """\
企业人力资源管理制度汇编

第一章 总则
本制度适用于公司全体正式员工、试用期员工及实习生。
人力资源部负责本制度的解释、修订和执行监督。

第二章 考勤管理
第二条 工作时间：公司实行标准工时制，每日工作时间为上午9:00至下午18:00，午休时间为12:00至13:30。
第三条 迟到与早退：员工迟到或早退30分钟以内，每次扣款50元；超过30分钟按旷工半天处理。
第四条 加班管理：加班需提前向直属上级提交申请，经审批后方可执行。加班补偿可选择调休或加班费，调休优先。

第三章 休假制度
第五条 年假：入职满一年的员工享有5天带薪年假；满三年享有10天；满十年享有15天。
第六条 病假：员工因病无法出勤，须在上班前通知直属上级并于当日提交医院证明。
第七条 事假：事假需提前一个工作日申请，全年累计事假不得超过15天。

第四章 薪酬福利
第八条 薪资发放：每月15日发放上月工资，遇节假日提前至最近工作日。
第九条 社会保险：公司按国家规定为员工缴纳五险一金。
第十条 餐饮补贴：公司提供每日30元餐饮补贴，随工资一并发放。
"""

TECH_GUIDE_TXT = """\
RAG 知识库系统技术指南

一、系统概述
RAG（Retrieval-Augmented Generation）是一种结合检索与生成的AI技术架构。
系统首先从知识库中检索与用户问题相关的文档片段，然后将这些片段作为上下文提供给大语言模型，从而生成准确且有据可查的回答。

二、技术栈
- 向量数据库：ChromaDB，支持本地持久化和高效的向量相似度搜索
- Embedding 模型：OpenAI text-embedding-3-small，将文本转换为高维向量
- 大语言模型：DeepSeek Chat，通过 OpenAI 兼容接口调用
- 后端框架：FastAPI，提供高性能异步 API 服务
- 缓存层：Redis + 语义缓存，加速重复问题的响应

三、文档处理流程
1. 文件上传：支持 PDF 和 TXT 格式，最大 50MB
2. 文档解析：使用 PyPDF 或 TextLoader 提取文本内容
3. 文本分块：采用 RecursiveCharacterTextSplitter，默认 chunk_size=500，overlap=50
4. 向量化入库：调用 Embedding 模型将文本块转为向量并存入 ChromaDB

四、检索与生成
1. 语义检索：基于余弦相似度从向量库中检索 Top-K 相关片段
2. Prompt 构建：将检索到的上下文与用户问题组合为提示词
3. LLM 生成：调用 DeepSeek 模型生成最终回答
4. 来源标注：回答中会标注引用来源的文件名和页码

五、性能优化
- 语义缓存：相似问题直接返回缓存结果，阈值 0.95
- MMR 检索：可选最大边际相关性检索，平衡相关性与多样性
- 异步处理：文档入库任务在后台异步执行，不阻塞 API 响应
"""

FAQ_TXT = """\
常见问题解答（FAQ）

Q1: 如何上传文档到知识库？
A1: 通过 POST /upload 接口上传文件，目前支持 PDF 和 TXT 格式。上传后系统会在后台自动完成解析、分块和向量化入库。

Q2: 如何进行知识问答？
A2: 通过 POST /v1/ask 接口发送问题，系统会自动检索知识库并生成回答。请求体格式为 {"question": "你的问题", "top_k": 5}。

Q3: 支持哪些文件格式？
A3: 目前支持 PDF（.pdf）和纯文本（.txt）两种格式，文件大小限制为 50MB。

Q4: 上传的文档多久可以被检索到？
A4: 文档上传后会在后台异步处理，通常在几秒到几分钟内完成入库，之后即可被检索。

Q5: 如果知识库中没有相关信息，系统会怎么回答？
A5: 系统会明确回复"知识库中未找到相关答案"，不会编造信息。

Q6: 如何查看服务的健康状态？
A6: 访问 GET /health 接口，返回服务状态和版本号。监控指标可通过 GET /metrics 获取。
"""


def create_txt_files():
    """创建 TXT 测试文档"""
    files = {
        "hr_policy.txt": HR_POLICY_TXT,
        "tech_guide.txt": TECH_GUIDE_TXT,
        "faq.txt": FAQ_TXT,
    }
    paths = []
    for name, content in files.items():
        path = os.path.join(TEST_DATA_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        paths.append(path)
    return paths


def create_minimal_pdf(filename: str, text_lines: list[str]) -> str:
    """创建最小有效 PDF 文件（无需第三方库）"""
    path = os.path.join(TEST_DATA_DIR, filename)

    # 构建 PDF 内容流
    stream_content = "BT\n"
    y = 750
    for line in text_lines:
        # 转义 PDF 特殊字符
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_content += f"/F1 12 Tf\n1 0 0 1 50 {y} Tm\n({escaped}) Tj\n"
        y -= 18
        if y < 50:
            y = 750  # 简单换页
    stream_content += "ET\n"

    stream_bytes = stream_content.encode("latin-1", errors="replace")

    objects = []

    def add_obj(content: str) -> int:
        objects.append(content)
        return len(objects)

    # Obj 1: Catalog
    add_obj("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # Obj 2: Pages
    add_obj("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # Obj 3: Page
    add_obj(
        "3 0 obj\n<< /Type /Page /Parent 2 0 R "
        "/MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    # Obj 4: Content stream
    add_obj(
        f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n"
        + stream_content
        + "endstream\nendobj\n"
    )
    # Obj 5: Font
    add_obj(
        "5 0 obj\n<< /Type /Font /Subtype /Type1 "
        "/BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n"
    )

    # 组装 PDF
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4\n")
        offsets = []
        for obj in objects:
            offsets.append(f.tell())
            f.write(obj.encode("latin-1", errors="replace"))
        xref_offset = f.tell()
        f.write(b"xref\n")
        f.write(f"0 {len(objects) + 1}\n".encode())
        f.write(b"0000000000 65535 f \n")
        for offset in offsets:
            f.write(f"{offset:010d} 00000 n \n".encode())
        f.write(b"trailer\n")
        f.write(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode())
        f.write(b"startxref\n")
        f.write(f"{xref_offset}\n".encode())
        f.write(b"%%EOF\n")

    return path


def create_pdf_files():
    """创建 PDF 测试文档"""
    paths = []

    # PDF 1: 公司产品手册
    product_lines = [
        "企业产品手册",
        "",
        "产品一：智能客服系统",
        "智能客服系统基于大语言模型构建，支持7x24小时自动应答。",
        "核心功能包括：意图识别、多轮对话、知识库检索、工单生成。",
        "系统可用性达到99.9%，平均响应时间低于2秒。",
        "",
        "产品二：数据分析平台",
        "数据分析平台提供可视化报表、实时监控和预测分析功能。",
        "支持的数据源包括：MySQL、PostgreSQL、Elasticsearch、Kafka。",
        "内置50+常用图表类型，支持自定义Dashboard。",
        "",
        "产品三：协同办公工具",
        "协同办公工具集成文档协作、任务管理和即时通讯。",
        "支持最多500人同时在线编辑同一文档。",
        "任务管理支持看板视图、甘特图和日历视图。",
    ]
    paths.append(create_minimal_pdf("product_manual.pdf", product_lines))

    # PDF 2: 安全规范
    security_lines = [
        "信息安全管理制度",
        "",
        "第一章 数据安全",
        "所有客户数据必须加密存储，传输过程使用TLS 1.3协议。",
        "数据库访问实行最小权限原则，需经安全部门审批。",
        "日志保留期限不少于180天，包含操作人、时间和操作类型。",
        "",
        "第二章 访问控制",
        "内部系统访问统一使用SSO单点登录，启用MFA多因素认证。",
        "密码策略：最少12位，包含大小写字母、数字和特殊字符。",
        "账户连续5次登录失败自动锁定30分钟。",
        "",
        "第三章 应急响应",
        "安全事件分为四级：P0特别重大、P1重大、P2较大、P3一般。",
        "P0事件需在15分钟内上报安全负责人，1小时内启动应急预案。",
    ]
    paths.append(create_minimal_pdf("security_policy.pdf", security_lines))

    return paths


def generate_all():
    """生成全部测试数据"""
    ensure_dir()
    txt_paths = create_txt_files()
    pdf_paths = create_pdf_files()
    all_paths = txt_paths + pdf_paths
    print(f"已生成 {len(all_paths)} 个测试文件：")
    for p in all_paths:
        size = os.path.getsize(p)
        print(f"  {os.path.basename(p):30s} ({size:,} bytes)")
    return all_paths


if __name__ == "__main__":
    generate_all()
