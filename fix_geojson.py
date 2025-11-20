import os
import json
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from shapely.geometry import shape, mapping
from shapely.geometry import Polygon, MultiPolygon
from shapely.errors import TopologicalError


# ===================== 修复逻辑（无 geopandas / fiona） =====================

def fix_polygon_validity(geom):
    """
    修复 Shapely 几何合法性，不依赖 geopandas / fiona。
    """
    try:
        if geom.is_valid:
            return geom
        fixed = geom.buffer(0)
        if fixed.is_valid:
            return fixed
    except TopologicalError:
        pass
    return None


def fix_geojson_structure(geom_dict):
    """
    修复 geometry 的 type 与 coordinates 层级不对应的问题。
    """
    if not geom_dict or "type" not in geom_dict or "coordinates" not in geom_dict:
        return geom_dict

    gtype = geom_dict["type"]
    coords = geom_dict["coordinates"]

    # 计算深度
    def depth(lst):
        if isinstance(lst, list) and lst:
            return 1 + depth(lst[0])
        return 0

    d = depth(coords)

    # 修复 Polygon 深度（应为 3）
    if gtype == "Polygon":
        if d == 2:
            coords = [coords]
        elif d > 3:
            coords = coords[0]
        geom_dict["coordinates"] = coords

    # 修复 MultiPolygon 深度（应为 4）
    elif gtype == "MultiPolygon":
        if d == 3:
            coords = [coords]
        elif d > 4:
            coords = coords[0]
        geom_dict["coordinates"] = coords

    return geom_dict


def repair_geojson_no_gpd(input_path, output_path, progress_var):
    """
    不使用 geopandas/fiona 修复 GeoJSON：
    1. 修复 coordinates 层级
    2. 修复 geometry 合法性
    """
    try:
        progress_var.set(10)

        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        progress_var.set(30)

        fixed_features = []
        total = len(data.get("features", []))
        done = 0

        for feat in data.get("features", []):
            geom_dict = feat.get("geometry")

            if geom_dict:
                geom_dict = fix_geojson_structure(geom_dict)

                try:
                    geom = shape(geom_dict)
                except Exception:
                    continue  # 不能解析的 geometry 直接跳过

                geom_fixed = fix_polygon_validity(geom)
                if geom_fixed:
                    feat["geometry"] = mapping(geom_fixed)
                    fixed_features.append(feat)

            done += 1
            progress_var.set(30 + int(60 * done / max(1, total)))

        # 写回文件
        data["features"] = fixed_features

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        progress_var.set(100)
        messagebox.showinfo("完成", f"修复成功：\n{output_path}")

    except Exception as e:
        messagebox.showerror("错误", str(e))


# ===================== GUI（保持你的“漂亮 UI”版本） =====================

def create_gui():
    root = tk.Tk()
    root.title("GeoJSON 修复工具")
    root.geometry("520x530")
    root.resizable(False, False)

    # ------ UI 样式 ------
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TButton",
                    font=("PingFang SC", 12),
                    padding=8,
                    relief="flat",
                    background="#4C8BF5",
                    foreground="white")
    style.map("TButton",
              background=[("active", "#3A72D8")])
    style.configure("TEntry", padding=6, relief="solid", borderwidth=1)
    style.configure("TProgressbar", thickness=12, troughcolor="#E5E5E5", background="#4C8BF5")

    container = tk.Frame(root, bg="white", padx=30, pady=30)
    container.pack(fill="both", expand=True)

    # 输入
    tk.Label(container, text="输入 GeoJSON 文件", font=("PingFang SC", 12), bg="white").pack(anchor="w")
    entry_input = ttk.Entry(container, width=45)
    entry_input.pack(pady=5)

    def select_input():
        path = filedialog.askopenfilename(filetypes=[("GeoJSON 文件", "*.geojson")])
        if path:
            entry_input.delete(0, tk.END)
            entry_input.insert(0, path)

    ttk.Button(container, text="选择文件", command=select_input).pack()

    # 输出
    tk.Label(container, text="输出文件路径", font=("PingFang SC", 12), bg="white", pady=10).pack(anchor="w")
    entry_output = ttk.Entry(container, width=45)
    entry_output.pack()

    def select_output():
        path = filedialog.asksaveasfilename(defaultextension=".geojson",
                                            filetypes=[("GeoJSON 文件", "*.geojson")])
        if path:
            entry_output.delete(0, tk.END)
            entry_output.insert(0, path)

    ttk.Button(container, text="选择保存位置", command=select_output).pack(pady=(5, 15))

    # 进度条
    progress_var = tk.IntVar()
    progress_bar = ttk.Progressbar(container, variable=progress_var, length=420)
    progress_bar.pack(pady=10)

    # 按钮行
    btn_frame = tk.Frame(container, bg="white")
    btn_frame.pack(pady=5)

    def start():
        input_path = entry_input.get().strip()
        output_path = entry_output.get().strip()

        if not os.path.exists(input_path):
            messagebox.showwarning("提示", "请选择正确的输入文件")
            return
        if not output_path:
            messagebox.showwarning("提示", "请设置输出路径")
            return

        progress_var.set(0)
        root.after(100, repair_geojson_no_gpd, input_path, output_path, progress_var)

    ttk.Button(btn_frame, text="开始处理", width=15, command=start).grid(row=0, column=0, padx=10)
    ttk.Button(btn_frame, text="取消", width=15, command=root.quit).grid(row=0, column=1, padx=10)

    root.mainloop()


if __name__ == "__main__":
    create_gui()
