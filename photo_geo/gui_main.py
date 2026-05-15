# gui_main.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import timedelta

from .scanner import collect_photo_paths, scan_photos
from .clustering import cluster_by_time, infer_cluster_locations, mixed_clusters
from .gui_preview import ClusterReviewer


class TimeDistanceApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Photo Geo Inference – Time Distance Tuner")
        self.root.geometry("900x600")

        # Cached state
        self.library_path = None
        self.records = []          # list[PhotoRecord]
        self.time_dists = []       # list[float] minutes, for no-geo photos
        self.clusters = []         # list[Cluster]
        self.mixed = []             # list mixed clusters

        self._build_ui()


        # make it look a bit more pretty
        style = ttk.Style(self.root)
        # Try different themes: 'clam', 'vista', 'xpnative', 'default'
        style.theme_use("clam")

        # Slightly larger default font
        style.configure(".", font=("Segoe UI", 10))

        # Make buttons a bit nicer
        style.configure("TButton", padding=(6, 3))
        style.configure("TLabel", padding=(2, 1))

    # ---------- UI layout ----------

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        # Library chooser
        ttk.Label(top, text="Library folder:").pack(side="left")
        self.path_var = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.path_var, width=60).pack(side="left", padx=4)
        ttk.Button(top, text="Browse…", command=self.choose_folder).pack(side="left", padx=4)
        ttk.Button(top, text="Scan", command=self.scan_library).pack(side="left", padx=4)

        # Time-distance summary + clustering controls
        mid = ttk.Frame(self.root, padding=8)
        mid.pack(fill="x")

        self.summary_text = tk.Text(mid, height=20, width=100, state="disabled")
        self.summary_text.pack(fill="x", pady=(0, 8))

        controls = ttk.Frame(mid)
        controls.pack(fill="x", pady=(4, 0))

        ttk.Label(controls, text="Max gap (minutes) for clustering:").pack(side="left")
        self.max_gap_var = tk.StringVar(value="20")
        ttk.Entry(controls, textvariable=self.max_gap_var, width=8).pack(side="left", padx=4)

        ttk.Button(controls, text="Run clustering", command=self.run_clustering).pack(side="left", padx=4)
        ttk.Button(controls, text="Preview clusters", command=self.preview_clusters).pack(side="left", padx=4)
        ttk.Button(controls, text="Write all", command=self.write_all).pack(side="left", padx=4)

        # Status area
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="both", expand=True)

        self.status = tk.Text(bottom, height=10, state="disabled")
        self.status.pack(fill="both", expand=True)

    # ---------- Helpers to write to text widgets ----------

    def _set_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _append_status(self, line):
        self.status.configure(state="normal")
        self.status.insert("end", line + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    # ---------- Library selection & scanning ----------

    def choose_folder(self):
        path = filedialog.askdirectory(title="Choose photo library folder")
        if path:
            self.library_path = path
            self.path_var.set(path)

    def scan_library(self):
        if not self.library_path:
            messagebox.showerror("No folder", "Please choose a library folder first.")
            return

        self._append_status(f"Scanning photos under: {self.library_path}")
        paths = collect_photo_paths(self.library_path)
        self._append_status(f"Found {len(paths)} image files")

        self.records = scan_photos(paths, debug=True)
        self._append_status(f"Scanned EXIF for {len(self.records)} photos")

        self.compute_time_distances()
        self.update_summary()

    # ---------- Time-distance computation ----------

    def compute_time_distances(self):
        """Compute time distance (minutes) from each no-geo photo to nearest geo photo."""
        self.time_dists = []

        geo = [p for p in self.records if p.has_gps and p.taken_at is not None]
        nogeo = [p for p in self.records if not p.has_gps and p.taken_at is not None]

        if not geo or not nogeo:
            return

        geo.sort(key=lambda p: p.taken_at)
        nogeo.sort(key=lambda p: p.taken_at)

        # two-pointer sweep for nearest neighbor in time
        j = 0
        for q in nogeo:
            # advance j while next geo is closer in time
            best_diff = None
            while j + 1 < len(geo):
                curr = abs((q.taken_at - geo[j].taken_at).total_seconds())
                nxt = abs((q.taken_at - geo[j + 1].taken_at).total_seconds())
                if nxt <= curr:
                    j += 1
                else:
                    break
            best_diff = abs((q.taken_at - geo[j].taken_at).total_seconds())
            self.time_dists.append(best_diff / 60.0)  # minutes

    def update_summary(self):
        if not self.time_dists:
            self._set_text(
                self.summary_text,
                "No time-distance data yet.\n\n"
                "You either have no photos without GPS, no photos with GPS, "
                "or dates are missing.\n"
            )
            return

        dists = sorted(self.time_dists)
        n = len(dists)

        def pct(p):
            idx = int(p * n)
            idx = max(0, min(n - 1, idx))
            return dists[idx]

        p50 = pct(0.50)
        p90 = pct(0.90)
        p99 = pct(0.99)
        maxd = dists[-1]

        # simple bucket summary to start with
        buckets = [0, 1, 2, 5, 10, 20, 30, 60, 120, 240]
        counts = [0] * (len(buckets) + 1)
        for v in dists:
            placed = False
            for i, b in enumerate(buckets):
                if v <= b:
                    counts[i] += 1
                    placed = True
                    break
            if not placed:
                counts[-1] += 1

        lines = []
        lines.append(f"No-GPS photos with timeDistance: {n}")
        lines.append("")
        lines.append(f"Median (50%): {p50:.1f} min")
        lines.append(f"90%: {p90:.1f} min")
        lines.append(f"99%: {p99:.1f} min")
        lines.append(f"Max: {maxd:.1f} min")
        lines.append("")
        lines.append("Rough bucket counts (timeDistance in minutes):")
        for i, b in enumerate(buckets):
            label = f"<= {b:>3} min"
            lines.append(f"  {label}: {counts[i]}")
        lines.append(f"  > {buckets[-1]:>3} min: {counts[-1]}")

        self._set_text(self.summary_text, "\n".join(lines))

    # ---------- Clustering & integration with existing gui_preview----------

    def run_clustering(self):
        if not self.records:
            messagebox.showerror("No records", "Scan a library first.")
            return

        try:
            max_gap = int(self.max_gap_var.get())
            if max_gap <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid value", "Max gap must be a positive integer (minutes).")
            return

        self._append_status(f"Clustering with max gap = {max_gap} minutes")

        items = [r for r in self.records if r.taken_at is not None]
        self.clusters = cluster_by_time(items, max_gap_minutes=max_gap)
        infer_cluster_locations(self.clusters)

        # Keep only mixed clusters for review / writing
        self.mixed = mixed_clusters(self.clusters)

        self._append_status(
            f"Total clusters: {len(self.clusters)} "
            f"(mixed: {len(self.mixed)} – clusters with both geo and no-geo photos)"
        )

    def preview_clusters(self):
        if not self.clusters:
            messagebox.showerror("No clusters", "Run clustering first.")
            return

        from .gui_preview import ClusterReviewer

        def on_preview_wrote():
            # recompute time-distance and histogram after preview writes
            self.compute_time_distances()
            self.update_summary()

        reviewer = ClusterReviewer(self.mixed, parent=self.root, on_write=on_preview_wrote)
        reviewer.run()

    def write_all(self):
        if not getattr(self, "mixed", None):
            messagebox.showerror("No clusters", "Run clustering first.")
            return

        confirm = messagebox.askyesno(
            "Write all",
            "This will write inferred GPS to ALL non-geo photos "
            "in mixed clusters that have inferred locations.\n\n"
            "Have you checked some previews?.\n\n"
            "Are you sure?",
        )
        if not confirm:
            return

        from .writer import write_cluster_gps

        written_count = 0
        for c in self.mixed:
            written_count += write_cluster_gps(c)

        self._append_status(f"Wrote inferred GPS to {written_count} photos.")

        # Recompute time-distance stats using cached records
        self.compute_time_distances()
        self.update_summary()

    # ---------- Entry point ----------

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TimeDistanceApp()
    app.run()