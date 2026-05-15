import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import piexif
from .writer import write_cluster_gps

def make_gps_exif(lat, lon):
    def dec_to_dms(x):
        x = abs(float(x))
        d = int(x)
        m_float = (x - d) * 60
        m = int(m_float)
        s = int(round((m_float - m) * 60 * 10000))
        return (d, 1), (m, 1), (s, 10000)

    lat_ref = "N" if lat >= 0 else "S"
    lon_ref = "E" if lon >= 0 else "W"

    return {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode("ascii"),
        piexif.GPSIFD.GPSLatitude: dec_to_dms(lat),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref.encode("ascii"),
        piexif.GPSIFD.GPSLongitude: dec_to_dms(lon),
    }

class ClusterReviewer:
    def __init__(self, clusters, parent, on_write=None):

        self.clusters = clusters
        self.idx = 0
        self.on_write = on_write  # callback to main GUI

        # Use a Toplevel window instead of a new Tk
        self.root = tk.Toplevel(parent)
        self.root.title("photogeo – review")
        self.root.geometry("1750x1120")

        # make it look a bit more pretty
        style = ttk.Style(self.root)
        # Try different themes: 'clam', 'vista', 'xpnative', 'default'
        style.theme_use("clam")

        # Slightly larger default font
        style.configure(".", font=("Segoe UI", 10))

        # Make buttons a bit nicer
        style.configure("TButton", padding=(6, 3))
        style.configure("TLabel", padding=(2, 1))

        self.top_info = ttk.Label(self.root, text="", justify="left")
        self.top_info.pack(fill="x", padx=8, pady=(6, 2))

        strip_frame = ttk.Frame(self.root)
        strip_frame.pack(fill='x', padx=8, pady=(2, 6))
        # Increased canvas height so thumbnail area is larger (doubled)
        self.strip_canvas = tk.Canvas(strip_frame, height=320, highlightthickness=0)
        self.strip_canvas.pack(side='top', fill='x', expand=True)
        self.strip_scroll = ttk.Scrollbar(strip_frame, orient='horizontal', command=self.strip_canvas.xview)
        self.strip_scroll.pack(side='top', fill='x')
        self.strip_canvas.configure(xscrollcommand=self.strip_scroll.set)

        self.strip_content = ttk.Frame(self.strip_canvas)
        self.strip_window = self.strip_canvas.create_window((0, 0), window=self.strip_content, anchor='nw')
        self.strip_content.bind('<Configure>', self._on_content_configure)
        self.strip_canvas.bind('<Configure>', self._on_canvas_configure)
        # Enable horizontal scrolling with the mouse wheel when pointer is over the strip.
        # On Windows/macOS Tk reports <MouseWheel> with event.delta; on many X11 setups
        # mouse wheel generates Button-4 / Button-5 events.
        self.strip_canvas.bind('<Enter>', lambda e: (self.strip_canvas.bind_all('<MouseWheel>', self._on_mousewheel), self.strip_canvas.bind_all('<Button-4>', self._on_mousewheel), self.strip_canvas.bind_all('<Button-5>', self._on_mousewheel)))
        self.strip_canvas.bind('<Leave>', lambda e: (self.strip_canvas.unbind_all('<MouseWheel>'), self.strip_canvas.unbind_all('<Button-4>'), self.strip_canvas.unbind_all('<Button-5>')))

        self.viewer = ttk.Frame(self.root)
        self.viewer.pack(fill='both', expand=True, padx=8, pady=(0, 6))

        self.main_image = ttk.Label(self.viewer)
        self.main_image.pack(fill='both', expand=True)

        self.main_text = ttk.Label(self.root, text='', justify='left')
        self.main_text.pack(fill='x', padx=8, pady=(0, 6))

        self.mid_text = ttk.Label(self.root, text='', justify='center')
        self.mid_text.pack(fill='x', padx=8, pady=(0, 6))

        self.controls = ttk.Frame(self.root)
        self.controls.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(self.controls, text='Prev cluster', command=self.prev_cluster).pack(side='left')
        ttk.Button(self.controls, text='Next cluster', command=self.next_cluster).pack(side='left')
        ttk.Button(self.controls, text='Write', command=self.write_current).pack(side='left')
        ttk.Button(self.controls, text='Quit', command=self.root.destroy).pack(side='right')

        self.written = set()
        self.selected = None
        self.thumb_images = []
        self.main_img = None
        self.resize_after_id = None
        # Recompute main image size when window is resized so it dynamically fits
        self.root.bind('<Configure>', self.on_root_configure)
        self.show_cluster()

    def run(self):
        # For Toplevel under a main root, mainloop is already running.
        # This exists so callers can still say reviewer.run().
        try:
            self.root.lift()
            self.root.focus_set()
        except Exception:
            pass

    def on_root_configure(self, event):
        # Debounce frequent configure events during resize
        try:
            if self._resize_after_id:
                self.root.after_cancel(self._resize_after_id)
        except Exception:
            pass
        self._resize_after_id = self.root.after(120, self._resize_main_image)

    def _compute_main_max_size(self):
        # Compute available width/height for main image similar to logic used in
        # show_cluster, but as a reusable helper.
        try:
            self.root.update_idletasks()
            root_h = self.root.winfo_height()
            root_w = self.root.winfo_width()
            strip_h = self.strip_canvas.winfo_height() or 0
            top_h = self.top_info.winfo_height() or 0
            main_text_h = self.main_text.winfo_height() or 0
            mid_text_h = self.mid_text.winfo_height() or 0
            controls_h = self.controls.winfo_height() or 0
            # Ensure we always reserve enough space for controls even if their
            # measured height is not yet available; this keeps buttons visible.
            controls_reserved = max(controls_h, 70)

            reserved = top_h + strip_h + main_text_h + mid_text_h + controls_reserved + 24
            avail_h = root_h - reserved
            avail_w = max(200, root_w - 40)

            if avail_h <= 0:
                return (1200, 600)
            return (max(200, avail_w), max(200, avail_h))
        except Exception:
            return (1200, 600)

    def _resize_main_image(self):
        # Reload the currently-selected main image to fit available space.
        c = self.current()
        if c is None:
            return
        photos = sorted(c.photos, key=lambda p: (p.taken_at is None, p.taken_at))
        geo = [p for p in photos if p.has_gps]
        anchor = geo[0] if geo else None
        sel = self.selected if self.selected in c.photos else (anchor or (photos[0] if photos else None))
        if sel and sel.path.exists():
            max_w, max_h = self._compute_main_max_size()
            try:
                img = self._load(sel.path, (max_w, max_h))
                self.main_img = img
                self.main_image.config(image=self.main_img, text='')
            except Exception:
                # ignore image reload errors
                pass

    def _on_content_configure(self, event=None):
        self.strip_canvas.configure(scrollregion=self.strip_canvas.bbox('all'))

    def _on_canvas_configure(self, event):
        # For horizontal scrolling we must not force the inner window's width to the
        # canvas width — that would prevent horizontal overflow and disable scrolling.
        # Keep the inner frame width natural and instead ensure its height matches
        # the canvas so thumbnails layout correctly.
        try:
            self.strip_canvas.itemconfigure(self.strip_window, height=event.height)
        except Exception:
            # Fallback: ignore if itemconfigure fails for any reason
            pass

    def _on_mousewheel(self, event):
        # Horizontal scroll handler. Normalize events for different platforms.
        try:
            if hasattr(event, 'delta') and event.delta:
                # Windows / macOS: event.delta is positive when wheel up.
                # Multiply by -1 so wheel-up scrolls left.
                delta = int(event.delta / 120)
                if delta == 0:
                    delta = 1 if event.delta > 0 else -1
                self.strip_canvas.xview_scroll(-delta, 'units')
            elif hasattr(event, 'num'):
                # X11: Button-4 = up, Button-5 = down
                if event.num == 4:
                    self.strip_canvas.xview_scroll(-1, 'units')
                elif event.num == 5:
                    self.strip_canvas.xview_scroll(1, 'units')
        except Exception:
            # Ignore any errors from unexpected event shapes
            pass

    def current(self):
        return self.clusters[self.idx] if self.clusters else None

    def _load(self, path, max_size):
        im = Image.open(path).convert('RGB')
        im.thumbnail(max_size)
        return ImageTk.PhotoImage(im)

    def _gps_exif(self, lat, lon):
        def dec_to_dms(x):
            x = abs(float(x))
            d = int(x)
            m_float = (x - d) * 60
            m = int(m_float)
            s = int(round((m_float - m) * 60 * 10000))
            return ((d, 1), (m, 1), (s, 10000))
        return {
            piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
            piexif.GPSIFD.GPSLatitude: dec_to_dms(lat),
            piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
            piexif.GPSIFD.GPSLongitude: dec_to_dms(lon),
        }

    def _fmt_dt(self, dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else 'unknown'

    def _fmt_delta(self, a, b):
        if not a or not b:
            return 'unknown'
        s = abs((b - a).total_seconds())
        days, rem = divmod(s, 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        return f'{int(days):02d} DAYS:{int(hours):02d}:{int(mins):02d}:{secs:06.3f}'

    def _select_photo(self, photo):
        self.selected = photo
        self.show_cluster()

    def show_cluster(self):
        c = self.current()
        if c is None:
            self.top_info.config(text='No clusters to show')
            return
        photos = sorted(c.photos, key=lambda p: (p.taken_at is None, p.taken_at))
        geo = [p for p in photos if p.has_gps]
        no_geo = [p for p in photos if not p.has_gps]
        anchor = geo[0] if geo else None
        loc = f'{c.inferred_lat:.6f},{c.inferred_lon:.6f}' if c.inferred_lat is not None else 'unknown'
        status = 'WRITTEN' if c.id in self.written else 'PENDING'
        self.top_info.config(text=f'Cluster {c.id} | idx {self.idx+1}/{len(self.clusters)} | {status} | photos={len(c.photos)} | geo={len(geo)} | no-geo={len(no_geo)} | loc={loc} | src={c.source} | conf={c.confidence:.2f}')

        for w in self.strip_content.winfo_children():
            w.destroy()
        self.thumb_images = []
        total = len(photos)
        for i, p in enumerate(photos):
            frame = ttk.Frame(self.strip_content, padding=2)
            frame.pack(side='left', padx=4, anchor='n')
            # Load a larger thumbnail (doubled from 100x100 -> 200x200)
            img = self._load(p.path, (200, 200))
            self.thumb_images.append(img)
            lbl = ttk.Label(frame, image=img)
            lbl.pack()
            kind = 'ANCHOR' if p.has_gps else 'NO-GEO'
            dt = self._fmt_dt(p.taken_at)
            # Show index
            ttk.Label(frame, text=f'{i+1}/{total}', justify='center').pack()
            # Show kind; style NO-GEO as bold red and show inferred lat/lon to be written
            if p.has_gps:
                ttk.Label(frame, text='ANCHOR', justify='center').pack()
            else:
                tk.Label(frame, text='NO-GEO', justify='center', fg='red', font=('TkDefaultFont', 9, 'bold')).pack()

            # Show taken time
            ttk.Label(frame, text=f'TAKEN: {dt}', justify='center').pack()
            # Optionally show inferred lat/lon for geo photos
            if p.has_gps:
                latlon = f'{p.lat:.6f},{p.lon:.6f}' if p.lat is not None else 'unknown'
                ttk.Label(frame, text=f'LAT/LON: {latlon}', justify='center').pack()
            else:
                # Show the inferred lat/lon (the coordinates that would be written) in red
                latlon_write = f'{c.inferred_lat:.6f},{c.inferred_lon:.6f}' if c.inferred_lat is not None else 'unknown'
                tk.Label(frame, text=f'WRITE: {latlon_write}', justify='center', fg='red').pack()
            lbl.bind('<Button-1>', lambda e, photo=p: self._select_photo(photo))
            frame.bind('<Button-1>', lambda e, photo=p: self._select_photo(photo))
            if self.selected is None and i == 0:
                self.selected = p

        self.strip_content.update_idletasks()
        self.strip_canvas.configure(scrollregion=self.strip_canvas.bbox('all'))
        self.strip_canvas.xview_moveto(0.0)

        sel = self.selected if self.selected in c.photos else (anchor or (photos[0] if photos else None))
        if sel and sel.path.exists():
            # Use centralized computation so sizing is consistent and respects
            # reserved space for thumbnails and controls.
            max_w, max_h = self._compute_main_max_size()
            try:
                self.main_img = self._load(sel.path, (max_w, max_h))
                self.main_image.config(image=self.main_img, text='')
            except Exception:
                # If image loading fails, show placeholder text
                self.main_image.config(image='', text='No image')
        else:
            self.main_image.config(image='', text='No image')
            self.main_img = None

        if sel:
            delta = self._fmt_delta(anchor.taken_at if anchor else None, sel.taken_at)
            kind = 'ANCHOR' if sel.has_gps else 'NO-GEO'
            self.main_text.config(text=f'SELECTED: {kind} | {sel.path} | taken: {self._fmt_dt(sel.taken_at)} | photos in cluster: {len(c.photos)} | geo={len(geo)} | no-geo={len(no_geo)}')
            self.mid_text.config(text=(f'LAT/LON: {c.inferred_lat:.6f},{c.inferred_lon:.6f}' if (not sel.has_gps and c.inferred_lat is not None and c.inferred_lon is not None) else ('anchor selected' if sel.has_gps else 'unknown')))
        else:
            self.main_text.config(text='')
            self.mid_text.config(text='')

    def prev_cluster(self):
        if self.clusters:
            self.idx = (self.idx - 1) % len(self.clusters)
            self.selected = None
            self.show_cluster()

    def next_cluster(self):
        if self.clusters:
            start = self.idx + 1
            if len(self.written) >= len(self.clusters):
                self.show_cluster()
                return
            for step in range(len(self.clusters)):
                i = (start + step) % len(self.clusters)
                if self.clusters[i].id not in self.written:
                    self.idx = i
                    self.selected = None
                    self.show_cluster()
                    return
            self.show_cluster()

    def write_current(self):
        c = self.current()
        if c is None:
            return

        written = write_cluster_gps(c)
        if written:
            self.written.add(c.id)

        # Tell main GUI to recompute histogram
        if self.on_write is not None and written:
            self.on_write()

        # If everything is written, close; otherwise advance
        if len(self.written) >= len(self.clusters):
            self.root.destroy()
            return

        self.next_cluster()
