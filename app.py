import streamlit as st
import requests
import subprocess
import os
import uuid
import mammoth
from weasyprint import HTML
from pdf2image import convert_from_path

# ================= 终极配置区 =================
PPD_FILE = "samsung.ppd"             # 确保此文件在 GitHub 仓库根目录
TUNNEL_URL = "https://dyj.yyjc.dpdns.org/cgi-bin/print" # 你的路由器 Tunnel 穿透入口
# =============================================

st.set_page_config(page_title="🖨️ 极客云打印大脑", page_icon="🖨️", layout="centered")
st.title("🖨️ 异地全栈自建云打印网关")
st.write("统一画质降维：所有 Word/PDF 在云端全自动扁平化为 A4 高清位图，由官方驱动秒级编译出纸。")
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
    
    if st.button("🚀 批准图像扁平化编译并投递", type="primary"):
        with st.spinner("⚡ 正在启动云端『图像级』转码流水线..."):
            try:
                # 0. 固定上传的文件流到临时区
                with open(unique_in, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # ─── 环节 A：Word 先无损渲染为通用高保真 PDF ───
                if orig_ext == ".docx":
                    st.text("⏳ 1/4 正在提取 Word 结构并渲染中间 PDF 容器...")
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
                
                # ─── 环节 B：【核心突破】把中间 PDF 强行扁平化为纯粹的 A4 JPEG 高清图片 ───
                st.text("⏳ 2/4 正在执行全文档图片化处理 (彻底碾碎 Band Size 限制)...")
                # 锁定 300 DPI 将 PDF 页面完美切片转换为 PIL Image 对象
                images = convert_from_path(unique_pdf, dpi=300)
                
                # 将切片出来的第一页（或全页）融合成一幅专门供给官方驱动吃下的标准点阵中间件
                flat_pdf = f"flat_{task_id}.pdf"
                images[0].save(flat_pdf, "PDF", resolution=300.0, save_all=True, append_images=images[1:])
                
                # ─── 环节 C：将标准化图片型 PDF 送入官方驱动过滤器进行高压真机编译 ───
                st.text("⏳ 3/4 正在激活云端原厂驱动核心翻译 SPL2 二进制特征流...")
                raster_tmp = f"raster_{task_id}.tmp"
                
                # 1. 寻找系统中的官方翻译官
                spl_filter_path = None
                for p in ["/usr/lib/cups/filter/rastertospl", "/usr/libexec/cups/filter/rastertospl"]:
                    if os.path.exists(p):
                        spl_filter_path = p
                        break
                if not spl_filter_path:
                    find_res = subprocess.run(["find", "/usr", "-name", "rastertospl"], stdout=subprocess.PIPE, text=True)
                    found_paths = find_res.stdout.strip().split('\n')
                    if found_paths and os.path.exists(found_paths[0]):
                        spl_filter_path = found_paths[0]
                
                if not spl_filter_path:
                    raise Exception("💥 云端环境未找到三星 splix 驱动，请检查 packages.txt 是否正确构建。")
                
                # 2. 利用 Ghostscript 将刚刚纯图片化的 PDF 还原为极其纯净的 cups-raster 位图流
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=cups",     
                    "-r300",             
                    f"-sOutputFile={raster_tmp}",
                    flat_pdf
                ]
                subprocess.run(gs_cmd, check=True)
                
                # 3. 官方驱动正式介入，挂载 ppd，由于数据源此时是纯图片，绝对能完美吐出 SPL 机器码
                drv_env = os.environ.copy()
                drv_env["PPD"] = PPD_FILE  
                drv_cmd = f"{spl_filter_path} 1 root 'CloudJob' 1 '' {raster_tmp} > {unique_prn}"
                res = subprocess.run(drv_cmd, shell=True, env=drv_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if res.returncode != 0:
                    raise Exception(f"官方驱动二级转码失败: {res.stderr}")
                
                # 清理本轮图片缓冲
                for f_path in [raster_tmp, flat_pdf]:
                    if os.path.exists(f_path): os.remove(f_path)
                
                # ─── 环节 D：Cloudflare Tunnel 秒级安全投递 ───
                prn_size = os.path.getsize(unique_prn)
                st.text(f"🚀 4/4 编译成功！官方无损 SPL 流体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                with open(unique_prn, "rb") as prn_file:
                    binary_data = prn_file.read()
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=binary_data, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【降维打击封箱成功】官方驱动完美出码！打印机已开始连续疯狂吐纸！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 垃圾清理
                for path in [unique_in, unique_pdf, unique_prn, f"raster_{task_id}.tmp", f"flat_{task_id}.pdf"]:
                    if os.path.exists(path):
                        os.remove(path)
