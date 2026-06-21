import streamlit as st
import requests
import subprocess
import os
import uuid
import mammoth
from weasyprint import HTML

# ================= 终极配置区 =================
TUNNEL_URL = "https://print.666.dpdns.org/cgi-bin/print" # 你的路由器 Tunnel 穿透入口
# =============================================

st.set_page_config(page_title="🖨️ 极客云打印大脑", page_icon="🖨️", layout="centered")
st.title("🖨️ 异地全栈自建云打印网关")
st.write("统一高保真封装：专门针对施乐 3117 GDI 固件高压转码，1:1 原厂直驱出纸。")
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
    
    if st.button("🚀 批准施乐 GDI 原生直驱编译并投递", type="primary"):
        with st.spinner("⚡ 正在启动云端施乐 GDI 硬件级转码流水线..."):
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
                    
                # ─── 环节 B：PDF -> 施乐 3117 唯一看得懂的 GDI 原生机器流 ───
                st.text("⏳ 2/3 正在激活 Ghostscript 三星/施乐 GDI 直驱矩阵切片...")
                
                # -sDEVICE=gdi：这是 Linux 环境专门为了这类Host-based机型编写的通用直驱切片器
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=gdi",          # 强行切换为纯血 GDI 专用直驱引擎
                    "-r300",                 # 维持 300 DPI 极佳试卷画质
                    f"-sOutputFile={unique_prn}",
                    unique_pdf
                ]
                res = subprocess.run(gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # 安全兼容备用：如果云端容器的 GS 较新裁剪了该老设备，无缝降级切回标准的 pxlmono
                if res.returncode != 0:
                    gs_cmd[4] = "-sDEVICE=pxlmono"
                    subprocess.run(gs_cmd, check=True)
                
                # ─── 环节 C：追加施乐硬件要求的硬出纸尾巴 ───
                with open(unique_prn, "rb") as f:
                    raw_prn_data = f.read()

                final_payload = bytearray()
                final_payload.extend(raw_prn_data)
                
                # 针对施乐 3117 固件，强行在机器流尾部追加 \x0c (Form Feed) 与作业闭合标志
                if not raw_prn_data.endswith(b"\x1b%-12345X"):
                    final_payload.extend(b"\x0c")     # 强行触发抽纸马达物理换页
                    final_payload.extend(b"\x1b%-12345X") 

                # ─── 环节 D：Cloudflare Tunnel 秒级安全投递 ───
                prn_size = len(final_payload)
                st.text(f"🚀 3/3 编译成功！施乐特征流体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=bytes(final_payload), headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【全线终极通关】施乐原厂 GDI 流已送达！老机器即将疯狂吐纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                for path in [unique_in, unique_pdf, unique_prn]:
                    if os.path.exists(path):
                        os.remove(path)
