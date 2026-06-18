#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
联通IPTV列表获取工具 - Windows桌面版
界面输入认证信息，点击获取即可生成 iptv.m3u
"""

import os
import sys
import time
import threading
import subprocess
import webbrowser
from datetime import datetime

# 检查 tkinter
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    print("错误: tkinter 未安装")
    sys.exit(1)

# 检查 yaml
try:
    import yaml
except ImportError:
    print("错误: pyyaml 未安装，请运行: pip install pyyaml")
    sys.exit(1)


class IPTVDesktopTool:
    def __init__(self, root):
        self.root = root
        self.root.title("联通IPTV列表获取工具 v1.0")
        self.root.geometry("750x650")
        self.root.resizable(False, False)
        self.root.configure(bg='#f0f0f0')

        self.is_running = False
        self.web_process = None

        # ===== 路径配置（兼容打包和开发环境） =====
        if getattr(sys, 'frozen', False):
            # 打包后的 exe：数据目录在 exe 同级目录
            self.base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境：脚本所在目录
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.data_dir = os.path.join(self.base_dir, "data")
        self.config_file = os.path.join(self.base_dir, "config.yaml")
        self.output_file = os.path.join(self.data_dir, "iptv.m3u")

        self._build_ui()
        self._load_saved_config()

    def _build_ui(self):
        """构建界面"""
        main_frame = tk.Frame(self.root, bg='#f0f0f0', padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ==================== 标题 ====================
        title_frame = tk.Frame(main_frame, bg='#f0f0f0')
        title_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(title_frame,
                 text="📡 联通IPTV列表获取工具",
                 font=("Microsoft YaHei", 18, "bold"),
                 bg='#f0f0f0', fg='#2c3e50').pack(side=tk.LEFT)

        tk.Label(title_frame,
                 text="v1.0",
                 font=("Microsoft YaHei", 10),
                 bg='#f0f0f0', fg='#95a5a6').pack(side=tk.LEFT, padx=(10, 0))

        # ==================== 配置输入面板 ====================
        config_frame = tk.LabelFrame(main_frame,
                                     text=" 认证配置（从机顶盒获取）",
                                     font=("Microsoft YaHei", 10, "bold"),
                                     bg='#f0f0f0', fg='#2c3e50',
                                     padx=12, pady=12)
        config_frame.pack(fill=tk.X, pady=(0, 10))

        # 行1: EDS服务器
        row1 = tk.Frame(config_frame, bg='#f0f0f0')
        row1.pack(fill=tk.X, pady=4)
        tk.Label(row1, text="EDS服务器:", width=12, anchor=tk.W,
                 bg='#f0f0f0', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.server_entry = tk.Entry(row1, width=50, font=("Consolas", 9))
        self.server_entry.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(row1, text="例:10.0.0.1 或 10.0.0.1:8080",
                 fg='#95a5a6', bg='#f0f0f0', font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)

        # 行2: UserID
        row2 = tk.Frame(config_frame, bg='#f0f0f0')
        row2.pack(fill=tk.X, pady=4)
        tk.Label(row2, text="UserID:", width=12, anchor=tk.W,
                 bg='#f0f0f0', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.userid_entry = tk.Entry(row2, width=50, font=("Consolas", 9))
        self.userid_entry.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(row2, text="有时和STBID相同", fg='#95a5a6',
                 bg='#f0f0f0', font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)

        # 行3: STBID
        row3 = tk.Frame(config_frame, bg='#f0f0f0')
        row3.pack(fill=tk.X, pady=4)
        tk.Label(row3, text="STBID:", width=12, anchor=tk.W,
                 bg='#f0f0f0', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.stbid_entry = tk.Entry(row3, width=50, font=("Consolas", 9))
        self.stbid_entry.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(row3, text="设备ID/序列号", fg='#95a5a6',
                 bg='#f0f0f0', font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)

        # 行4: MAC地址
        row4 = tk.Frame(config_frame, bg='#f0f0f0')
        row4.pack(fill=tk.X, pady=4)
        tk.Label(row4, text="MAC地址:", width=12, anchor=tk.W,
                 bg='#f0f0f0', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.mac_entry = tk.Entry(row4, width=50, font=("Consolas", 9))
        self.mac_entry.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(row4, text="格式: AA:BB:CC:DD:EE:FF", fg='#95a5a6',
                 bg='#f0f0f0', font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)

        # 配置操作按钮行
        btn_row = tk.Frame(config_frame, bg='#f0f0f0')
        btn_row.pack(fill=tk.X, pady=(8, 0))

        tk.Button(btn_row, text="💾 保存配置",
                  font=("Microsoft YaHei", 9), bg='#2ecc71', fg='white',
                  padx=15, pady=5, relief=tk.FLAT, cursor='hand2',
                  command=self.save_config).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(btn_row, text="📂 加载配置",
                  font=("Microsoft YaHei", 9), bg='#3498db', fg='white',
                  padx=15, pady=5, relief=tk.FLAT, cursor='hand2',
                  command=self.load_config).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(btn_row, text="🗑️ 清空配置",
                  font=("Microsoft YaHei", 9), bg='#e67e22', fg='white',
                  padx=15, pady=5, relief=tk.FLAT, cursor='hand2',
                  command=self.clear_config).pack(side=tk.LEFT)

        # ==================== 状态栏 ====================
        status_frame = tk.LabelFrame(main_frame,
                                     text=" 运行状态 ",
                                     font=("Microsoft YaHei", 10, "bold"),
                                     bg='#f0f0f0', fg='#2c3e50',
                                     padx=10, pady=6)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = tk.Label(status_frame, text="✅ 就绪",
                                      font=("Microsoft YaHei", 11),
                                      bg='#f0f0f0', fg='#27ae60')
        self.status_label.pack(anchor=tk.W)

        self.detail_label = tk.Label(status_frame, text="填写配置后点击「获取列表」",
                                       bg='#f0f0f0', fg='#7f8c8d',
                                       font=("Microsoft YaHei", 9))
        self.detail_label.pack(anchor=tk.W)

        # ==================== 日志面板 ====================
        log_frame = tk.LabelFrame(main_frame,
                                  text=" 运行日志 ",
                                  font=("Microsoft YaHei", 10, "bold"),
                                  bg='#f0f0f0', fg='#2c3e50',
                                  padx=10, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10,
                                                   font=("Consolas", 9),
                                                   bg='#1e1e1e', fg='#d4d4d4',
                                                   insertbackground='white')
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 日志颜色标签
        self.log_text.tag_config("info", foreground="#4fc3f7")
        self.log_text.tag_config("success", foreground="#81c784")
        self.log_text.tag_config("error", foreground="#e57373")
        self.log_text.tag_config("warning", foreground="#ffb74d")
        self.log_text.tag_config("title", foreground="#ffffff",
                                  font=("Consolas", 10, "bold"))

        # ==================== 底部按钮 ====================
        bottom_frame = tk.Frame(main_frame, bg='#f0f0f0')
        bottom_frame.pack(fill=tk.X)

        self.run_btn = tk.Button(bottom_frame, text="🚀 获取列表",
                                 font=("Microsoft YaHei", 11, "bold"),
                                 bg='#3498db', fg='white',
                                 padx=30, pady=8,
                                 relief=tk.FLAT, cursor='hand2',
                                 command=self.run_scraper)
        self.run_btn.pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(bottom_frame, text="📂 打开输出目录",
                  font=("Microsoft YaHei", 10),
                  bg='#ecf0f1', fg='#2c3e50',
                  padx=15, pady=8,
                  relief=tk.FLAT, cursor='hand2',
                  command=self.open_output_dir).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(bottom_frame, text="🌐 Web界面",
                  font=("Microsoft YaHei", 10),
                  bg='#9b59b6', fg='white',
                  padx=15, pady=8,
                  relief=tk.FLAT, cursor='hand2',
                  command=self.open_web).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(bottom_frame, text="❓ 帮助",
                  font=("Microsoft YaHei", 10),
                  bg='#ecf0f1', fg='#7f8c8d',
                  padx=15, pady=8,
                  relief=tk.FLAT, cursor='hand2',
                  command=self.show_help).pack(side=tk.RIGHT)

    # ==================== 配置管理 ====================
    def _load_saved_config(self):
        """启动时自动加载配置"""
        if os.path.exists(self.config_file):
            self.load_config(silent=True)

    def save_config(self):
        """保存配置到 config.yaml"""
        config = {
            "server": self.server_entry.get().strip(),
            "userId": self.userid_entry.get().strip(),
            "stbId": self.stbid_entry.get().strip(),
            "mac": self.mac_entry.get().strip()
        }

        # 验证
        if not all([config["server"], config["userId"], config["stbId"], config["mac"]]):
            messagebox.showwarning("提示", "请填写所有配置项！")
            return

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            self.log("✅ 配置已保存到 config.yaml", "success")
            self.set_status("✅ 配置已保存", "", "#27ae60")
            messagebox.showinfo("成功", "配置已保存到 config.yaml")
        except Exception as e:
            self.log(f"❌ 保存失败: {e}", "error")
            messagebox.showerror("错误", f"保存失败:\n{e}")

    def load_config(self, silent=False):
        """从 config.yaml 加载配置到界面"""
        if not os.path.exists(self.config_file):
            if not silent:
                messagebox.showwarning("提示", "未找到 config.yaml 配置文件")
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if not config:
                return

            self.server_entry.delete(0, tk.END)
            self.server_entry.insert(0, config.get("server", ""))
            self.userid_entry.delete(0, tk.END)
            self.userid_entry.insert(0, config.get("userId", ""))
            self.stbid_entry.delete(0, tk.END)
            self.stbid_entry.insert(0, config.get("stbId", ""))
            self.mac_entry.delete(0, tk.END)
            self.mac_entry.insert(0, config.get("mac", ""))

            self.log("✅ 配置已从 config.yaml 加载", "success")
        except Exception as e:
            self.log(f"❌ 加载失败: {e}", "error")
            if not silent:
                messagebox.showerror("错误", f"加载配置失败:\n{e}")

    def clear_config(self):
        """清空界面配置（不删除文件）"""
        if messagebox.askyesno("确认", "确定要清空当前填写的配置吗？"):
            self.server_entry.delete(0, tk.END)
            self.userid_entry.delete(0, tk.END)
            self.stbid_entry.delete(0, tk.END)
            self.mac_entry.delete(0, tk.END)
            self.log("🗑️ 配置已清空", "warning")
            self.set_status("⏳ 配置已清空", "请重新填写", "#f39c12")

    # ==================== 日志和状态 ====================
    def log(self, message, tag=None):
        """日志输出"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag if tag else None)
        self.log_text.see(tk.END)
        self.root.update()

    def set_status(self, text, detail=None, color="#27ae60"):
        """更新状态"""
        self.status_label.config(text=text, fg=color)
        if detail is not None:
            self.detail_label.config(text=detail)
        self.root.update()

    # ==================== 核心功能 ====================
    def run_scraper(self):
        """执行获取"""
        if self.is_running:
            messagebox.showwarning("提示", "任务正在运行中，请稍候...")
            return

        # 从界面获取配置
        server = self.server_entry.get().strip()
        user_id = self.userid_entry.get().strip()
        stb_id = self.stbid_entry.get().strip()
        mac = self.mac_entry.get().strip()

        if not all([server, user_id, stb_id, mac]):
            messagebox.showwarning("提示", "请填写完整的认证配置！\n\n需要填写：\n• EDS服务器\n• UserID\n• STBID\n• MAC地址")
            return

        self.is_running = True
        self.run_btn.config(state=tk.DISABLED, text="⏳ 运行中...")
        self.log("=" * 55, "title")
        self.log("开始获取 IPTV 频道列表...", "title")
        self.log(f"服务器: {server}", "info")
        self.set_status("⏳ 正在获取...", "请稍候，正在连接服务器", "#f39c12")

        # 创建数据目录
        os.makedirs(self.data_dir, exist_ok=True)

        # 后台执行
        thread = threading.Thread(target=self._run_scraper_thread,
                                  args=(server, user_id, stb_id, mac),
                                  daemon=True)
        thread.start()

    def _run_scraper_thread(self, server, user_id, stb_id, mac):
        """后台线程执行爬虫"""
        try:
            import sys
            import os

            # 获取路径
            if getattr(sys, 'frozen', False):
                base_dir = sys._MEIPASS
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))

            # 确保 src 在路径中
            src_dir = os.path.join(base_dir, "src")
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)

            # 数据目录
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else self.base_dir
            data_dir = os.path.join(exe_dir, "data")
            os.environ["DATA_DIR"] = data_dir

            self.log("📂 数据目录: " + data_dir, "info")

            # ===== 修复：去掉 http:// 前缀 =====
            if server.startswith('http://'):
                server = server[7:]
            elif server.startswith('https://'):
                server = server[8:]
            self.log(f"📡 服务器地址（处理后）: {server}", "info")

            # 导入 scraper 模块
            import scraper
            import yaml

            # 生成配置文件
            config = {
                "login": {
                    "server": server,
                    "userId": user_id,
                    "stbId": stb_id,
                    "mac": mac,
                    "password": "12345678",
                    "ipaddr": "0.0.0.0",
                    "headers": {
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "*/*",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
                    },
                    "igmp": {
                        "host": "127.0.0.1",
                        "port": 4022
                    },
                    "lang": "1",
                    "supportHD": "1",
                    "stbType": "1",
                    "stbVersion": "1.0",
                    "conntype": "1",
                    "templateName": "default",
                    "areaId": "0",
                    "softwareVersion": "1.0",
                    "stbidShort": stb_id[:8] if len(stb_id) >= 8 else stb_id
                },
                "epg": {
                    "esaasHost": "139.215.93.40:3100",
                    "areaCode": "0",
                    "daysBefore": 1,
                    "daysAfter": 1
                },
                "channels": []
            }

            # 保存配置文件
            config_path = os.path.join(data_dir, "config.yaml")
            os.makedirs(data_dir, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            self.log("📝 配置文件已生成: " + config_path, "info")

            # 调用 scraper.process()
            self.log("📡 正在连接 IPTV 服务器...", "info")
            scraper.process(config_path, data_dir)

            # 检查输出文件
            output_file = os.path.join(data_dir, "iptv.m3u")
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    channel_count = sum(1 for line in lines if line.startswith('#EXTINF'))
                self.log("=" * 55, "title")
                self.root.after(0, lambda: self._on_success(channel_count, output_file))
            else:
                self.log("❌ 未生成播放列表", "error")
                self.root.after(0, lambda: self._on_error("未能生成播放列表"))

        except ImportError as e:
            self.log(f"❌ 导入模块失败: {e}", "error")
            self.root.after(0, lambda: self._on_error(f"模块导入失败: {e}"))

        except Exception as e:
            self.log(f"❌ 错误: {str(e)}", "error")
            self.root.after(0, lambda: self._on_error(str(e)))

    def _on_success(self, count, output_file):
        """成功回调"""
        self.set_status(f"✅ 获取成功！共 {count} 个频道", f"文件: {output_file}", "#27ae60")
        self.run_btn.config(state=tk.NORMAL, text="🚀 获取列表")
        self.is_running = False

        messagebox.showinfo("完成",
            f"✅ 频道列表获取成功！\n\n"
            f"共获取 {count} 个频道\n"
            f"文件位置: {output_file}\n\n"
            f"点击「打开输出目录」查看文件。")

    def _on_error(self, msg):
        """错误回调"""
        self.set_status("❌ 获取失败", msg[:40] + "..." if len(msg) > 40 else msg, "#e74c3c")
        self.run_btn.config(state=tk.NORMAL, text="🚀 获取列表")
        self.is_running = False

        # 判断错误类型
        if "Connection" in msg or "timeout" in msg.lower():
            messagebox.showerror("网络错误",
                "⚠️ 无法连接到 IPTV 服务器\n\n"
                "可能原因：\n"
                "1. 电脑未连接到 IPTV 内网（需连接光猫IPTV口）\n"
                "2. 服务器地址配置错误\n"
                "3. 防火墙阻止了连接\n\n"
                f"详细错误: {msg}")
        elif "未获取到频道" in msg:
            messagebox.showwarning("无数据",
                "⚠️ 未获取到频道数据\n\n"
                "可能原因：\n"
                "1. 配置信息（UserID/STBID/MAC）有误\n"
                "2. 服务器返回了空数据\n"
                "3. 运营商接口有变化")
        else:
            messagebox.showerror("错误", f"运行失败:\n\n{msg}")

    # ==================== 辅助功能 ====================
    def open_output_dir(self):
        """打开输出目录"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        subprocess.Popen(f'explorer "{self.data_dir}"')

    def open_web(self):
        """启动Web界面（如果可用）"""
        try:
            # 获取 src 目录路径（兼容打包和开发环境）
            if getattr(sys, 'frozen', False):
                src_dir = os.path.join(sys._MEIPASS, "src")
            else:
                src_dir = os.path.join(self.base_dir, "src")

            if self.web_process is None or self.web_process.poll() is not None:
                self.log("🌐 正在启动 Web 服务...", "info")
                self.web_process = subprocess.Popen(
                    [sys.executable, os.path.join(src_dir, "web.py")],
                    cwd=self.base_dir,
                    env={**os.environ, "DATA_DIR": self.data_dir},
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(2)

            webbrowser.open("http://localhost:5000")
            self.log("🌐 Web 界面已打开: http://localhost:5000", "success")
        except Exception as e:
            self.log(f"❌ 启动 Web 失败: {e}", "error")
            messagebox.showerror("错误", f"启动 Web 服务失败:\n\n{e}")

    def show_help(self):
        """显示帮助"""
        help_text = """📖 使用帮助

【功能说明】
获取联通IPTV频道列表，生成 iptv.m3u 播放文件。

【使用步骤】
1. 填写认证信息（从机顶盒获取）
2. 点击「保存配置」
3. 点击「获取列表」
4. 成功后点击「打开输出目录」查看 iptv.m3u

【配置获取方法】
📺 查看机顶盒：
  - 背面标签（MAC地址）
  - 设置 → 系统信息（UserID/STBID）
  - 联系运营商客服

【播放器推荐】
  - PotPlayer：完美支持 .m3u
  - VLC：跨平台通用
  - Kodi：家庭影院中心

【输出文件】
  - data/iptv.m3u  ← 播放列表
  - data/epg.xml   ← 节目单（如有）

⚠️ 仅供学习交流，请遵守法律法规
"""
        messagebox.showinfo("使用帮助", help_text)


# ==================== 入口 ====================
def main():
    root = tk.Tk()
    app = IPTVDesktopTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()