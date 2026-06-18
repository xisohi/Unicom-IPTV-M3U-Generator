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

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_FILE = os.path.join(BASE_DIR, "config.yaml")
OUTPUT_FILE = os.path.join(DATA_DIR, "iptv.m3u")


class IPTVDesktopTool:
    def __init__(self, root):
        self.root = root
        self.root.title("联通IPTV列表获取工具 v1.0")
        self.root.geometry("750x650")
        self.root.resizable(False, False)
        self.root.configure(bg='#f0f0f0')

        self.is_running = False
        self.web_process = None

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
        tk.Label(row1, text="例: http://10.0.0.1 或 http://10.0.0.1:8080",
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
        if os.path.exists(CONFIG_FILE):
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
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            self.log("✅ 配置已保存到 config.yaml", "success")
            self.set_status("✅ 配置已保存", "", "#27ae60")
            messagebox.showinfo("成功", "配置已保存到 config.yaml")
        except Exception as e:
            self.log(f"❌ 保存失败: {e}", "error")
            messagebox.showerror("错误", f"保存失败:\n{e}")

    def load_config(self, silent=False):
        """从 config.yaml 加载配置到界面"""
        if not os.path.exists(CONFIG_FILE):
            if not silent:
                messagebox.showwarning("提示", "未找到 config.yaml 配置文件")
            return

        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
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
        os.makedirs(DATA_DIR, exist_ok=True)

        # 后台执行
        thread = threading.Thread(target=self._run_scraper_thread,
                                  args=(server, user_id, stb_id, mac),
                                  daemon=True)
        thread.start()

    def _run_scraper_thread(self, server, user_id, stb_id, mac):
        """后台线程执行爬虫"""
        try:
            # 添加 src 目录到路径
            src_dir = os.path.join(BASE_DIR, "src")
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)

            # 设置环境变量
            os.environ["DATA_DIR"] = DATA_DIR

            # 导入项目模块
            from scraper import get_channel_list

            self.log("📡 正在连接 IPTV 服务器...", "info")

            # 执行获取
            channels = get_channel_list(
                server=server,
                user_id=user_id,
                stb_id=stb_id,
                mac=mac
            )

            if not channels:
                self.log("⚠️ 未获取到任何频道", "warning")
                self.root.after(0, lambda: self._on_error("未获取到频道，请检查配置"))
                return

            self.log(f"✅ 成功获取 {len(channels)} 个频道", "success")

            # 生成 M3U
            self.log("📝 正在生成播放列表...", "info")
            lines = ["#EXTM3U"]
            for ch in channels:
                name = ch.get("name", "未知频道")
                url = ch.get("url", "")
                if url:
                    lines.append(f'#EXTINF:-1,{name}')
                    lines.append(url)

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            self.log(f"✅ 播放列表已保存: {OUTPUT_FILE}", "success")
            self.log("=" * 55, "title")

            self.root.after(0, lambda: self._on_success(len(channels)))

        except ImportError as e:
            self.log(f"❌ 导入模块失败: {e}", "error")
            self.log("请确保在项目根目录运行，且已安装所有依赖", "warning")
            self.root.after(0, lambda: self._on_error(f"模块导入失败: {e}"))

        except Exception as e:
            self.log(f"❌ 错误: {str(e)}", "error")
            self.root.after(0, lambda: self._on_error(str(e)))

    def _on_success(self, count):
        """成功回调"""
        self.set_status(f"✅ 获取成功！共 {count} 个频道", f"文件: {OUTPUT_FILE}", "#27ae60")
        self.run_btn.config(state=tk.NORMAL, text="🚀 获取列表")
        self.is_running = False

        messagebox.showinfo("完成",
            f"✅ 频道列表获取成功！\n\n"
            f"共获取 {count} 个频道\n"
            f"文件位置: {OUTPUT_FILE}\n\n"
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
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        subprocess.Popen(f'explorer "{DATA_DIR}"')

    def open_web(self):
        """启动Web界面（如果可用）"""
        try:
            if self.web_process is None or self.web_process.poll() is not None:
                self.log("🌐 正在启动 Web 服务...", "info")
                self.web_process = subprocess.Popen(
                    [sys.executable, os.path.join(BASE_DIR, "src", "web.py")],
                    cwd=BASE_DIR,
                    env={**os.environ, "DATA_DIR": DATA_DIR},
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