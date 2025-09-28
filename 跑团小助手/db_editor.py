# -*- coding: utf-8 -*-
"""
数据库修改器（标签版，无顶部菜单）
- 每个标签内部自带按钮：
  左侧第1行：新增 / 复制 / 删除 / 保存文件
  左侧第2行：导入 CSV / 另存为…
  右侧：保存修改 / 清空内容
- 先做“种族”标签；数据文件默认 data/races.json
- JSON 统一保存为 list[dict]
"""

import os, json, csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

APP_TITLE = "数据库修改器（标签版）"

# —— 可扩展 schema：要加“职业/背景”等，只需在此再加条目 —— #
SCHEMAS = {
    "种族": {
        "file": os.path.join(DATA_DIR, "races.json"),
        "fields": [
            {"key": "name",        "label": "名称",     "type": "str",  "width": 28, "required": True},
            {"key": "desc",        "label": "描述",     "type": "text", "height": 6},
            {"key": "speed",       "label": "速度",     "type": "int",  "min": 0, "max": 60, "step": 5, "default": 30},
            {"key": "size",        "label": "体型",     "type": "enum", "options": ["Small", "Medium"], "default": "Medium"},
            {"key": "darkvision",  "label": "黑暗视觉", "type": "int",  "min": 0, "max": 120, "step": 5, "default": 0},
            {"key": "languages",   "label": "语言",     "type": "str"},
            {"key": "traits",      "label": "特性",     "type": "text", "height": 8},
        ],
    },
}

# ===================== I/O 工具 =====================
def try_read_text(path):
    for enc in ["utf-8-sig", "utf-8", "gbk", "big5", "ansi", "iso-8859-1", "latin1"]:
        try:
            with open(path, "r", encoding=enc) as f:
                t = f.read()
            if t and t.strip():
                return t
        except Exception:
            pass
    return None

def read_json_list(path):
    """读取为 list[dict]；兼容常见 JSON/JSONL 结构。"""
    if not os.path.exists(path):
        return []
    text = try_read_text(path)
    if not text:
        return []

    def norm_one(rec, fallback_name=None):
        if isinstance(rec, dict):
            out = {}
            for k, v in rec.items():
                kk = str(k).strip() if k is not None else ""
                if kk:
                    out[kk] = v if v is not None else ""
            if "name" not in out:
                nm = out.get("名称") or out.get("title") or fallback_name
                if nm is not None:
                    out["name"] = str(nm)
            return out if out.get("name") else None
        elif isinstance(rec, str):
            return {"name": rec}
        return None

    try:
        data = json.loads(text)
    except Exception:
        # JSON Lines
        arr = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                x = norm_one(obj)
                if x:
                    arr.append(x)
            except Exception:
                pass
        return arr

    out = []
    if isinstance(data, list):
        for it in data:
            x = norm_one(it)
            if x:
                out.append(x)
    elif isinstance(data, dict):
        if isinstance(data.get("items"), list):
            for it in data["items"]:
                x = norm_one(it)
                if x:
                    out.append(x)
        else:
            for k, v in data.items():
                if isinstance(v, dict):
                    x = norm_one(v, fallback_name=str(k))
                else:
                    x = norm_one({"name": str(k), "value": v})
                if x:
                    out.append(x)
    return out

def write_json_list(path, records):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def read_csv_rows(path):
    """自动编码+分隔符，返回 list[dict]。第二行若非空视为中文说明行。"""
    if not os.path.exists(path):
        return []
    text = try_read_text(path)
    if not text:
        return []
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=[",", ";", "\t", "|"])
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ","
    rows = []
    for enc in ["utf-8-sig", "utf-8", "gbk", "big5", "ansi", "iso-8859-1", "latin1"]:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f, dialect)
                rows = [[(c or "").strip() for c in r] for r in reader]
            if rows:
                break
        except Exception:
            rows = []
    if not rows:
        return []
    headers = [h.lstrip("\ufeff").strip() for h in rows[0]]
    data_rows = rows[2:] if len(rows) >= 2 and any((c or "").strip() for c in rows[1]) else rows[1:]
    out = []
    for r in data_rows:
        if not any((c or "").strip() for c in r):
            continue
        d = {}
        for i, k in enumerate(headers):
            if not k:
                continue
            d[k] = r[i] if i < len(r) else ""
        out.append(d)
    return out

