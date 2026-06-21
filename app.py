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
st.write("统一高保真封装：由云端 GS 编译超高压缩比激光流，通用 PJL/PCL 物理平衡外壳直驱出纸。")
st.divider()

uploaded_file = st.file_uploader("请上传需要远程打印的文档", type=["docx", "pdf"])

if uploaded_file is not None:
    task_id = str(uuid.uuid4())[:8]
    orig_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # 动态分配临时路径
    unique_in = f"in_{task_id}{orig_ext}"
    unique_pdf = f"render_{task_id}.pdf"
    unique_prn = f"job_{task_id}.prn"
    
    st.info(f"📄 任务已建立: {uploaded_file.name} (ID: {task_id})")
    
    if st.button("🚀 批准超高压缩点编译并投递", type="primary"):
        with st.spinner("⚡ 正在启动云端『高压缩轻量化』转码流水线..."):
            try:
                # 0. 固定上传的文件流到临时区
                with open(unique_in, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # ─── 环节 A：Word -> PDF (保持 Weasyprint 完美公式排版) ───
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
                            body {{ font-family: sans-serif; line-height: 1.6; color: #000; font-size: 14pt; }}
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
                    
                # ─── 环节 B：PDF -> 工业级高压缩黑白流 (ljet4 经典轻量设备) ───
                st.text("⏳ 2/3 正在调用 Ghostscript 编译超高压缩黑白硬件流...")
                
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=ljet4",        # 使用经典的 LaserJet 4 硬件高压缩 RLE 驱动
                    "-r300",                 # 维持 300 DPI 极致高精度
                    f"-sOutputFile={unique_prn}",
                    unique_pdf
                ]
                res = subprocess.run(gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    raise Exception(f"Ghostscript 编译失败: {res.stderr}")
                
                # ─── 环节 C：【终极绝杀】注入 PJL 唤醒外壳与物理进纸换页符 ───
                st.text("🔧 正在向特征流中注入真机 PJL 换页外壳...")
                with open(unique_prn, "rb") as f:
                    raw_prn_data = f.read()

                final_payload = bytearray()
                
                # 1. 强行注入 PJL 任务开始头（通用标准唤醒）
                final_payload.extend(b"\x1b%-12345X@PJL JOB\r\n")
                final_payload.extend(b"@PJL ENTER LANGUAGE = PCL\r\n")
                
                # 2. 承接已经经过硬件 RLE 压缩的完美点阵机器码
                final_payload.extend(raw_prn_data)
                
                # 3. 追加强行进纸符(\x1b&l0H) 与 强制出纸物理指令(\x0c)
                final_payload.extend(b"\x1b&l0H")  
                final_payload.extend(b"\x0c")      # 物理强制吐纸
                final_payload.extend(b"\x1b%-12345X@PJL EOJ\r\n\x1b%-12345X") 

                # ─── 环节 D：Cloudflare Tunnel 秒级安全投递 ───
                prn_size = len(final_payload)
                st.text(f"🚀 3/3 编译成功！轻量机器流体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=bytes(final_payload), headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【全线通关】轻量化流已秒级空投，打印机马达已大口出纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 彻底清理临时垃圾
                for path in [unique_in, unique_pdf, unique_prn]:
                    if os.path.exists(path):
                        os.remove(path)
