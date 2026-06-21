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

st.set_page_config(page_title="🖨️ 极客云打印大脑", page_icon="🖨️", layout="centered")
st.title("🖨️ 异地全栈自建云打印网关")
st.write("由 Streamlit 云端容器代理重度驱动转码，挂载 PPD 编译真·原厂 SPL 特征流。")
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
                    
                # ─── 环节 B：PDF -> 真·三星原厂 SPL 机器码 (含 PPD 动态版本伪装) ───
                st.text("⏳ 2/3 正在激活云端 PPD 驱动引擎编译真机机器码...")
                raster_tmp = f"raster_{task_id}.tmp"
                spoofed_ppd = f"spoofed_{task_id}.ppd"
                
                # 💡 核心改进：读取原始 samsung.ppd，动态伪装内部版本号以适配容器中的 SpliX 2.0.0
                if not os.path.exists(PPD_FILE):
                    raise Exception(f"💥 仓库根目录下未找到 {PPD_FILE} 文件！")
                    
                with open(PPD_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    ppd_content = f.read()
                
                # 全局欺骗替换：将可能声明的 1.1 / 1.0 版本号暴力升级为 2.0.0
                spoofed_content = ppd_content.replace("1.1", "2.0.0").replace("1.0", "2.0.0")
                with open(spoofed_ppd, "w", encoding="utf-8") as f:
                    f.write(spoofed_content)
                
                # 1. 寻找 Linux 系统中 rastertospl 编译器的真实物理藏身路径
                spl_filter_path = None
                possible_paths = [
                    "/usr/lib/cups/filter/rastertospl",
                    "/usr/lib/cups/filter/rastertoqpdl",
                    "/usr/libexec/cups/filter/rastertospl"
                ]
                
                for p in possible_paths:
                    if os.path.exists(p):
                        spl_filter_path = p
                        break
                        
                if not spl_filter_path:
                    find_res = subprocess.run(["find", "/usr", "-name", "rastertospl"], stdout=subprocess.PIPE, text=True)
                    found_paths = find_res.stdout.strip().split('\n')
                    if found_paths and os.path.exists(found_paths[0]):
                        spl_filter_path = found_paths[0]
                
                if not spl_filter_path or not os.path.exists(spl_filter_path):
                    raise Exception("💥 云端环境未找到三星 splix 驱动组件！")
                
                # 2. 先用 Ghostscript 把 PDF 还原成 Linux 统一的标准点编位图格式 (cups-raster)
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=cups",     
                    "-r300",             # 优化为 300 DPI
                    f"-sOutputFile={raster_tmp}",
                    unique_pdf
                ]
                subprocess.run(gs_cmd, check=True)
                
                # 3. 模拟 Linux 标准 CUPS 管道执行真机驱动过滤编译 (使用伪装后的 PPD)
                drv_env = os.environ.copy()
                drv_env["PPD"] = spoofed_ppd  
                
                drv_cmd = f"{spl_filter_path} 1 root 'CloudJob' 1 '' {raster_tmp} > {unique_prn}"
                res = subprocess.run(drv_cmd, shell=True, env=drv_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if res.returncode != 0:
                    raise Exception(f"rastertospl 编译机器码失败: {res.stderr}")
                    
                # 清理本轮点阵缓存
                if os.path.exists(raster_tmp): os.remove(raster_tmp)
                if os.path.exists(spoofed_ppd): os.remove(spoofed_ppd)
                
                # ─── 环节 C：Cloudflare Tunnel 秒级安全透传 ───
                prn_size = os.path.getsize(unique_prn)
                st.text(f"🚀 3/3 编译成功！原厂 SPL 特征流体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                with open(unique_prn, "rb") as prn_file:
                    binary_data = prn_file.read()
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=binary_data, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【全线彻底通关】真·三星 SPL 2.0 完美机器码已灌入硬件，开始响动吐纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}，响应: {response.text}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 清理垃圾，保持容器绝对纯净
                for path in [unique_in, unique_pdf, unique_prn, f"raster_{task_id}.tmp", f"spoofed_{task_id}.ppd"]:
                    if os.path.exists(path):
                        os.remove(path)