# ===================== Tab 编辑器 =====================
class TabEditor(ttk.Frame):
    def __init__(self, master, schema):
        super().__init__(master)
        self.schema = schema
        self.file_path = schema["file"]
        self.records = []
        self.index = {}  # name -> idx

        # 左右布局
        left = ttk.Frame(self); left.pack(side="left", fill="y", padx=(0,8))
        right = ttk.Frame(self); right.pack(side="left", fill="both", expand=True)

        # —— 左侧：搜索（输入即筛选） + 列表 —— 
        sbar = ttk.Frame(left); sbar.pack(fill="x", pady=(0,4))
        ttk.Label(sbar, text="搜索").pack(side="left")
        self.var_q = tk.StringVar()
        ent = ttk.Entry(sbar, textvariable=self.var_q, width=20)
        ent.pack(side="left", padx=(6,0))
        ent.bind("<KeyRelease>", lambda e: self.refresh_list())

        ttk.Label(left, text="条目（name）").pack(anchor="w", pady=(4,2))
        self.listbox = tk.Listbox(left, width=26, height=24, exportselection=False)
        self.listbox.pack(fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # —— 左侧：按钮（两行） —— 
        row1 = ttk.Frame(left); row1.pack(fill="x", pady=(6,0))
        ttk.Button(row1, text="新增",   command=self.add_item).pack(side="left")
        ttk.Button(row1, text="复制",   command=self.dup_item).pack(side="left", padx=(6,0))
        ttk.Button(row1, text="删除",   command=self.del_item).pack(side="left", padx=(6,0))
        ttk.Button(row1, text="保存文件", command=self.save_file).pack(side="left", padx=(12,0))

        row2 = ttk.Frame(left); row2.pack(fill="x", pady=(6,0))
        ttk.Button(row2, text="导入 CSV", command=self.import_csv).pack(side="left")
        ttk.Button(row2, text="另存为…",   command=self.save_as).pack(side="left", padx=(6,0))

        # —— 右侧：表单（按 schema 生成） —— 
        frm = ttk.LabelFrame(right, text="详情")
        frm.pack(fill="both", expand=True)

        self.vars = {}      # key -> tk.Variable/None(for text)
        self.widgets = {}   # key -> widget
        row = 0
        for spec in self.schema["fields"]:
            key = spec["key"]; label = spec["label"]; ftype = spec["type"]
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="e", padx=8, pady=6)
            if ftype == "str":
                var = tk.StringVar()
                ent = ttk.Entry(frm, textvariable=var, width=spec.get("width", 30))
                ent.grid(row=row, column=1, sticky="w", padx=8, pady=6)
                self.vars[key] = var; self.widgets[key] = ent
            elif ftype == "int":
                var = tk.IntVar(value=spec.get("default", 0))
                spin = ttk.Spinbox(frm, from_=spec.get("min",0), to=spec.get("max",999),
                                   increment=spec.get("step",1), textvariable=var, width=8, wrap=True)
                spin.grid(row=row, column=1, sticky="w", padx=8, pady=6)
                self.vars[key] = var; self.widgets[key] = spin
            elif ftype == "enum":
                var = tk.StringVar(value=spec.get("default",""))
                cb = ttk.Combobox(frm, textvariable=var, values=spec.get("options",[]), state="readonly", width=12)
                cb.grid(row=row, column=1, sticky="w", padx=8, pady=6)
                self.vars[key] = var; self.widgets[key] = cb
            elif ftype == "text":
                txt = tk.Text(frm, height=spec.get("height",6), wrap="word")
                txt.grid(row=row, column=1, sticky="we", padx=8, pady=6)
                frm.grid_columnconfigure(1, weight=1)
                self.vars[key] = None; self.widgets[key] = txt
            else:
                var = tk.StringVar()
                ent = ttk.Entry(frm, textvariable=var, width=spec.get("width", 30))
                ent.grid(row=row, column=1, sticky="w", padx=8, pady=6)
                self.vars[key] = var; self.widgets[key] = ent
            row += 1

        bar = ttk.Frame(right); bar.pack(fill="x", pady=(6,0))
        ttk.Button(bar, text="保存修改", command=self.save_current_item).pack(side="left")
        ttk.Button(bar, text="清空内容", command=self.clear_form).pack(side="left", padx=(6,0))

        # 状态条
        self.status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", side="bottom")

        # 初始加载
        self.apply_records(read_json_list(self.file_path))

    # -------- records 操作 ----------
    def apply_records(self, records):
        # 去重保序
        seen = set(); out = []
        for r in records:
            if not isinstance(r, dict): continue
            nm = str(r.get("name","")).strip()
            if not nm: continue
            if nm in seen: continue
            seen.add(nm); out.append(r)
        self.records = out
        self.rebuild_index()
        self.refresh_list()
        self.status.set("记录数：{}（搜索框输入即筛选）".format(len(self.records)))
        self.clear_form()

    def rebuild_index(self):
        self.index = {}
        for i, r in enumerate(self.records):
            nm = str(r.get("name","")).strip()
            if nm and nm not in self.index:
                self.index[nm] = i

    def filtered_names(self):
        q = self.var_q.get().strip().lower()
        names = [str(r.get("name","")).strip() for r in self.records]
        if not q: return [n for n in names if n]
        return [n for n in names if n and q in n.lower()]

    def refresh_list(self):
        self.listbox.delete(0, "end")
        for nm in self.filtered_names():
            self.listbox.insert("end", nm)

    # -------- 表单绑定 ----------
    def fill_form(self, rec):
        for spec in self.schema["fields"]:
            k = spec["key"]; w = self.widgets[k]; v = self.vars[k]
            val = rec.get(k, spec.get("default",""))
            if v is None:     # text
                w.delete("1.0","end"); w.insert("1.0", str(val or ""))
            else:
                try:
                    if isinstance(v, tk.IntVar):
                        v.set(int(val) if str(val).strip()!="" else spec.get("default",0))
                    else:
                        v.set("" if val is None else str(val))
                except Exception:
                    v.set(str(val))
        self.status.set("已载入：{}".format(rec.get("name","")))

    def collect_form(self):
        rec = {}
        for spec in self.schema["fields"]:
            k = spec["key"]; v = self.vars[k]; w = self.widgets[k]
            if v is None:  # text
                rec[k] = w.get("1.0","end").strip()
            else:
                rec[k] = v.get()
        return rec

    def clear_form(self):
        for spec in self.schema["fields"]:
            k = spec["key"]; v = self.vars[k]; w = self.widgets[k]
            if v is None: w.delete("1.0","end")
            else: v.set("" if not isinstance(v, tk.IntVar) else spec.get("default",0))

    # -------- 列表事件 ----------
    def on_select(self, _=None):
        sel = self.listbox.curselection()
        if not sel: return
        nm = self.listbox.get(sel[0])
        idx = self.index.get(nm)
        if idx is None: return
        self.fill_form(self.records[idx])

    # -------- CRUD ----------
    def add_item(self):
        name = simpledialog.askstring("新增", "请输入名称（name）：", parent=self)
        if not name: return
        name = name.strip()
        if not name: return
        if name in self.index:
            messagebox.showwarning("已存在", "name='{}' 已存在。".format(name)); return
        rec = {"name": name}
        for f in self.schema["fields"]:
            if f["key"] not in rec:
                rec[f["key"]] = f.get("default","") if f["type"]!="text" else ""
        self.records.append(rec)
        self.rebuild_index(); self.refresh_list()
        self.select_name(name); self.fill_form(rec)
        self.status.set("已新增：{}".format(name))

    def dup_item(self):
        sel = self.listbox.curselection()
        if not sel: return
        old = self.listbox.get(sel[0])
        idx = self.index.get(old)
        if idx is None: return
        base = old; i = 2
        new = "{} (复制{})".format(base, i)
        while new in self.index:
            i += 1; new = "{} (复制{})".format(base, i)
        rec = dict(self.records[idx]); rec["name"] = new
        self.records.append(rec)
        self.rebuild_index(); self.refresh_list()
        self.select_name(new); self.fill_form(rec)
        self.status.set("已复制为：{}".format(new))

    def del_item(self):
        sel = self.listbox.curselection()
        if not sel: return
        nm = self.listbox.get(sel[0])
        if not messagebox.askyesno("删除确认", "确定删除：{} ？".format(nm)):
            return
        idx = self.index.get(nm)
        if idx is not None:
            del self.records[idx]
        self.rebuild_index(); self.refresh_list(); self.clear_form()
        self.status.set("已删除：{}".format(nm))

    def save_current_item(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先在左侧选择一条记录。"); return
        old = self.listbox.get(sel[0])
        idx = self.index.get(old)
        if idx is None: return

        rec = self.collect_form()
        for f in self.schema["fields"]:
            if f.get("required") and not str(rec.get(f["key"],"")).strip():
                messagebox.showerror("必填缺失", "请填写：{}".format(f["label"]))
                return

        new_name = str(rec.get("name","")).strip()
        if not new_name:
            messagebox.showerror("缺少名称", "name 不能为空。"); return
        if new_name != old and new_name in self.index:
            messagebox.showerror("重名", "已存在 name='{}'".format(new_name)); return

        self.records[idx] = rec
        self.rebuild_index(); self.refresh_list()
        self.select_name(new_name)
        self.status.set("已保存：{}".format(new_name))

    def reload_form(self):
        sel = self.listbox.curselection()
        if not sel: return
        nm = self.listbox.get(sel[0])
        idx = self.index.get(nm)
        if idx is None: return
        self.fill_form(self.records[idx])
        self.status.set("已还原：{}".format(nm))

    def select_name(self, nm):
        try:
            pos = self.filtered_names().index(nm)
            self.listbox.select_clear(0, "end")
            self.listbox.select_set(pos)
            self.listbox.event_generate("<<ListboxSelect>>")
        except Exception:
            pass

    # -------- 文件/导入（按钮触发） ----------
    def save_file(self):
        if not self.file_path:
            return self.save_as()
        try:
            write_json_list(self.file_path, self.records)
            self.status.set("已保存：{}".format(self.file_path))
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def save_as(self):
        p = filedialog.asksaveasfilename(title="另存为 JSON", defaultextension=".json",
                                         filetypes=[("JSON 文件","*.json")])
        if not p: return
        self.file_path = p
        self.save_file()

    def import_csv(self):
        p = filedialog.askopenfilename(title="选择 CSV", filetypes=[("CSV 文件","*.csv")])
        if not p: return
        rows = read_csv_rows(p)
        if not rows:
            messagebox.showwarning("没有数据", "未解析到有效 CSV 行。"); return

        headers = []
        for r in rows:
            for k in r.keys():
                if k not in headers:
                    headers.append(k)

        if "name" in headers:
            name_col = "name"
        else:
            dlg = tk.Toplevel(self); dlg.title("选择 name 列"); dlg.grab_set(); dlg.resizable(False, False)
            ttk.Label(dlg, text="请选择 CSV 中作为 name 的列：").pack(padx=12, pady=(12,6))
            var = tk.StringVar(value=headers[0] if headers else "")
            ttk.OptionMenu(dlg, var, var.get(), *headers).pack(padx=12, pady=6)
            ttk.Button(dlg, text="确定", command=dlg.destroy).pack(pady=(0,12))
            dlg.wait_window()
            name_col = var.get().strip()
            if not name_col:
                messagebox.showerror("导入中断", "未选择 name 列。"); return

        st = self.ask_merge_strategy()
        if not st: return

        field_keys = [f["key"] for f in self.schema["fields"]]
        added=updated=skipped=renamed=0
        for r in rows:
            nm = str(r.get(name_col,"")).strip()
            if not nm: continue
            rec = {k: r.get(k, "") for k in field_keys}
            rec["name"] = nm
            if nm in self.index:
                if st == "skip":
                    skipped += 1; continue
                elif st == "overwrite":
                    self.records[self.index[nm]] = rec; updated += 1
                elif st == "rename":
                    base = nm; i = 2; new_nm = f"{base} ({i})"
                    while new_nm in self.index:
                        i += 1; new_nm = f"{base} ({i})"
                    rec["name"] = new_nm; self.records.append(rec); renamed += 1
            else:
                self.records.append(rec); added += 1
            self.rebuild_index()
        self.refresh_list()
        message = f"导入完成：新增 {added}，覆盖 {updated}，重命名 {renamed}，跳过 {skipped}。"
        self.status.set(message); messagebox.showinfo("导入完成", message)

    def ask_merge_strategy(self):
        dlg = tk.Toplevel(self); dlg.title("选择合并策略"); dlg.grab_set(); dlg.resizable(False,False)
        ttk.Label(dlg, text="发现同名（name 冲突）时如何处理？").pack(padx=12, pady=(12,6))
        var = tk.StringVar(value="overwrite")
        for text,val in [("覆盖已有（推荐）","overwrite"),("跳过重名","skip"),("保留两者并重命名","rename")]:
            ttk.Radiobutton(dlg, text=text, value=val, variable=var).pack(anchor="w", padx=18, pady=2)
        ttk.Button(dlg, text="确定", command=dlg.destroy).pack(pady=(8,12))
        dlg.wait_window()
        return var.get()

# ===================== 主应用（仅标签容器，不含菜单） =====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x600")
        self.minsize(900, 520)

        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True)
        for tab_name, schema in SCHEMAS.items():
            self.nb.add(TabEditor(self.nb, schema), text=tab_name)

# ===================== 入口 =====================
if __name__ == "__main__":
    app = App()
    app.mainloop()
