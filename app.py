import streamlit as st
import requests
import subprocess
import os
import uuid

# ================= 终极配置区 =================
PPD_FILE = "samsung.ppd"             # 确保此文件在 GitHub 仓库根目录
TUNNEL_URL = "https://dyj.yyjc.dpdns.org/cgi-bin/print" # 你的路由器 Tunnel 穿透入口
# =============================================

st.set_page_config(page_title="🖨️ 极客云打印大脑", page_icon="🖨️", layout="centered")
st.title("🖨️ 异地全栈自建云打印网关")
st.write("分布式架构：云端集成 LibreOffice + 官方 SpliX 驱动编译，本地 OpenWrt 零负载直驱出纸。")
st.divider()

uploaded_file = st.file_uploader("请上传需要远程打印的文档", type=["docx", "pdf"])

if uploaded_file is not None:
    task_id = str(uuid.uuid4())[:8]
    orig_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # 动态分配临时路径
    unique_in = f"in_{task_id}{orig_ext}"
    unique_pdf = f"render_{task_id}.pdf"
    unique_raster = f"raster_{task_id}.raster"
    unique_prn = f"job_{task_id}.prn"
    
    st.info(f"📄 任务已建立: {uploaded_file.name} (ID: {task_id})")
    
    if st.button("🚀 批准云端官方驱动编译并投递", type="primary"):
        with st.spinner("⚡ 正在启动云端『官方驱动核心』转码流水线..."):
            try:
                # 0. 固定上传的文件流到临时区
                with open(unique_in, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # ─── 环节 A：如果是 Word，调用云端 LibreOffice 压成标准 Linux PDF ───
                if orig_ext == ".docx":
                    st.text("⏳ 1/3 正在调用云端 LibreOffice 引擎执行高保真排版渲染...")
                    # 利用 headless 模式将 docx 转换为 pdf
                    sub_res = subprocess.run([
                        "soffice", "--headless", "--convert-to", "pdf",
                        unique_in
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    # soffice 默认生成同名 pdf (in_xxxx.pdf)
                    generated_pdf = unique_in.replace(".docx", ".pdf")
                    if os.path.exists(generated_pdf):
                        os.rename(generated_pdf, unique_pdf)
                    else:
                        raise Exception(f"LibreOffice 转换失败: {sub_res.stderr}")
                else:
                    os.rename(unique_in, unique_pdf)
                
                # ─── 环节 B：利用 Ghostscript 将标准 PDF 转换为 CUPS 图像中间件 ───
                st.text("⏳ 2/3 正在生成 Linux 标准 cups-raster 打印位图流...")
                gs_cmd = [
                    "gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                    "-sDEVICE=cups",     # 必须是系统级标准的 cups 统一中间格式
                    "-r300",             
                    f"-sOutputFile={unique_raster}",
                    unique_pdf
                ]
                subprocess.run(gs_cmd, check=True)
                
                # ─── 环节 C：定位官方唯一合法翻译官 rastertospl ───
                st.text("🔧 正在挂载 PPD 说明书，调用原厂 SpliX 驱动编译二进制机器流...")
                spl_filter_path = None
                for p in ["/usr/lib/cups/filter/rastertospl", "/usr/libexec/cups/filter/rastertospl"]:
                    if os.path.exists(p):
                        spl_filter_path = p
                        break
                if not spl_filter_path:
                    # 如果常规路径找不到，用 find 搜一下
                    find_res = subprocess.run(["find", "/usr", "-name", "rastertospl"], stdout=subprocess.PIPE, text=True)
                    found_paths = find_res.stdout.strip().split('\n')
                    if found_paths and os.path.exists(found_paths[0]):
                        spl_filter_path = found_paths[0]
                
                if not spl_filter_path:
                    raise Exception("💥 云端 Debian 环境未成功构建 splix 驱动，请检查 packages.txt！")
                
                # 挂载 PPD 环境变量，开始正规军编译
                drv_env = os.environ.copy()
                drv_env["PPD"] = PPD_FILE  
                
                # 灌入 CUPS 过滤标准指令
                drv_cmd = f"{spl_filter_path} 1 root 'CloudJob' 1 '' {unique_raster} > {unique_prn}"
                res = subprocess.run(drv_cmd, shell=True, env=drv_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if res.returncode != 0:
                    raise Exception(f"官方驱动二级编译失败: {res.stderr}")
                
                # ─── 环节 D：将原厂直出的绝对合法的 .prn 机器流秒级投递 ───
                prn_size = os.path.getsize(unique_prn)
                st.text(f"🚀 3/3 编译成功！标准 SPL 机器流体积: {prn_size / 1024:.2f} KB。正在投递...")
                
                with open(unique_prn, "rb") as prn_file:
                    binary_prn = prn_file.read()
                
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.post(TUNNEL_URL, data=binary_prn, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    st.success("🎉【全线通关】云端官方 SpliX 驱动流已完美注入！物理出纸大功告成！")
                else:
                    st.error(f"❌ 投递失败：路由器网关拒收，状态码: {response.status_code}")
                    
            except Exception as e:
                st.error(f"💥 链路中途崩溃: {str(e)}")
            finally:
                # 彻底清理云端容器临时垃圾
                for path in [unique_in, unique_pdf, unique_raster, unique_prn]:
                    if os.path.exists(path):
                        os.remove(path)
