# Car Identifier v2

A Python GUI application that uses AI vision models to automatically identify cars in images and embed comprehensive metadata (EXIF, IPTC, XMP) for professional photo management software compatibility.

## Features

- **AI-Powered Car Identification**: Uses Ollama with qwen2.5vl:32b model for accurate car detection
- **Comprehensive Metadata Support**: Writes EXIF, IPTC, and XMP metadata for maximum compatibility
- **Professional Software Integration**: Compatible with Adobe Lightroom, Photoshop, and other photo management tools
- **Batch Processing**: Process entire folders with recursive directory scanning
- **Smart Metadata Handling**: Skip or overwrite existing metadata with user preference
- **Real-time Preview**: Live image preview with identified data display
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Requirements

- Python 3.7+
- Ollama with qwen2.5vl:32b model installed
- exiftool (included in this repository)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd CarIdentifier_GitHub
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Ollama and the required model:**
   ```bash
   # Install Ollama (https://ollama.ai/)
   # Then pull the vision model:
   ollama pull qwen2.5vl:32b
   ```

4. **Configure the application:**
   - Edit `config.json` to set your Ollama server URL (default: http://localhost:11434)
   - Ensure exiftool.exe is in the same directory as the application

## Usage

### Quick Start

1. **Run the application:**
   ```bash
   python car_identifier_gui.py
   ```

2. **Single Image Processing:**
   - Click "Select Image" to choose a single image
   - Click "Identify Car" to process the image
   - View results in the "Identified Data" panel

3. **Batch Processing:**
   - Click "Select Folder" to choose a directory
   - Enable "Recursive Scan" for subdirectory processing
   - Choose metadata handling preference (Skip/Overwrite)
   - Click "Start Batch Processing"

### Configuration Options

- **Skip Existing Metadata**: Automatically skip images that already have AI-generated metadata
- **Overwrite Existing Metadata**: Replace existing metadata with new AI identification
- **Recursive Directory Scan**: Process all subdirectories in the selected folder

## Metadata Support

The application writes metadata in multiple formats for maximum compatibility:

### EXIF Metadata
- UserComment: Contains full JSON metadata backup
- Compatible with most image viewers and editors

### IPTC Metadata
- Keywords: Car make, model, color, and other identified attributes
- Caption/Abstract: Detailed description of the identified car
- Title: Car identification summary
- Optimized for Adobe Lightroom and Photoshop

### XMP Metadata
- Dublin Core description with full car details
- Sidecar .xmp files for compatibility with all XMP-aware software
- Embedded XMP in JPG files when possible

## File Structure

```
CarIdentifier_GitHub/
├── car_identifier_gui.py    # Main application
├── config.json             # Configuration settings
├── requirements.txt        # Python dependencies
├── exiftool.exe           # Metadata writing tool
├── run.py                 # Alternative launcher
├── README.md              # This file
└── XMP_METADATA_GUIDE.md # Detailed XMP documentation
```

## Troubleshooting

### Common Issues

1. **"Ollama connection failed"**
   - Ensure Ollama is running: `ollama serve`
   - Check the server URL in config.json

2. **"exiftool not found"**
   - Ensure exiftool.exe is in the same directory as the application
   - On Linux/macOS, install exiftool via package manager

3. **Metadata not visible in Lightroom/Photoshop**
   - Check XMP_METADATA_GUIDE.md for detailed troubleshooting
   - Ensure .xmp sidecar files are present
   - Try refreshing metadata in your photo management software

### Performance Tips

- Use SSD storage for faster batch processing
- Close other applications during large batch operations
- For large folders, consider processing in smaller batches

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Ollama team for the vision model infrastructure
- ExifTool for robust metadata handling
- Pillow (PIL) for image processing capabilities
