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
st.write("由 Streamlit 云端容器代理重度驱动转码，利用通用激光点阵序列直驱本地硬件。")
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
    
    if st.button("🚀 批准高压编译并投递打印", type="primary"):
        with st.spinner("⚡ 正在启动云端转码流水线..."):
            try:
                # 0. 固定上传的文件流到临时区
                with open(unique_in, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # ─── 环节 A：Word -> PDF (免 LibreOffice 轻量化排版方案) ───
                if orig_ext == ".docx":
                    st.text("⏳ 1/3 正在提取 Word 结构并利用 WeasyPrint 渲染高保真 PDF...")
                    
                    with open(unique_in, "rb") as docx_file:
                        result = mammoth.convert_to_html(docx_file)
                        html_content = result.value
                    
                    # 注入符合 A4 打印标准的全局 CSS 样式
                    styled_html = f"""
                    <html>
                    <head>
                        <style>
                            @page {{ size: A4; margin: 2cm; }}
                            body {{ font-family: 'sans-serif'; line-height: 1.6; color: #000; font-size: 14pt; }}
                            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                            th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
                            p {{ margin-bottom: 10px; }}
                            img {{ max-width: 100%; height: auto; }} /* 确保图片不超出页边距 */
                        </style>
                    </head>
                    <body>{html_content}</body>
                    </html>
                    """
                    HTML(string=styled_html).write_pdf(unique_pdf)
                else:
                    os.rename(unique_in, unique_pdf)
                    
                # ─── 环节 B：PDF -> 物理点阵机器码 (降维打击：全图点阵化) ───
                st.text("⏳ 2/3 正在利用云端 Ghostscript 编译全像素点阵特征流...")
                
                # 🌟 核心修正：锁定为 -sDEVICE=laserjet 设备，并将分辨率收敛到 300 DPI
                # laserjet 会将文本、公式、图片全部揉碎成最单纯的 1-bit 点阵，不含任何高阶图形对象
                # 这样老打印机的主板固件不再需要解码图片，而是像读纯文本一样毫无压力地直接冲刷硬件马达
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=laserjet",     # 切换为最底层的通用激光纯点阵设备
                    "-r300",                 # 优化为 300 DPI（体积暴降，肉眼依然清晰，彻底解决 10MB 超时）
                    f"-sOutputFile={unique_prn}",
                    unique_pdf
                ]
                
                res = subprocess.run(gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    raise Exception(f"Ghostscript 激光点阵编译失败: {res.stderr}")
                
                # ─── 环节 C：校准并注入真机尾部强行抽纸控制字 ───
                with open(unique_prn, "rb") as prn_file:
                    raw_prn_data = prn_file.read()

                final_payload = bytearray()
                final_payload.extend(raw_prn_data)
                
                # 确保在流的最后死死补上一发硬出纸符，将纸张“踹”出加热辊
                if not raw_prn_data.endswith(b"\x0c"):
                    final_payload.extend(b"\x0c")
                final_payload.extend(b"\x1b%-12345X") # PJL 通用作业切断符

                with open(unique_prn, "wb") as f:
                    f.write(bytes(final_payload))
                
                # ─── 环节 D：Cloudflare Tunnel 秒级安全透传 ───
                prn_size = os.path.getsize(unique_prn)
                st.text(f"🚀 3/3 编译成功！全像素点阵体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                with open(unique_prn, "rb") as prn_file:
                    binary_data = prn_file.read()
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=binary_data, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【全线通关】带图/公式点阵流已强制注入，打印机开始连续抽纸出纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}，响应: {response.text}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 彻底清理云端临时文件
                for path in [unique_in, unique_pdf, unique_prn]:
                    if os.path.exists(path):
                        os.remove(path)
