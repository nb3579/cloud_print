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
st.write("统一画质降维封装：由云端 GS 渲染高规标准点阵，通过物理平衡帧全图盲灌直驱出纸。")
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
    
    if st.button("🚀 批准高保真点阵编译并投递", type="primary"):
        with st.spinner("⚡ 正在启动云端『无驱全图扁平化』转码流水线..."):
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
                    
                # ─── 环节 B：PDF -> 工业级无驱通用激光点阵 (tiffg4 设备) ───
                st.text("⏳ 2/3 正在调用 Ghostscript 编译极其小巧的 CCITT T.6 压缩点阵...")
                
                # tiffg4 是 Ghostscript 内置最稳固的黑白传真/激光压缩设备
                # 能够把带图和公式的试卷无损压缩到极致，且它是纯正的反向极性（0代表白，1代表黑）
                # 这与老三星主板的底层硬件期待完全天衣无缝地撞车！
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=tiffg4",       
                    "-r300",                 # 严格对齐 300 DPI 
                    f"-sOutputFile={unique_prn}",
                    unique_pdf
                ]
                res = subprocess.run(gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    raise Exception(f"Ghostscript 编译点阵失败: {res.stderr}")
                
                # ─── 环节 C：【核心黑客补丁】注入物理开机唤醒与硬件进纸推力控制 ───
                st.text("🔧 正在向特征流中追加真机 PJL 唤醒外壳与 FormFeed 强制出纸符...")
                with open(unique_prn, "rb") as f:
                    tiff_payload = f.read()

                final_payload = bytearray()
                
                # 1. 注入通用的通用打印机作业唤醒头，强制让硬件从睡眠中唤醒并进入接收状态
                final_payload.extend(b"\x1b%-12345X@PJL JOB\r\n")
                final_payload.extend(b"@PJL ENTER LANGUAGE = PCL\r\n")
                
                # 2. 灌入整个转码出来的、天生极性正确（大片白纸在内存里就是纯 0x00）的保真位图流
                final_payload.extend(tiff_payload)
                
                # 3. 核心绝杀：老打印机肚子里吃下了打包点阵后，我们死死补上一发硬换页出纸控制字
                # 把纸张推过加热辊
                final_payload.extend(b"\x1b&l0H")  # PCL 标准进纸/抽纸命令
                final_payload.extend(b"\x0c")      # ASCII 经典 Form Feed 强制吐纸符
                final_payload.extend(b"\x1b%-12345X@PJL EOJ\r\n\x1b%-12345X") # 安全关闭作业会话

                # ─── 环节 D：Cloudflare Tunnel 秒级安全投递 ───
                prn_size = len(final_payload)
                st.text(f"🚀 3/3 编译成功！特征流体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=bytes(final_payload), headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【全线彻底通关】无驱点阵流已空投，打印机开始同步响动出纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 彻底清理临时垃圾
                for path in [unique_in, unique_pdf, unique_prn]:
                    if os.path.exists(path):
                        os.remove(path)
