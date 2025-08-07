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
from pathlib import Path
from PIL import Image, ImageTk, ExifTags
import ollama

class CarIdentifierGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Car Identifier - Ollama Qwen2.5VL:32b")
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
        self.processing = False
        self.batch_folder = None
        self.batch_processing = False
        
        # Metadata handling preferences
        self.overwrite_existing = tk.StringVar(value="skip")  # "skip", "overwrite", "ask"
        self.recursive_scan = tk.BooleanVar(value=True)
        
        # Last identified image tracking
        self.last_identified_image_path = None
        self.last_identified_data = {}
        self.last_identified_thumbnail = None
        
        # Ollama client
        self.ollama_client = ollama.Client(host='http://localhost:11434')
        self.model_name = 'qwen2.5vl:32b'  # Enhanced vision model for better logo/text recognition
        
        self.setup_ui()
        self.check_ollama_connection()
    
    def setup_dark_theme(self):
        """Configure dark theme styling"""
        style = ttk.Style()
        
        # Configure theme
        style.theme_use('clam')
        
        # Configure colors for different widgets
        style.configure('Dark.TFrame', background=self.colors['bg_dark'])
        style.configure('Dark.TLabelframe', background=self.colors['bg_dark'], foreground=self.colors['text_primary'])
        style.configure('Dark.TLabelframe.Label', background=self.colors['bg_dark'], foreground=self.colors['text_primary'])
        
        # Button styling
        style.configure('Dark.TButton', 
                       background=self.colors['accent'],
                       foreground=self.colors['text_primary'],
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 9))
        
        style.map('Dark.TButton',
                 background=[('active', self.colors['accent_hover']),
                           ('pressed', self.colors['accent_hover'])])
        
        # Checkbutton styling
        style.configure('Dark.TCheckbutton',
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 9))
        
        # Label styling
        style.configure('Dark.TLabel',
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 9))
        
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
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, style='Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title with gradient effect
        title_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ttk.Label(title_frame, 
                               text="🚗 Car Identifier with Ollama Qwen2.5VL:32b", 
                               font=('Segoe UI', 18, 'bold'),
                               foreground=self.colors['accent'],
                               style='Dark.TLabel')
        title_label.pack()
        
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
        select_btn = ttk.Button(button_container, text="📁 Select Image", 
                               command=self.select_image, style='Dark.TButton')
        select_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Batch folder selection button
        folder_btn = ttk.Button(button_container, text="📂 Select Folder", 
                               command=self.select_folder, style='Dark.TButton')
        folder_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Process button
        self.process_btn = ttk.Button(button_container, text="🔍 Process Image", 
                                     command=self.process_image, style='Dark.TButton')
        self.process_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Batch process button
        self.batch_process_btn = ttk.Button(button_container, text="⚡ Batch Process", 
                                           command=self.batch_process_folder, style='Dark.TButton')
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
        
        # Recursive scan checkbox
        recursive_cb = ttk.Checkbutton(options_frame, text="📁 Recursive Scan", 
                                     variable=self.recursive_scan, style='Dark.TCheckbutton')
        recursive_cb.pack(side=tk.LEFT, padx=(0, 20))
        
        # Existing metadata handling
        metadata_label = ttk.Label(options_frame, text="Existing Metadata:", 
                                 style='Dark.TLabel')
        metadata_label.pack(side=tk.LEFT, padx=(0, 5))
        
        overwrite_combo = ttk.Combobox(options_frame, textvariable=self.overwrite_existing,
                                      values=["skip", "overwrite", "ask"], 
                                      state="readonly", width=10)
        overwrite_combo.pack(side=tk.LEFT, padx=(0, 20))
        
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
        
        # Action buttons frame
        button_frame = ttk.Frame(right_panel, style='Dark.TFrame')
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Approve button with success color
        self.approve_btn = ttk.Button(button_frame, text="✅ Approve & Save", 
                                     command=self.approve_and_save, 
                                     state=tk.DISABLED, style='Dark.TButton')
        self.approve_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Reject button
        self.reject_btn = ttk.Button(button_frame, text="❌ Reject", 
                                    command=self.reject_results, 
                                    state=tk.DISABLED, style='Dark.TButton')
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
        
        # Set a minimum height for the bottom panel to accommodate larger image
        last_identified_frame.configure(height=400)
        
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
        
        # Last identified image canvas (same size as main canvas)
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
        """Check if Ollama is running and qwen2.5vl:32b model is available"""
        try:
            models = self.ollama_client.list()
            
            # Handle different response structures
            if 'models' in models:
                model_list = models['models']
            else:
                model_list = models
                
            model_available = False
            for model in model_list:
                model_name = model.get('name', '') or model.get('model', '')
                if self.model_name in model_name:
                    model_available = True
                    break
            
            if model_available:
                self.status_label.config(text=f"🟢 Ollama connected - {self.model_name} ready",
                                       foreground=self.colors['success'])
            else:
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
            self.current_image = Image.open(self.current_image_path)
    
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
        self.status_label.config(text="🔄 Processing image...", foreground=self.colors['accent'])
        
        # Start processing in a separate thread
        thread = threading.Thread(target=self._process_image_thread)
        thread.daemon = True
        thread.start()
    
    def _process_image_thread(self):
        """Thread function for processing image"""
        try:
            # Prepare the prompt for car identification
            prompt = """Analyze this image and identify car details. If this is a car image, provide:

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

            # Read and encode the image
            with open(self.current_image_path, 'rb') as img_file:
                img_data = img_file.read()
                img_base64 = base64.b64encode(img_data).decode('utf-8')

            # Call Ollama with the image
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [img_base64]
                    }
                ]
            )

            # Parse the response
            result_text = response['message']['content']
            
            # Update UI in main thread
            self.root.after(0, lambda: self._update_results(result_text))
            
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
        lines = result_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Skip unknown, unclear, or not applicable values
                skip_values = ['not visible', 'unclear', 'not applicable', 'none', 'not a car', 'not clearly visible']
                if value.lower() in skip_values:
                    continue
                    
                data[key] = value
        
        # Ensure AI-Interpretation Summary is always present
        if 'AI-Interpretation Summary' not in data:
            # Try to find a general description from the response
            general_desc = result_text.split('\n')[0] if result_text else "Image analysis completed"
            data['AI-Interpretation Summary'] = general_desc[:200] + "..." if len(general_desc) > 200 else general_desc
        
        return data
    
    def _update_metadata_display(self):
        """Update the metadata editor with parsed data"""
        self.metadata_text.delete(1.0, tk.END)
        
        if self.identified_data:
            json_str = json.dumps(self.identified_data, indent=2)
            self.metadata_text.insert(1.0, json_str)
    
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
            # Save metadata as JSON file
            json_path = self.current_image_path.rsplit('.', 1)[0] + '.json'
            with open(json_path, 'w') as f:
                json.dump(self.identified_data, f, indent=2)
            
            # Embed metadata in JPG if requested
            if self.embed_metadata.get():
                self.write_metadata_to_image(self.current_image_path, self.identified_data)
            
            messagebox.showinfo("Success", f"Metadata saved to {json_path}")
            
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
                    
                    # Update identified data panel with current image results
                    if result['success']:
                        self.root.after(0, lambda: self._update_batch_results_display(
                            image_path, result['data'], result['raw_response']))
                        # Also update last identified panel
                        self.root.after(0, lambda: self.update_last_identified_panel(
                            image_path, result['data'], result['raw_response']))
                    
                    # Auto approve if enabled
                    if self.auto_approve.get() and result['success']:
                        self._save_metadata_batch(image_path, result['data'])
                        
                        # Verify metadata was written (for JPG files)
                        if str(image_path).lower().endswith(('.jpg', '.jpeg')):
                            self.verify_metadata_in_file(image_path)
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
        self.current_image_path = image_path
        self.load_image()
        self.display_image()
    
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
            # Prepare the prompt for car identification
            prompt = """Analyze this image and identify car details. If this is a car image, provide:

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

            # Read and encode the image
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
                img_base64 = base64.b64encode(img_data).decode('utf-8')

            # Call Ollama with the image
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [img_base64]
                    }
                ]
            )

            # Parse the response
            result_text = response['message']['content']
            parsed_data = self._parse_results(result_text)
            
            return {
                'success': True,
                'image_path': image_path,
                'data': parsed_data,
                'raw_response': result_text
            }
            
        except Exception as e:
            return {
                'success': False,
                'image_path': image_path,
                'error': str(e)
            }
    
    def _save_metadata_batch(self, image_path, metadata):
        """Save metadata for batch processing"""
        try:
            # Save as JSON
            json_path = str(image_path).rsplit('.', 1)[0] + '.json'
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Embed in JPG if requested
            if self.embed_metadata.get():
                self.write_metadata_to_image(str(image_path), metadata)
                print(f"✅ Metadata embedded in: {os.path.basename(image_path)}")
            else:
                print(f"📄 JSON saved for: {os.path.basename(image_path)}")
                
        except Exception as e:
            print(f"Error saving metadata for {image_path}: {str(e)}")
    
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
        """Write metadata directly to JPG file with EXIF, IPTC, and XMP support"""
        try:
            # Convert WindowsPath to string if needed
            image_path_str = str(image_path)
            if not image_path_str.lower().endswith(('.jpg', '.jpeg')):
                print(f"⚠️ Skipping {os.path.basename(image_path_str)} - not a JPG file")
                return  # Only write to JPG files
            
            # Open the image
            img = Image.open(image_path_str)
            
            # Convert metadata to string for EXIF backup
            metadata_str = json.dumps(metadata, indent=2)
            
            # Create EXIF data
            exif_data = img.getexif()
            
            # Add metadata to EXIF UserComment (backup)
            exif_data[0x9286] = metadata_str  # UserComment tag
            
            # Build searchable keywords for Lightroom
            keywords = []
            if 'Make' in metadata:
                keywords.append(f"Car Make: {metadata['Make']}")
                keywords.append(metadata['Make'])  # Add just the make name
            if 'Model' in metadata:
                keywords.append(f"Car Model: {metadata['Model']}")
                # Extract model name from the full model string
                model_parts = metadata['Model'].split()
                for part in model_parts:
                    if len(part) > 1:  # Avoid single letters
                        keywords.append(part)
            if 'Color' in metadata:
                keywords.append(f"Car Color: {metadata['Color']}")
                keywords.append(metadata['Color'])  # Add just the color
            if 'License Plate' in metadata:
                keywords.append(f"License: {metadata['License Plate']}")
            
            # Add general car identification
            keywords.append("Car Photo")
            keywords.append("Vehicle")
            keywords.append("Automotive")
            
            # Remove duplicates while preserving order
            unique_keywords = []
            for keyword in keywords:
                if keyword not in unique_keywords:
                    unique_keywords.append(keyword)
            
            # Create IPTC data for Lightroom compatibility
            from PIL import IptcImagePlugin
            iptc_data = IptcImagePlugin.getiptcinfo(img)
            
            if iptc_data is None:
                iptc_data = {}
            
            # Set IPTC keywords (searchable in Lightroom)
            iptc_data[(2, 25)] = unique_keywords  # Keywords
            
            # Set IPTC description (searchable in Lightroom)
            description = f"Car: {metadata.get('Make', 'Unknown')} {metadata.get('Model', 'Unknown')} - {metadata.get('Color', 'Unknown color')}"
            if 'License Plate' in metadata:
                description += f" - License: {metadata['License Plate']}"
            iptc_data[(2, 120)] = description  # Caption/Abstract
            
            # Set IPTC title
            title = f"{metadata.get('Make', 'Car')} {metadata.get('Model', '')}".strip()
            iptc_data[(2, 5)] = title  # Title
            
            # Create XMP metadata for wider compatibility
            xmp_data = self._create_xmp_metadata(metadata, unique_keywords, description)
            
            # Save the image with EXIF first
            img.save(image_path_str, exif=exif_data)
            
            # Use exiftool to write EXIF UserComment (more reliable than PIL)
            try:
                import subprocess
                result = subprocess.run([
                    './exiftool.exe', '-overwrite_original',
                    f'-EXIF:UserComment={metadata_str}',
                    image_path_str
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print(f"✅ EXIF UserComment written using exiftool")
                else:
                    print(f"⚠️ exiftool EXIF failed: {result.stderr}")
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                print(f"⚠️ exiftool not available for EXIF, using PIL only")
            
            # Now write IPTC and XMP data using a more reliable method
            try:
                # Use exiftool for IPTC writing if available (more reliable than PIL)
                import subprocess
                
                try:
                    # Try to use exiftool for IPTC writing
                    result = subprocess.run([
                        './exiftool.exe', '-overwrite_original',
                        f'-IPTC:Keywords={", ".join(unique_keywords)}',
                        f'-IPTC:Caption-Abstract={description}',
                        f'-IPTC:ObjectName={title}',
                        image_path_str
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        print(f"✅ IPTC metadata embedded using exiftool")
                    else:
                        print(f"⚠️ exiftool IPTC failed: {result.stderr}")
                        # Fallback to PIL method (may not work reliably)
                        img_with_iptc = Image.open(image_path_str)
                        img_with_iptc.save(image_path_str, iptc=iptc_data)
                        print(f"⚠️ Used PIL fallback for IPTC")
                        
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    print(f"⚠️ exiftool not available for IPTC, using PIL fallback")
                    # Fallback to PIL method
                    img_with_iptc = Image.open(image_path_str)
                    img_with_iptc.save(image_path_str, iptc=iptc_data)
                
                # Write XMP metadata
                self._write_xmp_metadata(image_path_str, xmp_data)
                
                print(f"💾 Metadata written to: {os.path.basename(image_path_str)} (EXIF + IPTC + XMP)")
                print(f"📋 Keywords: {unique_keywords[:3]}...")  # Show first 3 keywords
                print(f"📝 XMP Description: {description[:50]}...")
                
            except Exception as metadata_error:
                print(f"⚠️ IPTC/XMP writing failed: {metadata_error}")
                print(f"💾 EXIF metadata written to: {os.path.basename(image_path_str)}")
            
        except Exception as e:
            print(f"Error writing metadata to image: {str(e)}")
    
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
            
            img = Image.open(image_path_str)
            exif_data = img.getexif()
            
            # Try EXIF UserComment first (our primary storage)
            if 0x9286 in exif_data:  # UserComment tag
                metadata_str = exif_data[0x9286]
                return json.loads(metadata_str)
            
            # Try reading from JSON sidecar file
            json_path = image_path_str.rsplit('.', 1)[0] + '.json'
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Error reading JSON metadata: {str(e)}")
            
            # Try reading from XMP sidecar file
            xmp_path = image_path_str.rsplit('.', 1)[0] + '.xmp'
            if os.path.exists(xmp_path):
                return self._read_xmp_metadata(xmp_path)
            
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