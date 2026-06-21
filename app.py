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
                TARGET_ROWS = 3508  # 🌟 300 DPI 下 A4 纸张绝对硬标准的总行数
                
                total_rows = len(raw_raster_data) // ROW_BYTES
                
                # 3. 灌入 GS 生成的真实点阵行
                for r in range(total_rows):
                    start_idx = r * ROW_BYTES
                    end_idx = start_idx + ROW_BYTES
                    line_chunk = raw_raster_data[start_idx:end_idx]
                    
                    spl_stream.extend(b"\x11\x00\x36\x01")
                    spl_stream.extend(line_chunk)
                    
                # 4. 🌟【神级补丁】如果行数不够 A4 标准，用纯白点阵(0xff)强行把残行顶满！
                if total_rows < TARGET_ROWS:
                    blank_line = b"\xff" * ROW_BYTES  # 纯白像素行
                    for _ in range(TARGET_ROWS - total_rows):
                        spl_stream.extend(b"\x11\x00\x36\x01")
                        spl_stream.extend(blank_line)
                
                # 5. 强行切断并出纸
                spl_stream.extend(b"\x13\x00") # 三星物理页结束
                spl_stream.extend(b"\x0c")     # 物理吐纸符
                spl_stream.extend(b"\x1b%-12345X@PJL EOJ\r\n\x1b%-12345X")
