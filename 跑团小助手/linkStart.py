# -*- coding: utf-8 -*-
"""
跑团小助手 - 角色卡（JSON 数据版）
- 顶部：读取 / 保存；菜单：数据 → 浏览全部数据…
- 行1：角色名称 | 玩家名字
- 行2：种族（下拉·来自 data/races.json） + 「…」选择弹窗
- 行3：职业（下拉·来自 data/classes.json） + 「…」
- 行4：背景（下拉·来自 data/backgrounds.json） + 「…」
- 选择弹窗：左列表(name)，右侧显示该项所有字段，点【选择该项】回填主界面
- 数据总览：只读，按标签页显示三份 JSON 的全部内容（表格）

JSON 兼容输入格式：
1) 列表：[
      {"name":"人类","desc":"通用", "speed":30},
      {"name":"精灵","desc":"黑暗视觉"}
   ]
2) 对象带 items：{"items":[ {...}, {...} ]}
3) 字典表：{"人类":{"desc":"通用"}, "精灵":{"desc":"黑暗视觉"}}
4) JSON Lines（每行一个对象）：{...}\n{...}\n（应至少包含 name 或能推断 name）
"""

import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAR_DIR = os.path.join(BASE_DIR, "characters")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(CHAR_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# -------------------- JSON 读取工具 --------------------
def _try_read_text(path):
    """尝试多种常见编码读取文本，失败返回 None。"""
    encodings = ["utf-8-sig", "utf-8", "gbk", "big5", "ansi", "iso-8859-1", "latin1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            if text and text.strip():
                return text
        except Exception:
            continue
    return None

def _normalize_record(rec, fallback_name=None):
    """标准化单条记录为 dict，确保有 name 字段。"""
    if not isinstance(rec, dict):
        # 如果是纯字符串，作为 name
        if isinstance(rec, str):
            return {"name": rec}
        # 其它类型不处理
        return None

    # 容错：允许 '名称'、'title' 等作为 name
    name = rec.get("name")
    if not name:
        name = rec.get("名称") or rec.get("title") or fallback_name

    out = {}
    for k, v in rec.items():
        if k is None:
            continue
        kk = str(k).strip()
        if kk:
            out[kk] = v if v is not None else ""
    if name is not None and "name" not in out:
        out["name"] = str(name)
    return out if out.get("name") else None

def read_json_records(path):
    """
    读取 JSON，返回记录列表（每条为 dict，至少包含 name）。
    支持四种结构（见模块头注释）。
    """
    if not os.path.exists(path):
        return []

    text = _try_read_text(path)
    if not text:
        return []

    # 先尝试整体 json
    data = None
    try:
        data = json.loads(text)
    except Exception:
        # 尝试 JSON Lines（每行一个对象）
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                norm = _normalize_record(obj)
                if norm:
                    records.append(norm)
            except Exception:
                continue
        return records

    # 解析四种结构
    records = []
    if isinstance(data, list):
        for item in data:
            norm = _normalize_record(item)
            if norm:
                records.append(norm)
    elif isinstance(data, dict):
        if isinstance(data.get("items"), list):
            for item in data["items"]:
                norm = _normalize_record(item)
                if norm:
                    records.append(norm)
        else:
            # 字典表：键为名称，值为详情
            for k, v in data.items():
                if isinstance(v, dict):
                    norm = _normalize_record(v, fallback_name=str(k))
                else:
                    norm = _normalize_record({"name": str(k), "value": v})
                if norm:
                    records.append(norm)
    else:
        # 其它结构不支持
        pass

    # 去重保序（按 name）
    seen = set()
    out = []
    for r in records:
        nm = str(r.get("name", "")).strip()
        if not nm:
            continue
        if nm in seen:
            continue
        seen.add(nm)
        out.append(r)
    return out

def load_name_list(path):
    """仅取 name 列作为下拉候选。"""
    recs = read_json_records(path)
    names = []
    seen = set()
    for r in recs:
        nm = str(r.get("name", "")).strip()
        if nm and nm not in seen:
            seen.add(nm)
            names.append(nm)
    return names

# -------------------- 选择弹窗 --------------------
class SelectDialog(tk.Toplevel):
    def __init__(self, master, title, json_path, on_select):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(580, 360)

        self._json_path = json_path
        self.on_select = on_select
        self.records = read_json_records(json_path)

        if not self.records:
            messagebox.showwarning(
                "JSON 为空或未解析",
                "未从以下文件解析到数据：\n{}\n\n"
                "请确认：\n"
                "1) 文件位于 data/ 目录；\n"
                "2) 顶层为数组/对象（见文件头说明）；\n"
                "3) 每项含有 name（或可由“名称/title/字典键”推断）。".format(json_path)
            )

        container = ttk.Frame(self); container.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(container); left.pack(side="left", fill="y")
        right = ttk.Frame(container); right.pack(side="left", fill="both", expand=True, padx=(10,0))

        # 左列：name 列表
        ttk.Label(left, text="列表（name）").pack(anchor="w")
        self.listbox = tk.Listbox(left, height=18, exportselection=False)
        self.listbox.pack(fill="y", expand=False)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        for r in self.records:
            nm = str(r.get("name", "")).strip()
            if nm:
                self.listbox.insert("end", nm)

        # 右侧：详情
        ttk.Label(right, text="详情").pack(anchor="w")
        self.detail = tk.Text(right, height=18, wrap="word", state="disabled")
        self.detail.pack(fill="both", expand=True)

        # 底部按钮：刷新 / 关闭 / 选择该项
        btnbar = ttk.Frame(self); btnbar.pack(fill="x", pady=(0,10), padx=10)
        ttk.Button(btnbar, text="刷新", command=self._reload).pack(side="left")
        ttk.Button(btnbar, text="关闭", command=self.destroy).pack(side="right")
        self.btn_choose = ttk.Button(btnbar, text="选择该项", command=self.choose_current, state="disabled")
        self.btn_choose.pack(side="right", padx=(6,0))

        # 居中显示
        self.update_idletasks()
        try:
            x = self.master.winfo_rootx() + (self.master.winfo_width()-self.winfo_width())//2
            y = self.master.winfo_rooty() + (self.master.winfo_height()-self.winfo_height())//2
            self.geometry("+{}+{}".format(x, y))
        except Exception:
            pass

    def _reload(self):
        self.records = read_json_records(self._json_path)
        self.listbox.delete(0, "end")
        for r in self.records:
            nm = str(r.get("name", "")).strip()
            if nm:
                self.listbox.insert("end", nm)
        self.show_detail(None)
        self.btn_choose.config(state="disabled")

    def on_list_select(self, _ev=None):
        sel = self.listbox.curselection()
        if not sel:
            self.show_detail(None); self.btn_choose.config(state="disabled"); return
        nm = self.listbox.get(sel[0])
        rec = None
        for r in self.records:
            if str(r.get("name", "")).strip() == nm:
                rec = r; break
        self.show_detail(rec)
        self.btn_choose.config(state="normal" if rec else "disabled")

    def show_detail(self, rec):
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        if rec:
            # name 放到最前
            keys = list(rec.keys())
            if "name" in keys:
                keys.remove("name")
                keys = ["name"] + keys
            lines = []
            for k in keys:
                v = rec.get(k, "")
                lines.append("{}：{}".format(k, v))
            self.detail.insert("1.0", "\n".join(lines))
        else:
            self.detail.insert("1.0", "（未选中）")
        self.detail.config(state="disabled")

    def choose_current(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        nm = self.listbox.get(sel[0])
        if callable(self.on_select):
            self.on_select(nm)
        self.destroy()

# -------------------- 数据总览（只读） --------------------
class DataBrowser(tk.Toplevel):
    def __init__(self, master, datasets):
        super().__init__(master)
        self.title("数据总览（只读）")
        self.minsize(720, 420)

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True)

        for tab_name, path in datasets.items():
            frame = ttk.Frame(nb); nb.add(frame, text=tab_name)
            recs = read_json_records(path)
            if not recs:
                ttk.Label(frame, text="暂无数据或文件不存在：{}".format(path)).pack(padx=16, pady=16, anchor="w")
                continue
            # 收集所有出现过的键，做成表头
            cols = []
            seen = set()
            for r in recs:
                for k in r.keys():
                    if k not in seen:
                        seen.add(k); cols.append(k)
            tree = ttk.Treeview(frame, columns=cols, show="headings", height=16)
            for c in cols:
                tree.heading(c, text=c)
                tree.column(c, width=140, stretch=True)
            for r in recs:
                tree.insert("", "end", values=[r.get(c, "") for c in cols])
            tree.pack(fill="both", expand=True, padx=10, pady=10)

# -------------------- 主应用 --------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("跑团小助手 - 角色卡")
        self.geometry("820x440")
        self.resizable(False, False)

        # 菜单
        menubar = tk.Menu(self)
        m_data = tk.Menu(menubar, tearoff=0)
        m_data.add_command(label="浏览全部数据…", command=self.open_data_browser)
        m_data.add_command(label="刷新下拉（读JSON）", command=self.refresh_dropdowns)
        menubar.add_cascade(label="数据", menu=m_data)
        self.config(menu=menubar)

        # 顶部按钮
        top = ttk.Frame(self); top.pack(fill="x", pady=(12,0))
        ttk.Button(top, text="读取", command=self.load_character).pack(side="left", padx=(12,6))
        ttk.Button(top, text="保存", command=self.save_character).pack(side="left")

        frm = ttk.LabelFrame(self, text="角色信息"); frm.pack(fill="x", padx=12, pady=12)

        # 行1：角色/玩家
        ttk.Label(frm, text="角色名称").grid(row=0, column=0, sticky="e", padx=8, pady=10)
        self.var_name = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_name, width=22).grid(row=0, column=1, sticky="w", padx=8, pady=10)

        ttk.Label(frm, text="玩家名字").grid(row=0, column=2, sticky="e", padx=8, pady=10)
        self.var_player = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_player, width=22).grid(row=0, column=3, sticky="w", padx=8, pady=10)

        # 数据路径
        self.races_json = os.path.join(DATA_DIR, "races.json")
        self.classes_json = os.path.join(DATA_DIR, "classes.json")
        self.backgrounds_json = os.path.join(DATA_DIR, "backgrounds.json")

        # 下拉初始
        races = load_name_list(self.races_json)
        classes = load_name_list(self.classes_json)
        backgrounds = load_name_list(self.backgrounds_json)

        # 行2：种族
        ttk.Label(frm, text="种族").grid(row=1, column=0, sticky="e", padx=8, pady=10)
        self.var_race = tk.StringVar()
        self.cb_race = ttk.Combobox(frm, textvariable=self.var_race, values=races, state="readonly", width=25)
        self.cb_race.grid(row=1, column=1, sticky="w", padx=8, pady=10)
        ttk.Button(frm, text="…", width=3,
                   command=lambda: self.open_selector("选择种族", self.races_json, self.var_race))\
            .grid(row=1, column=2, sticky="w", padx=(0,8), pady=10)

        # 行3：职业
        ttk.Label(frm, text="职业").grid(row=2, column=0, sticky="e", padx=8, pady=10)
        self.var_class = tk.StringVar()
        self.cb_class = ttk.Combobox(frm, textvariable=self.var_class, values=classes, state="readonly", width=25)
        self.cb_class.grid(row=2, column=1, sticky="w", padx=8, pady=10)
        ttk.Button(frm, text="…", width=3,
                   command=lambda: self.open_selector("选择职业", self.classes_json, self.var_class))\
            .grid(row=2, column=2, sticky="w", padx=(0,8), pady=10)

        # 行4：背景
        ttk.Label(frm, text="背景").grid(row=3, column=0, sticky="e", padx=8, pady=10)
        self.var_background = tk.StringVar()
        self.cb_background = ttk.Combobox(frm, textvariable=self.var_background, values=backgrounds, state="readonly", width=25)
        self.cb_background.grid(row=3, column=1, sticky="w", padx=8, pady=10)
        ttk.Button(frm, text="…", width=3,
                   command=lambda: self.open_selector("选择背景", self.backgrounds_json, self.var_background))\
            .grid(row=3, column=2, sticky="w", padx=(0,8), pady=10)

        # 状态栏
        self.status = tk.StringVar(value="就绪")
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", side="bottom", padx=8, pady=6)

        # 数据模型
        self.model = {"name": "", "player": "", "race": "", "class": "", "background": ""}

        # 让主窗体置顶一下，防止被旧窗口挡住
        self.after(100, lambda: (self.lift(),
                                 self.attributes("-topmost", True),
                                 self.after(100, lambda: self.attributes("-topmost", False))))

    # —— 菜单：刷新下拉（从 JSON 重读） ——
    def refresh_dropdowns(self):
        cur_r, cur_c, cur_b = self.var_race.get(), self.var_class.get(), self.var_background.get()
        races = load_name_list(self.races_json)
        classes = load_name_list(self.classes_json)
        backgrounds = load_name_list(self.backgrounds_json)
        self.cb_race["values"] = races
        self.cb_class["values"] = classes
        self.cb_background["values"] = backgrounds
        if cur_r in races: self.var_race.set(cur_r)
        elif races: self.var_race.set(races[0])
        else: self.var_race.set("")
        if cur_c in classes: self.var_class.set(cur_c)
        elif classes: self.var_class.set(classes[0])
        else: self.var_class.set("")
        if cur_b in backgrounds: self.var_background.set(cur_b)
        elif backgrounds: self.var_background.set(backgrounds[0])
        else: self.var_background.set("")
        self.status.set("已刷新下拉（读 JSON）")

    # —— 打开选择器弹窗 ——
    def open_selector(self, title, json_path, target_var):
        def _on_select(name_val):
            target_var.set(name_val)
        SelectDialog(self, title, json_path, _on_select)

    # —— 数据总览 ——
    def open_data_browser(self):
        datasets = {
            "种族（races）": self.races_json,
            "职业（classes）": self.classes_json,
            "背景（backgrounds）": self.backgrounds_json,
        }
        DataBrowser(self, datasets)

    # —— 保存 —— 
    def save_character(self):
        name = (self.var_name.get() or "").strip()
        if not name:
            messagebox.showwarning("提示", "请先填写角色名称再保存。")
            return
        self.model.update({
            "name": name,
            "player": (self.var_player.get() or "").strip(),
            "race": (self.var_race.get() or "").strip(),
            "class": (self.var_class.get() or "").strip(),
            "background": (self.var_background.get() or "").strip(),
        })
        safe = "".join(c for c in name if c.isalnum() or c in (" ","_","-")).rstrip() or "Unnamed"
        path = os.path.join(CHAR_DIR, "{}.json".format(safe))
        if os.path.exists(path):
            if not messagebox.askyesno("确认覆盖", "角色「{}」已经存在。\n是否要覆盖原文件？".format(name)):
                self.status.set("已取消保存"); return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.model, f, indent=2, ensure_ascii=False)
            self.status.set("已保存：{}".format(path))
            messagebox.showinfo("已保存", "角色「{}」已保存到：\n{}".format(name, path))
        except Exception as e:
            messagebox.showerror("保存失败", "保存时发生错误：\n{}".format(e))

    # —— 读取 —— 
    def load_character(self):
        path = filedialog.askopenfilename(
            initialdir=CHAR_DIR, title="选择角色 JSON",
            filetypes=[("JSON 文件", "*.json")]
        )
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("读取失败", "无法读取文件：\n{}".format(e)); return

        self.model = data if isinstance(data, dict) else self.model
        self.var_name.set(self.model.get("name", ""))
        self.var_player.set(self.model.get("player", ""))
        self.var_race.set(self.model.get("race", ""))
        self.var_class.set(self.model.get("class", ""))
        self.var_background.set(self.model.get("background", ""))
        self.status.set("已读取：{}".format(path))

# -------------------- 入口（带启动信息） --------------------
if __name__ == "__main__":
    import sys, traceback
    print(">>> launching linkStart.py")
    print(">>> python:", sys.version)
    print(">>> exe   :", sys.executable)
    print(">>> cwd   :", os.getcwd())
    try:
        app = App()
        def _report_callback_exception(exc, val, tb):
            msg = "".join(traceback.format_exception(exc, val, tb))
            try:
                messagebox.showerror("未捕获异常", msg)
            except Exception:
                print(msg, file=sys.stderr)
        app.report_callback_exception = _report_callback_exception
        app.mainloop()
    except Exception:
        msg = traceback.format_exc()
        try:
            messagebox.showerror("启动失败", msg)
        except Exception:
            print(msg, file=sys.stderr)
