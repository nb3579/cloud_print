import streamlit as st
import requests
import subprocess
import os
import uuid
import mammoth
from weasyprint import HTML

# ================= 终极配置区 =================
PPD_FILE = "samsung.ppd"             # 确保此文件在 GitHub 仓库根目录
TUNNEL_URL = "https://dyj.yyjc.dpdns.org/cgi-bin/print" # 你的路由器 Tunnel 穿透入口
# =============================================

st.set_page_config(page_title="🖨️ 极客云打印大脑", page_icon="Streamlit", layout="centered")
st.title("🖨️ 异地全栈自建云打印网关")
st.write("由 Streamlit 云端容器代理重度驱动转码，无盘流式直灌家里 OpenWrt 9100d 端口。")
st.divider()

uploaded_file = st.file_uploader("请上传需要远程打印的文档", type=["docx", "pdf"])

if uploaded_file is not None:
    task_id = str(uuid.uuid4())[:8]
    orig_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # 动态分配内存临时路径
    unique_in = f"in_{task_id}{orig_ext}"
    unique_pdf = f"render_{task_id}.pdf"
    unique_prn = f"job_{task_id}.prn"
    
    st.info(f"📄 任务已建立: {uploaded_file.name} (ID: {task_id})")
    
    if st.button("🚀 批准编译并投递打印", type="primary"):
        with st.spinner("⚡ 正在启动云端转码流水线..."):
            try:
                # 0. 落地上传的文件
                with open(unique_in, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # ─── 环节 A：Word -> PDF (免 LibreOffice 轻量化方案) ───
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
                        </style>
                    </head>
                    <body>{html_content}</body>
                    </html>
                    """
                    HTML(string=styled_html).write_pdf(unique_pdf)
                else:
                    os.rename(unique_in, unique_pdf)
                    
                # ─── 环节 B：PDF -> 三星 SPL 机器码 (挂载 PPD 真机驱动编译) ───
                st.text(f"⏳ 2/3 正在加载存储库 [{PPD_FILE}] 编译真机 GDI 特征流...")
                raster_tmp = f"raster_{task_id}.tmp"
                
                # GS 切片标准 Linux 点阵
                gs_cmd = ["gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER", "-sDEVICE=cups", "-r600", f"-sOutputFile={raster_tmp}", unique_pdf]
                subprocess.run(gs_cmd, check=True)
                
                # 注入 PPD，让 Linux 官方驱动过滤器编译原厂机器码
                spl_filter = "/usr/lib/cups/filter/rastertospl"
                drv_env = os.environ.copy()
                drv_env["PPD"] = PPD_FILE
                
                drv_cmd = f"{spl_filter} 1 root 'CloudJob' 1 '' {raster_tmp} > {unique_prn}"
                subprocess.run(drv_cmd, shell=True, env=drv_env, check=True)
                os.remove(raster_tmp)
                
                # ─── 环节 C：Cloudflare Tunnel 毫秒级安全透传 ───
                prn_size = os.path.getsize(unique_prn)
                st.text(f"🚀 3/3 编译成功！原厂流体积: {prn_size / 1024:.2f} KB。正在强行倒入隧道...")
                
                with open(unique_prn, "rb") as prn_file:
                    binary_data = prn_file.read()
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=binary_data, headers=headers, timeout=60)
                
                if response.status_code == 200 and "Success" in response.text:
                    st.success("🎉【全线打通】家里打印机收到合法的原厂机器码，已经开始响动出纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收或返回异常: {response.text}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 彻底清理云端临时文件，保持容器绝对纯净
                for path in [unique_in, unique_pdf, unique_prn]:
                    if os.path.exists(path):
                        os.remove(path)
