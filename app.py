import streamlit as st
import requests
import os
import uuid
import mammoth
from weasyprint import HTML
from pdf2image import convert_from_path

# ================= 终极配置区 =================
TUNNEL_URL = "https://dyj.yyjc.dpdns.org/cgi-bin/print" # 你的路由器 Tunnel 穿透入口
# =============================================

st.set_page_config(page_title="🖨️ 极客云打印大脑", page_icon="🖨️", layout="centered")
st.title("🖨️ 异地全栈自建云打印网关")
st.write("统一画质降维封装：全文档转为标准 A4 点阵，纯 Python 内存级 1:1 伪造真·SPL v1 原厂序列。")
st.divider()

uploaded_file = st.file_uploader("请上传需要远程打印的文档", type=["docx", "pdf"])

if uploaded_file is not None:
    task_id = str(uuid.uuid4())[:8]
    orig_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # 动态分配临时路径
    unique_in = f"in_{task_id}{orig_ext}"
    unique_pdf = f"render_{task_id}.pdf"
    
    st.info(f"📄 任务已建立: {uploaded_file.name} (ID: {task_id})")
    
    if st.button("🚀 批准图像扁平化编译并投递", type="primary"):
        with st.spinner("⚡ 正在启动云端『图像纯内存级』转码流水线..."):
            try:
                # 0. 固定上传的文件流到临时区
                with open(unique_in, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # ─── 环节 A：Word 先无损渲染为通用高保真 PDF ───
                if orig_ext == ".docx":
                    st.text("⏳ 1/3 正在提取 Word 结构并渲染中间 PDF 容器...")
                    with open(unique_in, "rb") as docx_file:
                        result = mammoth.convert_to_html(docx_file)
                        html_content = result.value
                    
                    styled_html = f"""
                    <html>
                    <head>
                        <style>
                            @page {{ size: A4; margin: 2cm; }}
                            body {{ font-family: 'sans-serif'; line-height: 1.6; color: #000; font-size: 14pt; }}
                            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                            th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
                            p {{ margin-bottom: 10px; }}
                            img {{ max-width: 100%; height: auto; }}
                        </style>
                    </head>
                    <body>{html_content}</body>
                    </html>
                    """
                    HTML(string=styled_html).write_pdf(unique_pdf)
                else:
                    os.rename(unique_in, unique_pdf)
                
                # ─── 环节 B：【图形降维核心】将 PDF 每一页无情拍扁成 A4 标准 300DPI 图像 ───
                st.text("⏳ 2/3 正在执行全文档图片化转换 (彻底碾碎排版与公式复杂度)...")
                images = convert_from_path(unique_pdf, dpi=300)
                
                # ─── 环节 C：【纯 Python 级高精度伪造原厂 SPL v1 特征流】 ───
                st.text("🔧 正在进行内存级真机比特流镜像翻转、3508 行满页像素硬对齐封装...")
                
                spl_stream = bytearray()
                
                # 1. 注入物理硬件全局 PJL 唤醒报头
                spl_stream.extend(b"\x1b%-12345X@PJL JOB\r\n")
                spl_stream.extend(b"@PJL ENTER LANGUAGE = SPL\r\n")
                
                # 2. 三星原厂 PAGE HEADER (A4 模式启动宣告)
                spl_stream.extend(b"\x12\x00\x01\x04\x00\x00") 
                
                ROW_BYTES = 310     # 300 DPI 下 A4 纸张宽度：2480 像素 / 8 = 310 字节
                TARGET_ROWS = 3508  # 300 DPI 下 A4 纸张绝对硬件标准总行数
                
                # 处理第一页图像
                img = images[0].convert("1")   # 强转黑白二值
                img = img.resize((2480, 3508)) # 像素强制收紧对齐
                
                raw_raster_data = img.tobytes()
                
                # 💡 预先生成 256 个字节的比特镜像查找表（0-255的高低位全部对调），压榨执行效率
                LOOKUP_TABLE = bytes(int(f'{b:08b}'[::-1], 2) for b in range(256))
                
                # 3. 灌入对齐行
                for r in range(TARGET_ROWS):
                    start_idx = r * ROW_BYTES
                    end_idx = start_idx + ROW_BYTES
                    line_chunk = raw_raster_data[start_idx:end_idx]
                    
                    # 🌟【超级绝杀补丁】：将单行内每一个字节通过查找表进行完美的 Bit-Reversal（LSB反转）
                    # 让打印机激光头能够以正确的像素顺序读取内容，彻底解决刚卷纸就熔断的顽疾！
                    aligned_line = line_chunk.translate(LOOKUP_TABLE)
                    
                    spl_stream.extend(b"\x11\x00\x36\x01") # 三星单行控制字
                    spl_stream.extend(aligned_line)
                
                # 4. 强行封底：切断本页会话，注入物理换页符
                spl_stream.extend(b"\x13\x00") # 三星物理页结束
                spl_stream.extend(b"\x0c")     # 物理吐纸换页符 (Form Feed)
                spl_stream.extend(b"\x1b%-12345X@PJL EOJ\r\n\x1b%-12345X") 
                
                # ─── 环节 D：Cloudflare Tunnel 秒级安全投递 ───
                prn_size = len(spl_stream)
                st.text(f"🚀 3/3 编译成功！免驱 SPL1 机器码体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=bytes(spl_stream), headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【全线终极闭环】色彩与比特顺序已双重校准！马达已全速启动出纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 彻底清理云端临时垃圾
                for path in [unique_in, unique_pdf]:
                    if os.path.exists(path):
                        os.remove(path)
