#!/usr/bin/env python3
"""
Car Identifier GUI with Ollama
Enhanced version with better model configuration and dark theme
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import base64
import os
import io
from pathlib import Path
from PIL import Image, ImageTk, ImageFile
# Allow very large images without DecompressionBomb errors and handle truncated files
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True
import ollama
try:
    import ttkbootstrap as tb
except Exception:
    tb = None

class CarIdentifierGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Car Identifier - Ollama")
        self.root.geometry("1200x800")
        
        # Dark theme colors
        self.colors = {
            'bg_dark': '#1e1e1e',
            'bg_medium': '#2d2d2d', 
            'bg_light': '#3c3c3c',
            'accent': '#007acc',
            'accent_hover': '#005a9e',
            'text_primary': '#ffffff',
            'text_secondary': '#cccccc',
            'text_muted': '#999999',
            'border': '#404040',
            'success': '#28a745',
            'warning': '#ffc107',
            'error': '#dc3545'
        }
        
        # Apply dark theme
        self.root.configure(bg=self.colors['bg_dark'])
        self.setup_dark_theme()
        
        # Variables
        self.current_image_path = None
        self.current_image = None
        self.photo = None
        self.identified_data = {}
        self.auto_approve = tk.BooleanVar(value=False)
        self.high_fidelity_input = tk.BooleanVar(value=True)
        self.enhanced_inference = tk.BooleanVar(value=False)
        self.processing = False
        self.batch_folder = None
        self.batch_processing = False
        # Verification toggle
        self.verify_second_pass = tk.BooleanVar(value=True)
        
        # Metadata handling preferences
        self.overwrite_existing = tk.StringVar(value="skip")  # "skip", "overwrite", "ask"
        self.recursive_scan = tk.BooleanVar(value=True)
        
        # Last identified image tracking
        self.last_identified_image_path = None
        self.last_identified_data = {}
        self.last_identified_thumbnail = None
        
        # Ollama client
        self.ollama_client = ollama.Client(host='http://localhost:11434', timeout=60)
        self.model_name = 'qwen2.5vl:32b-q4_K_M'  # Enhanced vision model for better logo/text recognition
        
        self.setup_ui()
        self.check_ollama_connection()
        # Warm up model to reduce first-image latency and keep it in GPU memory
        try:
            self._warmup_model_async()
        except Exception:
            pass

    # UI helpers for themed widgets
    def _button(self, parent, text, command, bootstyle='primary', **kwargs):
        if tb is not None:
            return tb.Button(parent, text=text, command=command, bootstyle=bootstyle, **kwargs)
        return ttk.Button(parent, text=text, command=command, **kwargs)

    def _combobox(self, parent, textvariable, values, width, state='readonly', bootstyle='secondary', **kwargs):
        if tb is not None:
            cb = tb.Combobox(parent, textvariable=textvariable, values=values, width=width, bootstyle=bootstyle, **kwargs)
        else:
            cb = ttk.Combobox(parent, textvariable=textvariable, values=values, width=width, **kwargs)
        try:
            cb.state([state])
        except Exception:
            try:
                cb.configure(state=state)
            except Exception:
                pass
        return cb

    def _create_popup_dropdown(self, parent, variable, options_or_provider, width=14, bootstyle='secondary', on_select=None, list_height=8):
        """Create a reliable dropdown using a borderless Toplevel + Listbox next to the button."""
        def _current_options():
            try:
                if callable(options_or_provider):
                    return list(options_or_provider()) or []
                return list(options_or_provider) or []
            except Exception:
                return []

        initial_text = variable.get() or (_current_options()[0] if _current_options() else 'Select')
        btn = self._button(parent, text=initial_text, command=lambda: show_popup(), bootstyle=bootstyle, width=width)

        popup_ref = {'win': None}

        def close_popup():
            try:
                if popup_ref['win'] is not None:
                    popup_ref['win'].destroy()
            finally:
                popup_ref['win'] = None

        def on_pick(value):
            variable.set(value)
            try:
                btn.config(text=value)
            except Exception:
                pass
            if callable(on_select):
                on_select(value)
            close_popup()

        def show_popup():
            # If already open, close first (toggle)
            if popup_ref['win'] is not None:
                close_popup()
                return

            opts = _current_options()
            if not opts:
                return

            top = tk.Toplevel(self.root)
            popup_ref['win'] = top
            top.overrideredirect(True)
            top.configure(bg=self.colors['border'])

            # Position below the button
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            top.geometry(f"+{x}+{y}")

            frame = tk.Frame(top, bg=self.colors['bg_light'], bd=1)
            frame.pack(fill=tk.BOTH, expand=True)

            lb = tk.Listbox(frame, height=min(list_height, max(1, len(opts))),
                            bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                            selectbackground=self.colors['accent'], selectforeground=self.colors['text_primary'],
                            activestyle='none', highlightthickness=0, borderwidth=0)
            sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            for opt in opts:
                lb.insert(tk.END, opt)

            # Preselect current value
            try:
                current = variable.get()
                if current in opts:
                    idx = opts.index(current)
                    lb.selection_set(idx)
                    lb.see(idx)
            except Exception:
                pass

            def on_select_event(event=None):
                try:
                    sel = lb.curselection()
                    if not sel:
                        return
                    val = lb.get(sel[0])
                    on_pick(val)
                except Exception:
                    close_popup()

            lb.bind('<Double-Button-1>', on_select_event)
            lb.bind('<Return>', on_select_event)
            lb.bind('<Escape>', lambda e: close_popup())

            # Close when focus leaves
            def on_focus_out(event):
                # If click lands on the button, keep it (will toggle)
                widget = event.widget
                if widget is not top and widget is not lb:
                    close_popup()
            top.bind('<FocusOut>', on_focus_out)

            # Grab focus to detect focus-out
            try:
                top.focus_set()
            except Exception:
                pass

        return btn
    def _warmup_model_async(self):
        """Run a tiny dummy vision call to warm the model/GPU in the background."""
        def _do_warm():
            try:
                # Use a small but valid image (>= 28px on the short side) to avoid model panics
                from PIL import Image
                import io as _io
                img = Image.new('RGB', (64, 64), color=(255, 255, 255))
                buf = _io.BytesIO()
                img.save(buf, format='PNG')
                img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

                self._chat([
                    {
                        'role': 'user',
                        'content': 'warmup',
                        'images': [img_b64]
                    }
                ])
            except Exception:
                pass
    def _chat(self, messages):
        """Centralized chat call with keep-alive and conservative generation options."""
        return self.ollama_client.chat(
            model=self.model_name,
            messages=messages,
            keep_alive="10m",
            options={
                "temperature": 0.2,
                "top_p": 0.8,
                "num_predict": 160,
            },
        )


        t = threading.Thread(target=_do_warm, daemon=True)
        t.start()
    
    def setup_dark_theme(self):
        """Configure dark theme styling"""
        # Prefer ttkbootstrap themes for better Combobox/menu behavior
        if tb is not None:
            try:
                self.bootstrap_style = tb.Style(theme='darkly')
                style = self.bootstrap_style
            except Exception:
                style = ttk.Style()
        else:
            style = ttk.Style()
        
        # If not using ttkbootstrap, choose a Windows-friendly theme fallback
        if tb is None:
            try:
                style.theme_use('vista')
            except tk.TclError:
                try:
                    style.theme_use('xpnative')
                except tk.TclError:
                    style.theme_use('clam')
        
        # Configure colors for different widgets
        style.configure('Dark.TFrame', background=self.colors['bg_dark'])
        style.configure('Dark.TLabelframe', background=self.colors['bg_dark'], foreground=self.colors['text_primary'])
        style.configure('Dark.TLabelframe.Label', background=self.colors['bg_dark'], foreground=self.colors['text_primary'])
        
        # Button styling (ensure high-contrast)
        style.configure('Dark.TButton', 
                       background=self.colors['accent'],
                       foreground=self.colors['text_primary'],
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Dark.TButton',
                 background=[('active', self.colors['accent_hover']),
                           ('pressed', self.colors['accent_hover'])],
                 foreground=[('disabled', self.colors['text_muted']), ('!disabled', self.colors['text_primary'])])
        
        # Checkbutton styling
        style.configure('Dark.TCheckbutton',
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 9))
        
        # Label styling (increase size/contrast)
        style.configure('Dark.TLabel',
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 10))
        
        # Progress bar styling
        style.configure('Dark.Horizontal.TProgressbar',
                       background=self.colors['accent'],
                       troughcolor=self.colors['bg_light'],
                       borderwidth=0)
        
        # Entry styling
        style.configure('Dark.TEntry',
                       fieldbackground=self.colors['bg_light'],
                       foreground=self.colors['text_primary'],
                       borderwidth=1,
                       relief='flat')
        
        # Combobox styling (maximize contrast and hit-area)
        style.configure('Dark.TCombobox',
                        fieldbackground=self.colors['bg_light'],
                        foreground=self.colors['text_primary'],
                        background=self.colors['bg_light'],
                        selectbackground=self.colors['accent'],
                        selectforeground=self.colors['text_primary'],
                        arrowcolor=self.colors['text_primary'],
                        borderwidth=1,
                        relief='flat',
                        padding=6)
        style.map('Dark.TCombobox',
                  fieldbackground=[('readonly', self.colors['bg_light']), ('!disabled', self.colors['bg_light'])],
                  foreground=[('readonly', self.colors['text_primary']), ('!disabled', self.colors['text_primary'])],
                  background=[('readonly', self.colors['bg_light']), ('!disabled', self.colors['bg_light'])],
                  arrowcolor=[('active', self.colors['accent']), ('!active', self.colors['text_primary'])])

        # Ensure dropdown list (Listbox) colors are dark-theme friendly
        try:
            self.root.option_add('*TCombobox*Listbox.background', self.colors['bg_light'])
            self.root.option_add('*TCombobox*Listbox.foreground', self.colors['text_primary'])
            self.root.option_add('*TCombobox*Listbox.selectBackground', self.colors['accent'])
            self.root.option_add('*TCombobox*Listbox.selectForeground', self.colors['text_primary'])
            self.root.option_add('*TCombobox*Listbox.font', 'Segoe UI 9')
        except Exception:
            pass
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, style='Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title with gradient effect
        title_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.title_label = ttk.Label(title_frame, 
                                     text=f"🚗 Car Identifier - Model: {getattr(self, 'model_name', 'loading...')}", 
                                     font=('Segoe UI', 18, 'bold'),
                                     foreground=self.colors['accent'],
                                     style='Dark.TLabel')
        self.title_label.pack()
        
        subtitle_label = ttk.Label(title_frame,
                                  text="Advanced AI-powered car identification and metadata tagging",
                                  font=('Segoe UI', 10),
                                  foreground=self.colors['text_secondary'],
                                  style='Dark.TLabel')
        subtitle_label.pack(pady=(5, 0))
        
        # Control frame with modern styling
        control_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Create button container with rounded corners effect
        button_container = ttk.Frame(control_frame, style='Dark.TFrame')
        button_container.pack(fill=tk.X, pady=5)
        
        # File selection button
        select_btn = self._button(button_container, text="📁 Select Image",
                                  command=self.select_image, bootstyle='primary')
        select_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Batch folder selection button
        folder_btn = self._button(button_container, text="📂 Select Folder",
                                  command=self.select_folder, bootstyle='secondary')
        folder_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Process button
        self.process_btn = self._button(button_container, text="🔍 Process Image",
                                        command=self.process_image, bootstyle='success')
        self.process_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Batch process button
        self.batch_process_btn = self._button(button_container, text="⚡ Batch Process",
                                              command=self.batch_process_folder, bootstyle='warning')
        self.batch_process_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Options frame
        options_frame = ttk.Frame(control_frame, style='Dark.TFrame')
        options_frame.pack(fill=tk.X, pady=5)
        
        # Auto approve checkbox
        auto_approve_cb = ttk.Checkbutton(options_frame, text="✅ Auto Approve", 
                                         variable=self.auto_approve, style='Dark.TCheckbutton')
        auto_approve_cb.pack(side=tk.LEFT, padx=(0, 20))
        
        # Embed metadata checkbox
        self.embed_metadata = tk.BooleanVar(value=True)
        embed_metadata_cb = ttk.Checkbutton(options_frame, text="💾 Embed in JPG", 
                                           variable=self.embed_metadata, style='Dark.TCheckbutton')
        embed_metadata_cb.pack(side=tk.LEFT, padx=(0, 20))

        # High fidelity input toggle
        hf_cb = ttk.Checkbutton(options_frame, text="🖼️ High Fidelity Input", 
                                 variable=self.high_fidelity_input, style='Dark.TCheckbutton')
        hf_cb.pack(side=tk.LEFT, padx=(0, 20))
        # Toggle for enhanced inference (persona + crops)
        enh_cb = ttk.Checkbutton(options_frame, text="🤖 Enhanced Reasoning", 
                                  variable=self.enhanced_inference, style='Dark.TCheckbutton')
        enh_cb.pack(side=tk.LEFT, padx=(0, 20))

        # Second-pass verification toggle
        verify_cb = ttk.Checkbutton(options_frame, text="🔎 Verify (2nd Pass)", 
                                     variable=self.verify_second_pass, style='Dark.TCheckbutton')
        verify_cb.pack(side=tk.LEFT, padx=(0, 20))
        
        # Metadata handling dropdown
        metadata_label = ttk.Label(options_frame, text="Existing Metadata:", style='Dark.TLabel')
        metadata_label.pack(side=tk.LEFT, padx=(0, 5))

        # Menu-based dropdown (more reliable than Combobox on some systems)
        self.overwrite_dropdown_btn = self._create_popup_dropdown(
            options_frame, self.overwrite_existing, ["skip", "overwrite", "ask"], width=12, bootstyle='secondary')
        self.overwrite_dropdown_btn.pack(side=tk.LEFT, padx=(0, 20))
        
        # Recursive scan checkbox
        recursive_cb = ttk.Checkbutton(options_frame, text="📁 Recursive Scan", 
                                     variable=self.recursive_scan, style='Dark.TCheckbutton')
        recursive_cb.pack(side=tk.LEFT, padx=(0, 20))
        
        # Model selection dropdown
        model_label = ttk.Label(options_frame, text="Model:", style='Dark.TLabel')
        model_label.pack(side=tk.LEFT, padx=(0, 5))

        self.selected_model_var = tk.StringVar(value=self.model_name)
        # Reliable menu-based dropdown for model selection
        def on_model_pick(value):
            self.selected_model_var.set(value)
            self.on_model_selected()
        self._model_parent_container = options_frame
        self.model_dropdown_btn = self._create_popup_dropdown(options_frame, self.selected_model_var,
                                                             [self.model_name], width=35,
                                                             bootstyle='secondary', on_select=on_model_pick)
        self.model_dropdown_btn.pack(side=tk.LEFT, padx=(0, 5))

        refresh_btn = self._button(options_frame,
                                   text="🔄 Refresh Models",
                                   command=self._initialize_model_selector, bootstyle='info')
        refresh_btn.pack(side=tk.LEFT, padx=(5, 0))
        # Additional picker dialog if desired
        # pick_btn = self._button(options_frame,
        #                          text="🔽 Pick",
        #                          command=self._open_model_picker_dialog, bootstyle='info')
        # pick_btn.pack(side=tk.LEFT, padx=(5, 0))

        # (duplicate Existing Metadata dropdown removed)
        
        # Status and progress frame
        status_frame = ttk.Frame(control_frame, style='Dark.TFrame')
        status_frame.pack(fill=tk.X, pady=5)
        
        # Status label with icon
        self.status_label = ttk.Label(status_frame, text="🟢 Ready", 
                                     font=('Segoe UI', 9),
                                     foreground=self.colors['text_secondary'],
                                     style='Dark.TLabel')
        self.status_label.pack(side=tk.RIGHT)
        
        # Progress bar for batch processing
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, 
                                           maximum=100, length=200,
                                           style='Dark.Horizontal.TProgressbar')
        self.progress_bar.pack(side=tk.RIGHT, padx=(0, 10))
        self.progress_bar.pack_forget()  # Hidden by default
        
        # Main content frame
        content_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Image display
        left_panel = ttk.Frame(content_frame, style='Dark.TFrame')
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Image frame with dark styling
        image_frame = ttk.LabelFrame(left_panel, text="🖼️ Image Preview", 
                                   style='Dark.TLabelframe')
        image_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for image display with dark background
        self.canvas = tk.Canvas(image_frame, bg=self.colors['bg_light'], 
                               relief=tk.FLAT, bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right panel - Results and controls
        right_panel = ttk.Frame(content_frame, style='Dark.TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        
        # Results frame
        results_frame = ttk.LabelFrame(right_panel, text="📊 Identified Data", 
                                     style='Dark.TLabelframe')
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Results text with dark theme
        self.results_text = tk.Text(results_frame, height=15, width=50, wrap=tk.WORD,
                                   bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                                   insertbackground=self.colors['text_primary'],
                                   selectbackground=self.colors['accent'],
                                   font=('Consolas', 9),
                                   relief=tk.FLAT, bd=0)
        results_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, 
                                        command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Hide duplicate Identified Data panel (shown in Last Results)
        results_frame.pack_forget()
        
        # Action buttons frame
        button_frame = ttk.Frame(right_panel, style='Dark.TFrame')
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Approve button with success color
        self.approve_btn = self._button(button_frame, text="✅ Approve & Save",
                                        command=self.approve_and_save, bootstyle='success')
        self.approve_btn.config(state=tk.DISABLED)
        self.approve_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Reject button
        self.reject_btn = self._button(button_frame, text="❌ Reject",
                                       command=self.reject_results, bootstyle='danger')
        self.reject_btn.config(state=tk.DISABLED)
        self.reject_btn.pack(side=tk.LEFT)
        
        # Metadata editor frame
        metadata_frame = ttk.LabelFrame(right_panel, text="📝 Metadata Editor", 
                                      style='Dark.TLabelframe')
        metadata_frame.pack(fill=tk.BOTH, expand=True)
        
        # Metadata text with dark theme
        self.metadata_text = tk.Text(metadata_frame, height=10, width=50, wrap=tk.WORD,
                                    bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                                    insertbackground=self.colors['text_primary'],
                                    selectbackground=self.colors['accent'],
                                    font=('Consolas', 9),
                                    relief=tk.FLAT, bd=0)
        metadata_scrollbar = ttk.Scrollbar(metadata_frame, orient=tk.VERTICAL, 
                                         command=self.metadata_text.yview)
        self.metadata_text.configure(yscrollcommand=metadata_scrollbar.set)
        self.metadata_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        metadata_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Hide duplicate Metadata Editor (information also in Last Results)
        metadata_frame.pack_forget()
        
        # Bind mouse events for image navigation
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        
        # Image navigation variables
        self.image_scale = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Bottom panel - Last identified image and results
        bottom_panel = ttk.Frame(main_frame, style='Dark.TFrame')
        bottom_panel.pack(fill=tk.X, pady=(10, 0))
        
        # Last identified frame
        last_identified_frame = ttk.LabelFrame(bottom_panel, text="📋 Last Identified Image & Results", 
                                            style='Dark.TLabelframe')
        last_identified_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Expand last identified area to match preview proportions
        last_identified_frame.configure(height=1)
        
        # Split the bottom panel into left (image) and right (results)
        # Give more space to the image since it's now larger
        last_left_panel = ttk.Frame(last_identified_frame, style='Dark.TFrame')
        last_left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=5)
        
        last_right_panel = ttk.Frame(last_identified_frame, style='Dark.TFrame')
        last_right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 5), pady=5)
        
        # Last identified image frame
        last_image_frame = ttk.LabelFrame(last_left_panel, text="🖼️ Last Identified Image", 
                                        style='Dark.TLabelframe')
        last_image_frame.pack(fill=tk.BOTH, expand=True)
        
        # Last identified image canvas (sync size with main preview on resize)
        self.last_image_canvas = tk.Canvas(last_image_frame, bg=self.colors['bg_light'], 
                                          relief=tk.FLAT, bd=0, highlightthickness=0)
        self.last_image_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Last identified results frame
        last_results_frame = ttk.LabelFrame(last_right_panel, text="📊 Last Results", 
                                          style='Dark.TLabelframe')
        last_results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Last results text with dark theme
        self.last_results_text = tk.Text(last_results_frame, height=12, width=60, wrap=tk.WORD,
                                        bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                                        insertbackground=self.colors['text_primary'],
                                        selectbackground=self.colors['accent'],
                                        font=('Consolas', 9),
                                        relief=tk.FLAT, bd=0)
        last_results_scrollbar = ttk.Scrollbar(last_results_frame, orient=tk.VERTICAL, 
                                             command=self.last_results_text.yview)
        self.last_results_text.configure(yscrollcommand=last_results_scrollbar.set)
        self.last_results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        last_results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Initialize with placeholder text
        self.last_results_text.insert(1.0, "No images have been identified yet.\n\nProcess an image to see results here.")
        self.last_results_text.config(state=tk.DISABLED)
        
        # Populate model selector after UI is ready (non-blocking, but do not change current model)
        try:
            self._initialize_model_selector()
        except Exception:
            pass
    
    def update_last_identified_panel(self, image_path, identified_data, raw_response):
        """Update the last identified panel with new results"""
        try:
            # Update the last identified data
            self.last_identified_image_path = image_path
            self.last_identified_data = identified_data.copy()
            
            # Create last identified image display
            self.create_last_identified_image(image_path)
            
            # Update results text
            self.update_last_results_display(raw_response)
            
        except Exception as e:
            print(f"Error updating last identified panel: {str(e)}")
    
    def create_last_identified_image(self, image_path):
        """Create a display image for the last identified image (same size as main preview)"""
        try:
            if image_path and os.path.exists(image_path):
                # Open image
                img = Image.open(image_path)
                
                # Get canvas dimensions
                canvas_width = self.last_image_canvas.winfo_width()
                canvas_height = self.last_image_canvas.winfo_height()
                
                if canvas_width <= 1 or canvas_height <= 1:
                    # Canvas not yet sized, schedule redisplay
                    self.root.after(100, lambda: self.create_last_identified_image(image_path))
                    return
                
                # Calculate scale to fit image in canvas (same logic as main display)
                img_width, img_height = img.size
                scale_x = canvas_width / img_width
                scale_y = canvas_height / img_height
                scale = min(scale_x, scale_y, 1.0)  # Don't scale up
                
                # Resize image
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Convert to PhotoImage
                self.last_identified_thumbnail = ImageTk.PhotoImage(resized_img)
                
                # Clear canvas and display image
                self.last_image_canvas.delete("all")
                
                # Center the image
                x = (canvas_width - new_width) // 2
                y = (canvas_height - new_height) // 2
                self.last_image_canvas.create_image(x, y, anchor=tk.NW, image=self.last_identified_thumbnail)
                
        except Exception as e:
            print(f"Error creating last identified image: {str(e)}")
    
    def update_last_results_display(self, raw_response):
        """Update the last results display with new data"""
        try:
            # Enable text widget for editing
            self.last_results_text.config(state=tk.NORMAL)
            
            # Clear existing content
            self.last_results_text.delete(1.0, tk.END)
            
            # Add timestamp and file info
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            filename = os.path.basename(self.last_identified_image_path) if self.last_identified_image_path else "Unknown"
            
            header = f"📅 Processed: {timestamp}\n📁 File: {filename}\n\n"
            self.last_results_text.insert(tk.END, header)
            
            # Add the raw response
            self.last_results_text.insert(tk.END, raw_response)
            
            # Disable text widget to make it read-only
            self.last_results_text.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"Error updating last results display: {str(e)}")
    
    def check_ollama_connection(self):
        """Check if Ollama is running and the selected model is available."""
        try:
            if self._model_exists(self.model_name):
                self.status_label.config(text=f"🟢 Ollama connected - {self.model_name} ready",
                                         foreground=self.colors['success'])
                return

            # Only warn (no auto-switching)
            self.status_label.config(text=f"🟡 {self.model_name} model not found - please pull it",
                                     foreground=self.colors['warning'])
            messagebox.showwarning("Model Not Found",
                                   f"{self.model_name} model not found. Please run: ollama pull {self.model_name}")
        except Exception as e:
            self.status_label.config(text="🔴 Ollama connection failed",
                                   foreground=self.colors['error'])
            messagebox.showerror("Connection Error", 
                               f"Failed to connect to Ollama: {str(e)}\n"
                               "Please ensure Ollama is running on localhost:11434")
    
    def _initialize_model_selector(self):
        """Populate the model dropdown with available Ollama models."""
        try:
            names = self._list_ollama_model_names()
            # Keep current model if not present in the list
            if self.model_name and not any(self._names_match(self.model_name, n) for n in names):
                names.insert(0, self.model_name)

            if names:
                # Update menu-based model dropdown
                try:
                    self.model_dropdown_btn.destroy()
                except Exception:
                    pass
                def on_model_pick(value):
                    self.selected_model_var.set(value)
                    self.on_model_selected()
                host_parent = getattr(self, 'model_dropdown_btn', None)
                host_parent = host_parent.master if host_parent is not None else self._model_parent_container
                self.model_dropdown_btn = self._create_popup_dropdown(
                    host_parent,
                    self.selected_model_var, names, width=35, bootstyle='secondary', on_select=on_model_pick)
                self.model_dropdown_btn.pack(side=tk.LEFT, padx=(0, 5))

                if any(self._names_match(self.model_name, n) for n in names):
                    self.selected_model_var.set(self.model_name)
                else:
                    self.selected_model_var.set(names[0])
                    self.model_name = names[0]
                self.title_label.config(text=f"🚗 Car Identifier - Model: {self.model_name}")
                # Immediately check connection and possibly warm the chosen model
                self.check_ollama_connection()
                # Show count of models discovered
                try:
                    self.status_label.config(text=f"🟢 Models available: {len(names)} | Current: {self.model_name}",
                                             foreground=self.colors['success'])
                except Exception:
                    pass
            else:
                self.selected_model_var.set(self.model_name)
        except Exception as e:
            self.status_label.config(text=f"🟡 Unable to list models: {str(e)}",
                                     foreground=self.colors['warning'])
            self.selected_model_var.set(self.model_name)

    def _open_overwrite_picker_dialog(self):
        """Fallback dialog to pick Existing Metadata handling mode."""
        options = ["skip", "overwrite", "ask"]
        dlg = tk.Toplevel(self.root)
        dlg.title("Existing Metadata Handling")
        dlg.configure(bg=self.colors['bg_dark'])
        dlg.geometry("360x200")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="When metadata already exists, choose action:",
                  style='Dark.TLabel').pack(pady=(12, 8))

        var = tk.StringVar(value=self.overwrite_existing.get())
        radios_frame = ttk.Frame(dlg, style='Dark.TFrame')
        radios_frame.pack(fill=tk.BOTH, expand=True, padx=12)

        for opt in options:
            ttk.Radiobutton(radios_frame, text=opt.capitalize(), value=opt,
                            variable=var, style='Dark.TCheckbutton').pack(anchor='w', pady=4)

        btns = ttk.Frame(dlg, style='Dark.TFrame')
        btns.pack(fill=tk.X, padx=12, pady=(0, 12))

        def on_ok():
            choice = var.get()
            self.overwrite_existing.set(choice)
            try:
                self.overwrite_combo.set(choice)
            except Exception:
                pass
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        ok_btn = ttk.Button(btns, text="OK", command=on_ok, style='Dark.TButton')
        cancel_btn = ttk.Button(btns, text="Cancel", command=on_cancel, style='Dark.TButton')
        ok_btn.pack(side=tk.RIGHT, padx=6)
        cancel_btn.pack(side=tk.RIGHT)

    def _open_model_picker_dialog(self):
        """Fallback picker dialog in case the combobox dropdown is not visible on this theme/OS."""
        try:
            names = self._list_ollama_model_names()
        except Exception:
            names = [self.model_name]

        dlg = tk.Toplevel(self.root)
        dlg.title("Select Ollama Model")
        dlg.configure(bg=self.colors['bg_dark'])
        dlg.geometry("520x420")
        dlg.transient(self.root)
        dlg.grab_set()

        lbl = ttk.Label(dlg, text="Available Models", style='Dark.TLabel')
        lbl.pack(pady=(10, 5))

        frame = ttk.Frame(dlg, style='Dark.TFrame')
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        listbox = tk.Listbox(frame,
                             bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                             selectbackground=self.colors['accent'],
                             selectforeground=self.colors['text_primary'],
                             activestyle='dotbox')
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=sb.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for n in names:
            listbox.insert(tk.END, n)

        # Pre-select current
        try:
            idx = next((i for i, n in enumerate(names) if self._names_match(n, self.model_name)), 0)
            listbox.selection_set(idx)
            listbox.see(idx)
        except Exception:
            pass

        btns = ttk.Frame(dlg, style='Dark.TFrame')
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))

        def on_select():
            try:
                sel = listbox.curselection()
                if not sel:
                    return
                chosen = listbox.get(sel[0])
                self.model_name = chosen
                self.selected_model_var.set(chosen)
                self.title_label.config(text=f"🚗 Car Identifier - Model: {self.model_name}")
                self.check_ollama_connection()
                try:
                    self._warmup_model_async()
                except Exception:
                    pass
                dlg.destroy()
            except Exception:
                dlg.destroy()

        def on_cancel():
            dlg.destroy()

        select_btn = ttk.Button(btns, text="Select", command=on_select, style='Dark.TButton')
        cancel_btn = ttk.Button(btns, text="Cancel", command=on_cancel, style='Dark.TButton')
        select_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn.pack(side=tk.RIGHT)

        # Double-click to select
        listbox.bind('<Double-Button-1>', lambda e: on_select())


    def _list_ollama_model_names(self):
        """Return a list of model names available in Ollama, tolerant to varied response shapes."""
        all_names = []

        # 0) Try HTTP API first for consistent structure
        try:
            http_names = self._list_models_via_http()
            if http_names:
                all_names.extend(http_names)
        except Exception:
            pass
        # 1) Collect from Python client
        try:
            models = self.ollama_client.list()
        except Exception:
            models = None
        if isinstance(models, tuple) and len(models) >= 1:
            models = models[0]
        if isinstance(models, dict):
            model_list_client = models.get('models') if isinstance(models.get('models'), (list, tuple)) else [models]
        elif isinstance(models, (list, tuple)):
            model_list_client = models
        else:
            model_list_client = []

        client_names = []
        for entry in model_list_client:
            name = None
            if isinstance(entry, dict):
                name = entry.get('name') or entry.get('model') or entry.get('tag') or entry.get('digest')
            elif isinstance(entry, (str, bytes)):
                name = entry.decode('utf-8', errors='ignore') if isinstance(entry, bytes) else entry
            elif isinstance(entry, (list, tuple)):
                # Try to extract a string or dict name from the sequence
                for part in entry:
                    if isinstance(part, str):
                        name = part
                        break
                    if isinstance(part, dict):
                        name = part.get('name') or part.get('model')
                        if name:
                            break
            else:
                # Some SDKs may return objects; try common attributes
                try:
                    name = getattr(entry, 'name', None) or getattr(entry, 'model', None)
                except Exception:
                    name = None
            if name:
                client_names.append(name)
        all_names.extend(client_names)

        # 2) Collect from CLI JSON if available
        try:
            import subprocess, json as _json
            result = subprocess.run(['ollama', 'list', '--format', 'json'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                parsed = _json.loads(result.stdout)
                if isinstance(parsed, dict) and 'models' in parsed:
                    cli_models = parsed['models']
                elif isinstance(parsed, list):
                    cli_models = parsed
                else:
                    cli_models = []
                cli_names = []
                for entry in cli_models:
                    if isinstance(entry, dict):
                        nm = entry.get('name') or entry.get('model') or entry.get('tag')
                    else:
                        nm = str(entry)
                    if nm:
                        cli_names.append(nm)
                all_names.extend(cli_names)
            else:
                raise RuntimeError('json list failed')
        except Exception:
            # 3) Plain text CLI fallback
            try:
                import subprocess
                result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
                    if lines and lines[0].upper().startswith('NAME'):
                        lines = lines[1:]
                    text_names = [ln.split()[0] for ln in lines if ln]
                    all_names.extend(text_names)
            except Exception:
                pass

        # Deduplicate preserving order (case/format-insensitive)
        seen = set()
        unique_names = []
        for n in all_names:
            key = self._normalize_name(n)
            if key not in seen:
                seen.add(key)
                unique_names.append(n)
        return unique_names

    def _get_ollama_base_url(self):
        try:
            # Client may store base URL differently; best effort to recover
            base = getattr(self.ollama_client, 'host', None) or getattr(self.ollama_client, 'base_url', None)
            if not base:
                base = 'http://localhost:11434'
            return str(base).rstrip('/')
        except Exception:
            return 'http://localhost:11434'

    def _list_models_via_http(self):
        """Query Ollama REST API /api/tags and return model names list."""
        import json as _json
        from urllib import request, error

        def fetch(url):
            req = request.Request(url, method='GET')
            with request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                parsed = _json.loads(data.decode('utf-8'))
                models = parsed.get('models', []) if isinstance(parsed, dict) else []
                names_local = []
                for m in models:
                    if isinstance(m, dict):
                        nm = m.get('name') or m.get('model') or m.get('tag')
                        if nm:
                            names_local.append(nm)
                return names_local

        bases = [self._get_ollama_base_url(), 'http://127.0.0.1:11434']
        for base in bases:
            try:
                names = fetch(f"{base}/api/tags")
                if names:
                    return names
            except Exception:
                continue
        return []

    def _normalize_name(self, name):
        """Lowercase, remove dashes/underscores for fuzzy comparison."""
        try:
            return (name or '').lower().replace('-', '').replace('_', '').replace(':', '')
        except Exception:
            return str(name)

    def _names_match(self, a, b):
        """Fuzzy match between two model names, ignoring case/dashes/underscores and allowing substrings."""
        na = self._normalize_name(a)
        nb = self._normalize_name(b)
        return na in nb or nb in na

    def _model_exists(self, model_name):
        """Check directly with Ollama whether a model exists using the show endpoint if available."""
        try:
            # Some clients expose .show(model=...) or .show(name)
            try:
                info = self.ollama_client.show(model=model_name)
            except TypeError:
                info = self.ollama_client.show(model_name)
            # If we got here without exception, assume it exists
            return True if info is not None else False
        except Exception:
            # Fallback to name matching from the list
            try:
                available = self._list_ollama_model_names()
                return any(self._names_match(model_name, n) for n in available)
            except Exception:
                return False

    def _pick_preferred_vision_model(self, names):
        """Choose a likely vision-capable model from names; fallback to first if none match."""
        if not names:
            return self.model_name
        preferences = ['vl', 'vision', 'llava', 'bakllava', 'pixtral', 'moondream', 'minicpm', 'phi-3.5-vision', 'llama3.2-vision', 'llama-3.2-vision', 'qwen2.5vl', 'qwen-vl']
        for pref in preferences:
            for n in names:
                if pref in n.lower():
                    return n
        return names[0]

    def _model_supports_vision(self, model_name):
        """Heuristic check whether model name implies vision capability."""
        name = (model_name or '').lower()
        vision_tokens = ['vl', 'vision', 'llava', 'bakllava', 'moondream', 'pixtral', 'minicpm', 'llama3.2-vision', 'llama-3.2-vision', 'phi-3.5-vision', 'qwen-vl', 'qwen2.5vl']
        return any(tok in name for tok in vision_tokens)

    def on_model_selected(self, event=None):
        """Handle user changing the selected Ollama model."""
        new_model = self.selected_model_var.get().strip()
        if not new_model or new_model == self.model_name:
            return
        self.model_name = new_model
        # Update title and status
        self.title_label.config(text=f"🚗 Car Identifier - Model: {self.model_name}")
        self.status_label.config(text=f"🔄 Selected model: {self.model_name}",
                                 foreground=self.colors['accent'])
        # Re-check connection/availability and warm the model
        self.check_ollama_connection()
        try:
            self._warmup_model_async()
        except Exception:
            pass
    
    def select_image(self):
        """Select an image file"""
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif")]
        )
        if file_path:
            self.current_image_path = file_path
            self.load_image()
            self.display_image()
    
    def select_folder(self):
        """Select a folder for batch processing"""
        folder_path = filedialog.askdirectory(title="Select Folder for Batch Processing")
        if folder_path:
            self.batch_folder = folder_path
            image_count = self._count_images_in_folder(folder_path)
            messagebox.showinfo("Folder Selected", 
                              f"Selected folder: {folder_path}\n"
                              f"Found {image_count} image files")
    
    def _count_images_in_folder(self, folder_path):
        """Count image files in folder (with optional recursive scanning)"""
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
        image_files = set()  # Use set to avoid duplicates
        
        if self.recursive_scan.get():
            # Recursive scan
            for ext in supported_formats:
                # Add both lowercase and uppercase extensions
                image_files.update(Path(folder_path).rglob(f"*{ext}"))
                image_files.update(Path(folder_path).rglob(f"*{ext.upper()}"))
        else:
            # Non-recursive scan
            for ext in supported_formats:
                # Add both lowercase and uppercase extensions
                image_files.update(Path(folder_path).glob(f"*{ext}"))
                image_files.update(Path(folder_path).glob(f"*{ext.upper()}"))
        
        # Remove duplicates by converting to absolute paths
        unique_files = []
        seen_paths = set()
        for file_path in image_files:
            abs_path = str(file_path.absolute())
            if abs_path not in seen_paths:
                seen_paths.add(abs_path)
                unique_files.append(file_path)
        
        return len(unique_files)
    
    def load_image(self):
        """Load the current image"""
        if self.current_image_path:
            try:
                self.current_image = Image.open(self.current_image_path)
                # For huge images, load only when needed
                self.current_image.draft('RGB', (1920, 1920))
            except Exception as e:
                print(f"Error opening image for preview: {str(e)}")
                self.current_image = None
    
    def display_image(self):
        """Display the current image on canvas"""
        if self.current_image:
            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                # Canvas not yet sized, schedule redisplay
                self.root.after(100, self.display_image)
                return
            
            # Calculate scale to fit image in canvas
            img_width, img_height = self.current_image.size
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            self.image_scale = min(scale_x, scale_y, 1.0)  # Don't scale up
            
            # Resize image
            new_width = int(img_width * self.image_scale)
            new_height = int(img_height * self.image_scale)
            resized_image = self.current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            self.photo = ImageTk.PhotoImage(resized_image)
            
            # Clear canvas and display image
            self.canvas.delete("all")
            x = (canvas_width - new_width) // 2
            y = (canvas_height - new_height) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.photo)
            # Try to keep last image canvas proportionally similar
            try:
                self.last_image_canvas.update_idletasks()
            except Exception:
                pass
    
    def on_canvas_click(self, event):
        """Handle canvas click for panning"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def on_canvas_drag(self, event):
        """Handle canvas drag for panning"""
        if self.current_image:
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            self.image_offset_x += dx
            self.image_offset_y += dy
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.display_image()
    
    def on_mousewheel(self, event):
        """Handle mouse wheel for zooming"""
        if self.current_image:
            if event.delta > 0:
                self.image_scale *= 1.1
            else:
                self.image_scale /= 1.1
            
            # Limit zoom
            self.image_scale = max(0.1, min(5.0, self.image_scale))
            self.display_image()
    
    def process_image(self):
        """Process the current image"""
        if not self.current_image_path:
            messagebox.showwarning("No Image", "Please select an image first")
            return
        
        if self.processing:
            return
        
        # Check for existing metadata
        existing_metadata = self.read_metadata_from_image(self.current_image_path)
        if existing_metadata:
            overwrite_pref = self.overwrite_existing.get()
            if overwrite_pref == "skip":
                messagebox.showinfo("Skip Processing", 
                                  f"Image already has metadata. Skipping processing.\n\nExisting data: {existing_metadata}")
                return
            elif overwrite_pref == "ask":
                result = messagebox.askyesnocancel("Existing Metadata", 
                                                 f"This image already has metadata:\n{existing_metadata}\n\n"
                                                 f"Do you want to overwrite it?\n\n"
                                                 f"Yes = Overwrite\nNo = Skip\nCancel = Cancel")
                if result is None:  # Cancel
                    return
                elif not result:  # No = Skip
                    messagebox.showinfo("Skip Processing", "Skipping image processing.")
                    return
                # result is True = Yes = Overwrite, continue processing
        
        self.processing = True
        self.process_btn.config(state=tk.DISABLED)
        self.status_label.config(text="🔄 Processing image (optimized 1024px, PNG)...", foreground=self.colors['accent'])
        
        # Start processing in a separate thread
        thread = threading.Thread(target=self._process_image_thread)
        thread.daemon = True
        thread.start()
    
    def optimize_image_for_ollama(self, image_path):
        """
        Optimize image for Ollama processing to reduce CPU usage
        Returns base64 encoded image data
        """
        try:
            # Load image
            img = Image.open(image_path)
            try:
                img.draft('RGB', (2048, 2048))
            except Exception:
                pass
            
            # Get original dimensions
            original_width, original_height = img.size
            print(f"📏 Original image: {original_width}x{original_height}")

            # Decide whether resize is required (either to meet min side or cap max side)
            min_required = 28
            max_size = 1024
            need_upscale = (
                original_width > 0 and original_height > 0 and min(original_width, original_height) < min_required
            )
            need_downscale = original_width > max_size or original_height > max_size

            # If no resize is required, return the original bytes to avoid size bloat
            if not need_upscale and not need_downscale:
                print("📈 Skipped optimization: image within bounds; sending original bytes")
                with open(image_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')

            # Perform required resize
            if need_upscale:
                if original_width < original_height:
                    new_width = min_required
                    new_height = int(round(original_height * (min_required / original_width)))
                else:
                    new_height = min_required
                    new_width = int(round(original_width * (min_required / original_height)))
                img = img.resize((max(1, new_width), max(1, new_height)), Image.Resampling.LANCZOS)
                print(f"📏 Upscaled to meet min side {min_required}px: {img.size[0]}x{img.size[1]}")
            elif need_downscale:
                if original_width > original_height:
                    new_width = max_size
                    new_height = int(original_height * max_size / original_width)
                else:
                    new_height = max_size
                    new_width = int(original_width * max_size / original_height)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"📏 Resized to: {new_width}x{new_height} (optimized for processing)")

            # Convert to RGB if needed (some models require RGB)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Encode as JPEG to keep bytes compact when we had to resize
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=90, optimize=True)
            img_data = buffer.getvalue()
            
            # Encode to base64
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            # Calculate size reduction (informational only)
            original_size = os.path.getsize(image_path)
            optimized_size = len(img_data)
            try:
                reduction = ((original_size - optimized_size) / max(1, original_size)) * 100
            except Exception:
                reduction = 0.0
            print(f"📈 Size optimization: {original_size/1024:.1f}KB → {optimized_size/1024:.1f}KB ({reduction:.1f}% reduction)")
            
            return img_base64
            
        except Exception as e:
            print(f"⚠️ Image optimization failed: {str(e)}")
            # Safe fallback: stream read and cap size
            try:
                with Image.open(image_path) as img:
                    # Ensure minimum short side first
                    w, h = img.size
                    min_required = 28
                    if w > 0 and h > 0 and min(w, h) < min_required:
                        if w < h:
                            new_w = min_required
                            new_h = int(round(h * (min_required / w)))
                        else:
                            new_h = min_required
                            new_w = int(round(w * (min_required / h)))
                        img = img.resize((max(1, new_w), max(1, new_h)), Image.Resampling.LANCZOS)
                    # Then cap the max size
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format='PNG', optimize=True)
                    return base64.b64encode(buf.getvalue()).decode('utf-8')
            except Exception:
                with open(image_path, 'rb') as img_file:
                    img_data = img_file.read()
                    return base64.b64encode(img_data).decode('utf-8')

    def _infer_image_simple(self, image_path: str):
        """Unified inference used by both single-image and batch. Returns (raw_pretty_text, parsed_dict).
        Legacy-simple, robust path: single image only, classic prompt, line-parse first; JSON only as fallback."""
        # Input strategy
        if self.high_fidelity_input.get():
            # Even in high-fidelity mode, ensure minimum dimensions to avoid model panics
            try:
                with Image.open(str(image_path)) as _chk:
                    w_chk, h_chk = _chk.size
                if w_chk > 0 and h_chk > 0 and min(w_chk, h_chk) < 28:
                    img_base64 = self.optimize_image_for_ollama(str(image_path))
                else:
                    with open(str(image_path), 'rb') as f:
                        img_base64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                with open(str(image_path), 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode('utf-8')
        else:
            img_base64 = self.optimize_image_for_ollama(str(image_path))

        # Classic prompt that was working reliably
        prompt = (
            "Analyze this image and identify car details. If this is a car image, provide:\n\n"
            "1. Make (brand) of the car\n"
            "2. Model of the car\n"
            "3. Color of the car\n"
            "4. Any visible logos, emblems, or text on the car\n"
            "5. License plate number (if visible)\n"
            "6. Any other text visible on the car\n\n"
            "Please provide the information in this format:\n"
            "Make: [brand]\nModel: [model]\nColor: [color]\nLogos: [description]\nLicense Plate: [plate or Unknown]\nAI-Interpretation Summary: [<=200 chars]"
        )

        # Single-image call (no crops)
        response = self._chat([
            {'role': 'user', 'content': prompt, 'images': [img_base64]}
        ])

        # Prefer direct field first (old behavior), then fall back to robust extractor
        try:
            text = response['message']['content']
        except Exception:
            text = self._extract_message_text(response)
        parsed = self._parse_results(text)
        if not parsed or self._is_mostly_unknown(parsed):
            # Try JSON fallback
            parsed = self._parse_or_fallback_json(text)

        # Second-pass verification to correct sloppy identifications (toggle)
        if self.verify_second_pass.get():
            # Show verifying status in UI
            try:
                self.root.after(0, lambda: self.status_label.config(
                    text="🔎 Verifying (2nd pass)…", foreground=self.colors['accent']))
            except Exception:
                pass
            try:
                verified = self._verify_with_second_pass(image_path, parsed, img_base64)
                if verified and isinstance(verified, tuple) and verified[1]:
                    text, parsed = verified
            except Exception:
                pass
        return (text or ''), parsed

    def _infer_image_enhanced(self, image_path: str):
        """Enhanced inference with persona guidance and focused crops. Returns (raw_text, parsed_dict)."""
        # Input strategy
        if self.high_fidelity_input.get():
            # Even in high-fidelity mode, ensure minimum dimensions to avoid model panics
            try:
                with Image.open(str(image_path)) as _chk:
                    w_chk, h_chk = _chk.size
                if w_chk > 0 and h_chk > 0 and min(w_chk, h_chk) < 28:
                    img_base64 = self.optimize_image_for_ollama(str(image_path))
                else:
                    with open(str(image_path), 'rb') as f:
                        img_base64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                with open(str(image_path), 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode('utf-8')
        else:
            img_base64 = self.optimize_image_for_ollama(str(image_path))

        # Persona + disambiguation guidance
        prompt = (
            "Act as an expert automotive analyst. Your task is to perform a detailed forensic analysis.\n\n"
            "You must disambiguate look-alike models (e.g., Ferrari 430 Scuderia vs 458 Italia) by focusing on:"
            "\n- Tail light shape/position\n- Rear diffuser/exhaust layout\n- Badge text/placement\n- Side intake and rear deck differences\n\n"
            "Analyze this image and identify car details. Provide:\n"
            "Make: [brand]\nModel: [model]\nColor: [color]\nLogos: [logos/emblems/text]\n"
            "License Plate: [plate if visible]\nAI-Interpretation Summary: [<=200 chars]"
        )

        # Generate focused crops (use at most 1 crop for stability)
        crops = self._generate_detail_crops(str(image_path))[:1]
        images_payload = [img_base64] + crops

        # Call Ollama with multi-image payload; fallback to single image
        try:
            response = self._chat([
                {'role': 'user', 'content': prompt, 'images': images_payload}
            ])
        except Exception:
            response = self._chat([
                {'role': 'user', 'content': prompt, 'images': [img_base64]}
            ])

        # Prefer direct content first (matches old reliable path), then extractor
        try:
            primary_text = response['message']['content']
        except Exception:
            primary_text = self._extract_message_text(response)
        parsed = self._parse_or_fallback_json(primary_text)

        # Repair if needed
        if (not parsed) or self._is_mostly_unknown(parsed):
            repair_prompt = (
                "Return ONLY these 6 lines in this exact order, nothing else.\n"
                "Make: <brand>\nModel: <model>\nColor: <color>\nLogos: <logos/emblems/text>\n"
                "License Plate: <plate or Unknown>\nAI-Interpretation Summary: <<=200 chars>"
            )
            try:
                response_fix = self._chat([
                    {'role': 'user', 'content': repair_prompt, 'images': [img_base64]}
                ])
                text_fix = self._extract_message_text(response_fix)
                parsed_fix = self._parse_or_fallback_json(text_fix)
                for k, v in parsed_fix.items():
                    if v and str(v).lower() != 'unknown':
                        parsed[k] = v
            except Exception:
                pass

        # If still empty/unknown, fall back to classic JSON schema
        if (not parsed) or self._is_mostly_unknown(parsed):
            strict = (
                "Return ONLY JSON with keys exactly: Make, Model, Color, Logos, License Plate, AI-Interpretation Summary. "
                "No prose. Fill with 'Unknown' if not visible."
            )
            try:
                resp2 = self._chat([
                    {'role': 'user', 'content': strict, 'images': [img_base64]}
                ])
                txt2 = self._extract_message_text(resp2)
                parsed2 = self._parse_or_fallback_json(txt2)
                if parsed2:
                    parsed = parsed2
            except Exception:
                pass

        # Last-resort: if still bad, try simple path once
        if (not parsed) or self._is_mostly_unknown(parsed):
            try:
                raw_fallback, parsed_fallback = self._infer_image_simple(image_path)
                if raw_fallback:
                    return raw_fallback, parsed_fallback
            except Exception:
                pass

        # Second-pass verification to correct sloppy identifications (toggle)
        if self.verify_second_pass.get():
            # Show verifying status in UI
            try:
                self.root.after(0, lambda: self.status_label.config(
                    text="🔎 Verifying (2nd pass)…", foreground=self.colors['accent']))
            except Exception:
                pass
            try:
                verified = self._verify_with_second_pass(image_path, parsed, img_base64)
                if verified and isinstance(verified, tuple) and verified[1]:
                    v_text, v_parsed = verified
                    # Restore complete status and return verified
                    try:
                        self.root.after(0, lambda: self.status_label.config(
                            text="✅ Processing complete", foreground=self.colors['success']))
                    except Exception:
                        pass
                    return (v_text or primary_text or ''), v_parsed
            except Exception:
                pass

        return (primary_text or ''), parsed

    def _verify_with_second_pass(self, image_path, initial_parsed, img_base64=None):
        """Ask the model to re-check and correct the 6 fields strictly from the image.
        Returns (verified_text, verified_parsed) or None if verification fails."""
        try:
            # Prepare image
            if not img_base64:
                if self.high_fidelity_input.get():
                    try:
                        with Image.open(str(image_path)) as _chk:
                            w_chk, h_chk = _chk.size
                        if w_chk > 0 and h_chk > 0 and min(w_chk, h_chk) < 28:
                            img_base64 = self.optimize_image_for_ollama(str(image_path))
                        else:
                            with open(str(image_path), 'rb') as f:
                                img_base64 = base64.b64encode(f.read()).decode('utf-8')
                    except Exception:
                        with open(str(image_path), 'rb') as f:
                            img_base64 = base64.b64encode(f.read()).decode('utf-8')
                else:
                    img_base64 = self.optimize_image_for_ollama(str(image_path))

            # Compose strict verification prompt
            ip = initial_parsed or {}
            guess = (
                f"Make: {ip.get('Make','')}\n"
                f"Model: {ip.get('Model','')}\n"
                f"Color: {ip.get('Color','')}\n"
                f"Logos: {ip.get('Logos','')}\n"
                f"License Plate: {ip.get('License Plate','')}\n"
                f"AI-Interpretation Summary: {ip.get('AI-Interpretation Summary','')}\n"
            )
            verify_prompt = (
                "Re-check the identification STRICTLY from the image. If uncertain for any field, write 'Unknown'.\n"
                "Do not guess. Prefer exact text from badges/plates. Return ONLY these 6 lines, nothing else:\n"
                "Make: <brand>\nModel: <model>\nColor: <color>\nLogos: <logos/emblems/text>\n"
                "License Plate: <plate or Unknown>\nAI-Interpretation Summary: <<=200 chars>\n\n"
                "Here is the initial guess (correct it if wrong):\n" + guess
            )
            resp = self._chat([
                {'role': 'user', 'content': verify_prompt, 'images': [img_base64]}
            ])
            v_text = self._extract_message_text(resp)
            v_parsed = self._parse_or_fallback_json(v_text)
            if v_parsed:
                return v_text, v_parsed
        except Exception:
            return None
        return None

    def _generate_detail_crops(self, image_path):
        """Return a list of base64 PNG crops focusing on areas helpful for car model disambiguation
        (center badge area and lower rear/exhaust region). Best-effort; safe if anything fails."""
        crops_b64 = []
        try:
            img = Image.open(image_path)
            w, h = img.size
            # Helper to crop and encode
            def enc_crop(left, top, right, bottom):
                try:
                    box = (max(0, int(left)), max(0, int(top)), min(w, int(right)), min(h, int(bottom)))
                    # Require minimum 28px per side to satisfy model preprocessor
                    if (box[2] - box[0]) < 28 or (box[3] - box[1]) < 28:
                        return None
                    crop = img.crop(box)
                    # Normalize crop size for vision models
                    crop.thumbnail((720, 720), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    crop.save(buf, format='PNG', optimize=True)
                    return base64.b64encode(buf.getvalue()).decode('utf-8')
                except Exception:
                    return None

            # Center badge area (use mid-rectangle)
            cx0, cy0, cx1, cy1 = 0.28 * w, 0.30 * h, 0.72 * w, 0.70 * h
            # Lower rear/exhaust dominant area
            ex0, ey0, ex1, ey1 = 0.18 * w, 0.62 * h, 0.82 * w, 0.98 * h

            for box in [(cx0, cy0, cx1, cy1), (ex0, ey0, ex1, ey1)]:
                b64 = enc_crop(*box)
                if b64:
                    crops_b64.append(b64)
        except Exception:
            return crops_b64
        return crops_b64
    
    def _process_image_thread(self):
        """Thread function for processing image with optimized preprocessing"""
        try:
            # Use enhanced inference (persona + crops) when desired; fallback to simple
            if self.enhanced_inference.get():
                try:
                    raw_text, parsed = self._infer_image_enhanced(self.current_image_path)
                except Exception:
                    raw_text, parsed = self._infer_image_simple(self.current_image_path)
            else:
                raw_text, parsed = self._infer_image_simple(self.current_image_path)
                # If simple path produced no visible text, fallback to JSON or enhanced
                if not raw_text:
                    try:
                        raw_text = json.dumps(parsed or {}, indent=2)
                    except Exception:
                        raw_text = ''
                if not raw_text:
                    try:
                        raw_text, parsed = self._infer_image_enhanced(self.current_image_path)
                    except Exception:
                        pass
            # Always show some text in the panel
            self.root.after(0, lambda t=raw_text or json.dumps(parsed or {}, indent=2): self._update_results(t))
            
        except Exception as e:
            error_msg = f"Error processing image: {str(e)}"
            self.root.after(0, lambda: self._show_error(error_msg))
        finally:
            self.root.after(0, lambda: self._finish_processing())
    
    def _update_results(self, result_text):
        """Update the results display"""
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, result_text)
        
        # Parse the results for metadata
        # Attempt JSON first
        try:
            self.identified_data = json.loads(result_text)
        except Exception:
            self.identified_data = self._parse_results(result_text)
        
        # Update metadata text
        self._update_metadata_display()
        
        # Update the last identified panel
        self.update_last_identified_panel(self.current_image_path, self.identified_data, result_text)
        
        # Enable action buttons
        self.approve_btn.config(state=tk.NORMAL)
        self.reject_btn.config(state=tk.NORMAL)
        
        # Auto approve if enabled
        if self.auto_approve.get():
            self.approve_and_save()
    
    def _parse_results(self, result_text):
        """Parse the AI response into structured data"""
        data = {}
        lines = (result_text or '').split('\n')

        def normalize_key(raw_key: str) -> str:
            try:
                import re
                k = str(raw_key or '')
                k = k.strip().strip(':').strip()
                # Strip markdown decorations
                k = re.sub(r'^[\*`_"\s]+|[\*`_"\s]+$', '', k)
                k_low = k.lower().replace('-', ' ').replace('_', ' ').strip()
                # Canonical mapping
                mapping = {
                    'make': ['make', 'brand'],
                    'model': ['model'],
                    'color': ['color', 'colour'],
                    'logos': ['logos', 'logo', 'emblems', 'badges', 'text'],
                    'license plate': ['license plate', 'licence plate', 'plate', 'registration', 'number plate'],
                    'ai-interpretation summary': ['ai-interpretation summary', 'ai interpretation summary', 'summary', 'description']
                }
                for canon, alts in mapping.items():
                    for alt in alts:
                        if k_low == alt:
                            return canon.title() if canon != 'ai-interpretation summary' else 'AI-Interpretation Summary'
                # Fallbacks by containment
                if 'make' in k_low or 'brand' in k_low:
                    return 'Make'
                if 'model' in k_low:
                    return 'Model'
                if 'colour' in k_low or 'color' in k_low:
                    return 'Color'
                if 'license' in k_low or 'licence' in k_low or 'plate' in k_low:
                    return 'License Plate'
                if 'logo' in k_low or 'emblem' in k_low or 'badge' in k_low or 'text' in k_low:
                    return 'Logos'
                if 'summary' in k_low or 'interpretation' in k_low:
                    return 'AI-Interpretation Summary'
                return k
            except Exception:
                return str(raw_key)

        def normalize_value(raw_val: str) -> str:
            v = str(raw_val or '').strip()
            # Strip markdown bold/quotes
            if v.startswith('**'):
                v = v.lstrip('* ')
            v = v.strip().strip('"').strip()
            return v

        for line in lines:
            line = line.strip()
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = normalize_key(key)
            value = normalize_value(value)
            # Skip generic unknowns
            skip_values = ['not visible', 'unclear', 'not applicable', 'none', 'not a car', 'not clearly visible']
            if value.lower() in skip_values:
                continue
            data[key] = value

        if 'AI-Interpretation Summary' not in data:
            general_desc = (result_text or '').split('\n')[0] if result_text else 'Image analysis completed'
            data['AI-Interpretation Summary'] = general_desc[:200] + '...' if len(general_desc) > 200 else general_desc
        return data

    def _parse_or_fallback_json(self, result_text):
        """Try to parse strict JSON; if it fails, fallback to the older line parser and normalize."""
        try:
            parsed = json.loads(result_text)
            if isinstance(parsed, dict):
                # Normalize keys from JSON (strip markdown like **Make**)
                norm = {}
                for k, v in parsed.items():
                    # Reuse the same normalizers as in the line parser
                    try:
                        # Inline normalizers (avoid circular ref)
                        import re
                        kk = str(k or '')
                        kk = kk.strip().strip(':').strip()
                        kk = re.sub(r'^[\*`_"\s]+|[\*`_"\s]+$', '', kk)
                        kk_low = kk.lower().replace('-', ' ').replace('_', ' ').strip()
                        if 'make' in kk_low or 'brand' in kk_low:
                            canon = 'Make'
                        elif 'model' in kk_low:
                            canon = 'Model'
                        elif 'colour' in kk_low or 'color' in kk_low:
                            canon = 'Color'
                        elif 'license' in kk_low or 'licence' in kk_low or 'plate' in kk_low:
                            canon = 'License Plate'
                        elif 'logo' in kk_low or 'emblem' in kk_low or 'badge' in kk_low or 'text' in kk_low:
                            canon = 'Logos'
                        elif 'summary' in kk_low or 'interpretation' in kk_low:
                            canon = 'AI-Interpretation Summary'
                        else:
                            canon = kk
                        vv = str(v).strip()
                        if vv.startswith('**'):
                            vv = vv.lstrip('* ').strip('"').strip()
                        norm[canon] = vv
                    except Exception:
                        norm[str(k)] = v
                for req in ['Make', 'Model', 'Color', 'Logos', 'License Plate', 'AI-Interpretation Summary']:
                    norm.setdefault(req, 'Unknown' if req != 'Logos' else '')
                return norm
        except Exception:
            pass
        # Fallback to line parser
        data = self._parse_results(result_text)
        # Ensure required keys
        for k in ['Make', 'Model', 'Color', 'Logos', 'License Plate', 'AI-Interpretation Summary']:
            data.setdefault(k, 'Unknown' if k != 'Logos' else '')
        return data

    def _extract_message_text(self, response):
        """Extract plain assistant text from various Ollama client response shapes.
        Falls back to empty string if not found."""
        try:
            # Unwrap tuple-wrapped responses
            if isinstance(response, tuple) and len(response) >= 1:
                response = response[0]
            # If it's a streaming generator/iterator, accumulate content
            if hasattr(response, '__iter__') and not isinstance(response, (dict, str, bytes, list, tuple)):
                combined = ''
                try:
                    for chunk in response:
                        if isinstance(chunk, dict):
                            msg = chunk.get('message')
                            if isinstance(msg, dict):
                                c = msg.get('content')
                                if isinstance(c, str):
                                    combined += c
                        elif isinstance(chunk, str):
                            combined += chunk
                    return combined
                except Exception:
                    pass
            # Typical: { 'message': { 'content': '...' }, 'done': True, ... }
            if isinstance(response, dict):
                if 'message' in response and isinstance(response['message'], dict):
                    content = response['message'].get('content')
                    if isinstance(content, str):
                        return content
                # Some clients return a list of messages
                if 'messages' in response and isinstance(response['messages'], list):
                    for msg in response['messages']:
                        if isinstance(msg, dict) and msg.get('role') == 'assistant':
                            c = msg.get('content')
                            if isinstance(c, str):
                                return c
                # If content accidentally contains repr-like object text, strip known noise
                for key in ('content', 'text', 'output'):
                    c = response.get(key)
                    if isinstance(c, str):
                        return c
                # Fallback to pretty JSON but avoid binary repr
                return ''
            # Attribute-based clients (objects)
            # e.g. response.message.content or response.messages[i].content
            try:
                msg = getattr(response, 'message', None)
                if msg is not None:
                    if isinstance(msg, dict):
                        c = msg.get('content')
                        if isinstance(c, str):
                            return c
                    else:
                        c = getattr(msg, 'content', None)
                        if isinstance(c, str):
                            return c
                msgs = getattr(response, 'messages', None)
                if isinstance(msgs, (list, tuple)):
                    for m in msgs:
                        role = m.get('role') if isinstance(m, dict) else getattr(m, 'role', None)
                        if role == 'assistant':
                            c = m.get('content') if isinstance(m, dict) else getattr(m, 'content', None)
                            if isinstance(c, str):
                                return c
            except Exception:
                pass
            # If we got a string, assume it's already the message content
            if isinstance(response, str):
                return response
            # Unknown type: convert to string conservatively
            return ''
        except Exception:
            return ''
    
    def _update_metadata_display(self):
        """Update the metadata editor with parsed data"""
        self.metadata_text.delete(1.0, tk.END)
        
        if self.identified_data:
            json_str = json.dumps(self.identified_data, indent=2)
            self.metadata_text.insert(1.0, json_str)

    def _update_results_parsed(self, parsed_dict):
        """Update panels when we already have a parsed dict."""
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, json.dumps(parsed_dict, indent=2))
        self.identified_data = parsed_dict
        self._update_metadata_display()
        self.update_last_identified_panel(self.current_image_path, self.identified_data, json.dumps(parsed_dict, indent=2))
        self.approve_btn.config(state=tk.NORMAL)
        self.reject_btn.config(state=tk.NORMAL)
        if self.auto_approve.get():
            self.approve_and_save()

    # --------------------------
    # Metadata normalization/summarization helpers
    # --------------------------
    def _clean_metadata_values(self, metadata_dict):
        """Return a copy with 'Unknown'/None/empty stripped to ''."""
        cleaned = {}
        for key, value in (metadata_dict or {}).items():
            try:
                text = str(value).strip()
            except Exception:
                text = ''
            if not text or text.lower() == 'unknown':
                cleaned[key] = ''
            else:
                cleaned[key] = text
        return cleaned

    def _build_keywords(self, md):
        """Generate high-signal, deduplicated keyword list from cleaned metadata."""
        base = ["Car Photo", "Vehicle", "Automotive"]
        make = md.get('Make', '')
        model = md.get('Model', '')
        color = md.get('Color', '')
        plate = md.get('License Plate', '')

        if make:
            base.extend([f"Car Make: {make}", make])
        if model:
            base.append(f"Car Model: {model}")
            for part in model.split():
                if 1 < len(part) <= 32:
                    base.append(part)
        if color:
            base.extend([f"Car Color: {color}", color])
        if plate:
            base.append(f"License: {plate}")

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for kw in base:
            if kw and kw not in seen:
                seen.add(kw)
                deduped.append(kw)
        return deduped

    def _build_title_and_description(self, md):
        """Create a readable title and description from cleaned metadata."""
        make = md.get('Make', '')
        model = md.get('Model', '')
        color = md.get('Color', '')
        plate = md.get('License Plate', '')
        logos = md.get('Logos', '')
        summary = md.get('AI-Interpretation Summary', '')

        title_parts = []
        if make:
            title_parts.append(make)
        if model:
            title_parts.append(model)
        title = ' '.join(title_parts) if title_parts else 'Car Photo'

        desc_parts = []
        if title_parts:
            desc_parts.append(f"Car: {' '.join(title_parts)}")
        else:
            desc_parts.append("Car photo")
        if color:
            desc_parts.append(f"Color: {color}")
        if plate:
            desc_parts.append(f"License: {plate}")
        if logos:
            desc_parts.append(f"Logos: {logos[:120]}")
        if summary:
            desc_parts.append(f"Summary: {summary[:200]}")
        description = ' - '.join(desc_parts)

        return title, description

    def _compute_semantic_fields(self, metadata):
        """Return (cleaned_metadata, title, description, keywords)."""
        md = self._clean_metadata_values(metadata or {})
        title, description = self._build_title_and_description(md)
        keywords = self._build_keywords(md)
        return md, title, description, keywords

    def _is_mostly_unknown(self, data):
        try:
            keys = ['Make', 'Model', 'Color']
            vals = [str(data.get(k, 'Unknown')).lower() for k in keys]
            return all(v == 'unknown' for v in vals)
        except Exception:
            return False

    def _open_prompt_tester(self):
        """Open a small dialog to run A/B prompts against the current image with the selected model."""
        if not self.current_image_path:
            messagebox.showwarning("No Image", "Select an image first")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Prompt Tester")
        dlg.geometry("900x600")
        dlg.configure(bg=self.colors['bg_dark'])
        dlg.transient(self.root)
        dlg.grab_set()

        top = ttk.Frame(dlg, style='Dark.TFrame')
        top.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(top, text=f"Model: {self.model_name}", style='Dark.TLabel').pack(side=tk.LEFT)

        body = ttk.Frame(dlg, style='Dark.TFrame')
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        left = ttk.Frame(body, style='Dark.TFrame')
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        right = ttk.Frame(body, style='Dark.TFrame')
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))

        ttk.Label(left, text="Prompt A", style='Dark.TLabel').pack(anchor='w')
        prompt_a = tk.Text(left, height=12, bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                           insertbackground=self.colors['text_primary'], relief=tk.FLAT)
        prompt_a.pack(fill=tk.BOTH, expand=True)
        prompt_a.insert('1.0', "Analyze this image and identify car details. Provide:\nMake:\nModel:\nColor:\nLogos:\nLicense Plate:\nAI-Interpretation Summary:")

        ttk.Label(right, text="Prompt B", style='Dark.TLabel').pack(anchor='w')
        prompt_b = tk.Text(right, height=12, bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                           insertbackground=self.colors['text_primary'], relief=tk.FLAT)
        prompt_b.pack(fill=tk.BOTH, expand=True)
        prompt_b.insert('1.0', "Return ONLY these 6 lines in this exact order.\nMake: <brand>\nModel: <model>\nColor: <color>\nLogos: <logos/emblems/text>\nLicense Plate: <plate or Unknown>\nAI-Interpretation Summary: <<=200 chars>")

        run_bar = ttk.Frame(dlg, style='Dark.TFrame')
        run_bar.pack(fill=tk.X, padx=10, pady=(0,10))
        out_a = tk.Text(run_bar, height=12, width=60, bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                        insertbackground=self.colors['text_primary'], relief=tk.FLAT)
        out_b = tk.Text(run_bar, height=12, width=60, bg=self.colors['bg_light'], fg=self.colors['text_primary'],
                        insertbackground=self.colors['text_primary'], relief=tk.FLAT)
        out_a.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        out_b.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))

        def run_test(which):
            try:
                img_b64 = self.optimize_image_for_ollama(self.current_image_path)
                p = prompt_a.get('1.0', tk.END).strip() if which == 'A' else prompt_b.get('1.0', tk.END).strip()
                resp = self._chat([
                    {'role': 'user', 'content': p, 'images': [img_b64]}
                ])
                txt = self._extract_message_text(resp)
                parsed = self._parse_results(txt)
                pretty = json.dumps(parsed, indent=2)
                (out_a if which == 'A' else out_b).delete('1.0', tk.END)
                (out_a if which == 'A' else out_b).insert('1.0', pretty)
            except Exception as e:
                (out_a if which == 'A' else out_b).insert('1.0', f"Error: {str(e)}")

        btns = ttk.Frame(dlg, style='Dark.TFrame')
        btns.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(btns, text="Run A", command=lambda: run_test('A'), style='Dark.TButton').pack(side=tk.LEFT)
        ttk.Button(btns, text="Run B", command=lambda: run_test('B'), style='Dark.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Close", command=dlg.destroy, style='Dark.TButton').pack(side=tk.RIGHT)
    
    def _show_error(self, error_msg):
        """Show error message"""
        messagebox.showerror("Error", error_msg)
        self.status_label.config(text="❌ Error occurred", foreground=self.colors['error'])
    
    def _finish_processing(self):
        """Finish processing"""
        self.processing = False
        self.process_btn.config(state=tk.NORMAL)
        self.status_label.config(text="✅ Processing complete", foreground=self.colors['success'])
    
    def approve_and_save(self):
        """Approve and save the results"""
        if not self.identified_data:
            messagebox.showwarning("No Data", "No data to save")
            return
        
        try:
            # Normalize and enrich metadata
            md_clean, title, description, keywords = self._compute_semantic_fields(self.identified_data)

            # Embed metadata in JPG only (no JSON/XMP sidecars)
            embed_ok = False
            if self.embed_metadata.get():
                embed_ok = self.write_metadata_to_image(self.current_image_path, md_clean)

            if embed_ok:
                messagebox.showinfo("Success", "Metadata embedded in file")
            else:
                messagebox.showinfo("Saved", "Operation completed (no embedding requested)")
            
            # Disable buttons after saving
            self.approve_btn.config(state=tk.DISABLED)
            self.reject_btn.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save metadata: {str(e)}")
    
    def reject_results(self):
        """Reject the results"""
        self.results_text.delete(1.0, tk.END)
        self.metadata_text.delete(1.0, tk.END)
        self.identified_data = {}
        
        # Disable buttons
        self.approve_btn.config(state=tk.DISABLED)
        self.reject_btn.config(state=tk.DISABLED)
        
        self.status_label.config(text="❌ Results rejected", foreground=self.colors['error'])
    
    def batch_process_folder(self):
        """Process all images in the selected folder"""
        if not self.batch_folder:
            messagebox.showwarning("No Folder", "Please select a folder first")
            return
        
        if self.batch_processing:
            return
        
        self.batch_processing = True
        self.batch_process_btn.config(state=tk.DISABLED)
        self.progress_bar.pack(side=tk.RIGHT, padx=(0, 10))
        self.status_label.config(text="🔄 Starting batch processing...", foreground=self.colors['accent'])
        
        # Clear the identified data panel to avoid confusion during batch processing
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, "🔄 Batch processing in progress...\n\nIdentified data will be updated for each image as it's processed.")
        self.metadata_text.delete(1.0, tk.END)
        self.identified_data = {}
        
        # Start batch processing in a separate thread
        thread = threading.Thread(target=self._batch_process_thread)
        thread.daemon = True
        thread.start()
    
    def _batch_process_thread(self):
        """Thread function for batch processing"""
        try:
            supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
            image_files = set()  # Use set to avoid duplicates
            
            # Collect all image files (with recursive support)
            if self.recursive_scan.get():
                # Recursive scan
                for ext in supported_formats:
                    # Use case-insensitive pattern to avoid duplicates
                    image_files.update(Path(self.batch_folder).rglob(f"*{ext}"))
                    image_files.update(Path(self.batch_folder).rglob(f"*{ext.upper()}"))
            else:
                # Non-recursive scan
                for ext in supported_formats:
                    # Use case-insensitive pattern to avoid duplicates
                    image_files.update(Path(self.batch_folder).glob(f"*{ext}"))
                    image_files.update(Path(self.batch_folder).glob(f"*{ext.upper()}"))
            
            # Convert set to list and remove duplicates by absolute path
            image_files = list(image_files)
            # Remove duplicates by converting to absolute paths and back
            unique_files = []
            seen_paths = set()
            for file_path in image_files:
                abs_path = str(file_path.absolute())
                if abs_path not in seen_paths:
                    seen_paths.add(abs_path)
                    unique_files.append(file_path)
            image_files = unique_files
            total_files = len(image_files)
            processed = 0
            skipped = 0
            
            for image_path in image_files:
                if not self.batch_processing:  # Check if cancelled
                    break
                
                # Check for existing metadata
                existing_metadata = self.read_metadata_from_image(image_path)
                should_process = True
                
                if existing_metadata:
                    overwrite_pref = self.overwrite_existing.get()
                    if overwrite_pref == "skip":
                        should_process = False
                        skipped += 1
                        print(f"⏭️ Skipping {os.path.basename(image_path)} - existing metadata found")
                    elif overwrite_pref == "ask":
                        # For batch processing, we'll skip by default to avoid blocking
                        # User can set preference to "overwrite" if they want to process all
                        should_process = False
                        skipped += 1
                        print(f"⏭️ Skipping {os.path.basename(image_path)} - existing metadata found (ask mode)")
                
                if should_process:
                    # Update progress
                    processed += 1
                    progress = (processed / total_files) * 100
                    self.root.after(0, lambda p=progress, proc=processed, tot=total_files, 
                                  img=str(image_path): self._update_batch_display(img, proc, tot, 
                                  os.path.basename(image_path)))
                    
                    # Process the image
                    result = self._process_single_image_batch(image_path)
                    if not result.get('raw_response'):
                        # Ensure raw response is never empty to keep UI updating
                        try:
                            result['raw_response'] = json.dumps(result.get('data', {}), indent=2)
                        except Exception:
                            result['raw_response'] = 'No details returned.'
                    
                    # Update identified data panel with current image results
                    if result['success']:
                        self.root.after(0, lambda img=image_path, data=result['data'], raw=result['raw_response']:
                                        self._update_batch_results_display(img, data, raw))
                        # Also update last identified panel
                        self.root.after(0, lambda img=image_path, data=result['data'], raw=result['raw_response']:
                                        self.update_last_identified_panel(img, data, raw))
                    
                    # Save metadata for batch results (embed if enabled)
                    if result['success']:
                        # Prefer parsed data; if weak/unknown, re-parse from displayed text
                        data_for_write = result.get('data') or {}
                        try:
                            if (not data_for_write) or self._is_mostly_unknown(data_for_write):
                                reparsed = self._parse_or_fallback_json(result.get('raw_response') or '')
                                if reparsed:
                                    data_for_write = reparsed
                        except Exception:
                            pass
                        # Compute fields and write
                        md_clean, title, description, keywords = self._compute_semantic_fields(data_for_write)
                        if str(image_path).lower().endswith(('.jpg', '.jpeg')):
                            self.write_metadata_to_image(str(image_path), md_clean)
                else:
                    # Update progress for skipped files
                    progress = ((processed + skipped) / total_files) * 100
                    self.root.after(0, lambda p=progress, proc=processed, tot=total_files, 
                                  img=str(image_path): self._update_batch_display(img, proc, tot, 
                                  os.path.basename(image_path)))
            
            # Update final status with skip count
            if skipped > 0:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✅ Batch complete: {processed} processed, {skipped} skipped", 
                    foreground=self.colors['success']))
            
            self.root.after(0, self._finish_batch_processing)
            
        except Exception as e:
            error_msg = f"Error in batch processing: {str(e)}"
            self.root.after(0, lambda: self._show_error(error_msg))
            self.root.after(0, self._finish_batch_processing)
    
    def _update_batch_display(self, image_path, processed, total, image_name):
        """Update batch processing display"""
        self.progress_var.set((processed / total) * 100)
        self.status_label.config(text=f"🔄 Processing {image_name} ({processed}/{total})", 
                               foreground=self.colors['accent'])
        
        # Update image display
        try:
            self.current_image_path = image_path
            self.load_image()
            self.display_image()
        except Exception as e:
            print(f"Error updating preview for {image_name}: {str(e)}")
    
    def _show_batch_results(self, result):
        """Show batch processing results"""
        if result['success']:
            self._update_results(result['raw_response'])
        else:
            self._show_error(f"Error processing {result['image_path']}: {result['error']}")
    
    def _update_batch_results_display(self, image_path, identified_data, raw_response):
        """Update the identified data panel during batch processing"""
        try:
            # Update the results text with current image data
            self.results_text.delete(1.0, tk.END)
            
            # Add current image info
            filename = os.path.basename(image_path)
            self.results_text.insert(1.0, f"🔄 Currently Processing: {filename}\n\n")
            
            # Add the raw response
            self.results_text.insert(tk.END, raw_response)
            
            # Update metadata display
            self.identified_data = identified_data.copy()
            self._update_metadata_display()
            
        except Exception as e:
            print(f"Error updating batch results display: {str(e)}")
    
    def _process_single_image_batch(self, image_path):
        """Process a single image for batch processing"""
        try:
            # Enhanced path mirrors single-image enhanced inference
            if self.enhanced_inference.get():
                raw_text, parsed = self._infer_image_enhanced(str(image_path))
                if not raw_text:
                    try:
                        raw_text = json.dumps(parsed or {}, indent=2)
                    except Exception:
                        raw_text = 'No details returned.'
                return {
                    'success': True,
                    'image_path': image_path,
                    'data': parsed or {},
                    'raw_response': raw_text
                }

            # If enhanced reasoning is OFF, use the same simple path as single-image
            if not self.enhanced_inference.get():
                raw_text, parsed = self._infer_image_simple(str(image_path))
                # Ensure non-empty raw response for UI
                if not raw_text:
                    try:
                        raw_text = json.dumps(parsed or {}, indent=2)
                    except Exception:
                        raw_text = 'No details returned.'
                return {
                    'success': True,
                    'image_path': image_path,
                    'data': parsed or {},
                    'raw_response': raw_text
                }

            # Persona-prefaced prompt for batch mode with Ferrari disambiguation hints
            prompt = """Act as an expert automotive analyst. Your task is to perform a detailed forensic analysis.

You must disambiguate look-alike Ferrari models (e.g., 430 Scuderia vs 458 Italia) by focusing on:
- Tail light shape and position (round vs more modern units)
- Rear bumper diffuser/exhaust layout (center twin pipes on 430 Scuderia vs 458 pattern)
- Badge text and position (e.g., 'Scuderia' stripes/badges)
- Side intake and rear deck differences

Analyze this image and identify car details. If this is a car image, provide:

1. Make (brand) of the car
2. Model of the car - look for model names on badges, body, or trunk. Also identify by distinctive shape (e.g., Porsche 911, BMW X5, Mercedes C-Class)
3. Color of the car
4. Any visible logos, emblems, or text on the car
5. License plate number (if visible) - read any text on license plates carefully
6. Any other text visible on the car

If this is NOT a car image, provide a general description.

Please provide the information in this format:
Make: [brand]
Model: [model]
Color: [color]
Logos: [description of logos/emblems/text]
License Plate: [number if visible]
AI-Interpretation Summary: [brief 200 character summary of what you see]

IMPORTANT: Look carefully for any text, badges, or logos on the car and include them in your analysis. Identify models by both visible text and distinctive car shapes. Pay special attention to license plates and any text on the car."""

            # Match input strategy with toggle
            if self.high_fidelity_input.get():
                with open(str(image_path), 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode('utf-8')
                print(f"🧪 (Batch) Sending original bytes as base64: {len(img_base64)} chars")
            else:
                img_base64 = self.optimize_image_for_ollama(str(image_path))

            # Respect enhanced toggle for crops
            if self.enhanced_inference.get():
                crops = self._generate_detail_crops(str(image_path))
                images_payload = [img_base64] + crops
            else:
                images_payload = [img_base64]

            # Call Ollama
            try:
                response = self._chat([
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': images_payload
                    }
                ])
            except Exception:
                response = self._chat([
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [img_base64]
                    }
                ])

            # Parse response; keep raw text as primary display for parity with single-image
            result_text = self._extract_message_text(response)
            try:
                print(f"🧪 Batch raw (first 200): {str(result_text)[:200]}")
            except Exception:
                pass
            parsed_data = self._parse_results(result_text)
            if (not parsed_data) or self._is_mostly_unknown(parsed_data):
                repair_prompt = (
                    "Return ONLY these 6 lines in this exact order, nothing else.\n"
                    "Make: <brand>\n"
                    "Model: <model>\n"
                    "Color: <color>\n"
                    "Logos: <logos/emblems/text>\n"
                    "License Plate: <plate or Unknown>\n"
                    "AI-Interpretation Summary: <<=200 chars>"
                )
                try:
                    response_fix = self._chat([
                        { 'role': 'user', 'content': repair_prompt, 'images': [img_base64] }
                    ])
                    rt_fix = self._extract_message_text(response_fix)
                    parsed_fix = self._parse_results(rt_fix)
                    for k, v in parsed_fix.items():
                        if v and v.lower() != 'unknown':
                            parsed_data[k] = v
                    # If still empty/unknown, try a strict JSON schema
                    if (not parsed_data) or self._is_mostly_unknown(parsed_data):
                        strict = (
                            "Return ONLY JSON with keys exactly: Make, Model, Color, Logos, License Plate, AI-Interpretation Summary. "
                            "No prose. Fill with 'Unknown' if not visible."
                        )
                        try:
                            resp2 = self._chat([
                                { 'role': 'user', 'content': strict, 'images': [img_base64] }
                            ])
                            result_text = self._extract_message_text(resp2)
                            parsed_data = self._parse_or_fallback_json(result_text)
                        except Exception:
                            pass
                    else:
                        pass
                except Exception:
                    pass
            # Ensure we always provide a readable raw_response string for UI
            try:
                display_text = json.dumps(parsed_data, indent=2) if parsed_data else (result_text or '')
            except Exception:
                display_text = result_text or ''
            return {
                'success': True,
                'image_path': image_path,
                'data': parsed_data,
                'raw_response': display_text
            }
            
        except Exception as e:
            return {
                'success': False,
                'image_path': image_path,
                'error': str(e)
            }
    
    def _save_metadata_batch(self, image_path, metadata):
        """Deprecated: no-op (sidecar saving removed)."""
        return
    
    def _finish_batch_processing(self):
        """Finish batch processing"""
        self.batch_processing = False
        self.batch_process_btn.config(state=tk.NORMAL)
        self.progress_bar.pack_forget()
        self.status_label.config(text="✅ Batch processing complete", foreground=self.colors['success'])
        
        # Clear the identified data panel and show completion message
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, "✅ Batch processing complete!\n\nAll images have been processed. Check the 'Last Identified Image & Results' panel below for the most recent result.")
        self.metadata_text.delete(1.0, tk.END)
        self.identified_data = {}
    
    def write_metadata_to_image(self, image_path, metadata):
        """Embed metadata without re-encoding JPG pixels using exiftool. Always writes XMP sidecar.
        Returns True iff any in-file embed (EXIF/IPTC/XMP) succeeded."""
        try:
            image_path_str = str(image_path)
            if not image_path_str.lower().endswith(('.jpg', '.jpeg')):
                print(f"⚠️ Skipping {os.path.basename(image_path_str)} - not a JPG file")
                return

            metadata_str = json.dumps(metadata, indent=2)

            # Normalize and sanitize metadata values to avoid empty tags
            def _clean_text(value):
                text = (value or "").strip()
                if not text:
                    return ""
                if text.lower() in {"unknown", "n/a", "na", "none", "not visible", "unclear"}:
                    return ""
                return text

            md_lower = {str(k).lower(): v for k, v in (metadata or {}).items()}
            make_val = _clean_text(metadata.get('Make') or md_lower.get('make') or md_lower.get('car make'))
            model_val = _clean_text(metadata.get('Model') or md_lower.get('model') or md_lower.get('car model'))
            color_val = _clean_text(metadata.get('Color') or md_lower.get('color') or md_lower.get('car color'))
            license_val = _clean_text(metadata.get('License Plate') or md_lower.get('license plate') or md_lower.get('license') or md_lower.get('plate'))

            # Build keywords (unique, short tokens only)
            keywords = []
            if make_val:
                keywords.extend([f"Car Make: {make_val}", make_val])
            if model_val:
                keywords.append(f"Car Model: {model_val}")
                for part in model_val.split():
                    if 1 < len(part) <= 32:
                        keywords.append(part)
            if color_val:
                keywords.extend([f"Car Color: {color_val}", color_val])
            if license_val:
                keywords.append(f"License: {license_val}")
            keywords += ["Car Photo", "Vehicle", "Automotive"]
            unique_keywords = []
            for kw in keywords:
                kwc = (kw or "").strip()
                if kwc and kwc not in unique_keywords:
                    unique_keywords.append(kwc)

            # Description and title only include available parts
            name_part = " ".join([p for p in [make_val, model_val] if p]).strip()
            description = f"Car: {name_part or 'Unknown'}"
            if color_val:
                description += f" - {color_val}"
            if license_val:
                description += f" - License: {license_val}"
            title = " ".join([p for p in [make_val or 'Car', model_val] if p]).strip()

            # Compose XMP (kept for compatibility if needed in future)
            xmp_data = self._create_xmp_metadata(metadata, unique_keywords, description)

            # Try exiftool for EXIF + IPTC (no re-encode)
            exiftool_available = True
            embed_success = False
            try:
                import subprocess
                result = subprocess.run([
                    './exiftool.exe', '-overwrite_original',
                    f'-EXIF:UserComment={metadata_str}',
                    image_path_str
                ], capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    exiftool_available = False
                    print(f"⚠️ exiftool EXIF failed: {result.stderr}")
                else:
                    print("✅ EXIF UserComment written using exiftool (no re-encode)")
                    embed_success = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                exiftool_available = False
                print("⚠️ exiftool not available for EXIF; using sidecars only")

            if exiftool_available:
                try:
                    import subprocess
                    # Pass keywords individually so they become separate tags
                    iptc_args = []
                    for i, kw in enumerate(unique_keywords):
                        if i == 0:
                            iptc_args.append(f"-IPTC:Keywords={kw}")
                        else:
                            iptc_args.append(f"-IPTC:Keywords+={kw}")
                    result = subprocess.run([
                        './exiftool.exe', '-overwrite_original',
                        *iptc_args,
                        f'-IPTC:Caption-Abstract={description}',
                        f'-IPTC:ObjectName={title}',
                        image_path_str
                    ], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print("✅ IPTC metadata embedded using exiftool (no re-encode)")
                        embed_success = True
                    else:
                        print(f"⚠️ exiftool IPTC failed: {result.stderr}")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    print("⚠️ exiftool not available for IPTC; skipping IPTC embed")

            # Do not create sidecar files anymore
            print(f"💾 Metadata written to: {os.path.basename(image_path_str)} (no pixel re-encode)")
            print(f"📋 Keywords: {unique_keywords[:3]}...")
            print(f"📝 Description: {description[:50]}...")

            return embed_success

        except Exception as e:
            print(f"Error writing metadata to image: {str(e)}")
            return False
    
    def _create_xmp_metadata(self, metadata, keywords, description):
        """Create XMP metadata structure"""
        from datetime import datetime
        
        # Create XMP XML structure
        xmp_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:xmp="http://ns.adobe.com/xap/1.0/"
      xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">
      
      <!-- Dublin Core metadata -->
      <dc:description>{description}</dc:description>
      <dc:title>{metadata.get('Make', 'Car')} {metadata.get('Model', '')}</dc:title>
      <dc:subject>
        <rdf:Bag>
          {''.join([f'<rdf:li>{keyword}</rdf:li>' for keyword in keywords])}
        </rdf:Bag>
      </dc:subject>
      
      <!-- XMP metadata -->
      <xmp:Description>{description}</xmp:Description>
      <xmp:Title>{metadata.get('Make', 'Car')} {metadata.get('Model', '')}</xmp:Title>
      
      <!-- Photoshop metadata -->
      <photoshop:Keywords>
        <rdf:Bag>
          {''.join([f'<rdf:li>{keyword}</rdf:li>' for keyword in keywords])}
        </rdf:Bag>
      </photoshop:Keywords>
      
      <!-- Custom car identification metadata -->
      <xmp:CarMake>{metadata.get('Make', '')}</xmp:CarMake>
      <xmp:CarModel>{metadata.get('Model', '')}</xmp:CarModel>
      <xmp:CarColor>{metadata.get('Color', '')}</xmp:CarColor>
      <xmp:LicensePlate>{metadata.get('License Plate', '')}</xmp:LicensePlate>
      <xmp:AIInterpretation>{metadata.get('AI-Interpretation Summary', '')}</xmp:AIInterpretation>
      <xmp:ProcessingDate>{datetime.now().isoformat()}</xmp:ProcessingDate>
      
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""
        
        return xmp_template
    
    def _write_xmp_metadata(self, image_path, xmp_data):
        """Write XMP metadata to JPG file"""
        try:
            # Convert WindowsPath to string if needed
            image_path_str = str(image_path)
            
            # Use exiftool if available for XMP writing
            import subprocess
            import tempfile
            
            # Create temporary XMP file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xmp', delete=False) as temp_xmp:
                temp_xmp.write(xmp_data)
                temp_xmp_path = temp_xmp.name
            
            exiftool_success = False
            try:
                # Try to use exiftool to embed XMP
                result = subprocess.run([
                    './exiftool.exe', '-overwrite_original',
                    '-XMP:All<=', temp_xmp_path,
                    image_path_str
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print(f"✅ XMP metadata embedded using exiftool")
                    exiftool_success = True
                else:
                    print(f"⚠️ exiftool failed: {result.stderr}")
                    # Attempt to clean leftover temp file warning
                    if 'Temporary file already exists' in result.stderr:
                        try:
                            leftover = image_path_str + '_exiftool_tmp'
                            if os.path.exists(leftover):
                                os.remove(leftover)
                        except Exception:
                            pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                print(f"⚠️ exiftool not available")
            
            # Always create fallback .xmp file for compatibility
            # This ensures XMP metadata is available even if embedding fails
            xmp_path = image_path_str.rsplit('.', 1)[0] + '.xmp'
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write(xmp_data)
            print(f"📄 XMP metadata saved to: {os.path.basename(xmp_path)}")
            
            # Clean up temporary file
            try:
                os.unlink(temp_xmp_path)
            except:
                pass
                    
        except Exception as e:
            print(f"⚠️ XMP writing failed: {str(e)}")
    
    def read_metadata_from_image(self, image_path):
        """Read metadata from JPG file (EXIF, IPTC, XMP, and JSON sidecar)"""
        try:
            # Convert WindowsPath to string if needed
            image_path_str = str(image_path)
            if not image_path_str.lower().endswith(('.jpg', '.jpeg')):
                return None
            
            try:
                img = Image.open(image_path_str)
                exif_data = img.getexif()
            except Exception as e:
                print(f"Error opening image for metadata read: {str(e)}")
                exif_data = {}
            
            # Try EXIF UserComment first (our primary storage)
            if 0x9286 in exif_data:  # UserComment tag
                metadata_str = exif_data[0x9286]
                return json.loads(metadata_str)
            
            # Skip JSON/XMP sidecars (no longer used)
            
            # Try reading embedded XMP using exiftool
            try:
                import subprocess
                result = subprocess.run([
                    './exiftool.exe', '-XMP:All', '-j', image_path_str
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    return self._parse_exiftool_xmp(result.stdout)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            return None
            
        except Exception as e:
            print(f"Error reading metadata from image: {str(e)}")
            return None
    
    def _read_xmp_metadata(self, xmp_path):
        """Read metadata from XMP sidecar file"""
        try:
            import xml.etree.ElementTree as ET
            
            with open(xmp_path, 'r', encoding='utf-8') as f:
                xmp_content = f.read()
            
            # Parse XMP XML
            root = ET.fromstring(xmp_content)
            
            # Extract metadata from XMP structure
            metadata = {}
            
            # Look for our custom car identification tags
            for elem in root.iter():
                if elem.tag.endswith('CarMake') and elem.text:
                    metadata['Make'] = elem.text
                elif elem.tag.endswith('CarModel') and elem.text:
                    metadata['Model'] = elem.text
                elif elem.tag.endswith('CarColor') and elem.text:
                    metadata['Color'] = elem.text
                elif elem.tag.endswith('LicensePlate') and elem.text:
                    metadata['License Plate'] = elem.text
                elif elem.tag.endswith('AIInterpretation') and elem.text:
                    metadata['AI-Interpretation Summary'] = elem.text
            
            return metadata if metadata else None
            
        except Exception as e:
            print(f"Error reading XMP metadata: {str(e)}")
            return None
    
    def _parse_exiftool_xmp(self, exiftool_output):
        """Parse XMP metadata from exiftool output"""
        try:
            import json
            
            data = json.loads(exiftool_output)
            if not data or len(data) == 0:
                return None
            
            # Extract XMP data from exiftool output
            xmp_data = data[0].get('XMP', {})
            
            metadata = {}
            
            # Map XMP fields to our metadata structure
            if 'CarMake' in xmp_data:
                metadata['Make'] = xmp_data['CarMake']
            if 'CarModel' in xmp_data:
                metadata['Model'] = xmp_data['CarModel']
            if 'CarColor' in xmp_data:
                metadata['Color'] = xmp_data['CarColor']
            if 'LicensePlate' in xmp_data:
                metadata['License Plate'] = xmp_data['LicensePlate']
            if 'AIInterpretation' in xmp_data:
                metadata['AI-Interpretation Summary'] = xmp_data['AIInterpretation']
            
            return metadata if metadata else None
            
        except Exception as e:
            print(f"Error parsing exiftool XMP output: {str(e)}")
            return None

    def verify_metadata_in_file(self, image_path):
        """Verify metadata was written to JPG file and display it"""
        try:
            # Convert WindowsPath to string if needed
            image_path_str = str(image_path)
            if not image_path_str.lower().endswith(('.jpg', '.jpeg')):
                print(f"⚠️ {os.path.basename(image_path_str)} is not a JPG file")
                return None
            
            metadata = self.read_metadata_from_image(image_path_str)
            if metadata:
                print(f"✅ Metadata found in {os.path.basename(image_path_str)}:")
                print(json.dumps(metadata, indent=2))
                return metadata
            else:
                print(f"❌ No metadata found in {os.path.basename(image_path_str)}")
                return None
                
        except Exception as e:
            print(f"Error reading metadata from {image_path_str}: {str(e)}")
            return None

def main():
    # If ttkbootstrap is available, start with its themed window
    if tb is not None:
        root = tb.Window(themename='darkly')
    else:
        root = tk.Tk()
    app = CarIdentifierGUI(root)
    
    def on_resize(event):
        # Redisplay image when window is resized
        if app.current_image:
            app.display_image()
    
    root.bind('<Configure>', on_resize)
    root.mainloop()

if __name__ == "__main__":
    main() 
