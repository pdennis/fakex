# FakeFeed

FakeFeed is a web application that generates tweet-like content from your ebook library. It scrolls through your books, extracts passages, and uses an Ollama LLM to generate thoughtful tweets about what you're reading.

## Features

- Randomly selects books from your ebook library
- Extracts passages from EPUB and TXT files
- Uses Ollama (gemma3:4b model) to generate thoughtful tweets
- Real-time scrollable feed interface
- Infinite scroll loading of new content

## Requirements

- Python 3.7+
- Flask
- Ollama server running locally
- Network drive with ebook library

## Setup

1. Make sure you have Python 3.7+ installed

2. Clone this repository:
   ```
   git clone <repository-url>
   cd fakefeed
   ```

3. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

4. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

5. Ensure Ollama is installed and running:
   ```
   # Install Ollama if not already installed
   # https://ollama.com/download
   
   # Pull the gemma3:4b model
   ollama pull gemma3:4b
   
   # Make sure Ollama server is running
   ollama serve
   ```

6. Update the configuration in `app.py`:
   - Set `BOOK_LIBRARY_PATH` to the path of your ebook library
   - Verify `OLLAMA_API_URL` is correct (default: "http://localhost:11434/api/generate")
   - Adjust `OLLAMA_MODEL` if using a different model
   - Set `WORDS_PER_PASSAGE` to change the length of extracted passages

## Usage

1. Start the application:
   ```
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

3. Scroll through your generated book tweets!

## Current Limitations

- PDF parsing is not yet implemented
- Limited error handling for corrupted ebook files
- May not work well with very small ebook libraries

## Future Improvements

- Add PDF parsing support
- Improve book metadata extraction
- Add user controls for tweet generation frequency
- Support for custom prompt templates
- Add likes/bookmarks for favorite generated tweets