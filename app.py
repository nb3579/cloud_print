import streamlit as st
import requests
import subprocess
import os
import uuid
import mammoth
from weasyprint import HTML

# ================= 终极配置区 =================
TUNNEL_URL = "https://dyj.yyjc.dpdns.org/cgi-bin/print" # 你的路由器 Tunnel 穿透入口
# =============================================

st.set_page_config(page_title="🖨️ 极客云打印大脑", page_icon="🖨️", layout="centered")
st.title("🖨️ 异地全栈自建云打印网关")
st.write("由 Streamlit 云端容器代理重度转码，纯内存真二进制 SPL v1 序列直驱本地硬件。")
st.divider()

uploaded_file = st.file_uploader("请上传需要远程打印的文档", type=["docx", "pdf"])

if uploaded_file is not None:
    task_id = str(uuid.uuid4())[:8]
    orig_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # 动态分配临时路径
    unique_in = f"in_{task_id}{orig_ext}"
    unique_pdf = f"render_{task_id}.pdf"
    unique_prn = f"job_{task_id}.prn"
    unique_raw = f"raw_{task_id}.pbm"
    
    st.info(f"📄 任务已建立: {uploaded_file.name} (ID: {task_id})")
    
    if st.button("🚀 批准高压编译并投递打印", type="primary"):
        with st.spinner("⚡ 正在启动云端转码流水线..."):
            try:
                # 0. 固定上传的文件流到临时区
                with open(unique_in, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # ─── 环节 A：Word -> PDF ───
                if orig_ext == ".docx":
                    st.text("⏳ 1/3 正在提取 Word 结构并利用 WeasyPrint 渲染高保真 PDF...")
                    
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
                    
                # ─── 环节 B：PDF -> 1-bit PBM 裸点阵切片 ───
                st.text("⏳ 2/3 正在生成 A4 300DPI 绝对对齐位图矩阵...")
                
                # A4 在 300 DPI 下的标准像素宽为 2480 点 (刚好等于 310 字节)
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=pbmraw",       # 提取最纯粹的 1-bit 裸位图点阵 (P4 格式)
                    "-r300",                 # 严丝合缝扣死 300 DPI 
                    f"-sOutputFile={unique_raw}",
                    unique_pdf
                ]
                res = subprocess.run(gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    raise Exception(f"Ghostscript 矩阵切片失败: {res.stderr}")
                
                # ─── 环节 C：【真·原厂 SPL v1 满页高度对齐封装】 ───
                st.text("🔧 正在进行真机 3508 行满页像素对齐与尾部强推逻辑...")
                
                with open(unique_raw, "rb") as f:
                    pbm_bytes = f.read()
                
                # 精准跳过 PBM 的文本头
                header_offset = pbm_bytes.find(b'\n', pbm_bytes.find(b'\n') + 1) + 1
                raw_raster_data = pbm_bytes[header_offset:]
                
                spl_stream = bytearray()
                
                # 1. PJL 硬件唤醒
                spl_stream.extend(b"\x1b%-12345X@PJL JOB\r\n")
                spl_stream.extend(b"@PJL ENTER LANGUAGE = SPL\r\n")
                
                # 2. 三星原厂 PAGE HEADER (A4 启动)
                spl_stream.extend(b"\x12\x00\x01\x04\x00\x00") 
                
                ROW_BYTES = 310
                TARGET_ROWS = 3508  # 300 DPI 下 A4 纸张绝对硬标准的总行数
                
                total_rows = len(raw_raster_data) // ROW_BYTES
                
                # 3. 灌入 GS 生成的真实点阵行
                for r in range(total_rows):
                    start_idx = r * ROW_BYTES
                    end_idx = start_idx + ROW_BYTES
                    line_chunk = raw_raster_data[start_idx:end_idx]
                    
                    spl_stream.extend(b"\x11\x00\x36\x01")
                    spl_stream.extend(line_chunk)
                    
                # 4. 【补行特效】如果行数不够 A4 标准，用纯白点阵(0xff)强行把残行顶满
                if total_rows < TARGET_ROWS:
                    blank_line = b"\x00" * ROW_BYTES  
                    for _ in range(TARGET_ROWS - total_rows):
                        spl_stream.extend(b"\x11\x00\x36\x01")
                        spl_stream.extend(blank_line)
                
                # 5. 强行切断并出纸
                spl_stream.extend(b"\x13\x00") # 三星物理页结束
                spl_stream.extend(b"\x0c")     # 物理吐纸符
                spl_stream.extend(b"\x1b%-12345X@PJL EOJ\r\n\x1b%-12345X") 
                
                with open(unique_prn, "wb") as f:
                    f.write(bytes(spl_stream))
                
                # ─── 环节 D：Cloudflare Tunnel 秒级安全投递 ───
                prn_size = os.path.getsize(unique_prn)
                st.text(f"🚀 3/3 编译成功！脱水 SPL1 机器码体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=bytes(spl_stream), headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【神级闭环突破】真·SPL v1 点阵流已完美注入！老机器检测到合法的 310 对齐，开始大口吐纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 垃圾清理
                for path in [unique_in, unique_pdf, unique_prn, unique_raw]:
                    if os.path.exists(path):
                        os.remove(path)
