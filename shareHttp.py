import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import threading
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
from datetime import datetime
import netifaces
import ipaddress
import qrcode
from PIL import Image, ImageTk
import io
import time
import json
import urllib.parse
import mimetypes
import re
import socketserver
import select

class FileSharingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python HTTP 文件共享工具")
        self.root.geometry("950x720")
        
        # 配置文件路径
        self.config_file = "file_sharing_config.json"
        
        # 服务器相关变量
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.shared_path = ""
        self.port = 1238
        self.selected_ip = ""
        self.network_interfaces = {}
        self.qr_image = None
        self.qr_photo = None
        
        # 配置变量（用于保存）
        self.last_config = {
            "shared_path": "",
            "selected_ip": "",
            "port": 1238,
            "bind_address": "0.0.0.0"
        }
        
        # 加载上一次的配置
        self.load_config()
        
        # 设置样式
        self.setup_styles()
        
        # 创建界面
        self.create_widgets()
        
        # 初始化网络接口
        self.refresh_network_interfaces()
        
        # 应用保存的配置
        self.apply_saved_config()
        
        # 初始化mimetypes
        mimetypes.init()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.last_config = json.load(f)
                print(f"加载配置: {self.last_config}")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            # 使用默认配置
            self.last_config = {
                "shared_path": "",
                "selected_ip": "",
                "port": 1238,
                "bind_address": "0.0.0.0"
            }
    
    def save_config(self):
        """保存配置文件"""
        try:
            # 更新配置
            self.last_config.update({
                "shared_path": self.folder_path.get() if hasattr(self, 'folder_path') else "",
                "selected_ip": self.selected_ip,
                "port": int(self.port_var.get()) if hasattr(self, 'port_var') else self.port,
                "bind_address": self.bind_address_var.get() if hasattr(self, 'bind_address_var') else "0.0.0.0"
            })
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.last_config, f, indent=2, ensure_ascii=False)
            print(f"保存配置: {self.last_config}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def apply_saved_config(self):
        """应用保存的配置到界面"""
        try:
            # 应用共享文件夹
            if hasattr(self, 'folder_path') and self.last_config["shared_path"]:
                if os.path.isdir(self.last_config["shared_path"]):
                    self.folder_path.set(self.last_config["shared_path"])
                    self.shared_path = self.last_config["shared_path"]
                    self.log_message(f"已加载上次共享文件夹: {self.last_config['shared_path']}")
            
            # 应用IP地址（需要在网络接口刷新后）
            if self.last_config["selected_ip"]:
                self.selected_ip = self.last_config["selected_ip"]
            
            # 应用端口
            if hasattr(self, 'port_var'):
                self.port_var.set(str(self.last_config["port"]))
            
            # 应用绑定地址
            if hasattr(self, 'bind_address_var'):
                self.bind_address_var.set(self.last_config["bind_address"])
            
            # 更新访问URL
            if hasattr(self, 'update_access_url'):
                self.update_access_url()
                
        except Exception as e:
            print(f"应用保存配置失败: {e}")
    
    def get_all_network_interfaces(self):
        """获取所有网络接口及其IP地址"""
        interfaces = {}
        
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                
                if netifaces.AF_INET in addrs:
                    ipv4_info = addrs[netifaces.AF_INET]
                    for addr in ipv4_info:
                        ip = addr['addr']
                        netmask = addr.get('netmask', '255.255.255.0')
                        
                        if (ip != '127.0.0.1' and 
                            not ip.startswith('169.254') and
                            not iface.startswith(('docker', 'veth', 'br-', 'vmnet'))):
                            
                            interface_info = {
                                'ip': ip,
                                'netmask': netmask,
                                'broadcast': addr.get('broadcast', ''),
                                'interface': iface
                            }
                            
                            if netifaces.AF_LINK in addrs:
                                link_info = addrs[netifaces.AF_LINK]
                                if link_info:
                                    interface_info['mac'] = link_info[0].get('addr', '')
                            
                            interfaces[ip] = interface_info
        except Exception as e:
            self.log_message(f"获取网络接口时出错: {str(e)}")
        
        if not interfaces:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                
                interfaces[ip] = {
                    'ip': ip,
                    'netmask': '255.255.255.0',
                    'broadcast': '',
                    'interface': 'eth0'
                }
            except:
                pass
        
        return interfaces
    
    def refresh_network_interfaces(self):
        """刷新网络接口列表"""
        self.network_interfaces = self.get_all_network_interfaces()
        
        if hasattr(self, 'ip_combobox'):
            ip_list = list(self.network_interfaces.keys())
            
            if ip_list:
                # 优先使用保存的IP
                saved_ip = self.last_config.get("selected_ip", "")
                current_ip = saved_ip if saved_ip and saved_ip in ip_list else ""
                
                if not current_ip:
                    current_ip = self.ip_var.get() if self.ip_var.get() != '未找到有效IP' else ""
                
                self.ip_combobox['values'] = ip_list
                
                if not current_ip or current_ip not in ip_list:
                    self.selected_ip = ip_list[0]
                    self.ip_var.set(ip_list[0])
                    self.update_interface_info(ip_list[0])
                else:
                    self.selected_ip = current_ip
                    self.ip_var.set(current_ip)
                    self.update_interface_info(current_ip)
            else:
                self.ip_combobox['values'] = ['未找到有效IP']
                self.ip_var.set('未找到有效IP')
                self.selected_ip = ""
                self.clear_interface_info()
        
        # 保存配置
        self.save_config()
    
    def update_interface_info(self, ip):
        """更新网卡详细信息"""
        if ip in self.network_interfaces:
            info = self.network_interfaces[ip]
            
            details = []
            details.append(f"网卡: {info['interface']}")
            details.append(f"IP: {info['ip']}")
            details.append(f"掩码: {info['netmask']}")
            if info.get('mac'):
                details.append(f"MAC: {info['mac']}")
            
            self.interface_info_text.delete(1.0, tk.END)
            self.interface_info_text.insert(tk.END, "\n".join(details))
            
            # 更新选择
            self.selected_ip = ip
            self.update_access_url()
            
            # 保存配置
            self.save_config()
    
    def clear_interface_info(self):
        """清空网卡信息"""
        self.interface_info_text.delete(1.0, tk.END)
        self.interface_info_text.insert(tk.END, "没有网络接口信息")
    
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="12")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题
        title_label = ttk.Label(main_frame, text="HTTP 文件共享工具", 
                                font=("Microsoft YaHei", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 15))
        
        # 左侧配置区域
        config_frame = ttk.Frame(main_frame)
        config_frame.grid(row=1, column=0, rowspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), 
                         padx=(0, 10))
        
        # 共享文件夹选择
        folder_frame = ttk.LabelFrame(config_frame, text="共享设置", padding="10")
        folder_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(folder_frame, text="共享文件夹:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.folder_path = tk.StringVar(value=self.last_config["shared_path"])
        path_entry = ttk.Entry(folder_frame, textvariable=self.folder_path, width=40)
        path_entry.grid(row=0, column=1, padx=(5, 5), pady=5)
        
        browse_btn = ttk.Button(folder_frame, text="浏览", command=self.browse_folder, width=8)
        browse_btn.grid(row=0, column=2, pady=5)
        
        # 网络接口选择
        network_frame = ttk.LabelFrame(config_frame, text="网络设置", padding="10")
        network_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(network_frame, text="选择IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.ip_var = tk.StringVar(value=self.last_config.get("selected_ip", ""))
        self.ip_combobox = ttk.Combobox(network_frame, textvariable=self.ip_var, 
                                        state="readonly", width=25)
        self.ip_combobox.grid(row=0, column=1, sticky=tk.W, padx=(5, 10), pady=5)
        self.ip_combobox.bind('<<ComboboxSelected>>', self.on_ip_selected)
        
        refresh_ip_btn = ttk.Button(network_frame, text="刷新", command=self.refresh_network_interfaces, width=8)
        refresh_ip_btn.grid(row=0, column=2, pady=5)
        
        # 端口设置
        port_frame = ttk.Frame(network_frame)
        port_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        ttk.Label(port_frame, text="端口号:").grid(row=0, column=0, sticky=tk.W)
        self.port_var = tk.StringVar(value=str(self.last_config["port"]))
        port_spinbox = ttk.Spinbox(port_frame, from_=1024, to=65535, 
                                   textvariable=self.port_var, width=10)
        port_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(5, 20))
        port_spinbox.bind('<KeyRelease>', lambda e: self.on_port_changed())
        
        ttk.Label(port_frame, text="绑定:").grid(row=0, column=2, sticky=tk.W)
        self.bind_address_var = tk.StringVar(value=self.last_config["bind_address"])
        bind_combo = ttk.Combobox(port_frame, textvariable=self.bind_address_var, 
                                 values=["0.0.0.0", "选择IP"], 
                                 state="readonly", width=10)
        bind_combo.grid(row=0, column=3, sticky=tk.W, padx=(5, 0))
        bind_combo.bind('<<ComboboxSelected>>', lambda e: self.save_config())
        
        # 网卡详细信息
        interface_frame = ttk.LabelFrame(config_frame, text="网卡信息", padding="10")
        interface_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.interface_info_text = scrolledtext.ScrolledText(interface_frame, height=6, width=40, 
                                                           font=("Consolas", 9))
        self.interface_info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 控制按钮部分
        control_frame = ttk.Frame(config_frame)
        control_frame.grid(row=3, column=0, pady=(15, 0))
        
        self.start_btn = ttk.Button(control_frame, text="启动共享", 
                                   command=self.start_sharing, width=12)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_btn = ttk.Button(control_frame, text="停止共享", 
                                  command=self.stop_sharing, width=12, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=(0, 10))
        
        test_btn = ttk.Button(control_frame, text="测试连接", 
                             command=self.test_connection, width=12)
        test_btn.grid(row=0, column=2)
        
        # 右侧访问信息区域
        access_frame = ttk.Frame(main_frame)
        access_frame.grid(row=1, column=1, rowspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 访问信息
        info_frame = ttk.LabelFrame(access_frame, text="访问信息", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(info_frame, text="访问地址:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.url_var = tk.StringVar(value="未选择IP")
        self.url_label = tk.Label(info_frame, textvariable=self.url_var, 
                                 font=("Arial", 10, "bold"), foreground="blue",
                                 cursor="hand2")
        self.url_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0), pady=5)
        self.url_label.bind("<Button-1>", self.on_url_click)
        
        copy_btn = ttk.Button(info_frame, text="复制", command=self.copy_url_to_clipboard, width=8)
        copy_btn.grid(row=0, column=2, padx=(10, 0), pady=5)
        
        browser_btn = ttk.Button(info_frame, text="打开浏览器", command=self.open_in_browser, width=12)
        browser_btn.grid(row=1, column=0, columnspan=3, pady=(10, 5))
        
        # 二维码区域
        qr_frame = ttk.Frame(info_frame)
        qr_frame.grid(row=2, column=0, columnspan=3, pady=(10, 5))
        
        self.qr_canvas = tk.Canvas(qr_frame, width=200, height=200, bg='white', 
                                  highlightthickness=1, highlightbackground="gray")
        self.qr_canvas.grid(row=0, column=0, pady=(5, 5))
        
        self.qr_label = ttk.Label(qr_frame, text="启动后生成二维码", 
                                 font=("Arial", 9), foreground="gray")
        self.qr_label.grid(row=1, column=0)
        
        qr_control_frame = ttk.Frame(qr_frame)
        qr_control_frame.grid(row=2, column=0, pady=(5, 0))
        
        self.save_qr_btn = ttk.Button(qr_control_frame, text="保存二维码", 
                                     command=self.save_qr_code, width=12, state=tk.DISABLED)
        self.save_qr_btn.grid(row=0, column=0, padx=(0, 5))
        
        refresh_qr_btn = ttk.Button(qr_control_frame, text="刷新", 
                                   command=self.generate_qr_code, width=8)
        refresh_qr_btn.grid(row=0, column=1)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(15, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, width=100, 
                                                font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        
        clear_btn = ttk.Button(log_control_frame, text="清空日志", 
                              command=self.clear_log, width=10)
        clear_btn.grid(row=0, column=0, padx=(0, 10))
        
        save_btn = ttk.Button(log_control_frame, text="保存日志", 
                             command=self.save_log, width=10)
        save_btn.grid(row=0, column=1)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W, padding=(5, 5))
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(15, 0))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        config_frame.columnconfigure(0, weight=1)
        config_frame.rowconfigure(2, weight=1)
        interface_frame.columnconfigure(0, weight=1)
        interface_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 初始化二维码
        self.clear_qr_code()
        
        # 绑定关闭事件保存配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_port_changed(self):
        """端口改变时更新并保存"""
        self.update_access_url()
        self.save_config()
    
    def on_url_click(self, event):
        """点击URL时打开浏览器"""
        if self.is_running and hasattr(self, 'access_url'):
            if "未选择IP" not in self.access_url:
                webbrowser.open(self.access_url)
                self.log_message(f"在浏览器中打开")
            else:
                messagebox.showwarning("警告", "请先选择有效的IP地址")
        else:
            messagebox.showwarning("警告", "请先启动共享服务器！")
    
    def browse_folder(self):
        """浏览并选择文件夹"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path.set(folder_selected)
            self.log_message(f"已选择文件夹: {folder_selected}")
            # 保存配置
            self.save_config()
    
    def on_ip_selected(self, event):
        """IP地址选择事件"""
        selected_ip = self.ip_var.get()
        if selected_ip and selected_ip in self.network_interfaces:
            self.selected_ip = selected_ip
            self.update_interface_info(selected_ip)
            self.log_message(f"已选择IP地址: {selected_ip}")
            if self.is_running:
                self.generate_qr_code()
    
    def update_access_url(self):
        """更新访问URL"""
        try:
            port = int(self.port_var.get())
            if self.bind_address_var.get() == "选择IP":
                ip = self.selected_ip if self.selected_ip else "未选择IP"
            else:
                ip = self.selected_ip if self.selected_ip else "未选择IP"
            
            self.access_url = f"http://{ip}:{port}"
            self.url_var.set(self.access_url)
            
            if "未选择IP" in self.access_url:
                self.url_label.config(fg="gray", cursor="arrow")
            else:
                self.url_label.config(fg="blue", cursor="hand2")
            
            if self.is_running and "未选择IP" not in self.access_url:
                self.generate_qr_code()
        except ValueError:
            self.url_var.set("端口无效")
    
    def generate_qr_code(self):
        """生成并显示二维码"""
        if not hasattr(self, 'access_url') or "未选择IP" in self.access_url:
            self.clear_qr_code()
            return
        
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6,
                border=2,
            )
            qr.add_data(self.access_url)
            qr.make(fit=True)
            
            self.qr_image = qr.make_image(fill_color="black", back_color="white")
            qr_image_resized = self.qr_image.resize((180, 180), Image.Resampling.LANCZOS)
            self.qr_photo = ImageTk.PhotoImage(qr_image_resized)
            
            self.qr_canvas.delete("all")
            self.qr_canvas.create_image(100, 100, image=self.qr_photo)
            
            self.qr_label.config(text="扫描二维码访问", foreground="green")
            self.save_qr_btn.config(state=tk.NORMAL)
            
            self.log_message(f"二维码已生成")
            
        except Exception as e:
            self.log_message(f"生成二维码时出错: {str(e)}")
            self.clear_qr_code()
    
    def clear_qr_code(self):
        """清空二维码显示"""
        self.qr_canvas.delete("all")
        self.qr_canvas.create_rectangle(0, 0, 200, 200, fill="white", outline="")
        self.qr_canvas.create_text(100, 100, text="无访问地址", 
                                  fill="gray", font=("Arial", 12))
        self.qr_label.config(text="启动后生成二维码", foreground="gray")
        self.save_qr_btn.config(state=tk.DISABLED)
    
    def save_qr_code(self):
        """保存二维码到文件"""
        if self.qr_image:
            try:
                filename = f"qr_code_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.qr_image.save(filename)
                self.log_message(f"二维码已保存: {filename}")
                messagebox.showinfo("成功", f"二维码已保存到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"保存二维码失败: {str(e)}")
    
    def get_bind_address(self):
        """获取服务器绑定地址"""
        bind_option = self.bind_address_var.get()
        
        if bind_option == "选择IP":
            return self.selected_ip if self.selected_ip else "0.0.0.0"
        else:
            return "0.0.0.0"
    
    def log_message(self, message):
        """记录日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("日志已清空")
    
    def save_log(self):
        """保存日志到文件"""
        try:
            log_content = self.log_text.get(1.0, tk.END)
            if log_content.strip():
                filename = f"file_sharing_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                self.log_message(f"日志已保存: {filename}")
                messagebox.showinfo("成功", f"日志已保存到: {filename}")
            else:
                messagebox.showwarning("警告", "没有日志内容可保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存日志失败: {str(e)}")
    
    def copy_url_to_clipboard(self):
        """复制URL到剪贴板"""
        if hasattr(self, 'access_url') and self.access_url and "未选择IP" not in self.access_url:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.access_url)
            self.log_message(f"已复制URL到剪贴板")
            messagebox.showinfo("成功", "URL已复制到剪贴板")
        else:
            messagebox.showwarning("警告", "没有有效的URL可复制")
    
    def test_connection(self):
        """测试服务器连接"""
        if not self.selected_ip:
            messagebox.showwarning("警告", "请先选择或输入IP地址")
            return
        
        try:
            port = int(self.port_var.get())
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            
            result = sock.connect_ex((self.selected_ip, port))
            sock.close()
            
            if result == 0:
                self.log_message(f"端口 {port} 已被占用")
                messagebox.showwarning("端口被占用", f"端口 {port} 已被占用")
                return False
            else:
                self.log_message(f"端口 {port} 可用")
                return True
                
        except Exception as e:
            self.log_message(f"连接测试失败: {str(e)}")
            return False
    
    def start_sharing(self):
        """启动HTTP文件共享"""
        # 验证文件夹
        shared_path = self.folder_path.get()
        if not shared_path or not os.path.isdir(shared_path):
            messagebox.showerror("错误", "请选择有效的共享文件夹！")
            return
        
        # 验证IP地址
        if not self.selected_ip:
            messagebox.showerror("错误", "请选择或输入有效的IP地址！")
            return
        
        # 验证端口
        try:
            self.port = int(self.port_var.get())
            if not (1024 <= self.port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "端口号必须在1024-65535之间！")
            return
        
        # 测试端口可用性
        if not self.test_connection():
            if not messagebox.askyesno("确认", "端口可能被占用，是否继续尝试启动？"):
                return
        
        self.shared_path = shared_path
        self.update_access_url()
        
        # 保存配置
        self.save_config()
        
        # 获取绑定地址
        bind_address = self.get_bind_address()
        
        # 启动服务器线程
        self.is_running = True
        self.server_thread = threading.Thread(
            target=self.run_server, 
            args=(bind_address, self.shared_path),
            daemon=True
        )
        self.server_thread.start()
        
        # 更新界面状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set(f"正在运行 - {self.selected_ip}:{self.port}")
        
        # 生成二维码
        self.generate_qr_code()
        
        self.log_message(f"HTTP服务器已启动")
        self.log_message(f"绑定地址: {bind_address}")
        self.log_message(f"共享文件夹: {shared_path}")
        self.log_message(f"访问地址: {self.access_url}")
        self.log_message("提示: 确保防火墙已允许端口访问")
        self.log_message("支持多设备同时访问")
    
    def run_server(self, bind_address, shared_path):
        """运行HTTP服务器 - 修复多设备访问和停止卡顿问题"""
        try:
            # 自定义HTTP请求处理器
            class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
                server_version = "FileSharingServer/1.0"
                protocol_version = "HTTP/1.1"
                
                # 设置超时时间，避免连接卡住
                timeout = 30
                
                def __init__(self, *args, **kwargs):
                    # 保存shared_path作为实例属性
                    self.shared_path = shared_path
                    # 调用父类的__init__，传递directory参数
                    super().__init__(*args, directory=self.shared_path, **kwargs)
                
                def handle(self):
                    """重写handle方法以支持更好的并发"""
                    try:
                        self.raw_requestline = self.rfile.readline(65537)
                        if len(self.raw_requestline) > 65536:
                            self.requestline = ''
                            self.request_version = ''
                            self.command = ''
                            self.send_error(414)
                            return
                        
                        if not self.raw_requestline:
                            self.close_connection = 1
                            return
                            
                        if not self.parse_request():
                            return
                            
                        method_handler = getattr(self, 'do_' + self.command, None)
                        if method_handler is None:
                            self.send_error(501, "Unsupported method (%r)" % self.command)
                            return
                            
                        method_handler()
                        
                    except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError) as e:
                        # 忽略常见的网络错误
                        pass
                    except Exception as e:
                        if hasattr(self, 'server_app'):
                            self.server_app.log_message(f"请求处理异常: {str(e)}")
                        try:
                            self.send_error(500)
                        except:
                            pass
                    finally:
                        try:
                            self.wfile.flush()
                        except:
                            pass
                
                def do_GET(self):
                    """处理GET请求"""
                    try:
                        # 解码URL路径
                        path = urllib.parse.unquote(self.path)
                        
                        # 处理根路径
                        if path == '/' or path == '':
                            self.send_directory_listing()
                            return
                        
                        # 获取文件完整路径
                        full_path = os.path.abspath(os.path.join(self.shared_path, path.lstrip('/')))
                        
                        # 安全性检查：确保请求路径在共享目录内
                        if not full_path.startswith(os.path.abspath(self.shared_path)):
                            self.send_error(403, "Forbidden")
                            return
                        
                        # 检查文件是否存在
                        if not os.path.exists(full_path):
                            self.send_error(404, "File not found")
                            return
                        
                        # 如果是目录，显示目录列表
                        if os.path.isdir(full_path):
                            self.directory = full_path
                            self.send_directory_listing()
                            return
                        
                        # 如果是文件，提供下载
                        self.send_file(full_path)
                        
                    except Exception as e:
                        if hasattr(self, 'server_app'):
                            self.server_app.log_message(f"请求处理错误: {str(e)}")
                        self.send_error(500, "Internal Server Error")
                
                def send_directory_listing(self):
                    """发送目录列表HTML页面"""
                    try:
                        # 获取当前目录 - 使用实例属性self.shared_path
                        current_dir = getattr(self, 'directory', self.shared_path)
                        relative_path = os.path.relpath(current_dir, self.shared_path)
                        if relative_path == '.':
                            relative_path = ''
                        
                        # 读取目录内容
                        try:
                            list_dir = os.listdir(current_dir)
                        except PermissionError:
                            self.send_error(403, "Permission denied")
                            return
                        
                        # 生成HTML - 使用实例属性self.shared_path
                        html = [
                            '<!DOCTYPE html>',
                            '<html>',
                            '<head>',
                            '<meta charset="utf-8">',
                            '<title>文件共享 - ' + (relative_path if relative_path else '根目录') + '</title>',
                            '<style>',
                            'body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }',
                            '.container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }',
                            'h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }',
                            '.path-info { background-color: #e8f5e9; padding: 10px; border-radius: 4px; margin-bottom: 20px; }',
                            '.path-info strong { color: #2e7d32; }',
                            'table { border-collapse: collapse; width: 100%; margin-top: 20px; }',
                            'th { background-color: #4CAF50; color: white; padding: 15px; text-align: left; font-weight: bold; }',
                            'td { padding: 12px; border-bottom: 1px solid #ddd; }',
                            'tr:hover { background-color: #f1f8e9; }',
                            'a { color: #0066cc; text-decoration: none; display: block; }',
                            'a:hover { text-decoration: underline; color: #ff5722; }',
                            '.dir-link { color: #009688; }',
                            '.file-link { color: #2196f3; }',
                            '.file-size { color: #666; font-size: 0.9em; }',
                            '.file-date { color: #888; font-size: 0.9em; }',
                            '.icon { margin-right: 8px; font-size: 1.1em; }',
                            '.breadcrumb { margin-bottom: 15px; font-size: 0.9em; }',
                            '.breadcrumb a { color: #4CAF50; }',
                            '.stats { color: #666; font-size: 0.9em; margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee; }',
                            '</style>',
                            '</head>',
                            '<body>',
                            '<div class="container">',
                            '<h1>📁 文件共享</h1>',
                            '<div class="path-info">',
                            '<p><strong>共享目录:</strong> ' + self.shared_path + '</p>',
                            '<p><strong>当前路径:</strong> ' + (relative_path if relative_path else '根目录') + '</p>',
                            '</div>'
                        ]
                        
                        # 添加面包屑导航
                        breadcrumb_parts = []
                        if relative_path:
                            parts = relative_path.split('/')
                            current_path = ''
                            for i, part in enumerate(parts):
                                if part:
                                    current_path += '/' + part if current_path else part
                                    if i == len(parts) - 1:
                                        breadcrumb_parts.append(f'<span>{part}</span>')
                                    else:
                                        breadcrumb_parts.append(f'<a href="/{current_path}">{part}</a>')
                        
                        if breadcrumb_parts:
                            html.append('<div class="breadcrumb">')
                            html.append('<a href="/">根目录</a> / ' + ' / '.join(breadcrumb_parts))
                            html.append('</div>')
                        
                        # 添加目录和文件列表
                        html.extend([
                            '<table>',
                            '<tr><th>名称</th><th>类型</th><th>大小</th><th>修改时间</th></tr>'
                        ])
                        
                        # 添加上级目录链接（如果不是根目录）
                        if current_dir != self.shared_path:
                            parent_dir = os.path.dirname(current_dir)
                            parent_rel = os.path.relpath(parent_dir, self.shared_path)
                            if parent_rel == '.':
                                parent_rel = ''
                            html.append('<tr>')
                            html.append('<td><a href="/' + parent_rel.replace('\\', '/') + '" class="dir-link"><span class="icon">⬆</span>上级目录</a></td>')
                            html.append('<td>目录</td>')
                            html.append('<td>-</td>')
                            html.append('<td>-</td>')
                            html.append('</tr>')
                        
                        # 先列出目录，再列出文件
                        dirs = []
                        files = []
                        for name in list_dir:
                            full_path = os.path.join(current_dir, name)
                            if os.path.isdir(full_path):
                                dirs.append(name)
                            else:
                                files.append(name)
                        
                        # 添加目录列表
                        for name in sorted(dirs):
                            full_path = os.path.join(current_dir, name)
                            rel_path = os.path.relpath(full_path, self.shared_path).replace('\\', '/')
                            
                            mtime = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')
                            
                            html.append('<tr>')
                            html.append(f'<td><a href="/{rel_path}" class="dir-link"><span class="icon">📁</span>{name}</a></td>')
                            html.append('<td>目录</td>')
                            html.append('<td>-</td>')
                            html.append(f'<td class="file-date">{mtime}</td>')
                            html.append('</tr>')
                        
                        # 添加文件列表
                        for name in sorted(files):
                            full_path = os.path.join(current_dir, name)
                            rel_path = os.path.relpath(full_path, self.shared_path).replace('\\', '/')
                            
                            size = self.format_size(os.path.getsize(full_path))
                            mtime = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')
                            
                            html.append('<tr>')
                            html.append(f'<td><a href="/{rel_path}" class="file-link" download><span class="icon">📄</span>{name}</a></td>')
                            html.append('<td>文件</td>')
                            html.append(f'<td><span class="file-size">{size}</span></td>')
                            html.append(f'<td class="file-date">{mtime}</td>')
                            html.append('</tr>')
                        
                        html.extend([
                            '</table>',
                            '<div class="stats">',
                            f'<p>共 {len(dirs)} 个目录, {len(files)} 个文件</p>',
                            '<p>点击文件名可直接下载文件</p>',
                            '</div>',
                            '</div>',
                            '</body>',
                            '</html>'
                        ])
                        
                        # 发送响应
                        self.send_response(200)
                        self.send_header("Content-type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len('\n'.join(html).encode('utf-8'))))
                        self.end_headers()
                        self.wfile.write('\n'.join(html).encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, "Internal Server Error")
                        if hasattr(self, 'server_app'):
                            self.server_app.log_message(f"目录列表生成错误: {str(e)}")
                
                def send_file(self, filepath):
                    """发送文件内容，支持下载 - 使用系统mimetypes"""
                    try:
                        # 获取文件大小
                        file_size = os.path.getsize(filepath)
                        
                        # 使用系统的mimetypes模块自动识别文件类型
                        content_type, _ = mimetypes.guess_type(filepath)
                        if content_type is None:
                            content_type = 'application/octet-stream'
                        
                        # 设置响应头
                        self.send_response(200)
                        self.send_header("Content-Type", content_type)
                        self.send_header("Content-Length", str(file_size))
                        
                        # 添加下载相关头
                        filename = os.path.basename(filepath)
                        safe_filename = urllib.parse.quote(filename)
                        self.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
                        
                        # 缓存控制
                        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                        self.send_header("Pragma", "no-cache")
                        self.send_header("Expires", "0")
                        
                        # 跨域支持
                        self.send_header("Access-Control-Allow-Origin", "*")
                        
                        self.end_headers()
                        
                        # 发送文件内容
                        with open(filepath, 'rb') as f:
                            # 使用更大的缓冲区提高传输速度
                            buffer_size = 8192 * 8  # 64KB
                            while True:
                                data = f.read(buffer_size)
                                if not data:
                                    break
                                try:
                                    self.wfile.write(data)
                                except (ConnectionResetError, BrokenPipeError):
                                    # 客户端断开连接，停止发送
                                    break
                        
                        if hasattr(self, 'server_app'):
                            self.server_app.log_message(f"下载文件: {filename} ({self.format_size(file_size)})")
                            
                    except Exception as e:
                        self.send_error(500, "Internal Server Error")
                        if hasattr(self, 'server_app'):
                            self.server_app.log_message(f"文件发送错误: {str(e)}")
                
                @staticmethod
                def format_size(size):
                    """格式化文件大小"""
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if size < 1024.0:
                            return f"{size:.1f} {unit}"
                        size /= 1024.0
                    return f"{size:.1f} TB"
                
                def log_message(self, format, *args):
                    """简化日志输出"""
                    # 完全禁用父类的日志输出，避免标题栏显示多余信息
                    pass
                
                def log_request(self, format, *args):
                    """请求日志"""
                    try:
                        message = format % args
                        if hasattr(self, 'server_app'):
                            # 忽略favicon.ico等不重要的请求
                            if 'favicon.ico' not in message:
                                # 使用正则表达式安全地解析日志
                                request_match = re.search(r'"([^"]+)"', message)
                                if request_match:
                                    request_line = request_match.group(1)
                                    
                                    # 查找状态码（3位数字）
                                    status_match = re.search(r'\s(\d{3})\s', message)
                                    status_code = status_match.group(1) if status_match else "000"
                                    
                                    # 解析请求行
                                    request_parts = request_line.split()
                                    if len(request_parts) >= 2:
                                        method = request_parts[0]
                                        path = request_parts[1]
                                        
                                        # 记录不同类型的请求
                                        if status_code.startswith('4') or status_code.startswith('5'):
                                            # 错误请求
                                            self.server_app.log_message(f"错误: {method} {path} - {status_code}")
                                        elif method == 'GET' and path != '/' and '.' in os.path.basename(path):
                                            # 文件下载
                                            self.server_app.log_message(f"下载: {path}")
                    except Exception as e:
                        # 静默处理日志错误
                        pass
                
                def log_error(self, format, *args):
                    """错误日志"""
                    message = format % args
                    if hasattr(self, 'server_app'):
                        self.server_app.log_message(f"错误: {message}")
                
                def version_string(self):
                    """自定义服务器版本字符串，避免显示Python版本"""
                    return self.server_version
                
                def date_time_string(self, timestamp=None):
                    """重写日期时间字符串生成"""
                    if timestamp is None:
                        timestamp = time.time()
                    return time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(timestamp))
            
            # 创建服务器，使用ThreadingHTTPServer支持多设备同时访问
            class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
                """支持多线程的HTTP服务器"""
                daemon_threads = True  # 设置线程为守护线程，这样停止时不会卡住
                timeout = 5  # 设置socket超时时间
                
                def server_bind(self):
                    """绑定服务器socket"""
                    HTTPServer.server_bind(self)
                    self.socket.settimeout(self.timeout)  # 设置超时
            
            server_address = (bind_address, self.port)
            self.server = ThreadedHTTPServer(server_address, CustomHTTPRequestHandler)
            
            # 设置socket选项以提高性能
            self.server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.server.socket.settimeout(5)  # 设置socket超时
            
            # 设置请求队列大小
            self.server.request_queue_size = 128
            
            # 设置处理器的应用实例
            for handler in [CustomHTTPRequestHandler]:
                handler.server_app = self
            
            self.log_message(f"服务器监听: {bind_address}:{self.port}")
            self.log_message("支持多设备同时访问，性能已优化")
            self.log_message(f"共享目录: {shared_path}")
            
            # 使用自定义的serve_forever，支持优雅停止
            self.server.serve_forever(poll_interval=0.5)
            
        except Exception as e:
            if self.is_running:
                error_msg = str(e)
                self.log_message(f"服务器错误: {error_msg}")
                self.root.after(0, self.handle_server_error, error_msg)
    
    def stop_sharing(self):
        """停止HTTP文件共享 - 修复卡顿问题"""
        self.is_running = False
        
        if self.server:
            try:
                # 先关闭socket，强制断开所有连接
                self.server.socket.close()
                
                # 创建一个线程来执行shutdown，避免主线程卡住
                def shutdown_server():
                    try:
                        # 设置超时，避免shutdown卡住
                        self.server.shutdown()
                        self.server.server_close()
                        self.server = None
                        
                        # 在主线程中更新UI
                        self.root.after(0, self._update_ui_after_stop)
                    except Exception as e:
                        self.root.after(0, self._update_ui_after_stop)
                        self.log_message(f"停止服务器时出错: {str(e)}")
                
                # 启动关闭线程
                shutdown_thread = threading.Thread(target=shutdown_server, daemon=True)
                shutdown_thread.start()
                
                # 立即更新UI状态，不等待服务器完全关闭
                self._update_ui_after_stop()
                
            except Exception as e:
                self.log_message(f"停止服务器时出错: {str(e)}")
                self._update_ui_after_stop()
        else:
            self._update_ui_after_stop()
    
    def _update_ui_after_stop(self):
        """停止服务器后更新UI"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("已停止")
        self.clear_qr_code()
        self.log_message("HTTP服务器已停止")
    
    def handle_server_error(self, error_msg):
        """处理服务器错误"""
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("服务器错误")
        
        self.clear_qr_code()
        
        if "10049" in error_msg:
            messagebox.showerror("绑定错误", 
                f"无法绑定到IP地址\n建议使用 '0.0.0.0' 绑定所有接口")
        else:
            messagebox.showerror("服务器错误", f"无法启动HTTP服务器:\n{error_msg}")
    
    def open_in_browser(self):
        """在浏览器中打开共享地址"""
        if self.is_running and hasattr(self, 'access_url'):
            if "未选择IP" not in self.access_url:
                webbrowser.open(self.access_url)
                self.log_message(f"在浏览器中打开")
            else:
                messagebox.showwarning("警告", "请先选择有效的IP地址")
        else:
            messagebox.showwarning("警告", "请先启动共享服务器！")
    
    def on_closing(self):
        """关闭窗口时的处理"""
        # 保存配置
        self.save_config()
        
        if self.is_running:
            if messagebox.askokcancel("退出", "HTTP服务器正在运行，确定要退出吗？"):
                # 快速停止服务器，不等待完全关闭
                self.is_running = False
                if self.server:
                    try:
                        self.server.socket.close()
                    except:
                        pass
                self.root.destroy()
        else:
            self.root.destroy()

def main():
    root = tk.Tk()
    app = FileSharingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()